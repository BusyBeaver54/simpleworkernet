"""Фикстуры только для integration."""

import pytest


def pytest_collection_modifyitems(config, items):
    """Автоматически помечаем все тесты в integration маркером."""
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
