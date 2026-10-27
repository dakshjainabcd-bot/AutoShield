"""Copy the built AutoShield landing page (landing/dist) into web/.
Safe to repeat. Does NOT touch web/dashboard/ or web/assets/css/. The React
landing page includes its own Explore Dashboard link. Run from the repository
root after `pnpm build` in landing/: python tools/deploy_landing.py
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "landing" / "dist"
WEB = ROOT / "web"
if not (DIST / "index.html").is_file():
    sys.exit("landing/dist/index.html not found. Run `pnpm build` inside landing/ first.")

shutil.copy2(DIST / "index.html", WEB / "index.html")
(WEB / "assets").mkdir(parents=True, exist_ok=True)
fresh = {f.name for f in (DIST / "assets").iterdir() if f.is_file()}
for old in (WEB / "assets").glob("index-*"):      # remove files of earlier builds only
    if old.is_file() and old.name not in fresh:
        old.unlink()
for f in (DIST / "assets").iterdir():
    if f.is_file():
        shutil.copy2(f, WEB / "assets" / f.name)
if (DIST / "media").is_dir():
    shutil.copytree(DIST / "media", WEB / "media", dirs_exist_ok=True)

# The React landing page now includes its own Explore Dashboard header CTA.
# Do not inject the previous fixed lime button; that would duplicate the CTA and
# break the approved visual composition. Dashboard files remain untouched.
print("Landing page deployed to web/. Dashboard and its styling are untouched.")
