"""
Дымовые тесты против реального WorkerNet API.

Запуск:
    pytest tests/integration/ -v \\
        --wn-host=my.workernet.ru --wn-apikey=SECRET

    # или через env:
    export WORKERNET_HOST=my.workernet.ru
    export WORKERNET_APIKEY=SECRET
    pytest tests/integration/ -v

Unit-тесты (без сети):
    pytest tests/ -m "not integration" -v
"""

import pytest

pytestmark = pytest.mark.integration


def test_client_online(live_client):
    """Сервер отвечает на базовый запрос."""
    status = live_client.is_online()
    # is_online возвращает status_code или False
    assert status is not False


def test_module_api_information(live_client):
    """Module.get_api_information — лёгкий read-only метод."""
    info = live_client.Module.get_api_information()
    assert info is not None
    # SmartData или dict/list — главное, что не упало
    assert len(info) >= 0 or bool(info) or info is not None


def test_system_info(live_client):
    """System.get_system_info."""
    data = live_client.System.get_system_info()
    assert data is not None


def test_fiber_catalog(live_client):
    """Каталог типов/кабелей доступен."""
    types = live_client.Fiber.catalog_types_get()
    assert types is not None


def test_node_list_smoke(live_client):
    """Список узлов (может быть пустым, но запрос успешен)."""
    nodes = live_client.Node.get()
    assert nodes is not None
    # count/len если SmartData
    if hasattr(nodes, "count"):
        assert nodes.count() >= 0
    else:
        assert len(nodes) >= 0
