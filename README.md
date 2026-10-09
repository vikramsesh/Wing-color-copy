# Wingspan Bird Palettes

Browse the 180 core-set Wingspan birds by color. Each bird's palette is taken from the bird only (perches, paper and signatures are ignored), with a heat map of where each color sits, color names, editable palettes, and similar-bird matching within the same color family.

**Live site:** https://vikramsesh.github.io/Wing-color-copy/ (artist originals) · [digital game art](https://vikramsesh.github.io/Wing-color-copy/?set=digital)

## Two modes

- **Color Copy**: each bird's palette, a heat map of where each color sits, and birds with similar colors (same color family only).
- **Artist's Palette** (`?mode=palette`): a bird gets the 🖌️ flag when the color of a food in its cost appears on the bird or in its background (perch, plants, water): Wheat = Yellow, Cherry = Red, Rat = Brown or Gray, Worm = Green, Fish = Blue, Omnivore = Black or White. The card view shows which food matched and where.

Both modes work with the artist originals and with the digital-game art (`?set=digital`). Birds are listed alphabetically. In a bird's card view, the ‹ › arrows (or ← → keys) step through the birds that match your current search and filters.

## Card art is password protected

The bird illustrations belong to their artists, Natalia Rojas and Ana María Martínez Jaramillo, and Stonemaier Games. This repo contains only **encrypted** copies (`art-enc/`). The site decrypts them in your browser after you enter the password. Without it you can still browse stats and palettes.

## Admin: removing colors and repositioning pictures

Click **Admin** under the search box and log in with the admin password. In a bird's card view you can then:

- remove colors that aren't part of the bird (× on a color) and restore them,
- add colors by typing them (a name like `yellow`, a hex code like `#3c7fd0`, or any CSS color name) or by clicking the picture; in Artist's Palette mode, choose whether they go to the bird or its background,
- force the 🖌️ Artist's Palette flag on or off (or leave it automatic), and
- zoom and drag the picture (**Picture position**) so the whole bird shows.

Your changes are saved in your browser as a draft. To publish them for everyone, click **Download overrides.json**, then upload that file to the root of this repo (on GitHub: **Add file → Upload files**, replacing the existing `overrides.json`). Visitors who aren't admin can't remove colors. They can still add colors in their own browser by clicking the bird.

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
