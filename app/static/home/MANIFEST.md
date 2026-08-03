---
type: Concept
title: Home hero artwork drop folder
description: Where to drop the Home page hero background image and the exact filename Home.tsx expects.
timestamp: 2026-08-04T00:00:00Z
---

# Home hero artwork drop folder

Drop the dark-blue hero artwork here using the **exact filename** below. FastAPI already
serves this directory (`app.mount("/static", ...)` in `app/server.py`), so the file is live
at `/static/home/<file>` with **no frontend rebuild** — replacing the image is a file copy.

| Slot | Filename | Used by |
|---|---|---|
| Home hero background | `home-hero-bg.png` | `frontend/src/views/Home.tsx` -> `HERO_IMAGE` |

## Requirements

- **Format:** PNG or JPG. `.jpg` is fine — change `HERO_IMAGE` in `Home.tsx` to match.
- **Size:** at least 2400 x 640. It renders `background-size: cover` in a panel that is
  ~1240px wide and 300-340px tall, and gets cropped from the centre on narrow viewports.
- **Composition:** keep the interesting artwork in the **left third**. The right side sits
  under the stat tiles and the whole panel carries a navy scrim, so detail there is lost.
- **Tone:** dark. The hero paints white text on top of it.

If the file is missing nothing breaks — the hero falls back to the flat
`tokens.color.heroInk` navy panel.

## Dev server note

`npm run dev` (Vite, port 5173) proxies both `/api` and `/static` to the FastAPI server on
`127.0.0.1:8733`, so this path resolves in dev as well as in the built bundle. That proxy
rule was added for exactly this reason — without it every `/static/*` asset 404s in dev.
