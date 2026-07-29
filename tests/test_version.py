"""Версия и метаданные пакета."""

from simpleworkernet.__version__ import __author__, __license__, __version__


def test_version_format():
    parts = __version__.split(".")
    assert len(parts) >= 2
    assert all(p.isdigit() for p in parts[:2])


def test_meta():
    assert __author__
    assert __license__ == "MIT"
