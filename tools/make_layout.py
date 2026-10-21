"""Create the AutoShield folder layout (Section 8 of the roadmap).
Safe to run many times: it only creates what is missing.
Run from the repository root:  python tools/make_layout.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FOLDERS = [
    'contracts', 'docs',
    'sim', 'core',
    'ml', 'ml/data', 'ml/models',
    'backend',
    'web', 'web/dashboard', 'web/assets', 'web/assets/css',
    'web/assets/js', 'web/assets/img', 'web/vendor',
    'firmware', 'firmware/gateway', 'firmware/target', 'firmware/shared',
    'firmware/tests', 'firmware/bin',
    'tools', 'tests',
]
# Folders that hold Python code get an empty __init__.py so imports work.
PY_PACKAGES = ['sim', 'core', 'ml', 'backend']

created = 0
for f in FOLDERS:
    d = ROOT / f
    d.mkdir(parents=True, exist_ok=True)
    keep = d / '.gitkeep'
    has_other = any(p.name != '.gitkeep' for p in d.iterdir())
    if not has_other and not keep.exists():
        keep.touch()
        created += 1
for p in PY_PACKAGES:
    init = ROOT / p / '__init__.py'
    if not init.exists():
        init.touch()
        created += 1
print(f'Layout ready. Created {created} placeholder file(s).')
