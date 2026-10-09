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


MARKS = json.load(open("data/marks.json", encoding="utf-8"))["logos"] if os.path.exists("data/marks.json") else {}


def artist_marks(name, scale, keep, bird):
    """Pixels of the artist's marks, never used for colors: the AnaM logo (located per image in data/marks.json)
    and signatures/text, i.e. small, separate, low-color marks on the paper that don't touch the bird."""
    from scipy import ndimage
    h, w = keep.shape
    marks = np.zeros((h, w), bool)
    if name in MARKS:
        x0, y0, x1, y1 = (int(v * scale) for v in MARKS[name])
        pad = int(10 * scale)
        marks[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad] = True
    return marks, ndimage, h, w


def masks(img, area=None, mark=None, raw=False):
    """(bird, background, leaked) for an image. Bird: CLIPSeg ranks 'a bird' first. Background: anything else that
    isn't paper, card cream, text or the artist's logo/signature. Digital crops pass `area` to stay inside the card;
    artist images pass `mark` = (name, scale) so their logo and signature are ignored. `leaked` counts logo/signature
    pixels that would otherwise have been used."""
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
    if raw:  # the model's own bird outline (keeps white feathers that look like paper) + background
        return mask, bg
    bird = mask & keep
    if not mark:
        return bird, bg, 0
    marks, ndimage, h, w = artist_marks(*mark, keep, bird)
    # signatures/text: separate components of non-paper pixels that are small, low in color and away from the bird
    labels, n = ndimage.label(keep)
    if n:
        idx = np.arange(1, n + 1)
        size = ndimage.sum(np.ones_like(labels), labels, idx)
        sat = (px.max(axis=2) - px.min(axis=2)) / np.maximum(px.max(axis=2), 1)
        mean_sat = ndimage.mean(sat, labels, idx)
        touches = ndimage.maximum(ndimage.binary_dilation(bird, iterations=6).astype(np.uint8), labels, idx)
        text = idx[(size < 0.004 * h * w) & (mean_sat < 0.3) & ~touches.astype(bool)]
        marks |= np.isin(labels, text)
    leaked = int(((bird | bg) & marks).sum())
    return bird & ~marks, bg & ~marks, leaked


def bird_mask(img, mark=None):
    return masks(img, mark=mark)[0]


def artist_palettes(path):
    """(bird palette, background palette, leaked pixels) for an artist image, ignoring its logo and signature."""
    img = Image.open(path).convert("RGB")
    full_w = img.width
    img.thumbnail((500, 500))
    bird, bg, leaked = masks(img, mark=(os.path.basename(path)[:-4], img.width / full_w))
    px = np.asarray(img)
    sample = lambda m: [tuple(p) for p in px[m].tolist()]
    return palette_from_pixels(sample(bird)), (palette_from_pixels(sample(bg)) if bg.sum() >= 150 else []), leaked


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
    palette, bg, _ = artist_palettes(path)
    return {"artist": artist, "site": site, "image": path, "palette": palette, "bgPalette": bg, "marksChecked": True}


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


def digital_cutout(path):
    """Transparent PNG of a digital crop: only the bird and its perch/scenery stay; the card's cream, title,
    icons and the screen around it become transparent, so the picture blends into the page's card."""
    from scipy import ndimage
    out = path.replace("/d-", "/dp-")[:-4] + ".png"
    if not os.path.exists(out):
        img = Image.open(path).convert("RGB")
        bird, bg = masks(img, DIGITAL_ART_AREA, raw=True)
        keep = ndimage.binary_fill_holes(bird) | ndimage.binary_dilation(bg, iterations=1)
        # drop stray specks (card edge shading, dust): keep pieces that touch the bird or are reasonably big
        labels, n = ndimage.label(keep)
        if n:
            idx = np.arange(1, n + 1)
            size = ndimage.sum(np.ones_like(labels), labels, idx)
            touches = ndimage.maximum(ndimage.binary_dilation(bird, iterations=3).astype(np.uint8), labels, idx).astype(bool)
            keep = np.isin(labels, idx[touches | (size > 400)])
        alpha = ndimage.uniform_filter(keep.astype(float), 3) * 255  # soft 1-2px edge
        Image.fromarray(np.dstack([np.asarray(img), alpha.astype(np.uint8)]), "RGBA").save(out)
    return out


def artist_cutout(path):
    """Bird + scenery of an artist image with everything else transparent (WebP, 700px), shown on top of the original
    so the page can fade the background with a slider."""
    from scipy import ndimage
    out = path.replace("art/", "art/ap-")[:-4] + ".webp"
    if not os.path.exists(out):
        img = Image.open(path).convert("RGB")
        img.thumbnail((700, 700))
        small = img.copy(); small.thumbnail((500, 500))
        bird, bg = masks(small, raw=True)
        # trim the white-paper rim the model's outline includes, then refill white feathers enclosed by the outline
        bird = ndimage.binary_fill_holes(bird & (np.asarray(small).min(axis=2) < 238))
        keep = bird | ndimage.binary_dilation(bg, iterations=1)
        labels, n = ndimage.label(keep)
        if n:
            idx = np.arange(1, n + 1)
            size = ndimage.sum(np.ones_like(labels), labels, idx)
            touches = ndimage.maximum(ndimage.binary_dilation(bird, iterations=3).astype(np.uint8), labels, idx).astype(bool)
            keep = np.isin(labels, idx[touches | (size > 400)])
        alpha = Image.fromarray((ndimage.uniform_filter(keep.astype(float), 3) * 255).astype(np.uint8)).resize(img.size, Image.BILINEAR)
        rgba = img.convert("RGBA"); rgba.putalpha(alpha)
        rgba.save(out, "WEBP", quality=85)
    return out


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
    # originals (art/*.jpg, art/d-*.jpg) and their bird+scenery cut-outs (art/ap-*.webp, art/dp-*.png) for the fade slider
    files = [("art/" + f, "art-enc/" + f.rsplit(".", 1)[0] + ".bin") for f in os.listdir("art") if f.endswith((".jpg", ".png", ".webp"))]
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
            "foodOr": bool(card["/ (food cost)"]),
            "beak": card["Beak direction"] or "",  # L, R, N (neither: facing forward) or LR (both)  # the game shows "/" (pay one of them) instead of "+"
            "art": None, "digital": None,
        }
        if norm(name) in digital:
            bird["digital"] = old_digital.get(sci) or digital_for(name, *digital[norm(name)], steam["shots"])
            if "bgPalette" not in bird["digital"]:
                bird["digital"]["bgPalette"] = bg_palette(bird["digital"]["image"], DIGITAL_ART_AREA)
            if "cutout" not in bird["digital"]:  # what the page shows; palettes still come from the full crop
                bird["digital"]["cutout"] = digital_cutout(bird["digital"]["image"])
        if norm(name) in art:
            uri, artist, site = art[norm(name)]
            bird["art"] = old.get(sci) or art_for(name, uri, artist, site)
            if not bird["art"].get("marksChecked"):
                palette, bg, leaked = artist_palettes(bird["art"]["image"])
                if leaked > 20:  # the logo or signature had crept into the colors: use the clean palettes
                    print("logo/signature removed from colors:", name, leaked, "px", flush=True)
                    bird["art"]["palette"], bird["art"]["bgPalette"] = palette, bg
                bird["art"]["marksChecked"] = True
            if "bgPalette" not in bird["art"]:
                bird["art"]["bgPalette"] = bg_palette(bird["art"]["image"])
            if "cutout" not in bird["art"]:
                bird["art"]["cutout"] = artist_cutout(bird["art"]["image"])
        birds.append(bird)
    birds.sort(key=lambda b: b["name"])
    with open("birds.js", "w", encoding="utf-8") as f:
        f.write("const BIRDS = " + json.dumps(birds, ensure_ascii=False) + ";\n")
    print(len(birds), "birds,", sum(1 for b in birds if b["art"]), "with card art,", sum(1 for b in birds if b["digital"]), "with digital art")
    if os.environ.get("WINGSPAN_PASSWORD"):
        encrypt_art(os.environ["WINGSPAN_PASSWORD"])
    else:
        print("WINGSPAN_PASSWORD not set: art-enc/ not updated")
