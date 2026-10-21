"""Environment check for AutoShield. Run from the repository root:
    python tools/check_env.py
Every line must start with OK. Exit code is 0 if all is well, 1 otherwise.
"""
import importlib
import sys

need = {
    'numpy': 'numpy',
    'sklearn': 'scikit-learn',
    'pandas': 'pandas',
    'fastapi': 'fastapi',
    'uvicorn': 'uvicorn',
    'websockets': 'websockets',
    'can': 'python-can',
    'serial': 'pyserial',
    'pytest': 'pytest',
    'httpx': 'httpx',
}

print('Python', sys.version.split()[0])
bad = 0
for mod, pkg in need.items():
    try:
        m = importlib.import_module(mod)
        print(f'OK   {pkg:14s} {getattr(m, "__version__", "?")}')
    except Exception as e:
        bad += 1
        print(f'FAIL {pkg:14s} {e}')

if bad:
    print(f'\n{bad} package(s) failed. Is the virtual environment activated? '
          'Did "pip install -r requirements.txt" finish without errors?')
else:
    print('\nAll packages found. Environment is ready.')
sys.exit(1 if bad else 0)
