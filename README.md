# Wingspan Bird Palettes

Browse the 180 core-set Wingspan birds by color. Each bird's palette is taken from the bird only (perches, paper and signatures are ignored), with a heat map of where each color sits, color names, editable palettes, and similar-bird matching within the same color family.

**Live site:** https://vikramsesh.github.io/Wing-color-copy/ (artist originals) · [digital game art](https://vikramsesh.github.io/Wing-color-copy/?set=digital)

## Card art is password protected

The bird illustrations belong to their artists, Natalia Rojas and Ana María Martínez Jaramillo, and Stonemaier Games. This repo contains only **encrypted** copies (`art-enc/`). The site decrypts them in your browser after you enter the password. Without it you can still browse stats and palettes.

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
