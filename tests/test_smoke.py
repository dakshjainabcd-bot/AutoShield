"""Smoke test: proves pytest runs and the project folders are importable."""
import sys


def test_python_version():
    assert sys.version_info >= (3, 10)


def test_project_packages_importable():
    import backend, core, ml, sim  # noqa: F401
