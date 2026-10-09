"""Build birds.js: core-set Wingspan birds + bird-only color palettes from the card art.
Card data: data/master.json (navarog/wingsearch, GPLv3). Art list: data/art.json (Natalia Rojas, Ana María Martínez Jaramillo).
Art is copyrighted by the artists: it's cached in art/ for personal use only.

Run with torch + transformers installed:  python build.py
Birds already in birds.js keep their palette; delete birds.js to redo them all.

The art is published only encrypted: with WINGSPAN_PASSWORD set, each art/*.jpg is AES-GCM encrypted into
art-enc/*.bin (key = PBKDF2-SHA256 of the password) and the page decrypts it in the browser after login.
The password itself is never written to the repo. art/ stays local (.gitignore).
"""
import base64, json, os, re, urllib.request
import numpy as np
from PIL import Image

HABITATS = ["Forest", "Grassland", "Wetland"]
FOODS = ["Invertebrate", "Seed", "Fish", "Fruit", "Rodent", "Nectar", "Wild (food)"]
PROMPTS = ["a bird", "a tree branch or trunk", "berries, leaves or flowers", "handwritten signature or logo", "plain white paper",
           "printed title text", "light blue sky background", "water, rocks or ground"]
DIGITAL_ART_AREA = (120, 80, 330, 305)  # x0, y0, x1, y1 inside a digital crop: skips the card's icons, numbers and title
_clipseg = None


def masks(img, area=None):
    """(bird, background) boolean HxW masks. Bird: CLIPSeg ranks 'a bird' first. Background: it ranks a perch, foliage
    or water/ground first. Both exclude paper and the card cream; digital crops pass `area` to stay inside the card."""
    global _clipseg
    import torch
    if _clipseg is None:  # loaded only when there is new art to process
        from transformers import CLIPSegForImageSegmentation, CLIPSegProcessor
        name = "CIDAS/clipseg-rd64-refined"
        _clipseg = CLIPSegProcessor.from_pretrained(name), CLIPSegForImageSegmentation.from_pretrained(name).eval()
    processor, model = _clipseg
    inputs = processor(text=PROMPTS, images=[img] * len(PROMPTS), padding=True, return_tensors="pt")
    with torch.no_grad():
        logits = model(**inputs).logits  # (prompts, 352, 352)
    up = torch.nn.functional.interpolate(logits[:, None], size=img.size[::-1], mode="bilinear")[:, 0]
    top = up.argmax(0).numpy()
    mask = (top == 0) & (up[0].sigmoid() > 0.3).numpy()
    px = np.asarray(img).astype(int)
    border = np.concatenate([px[:4].reshape(-1, 3), px[-4:].reshape(-1, 3), px[:, :4].reshape(-1, 3), px[:, -4:].reshape(-1, 3)])
    # background colors to drop: the border's median (white paper / screen) and the crop's most common color
    # (the cream card itself, which dominates the digital crops)
    bins, counts = np.unique((px // 16).reshape(-1, 3), axis=0, return_counts=True)
    papers = [np.median(border, axis=0), bins[counts.argmax()] * 16 + 8]
    not_paper = np.all([np.sqrt(((px - p) ** 2).sum(axis=2)) > 40 for p in papers], axis=0)
    keep = (px.min(axis=2) < 235) & not_paper
    # Background = whatever isn't the bird, a signature/logo or title text, clearly away from the paper/card color,
    # not a pale gray halo, and a few pixels clear of the bird's outline. Water stays in (blue can match Fish).
    far = np.all([np.sqrt(((px - p) ** 2).sum(axis=2)) > 60 for p in papers], axis=0)
    pale_gray = (px.min(axis=2) > 190) & (px.max(axis=2) - px.min(axis=2) < 30)
    near_bird = mask.copy()
    for _ in range(4):
        g = near_bird.copy(); g[1:] |= near_bird[:-1]; g[:-1] |= near_bird[1:]; g[:, 1:] |= near_bird[:, :-1]; g[:, :-1] |= near_bird[:, 1:]; near_bird = g
    bg = ~near_bird & ~np.isin(top, [3, 5]) & keep & far & ~pale_gray
    if area:
        inside = np.zeros(bg.shape, bool); inside[area[1]:area[3], area[0]:area[2]] = True
        bg &= inside
    return mask & keep, bg


def bird_mask(img):
    return masks(img)[0]


def bg_palette(path, area=None):
    """Colors of the bird's surroundings (perch, berries, water...), for the Artist's Palette."""
    img = Image.open(path).convert("RGB")
    if area is None:
        img.thumbnail((500, 500))  # plenty for a palette, and much faster
    pixels = np.asarray(img)[masks(img, area)[1]]
    if len(pixels) < 150:  # essentially no scenery
        return []
    return palette_from_pixels([tuple(p) for p in pixels[::max(1, len(pixels) // 40000)].tolist()])


def palette_from_pixels(pixels, n=6):
    """Bucket pixels by hue x brightness (saturated) or brightness alone (neutrals), so a small blue
    patch keeps its own bucket instead of being averaged into the greens. Returns n distinct colors."""
    strip = Image.new("RGB", (len(pixels), 1))
    strip.putdata(pixels)
    buckets = {}
    for (r, g, b), (hu, s, v) in zip(pixels, strip.convert("HSV").getdata()):
        key = (hu * 12 // 256, v * 3 // 256) if s >= 70 else (-1, v * 4 // 256)
        acc = buckets.setdefault(key, [0, 0, 0, 0])
        acc[0] += 1; acc[1] += r; acc[2] += g; acc[3] += b
    picked = []
    for c, r, g, b in sorted(buckets.values(), reverse=True):
        rgb = (r // c, g // c, b // c)
        if all(sum((x - y) ** 2 for x, y in zip(rgb, p[1])) > 40 ** 2 for p in picked):
            picked.append((c, rgb))
        if len(picked) == n:
            break
    total = sum(c for c, _ in picked)
    return [{"hex": "#%02x%02x%02x" % rgb, "pct": round(100 * c / total)} for c, rgb in picked]


def art_for(name, uri, artist, site):
    path = "art/" + norm(name) + ".jpg"
    if not os.path.exists(path):
        req = urllib.request.Request("https://static.wixstatic.com/media/" + uri, headers={"User-Agent": "Mozilla/5.0"})
        img = Image.open(urllib.request.urlopen(req, timeout=60)).convert("RGB")
        img.thumbnail((1000, 1000))
        img.save(path, quality=90)
    img = Image.open(path).convert("RGB")
    pixels = np.asarray(img)[bird_mask(img)]
    sample = pixels[::max(1, len(pixels) // 40000)].tolist()
    return {"artist": artist, "site": site, "image": path, "palette": palette_from_pixels([tuple(p) for p in sample])}


def digital_for(name, shot, left, top, shots):
    """Crop one card's art out of a Steam screenshot of the digital edition, then palette it like the artists' art."""
    os.makedirs("art/steam", exist_ok=True)
    src = "art/steam/%02d.jpg" % shot
    if not os.path.exists(src):
        urllib.request.urlretrieve(shots[shot], src)
    path = "art/d-" + norm(name) + ".jpg"
    if not os.path.exists(path):
        # generous crop (whole card plus a margin) so birds that overflow the card or reach into the title aren't cut;
        # the title text, icons and screen background are masked out below and can be panned away in the page
        Image.open(src).convert("RGB").crop((left - 15, top + 10, left + 340, top + 345)).save(path, quality=92)
    img = Image.open(path).convert("RGB")
    pixels = np.asarray(img)[bird_mask(img)]
    return {"image": path, "palette": palette_from_pixels([tuple(p) for p in pixels.tolist()])}


def encrypt_art(password):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.hashes import SHA256
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    os.makedirs("art-enc", exist_ok=True)
    b64 = lambda b: base64.b64encode(b).decode()
    try:
        meta = json.load(open("art-enc/meta.json"))
    except FileNotFoundError:
        meta = {"salt": b64(os.urandom(16)), "iterations": 600_000}
    key = PBKDF2HMAC(SHA256(), 32, base64.b64decode(meta["salt"]), meta["iterations"]).derive(password.encode())
    aes = AESGCM(key)
    seal = lambda data: (iv := os.urandom(12)) + aes.encrypt(iv, data, None)  # iv || ciphertext || tag (WebCrypto layout)
    if "check" in meta:  # same password as the existing files? otherwise start over with a new salt
        try:
            blob = base64.b64decode(meta["check"]); aes.decrypt(blob[:12], blob[12:], None)
        except Exception:
            for f in os.listdir("art-enc"):
                os.remove(os.path.join("art-enc", f))
            return encrypt_art(password)
    meta["check"] = meta.get("check") or b64(seal(b"wingspan"))
    # card art (art/*.jpg) and the game's habitat/food icons cropped from the Steam screenshots (art/icons/*.png -> icon-*.bin)
    files = [("art/" + f, "art-enc/" + f[:-4] + ".bin") for f in os.listdir("art") if f.endswith(".jpg")]
    if os.path.isdir("art/icons"):
        files += [("art/icons/" + f, "art-enc/icon-" + f[:-4] + ".bin") for f in os.listdir("art/icons") if f.endswith(".png")]
    for src, out in sorted(files):
        if not os.path.exists(out):  # existing files are kept, so rebuilds don't churn git
            open(out, "wb").write(seal(open(src, "rb").read()))
    json.dump(meta, open("art-enc/meta.json", "w"))
    print(len(os.listdir("art-enc")) - 1, "encrypted images in art-enc/")


def norm(s):
    return re.sub(r"[^a-z]", "", s.lower())


if __name__ == "__main__":
    os.makedirs("art", exist_ok=True)
    try:
        prev = json.loads(open("birds.js", encoding="utf-8").read()[len("const BIRDS = "):-2])
    except FileNotFoundError:
        prev = []
    old = {b["sci"]: b.get("art") for b in prev}
    old_digital = {b["sci"]: b.get("digital") for b in prev}
    steam = json.load(open("data/steam.json", encoding="utf-8"))
    digital = {norm(n): (s, l, t) for n, s, l, t in steam["cards"]}
    art = {}
    for artist, info in json.load(open("data/art.json", encoding="utf-8")).items():
        for uri, name in info["items"]:
            art.setdefault(norm(name), (uri, artist, info["site"]))
    birds = []
    if not os.path.exists("data/master.json"):  # card data from Wingsearch (GPLv3), not committed here
        urllib.request.urlretrieve("https://raw.githubusercontent.com/navarog/wingsearch/master/src/assets/data/master.json", "data/master.json")
    for card in json.load(open("data/master.json", encoding="utf-8")):
        if card["Set"] != "core":
            continue
        name, sci = card["Common name"], card["Scientific name"]
        bird = {
            "name": name, "sci": sci,
            "points": int(card["Victory points"] or 0), "wingspan": card["Wingspan"], "nest": card["Nest type"],
            "power": card["Power text"], "color": card["Color"], "eggs": int(card["Egg limit"] or 0), "flavor": card["Flavor text"],
            "habitats": [h for h in HABITATS if card[h]],
            "food": {f.replace(" (food)", ""): int(card[f]) for f in FOODS if card[f]},
            "foodOr": bool(card["/ (food cost)"]),  # the game shows "/" (pay one of them) instead of "+"
            "art": None, "digital": None,
        }
        if norm(name) in digital:
            bird["digital"] = old_digital.get(sci) or digital_for(name, *digital[norm(name)], steam["shots"])
            if "bgPalette" not in bird["digital"]:
                bird["digital"]["bgPalette"] = bg_palette(bird["digital"]["image"], DIGITAL_ART_AREA)
        if norm(name) in art:
            uri, artist, site = art[norm(name)]
            bird["art"] = old.get(sci) or art_for(name, uri, artist, site)
            if "bgPalette" not in bird["art"]:
                bird["art"]["bgPalette"] = bg_palette(bird["art"]["image"])
        birds.append(bird)
    birds.sort(key=lambda b: b["name"])
    with open("birds.js", "w", encoding="utf-8") as f:
        f.write("const BIRDS = " + json.dumps(birds, ensure_ascii=False) + ";\n")
    print(len(birds), "birds,", sum(1 for b in birds if b["art"]), "with card art,", sum(1 for b in birds if b["digital"]), "with digital art")
    if os.environ.get("WINGSPAN_PASSWORD"):
        encrypt_art(os.environ["WINGSPAN_PASSWORD"])
    else:
        print("WINGSPAN_PASSWORD not set: art-enc/ not updated")
