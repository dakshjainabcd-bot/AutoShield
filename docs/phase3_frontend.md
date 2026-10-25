# AutoShield, Phase 3: landing page and dashboard (frontend)

## What is in this package

| Path | What it is |
| --- | --- |
| `web/index.html`, `web/assets/index-*.js/css`, `web/media/` | Landing page: the VEYRA interactive-car scene (MIT licensed, see `landing/LICENSE`), copy retargeted to AutoShield. Served at `/`. |
| `web/dashboard/index.html` | Live dashboard. Served at `/dashboard/`. WebSocket `/ws`, automatic reconnect, REPLAY fallback, fault controls, two themes. |
| `web/assets/css/style.css` | Dashboard styles (studio blue by default, black/orange/cream via the Theme button). |
| `web/assets/sample_run.jsonl` | 190 s replay sample for the dashboard (script-generated stand-in, see below). |
| `landing/` | Source of the landing page (Vite + React). Needed only if you want to change it. |
| `tools/deploy_landing.py` | Copies `landing/dist` into `web/` and adds the dashboard link. |
| `tools/make_sample_run.py` | Regenerates `web/assets/sample_run.jsonl`. |

## Run it

Copy `web/`, `landing/`, `tools/` and `docs/` into the repository root (only the old `web/index.html` is replaced). With the Phase 2 backend:

    python -m uvicorn backend.main:app --port 8000

Open http://127.0.0.1:8000/ and http://127.0.0.1:8000/dashboard/. Without the backend, serve `web/` with any static server (for example `python -m http.server 8000` inside `web/`) and open `/dashboard/?replay=1`.

## Rebuild the landing page (needs Node 22 and pnpm 10.15.1)

    cd landing && pnpm install --frozen-lockfile && pnpm build && cd .. && python tools/deploy_landing.py

## Honest notes

* `web/assets/sample_run.jsonl` is NOT simulator output. It follows the Phase 1 scenario timeline, its `ml` values are placeholders until the Phase 2 SVM exists, and the dashboard labels it REPLAY. Replace it with a real export from the backend when ready.
* `pnpm verify:reference` now reports 3 differing files (`index.html`, `src/App.tsx`, `src/content.ts`). That is the intended AutoShield copy; media bytes are unchanged. Do not regenerate the manifest.
* The landing page still contains the original Body colour and Wheel design menus, and the car images are the original blue renders.
* Tested in headless Chromium without an H.264 decoder: the hood and battery hover videos could not be played there. Test them once in normal Chrome or Edge.
* The font loads from Google Fonts and needs internet on first load; offline it falls back to the system font.
