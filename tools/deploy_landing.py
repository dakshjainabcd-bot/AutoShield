"""Copy the built VEYRA-style landing page (landing/dist) into web/ and add the
'Open AutoShield dashboard' link. Safe to repeat. Does NOT touch web/dashboard/
or web/assets/css/. Run from the repository root after `pnpm build` in landing/:
    python tools/deploy_landing.py
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "landing" / "dist"
WEB = ROOT / "web"
MARK = "<!--autoshield-link-->"
LINK = MARK + (
    '<style>.as-dash{position:fixed;left:50%;bottom:calc(env(safe-area-inset-bottom,0px) + 9px);'
    'transform:translateX(-50%);z-index:50;display:inline-flex;align-items:center;justify-content:center;gap:8px;'
    'height:26px;padding:0 14px;border-radius:999px;background:#edff39;color:#10190c;text-decoration:none;'
    "font:400 12px 'Space Grotesk',sans-serif;letter-spacing:-.01em;box-shadow:0 4px 18px #0003;"
    'transition:transform .25s cubic-bezier(.22,.7,.25,1),box-shadow .25s}'
    '.as-dash:hover{transform:translateX(-50%) translateY(-2px);box-shadow:0 8px 24px #0004}'
    '.as-dash:focus-visible{outline:3px solid #fff;outline-offset:3px}'
    '@media(max-width:900px){.as-dash{bottom:auto;left:auto;right:20px;top:calc(env(safe-area-inset-top,0px) + 84px);'
    'transform:none;width:40px;height:40px;padding:0;font-size:18px}.as-dash:hover{transform:translateY(-2px)}'
    '.as-dash .t{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}}'
    '@media(prefers-reduced-motion:reduce){.as-dash{transition:none}}</style>'
    '<a class="as-dash" href="/dashboard/" aria-label="Open AutoShield dashboard" title="Open AutoShield dashboard">'
    '<span class="t" style="font-size:12px">AutoShield dashboard</span><span aria-hidden="true">\u2192</span></a>'
)

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

html = (WEB / "index.html").read_text(encoding="utf-8")
if MARK not in html:
    html = html.replace("</body>", LINK + "</body>")
    (WEB / "index.html").write_text(html, encoding="utf-8")
print("Landing page deployed to web/. Dashboard and CSS untouched.")
