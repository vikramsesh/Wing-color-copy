# Wingspan Bird Palettes

Browse the 180 core-set Wingspan birds by color. Each bird's palette is taken from the bird only (perches, paper and signatures are ignored), with a heat map of where each color sits, color names, editable palettes, and similar-bird matching within the same color family.

**Live site:** https://vikramsesh.github.io/Wing-color-copy/

## Artist's Palette

A bird gets the 🖌️ flag when the color of a food in its cost appears on the bird or in its background (perch, plants, water): Wheat = Yellow, Cherry = Red, Rat = Brown or Gray, Worm = Green, Fish = Blue, Omnivore = Black or White. The card view shows which food matched and where. **Points:** 2 for every food icon whose color is on the bird or in its background (worm + cherry with green and red = 4; three worms with green = 6). Each bird has a serial number (No. 001 to 180, alphabetical); type a number in the search box to jump to it. In a bird's card view, the ‹ › arrows (or ← → keys) step through the birds that match your current search and filters. Click **Select** at the top of any cards to select them: the panel at the top right adds up their Artist's Palette points and victory points (with "Show only these" and Clear). Open **Per-bird breakdown** for a table of each selected bird (serial number, victory points, Artist's Palette points, matched foods) with totals; **Copy for spreadsheet** (tab-separated) or **Copy as text** (aligned columns) to paste it elsewhere. Each card shows a beak icon for the beak direction (left, right, or center = facing forward; the Common Loon faces both ways), and the **Beak** filter selects by it. The **Wingspan** filter shows birds less than or greater than a size you type (cm). The color filter looks at the bird's own colors only, not its background. The **Background** slider under the search box fades everything except the bird and its perch (100% = the original picture); it's remembered in your browser.

The digital-game art (`?set=digital`) is hidden from visitors unless the admin turns on "Show the digital game art to visitors" and publishes `overrides.json`.

## Card art is password protected

The bird illustrations belong to their artists, Natalia Rojas and Ana María Martínez Jaramillo, and Stonemaier Games. This repo contains only **encrypted** copies (`art-enc/`). The site decrypts them in your browser after you enter the password. Without it you can still browse stats and palettes.

## Admin: removing colors and repositioning pictures

Click **Admin** under the search box and log in with the admin password. In a bird's card view you can then:

- remove colors that aren't part of the bird (× on a color) and restore them,
- add colors by typing them, one or several at once (`red, yellow, #3c7fd0`; names, hex codes or CSS color names), or by clicking the picture; in Artist's Palette mode, choose whether they go to the bird or its background,
- force the 🖌️ Artist's Palette flag on or off (or leave it automatic),
- correct a bird's beak direction, and
- zoom and drag the picture (**Picture position**) so the whole bird shows.

**Publishing for everyone:** click **Connect GitHub to publish automatically** in the admin bar once and paste a GitHub fine-grained personal access token for this repo with **Contents: Read and write** (GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens). After that, every admin change is saved to `overrides.json` in the repo a few seconds after you stop editing, and the live site shows it to everyone within about a minute. The token is kept only in your browser (IndexedDB); **Disconnect GitHub** removes it. Without a token, **Download overrides.json** and upload it to the repo as before.

Only the admin can add or remove colors; regular visitors see the published palettes. The admin login lasts until the browser is closed.

## Passwords

Neither password is stored anywhere in this repo.

- **Art password:** the art is encrypted with a key derived from it (PBKDF2-SHA256, 600,000 rounds). After logging in, the browser keeps only a non-extractable key in IndexedDB, which can decrypt but can't be read back out. To change it: `WINGSPAN_PASSWORD=<new> python build.py` after deleting `art-enc/` (everything is re-encrypted), then commit `art-enc/`.
- **Admin password:** `index.html` holds only a salted PBKDF2-SHA256 hash (`ADMIN_KDF`). To change it, run
  `python -c "import hashlib,os,base64;s=os.urandom(16);print(base64.b64encode(s).decode(), hashlib.pbkdf2_hmac('sha256', b'NEW-PASSWORD', s, 600000).hex())"`
  and put the two printed values into `ADMIN_KDF.salt` and `ADMIN_KDF.hash`. The admin password only unlocks the editing tools; publishing still needs write access to this repo.

Use long, random passphrases and keep them in a password manager.

## Credits

- Card data: [Wingsearch](https://github.com/navarog/wingsearch) (GPLv3), downloaded at build time.
- Card art: [Natalia Rojas](https://www.nataliarojasart.com/portfolio/wingspan-base), [Ana María Martínez Jaramillo](https://www.anammartinez.com/wingspanbasegame). Wingspan © Stonemaier Games.
- Digital-edition card art (`?set=digital`): cropped from the screenshots in [ungeni's Steam guide](https://steamcommunity.com/sharedfiles/filedetails/?id=2690214466).
- Layout inspired by [Wingsearch](https://navarog.github.io/wingsearch/).

## Rebuilding

```bash
pip install pillow numpy cryptography torch transformers
WINGSPAN_PASSWORD=... python build.py
```

`build.py` downloads the art into `art/` (git-ignored), finds the bird in each image with CLIPSeg, extracts the palettes into `birds.js`, and encrypts the art into `art-enc/`.

Run locally with `python -m http.server`, then open http://localhost:8000.
