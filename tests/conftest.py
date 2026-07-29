"""Корневые фикстуры и CLI-опции pytest."""

from __future__ import annotations

import os
from typing import Optional

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("workernet", "WorkerNet live API")
    group.addoption(
        "--wn-host",
        action="store",
        default=None,
        help="Хост API WorkerNet (или env WORKERNET_HOST)",
    )
    group.addoption(
        "--wn-apikey",
        action="store",
        default=None,
        help="API-ключ (или env WORKERNET_APIKEY)",
    )
    group.addoption(
        "--wn-protocol",
        action="store",
        default=None,
        help="http|https (или env WORKERNET_PROTOCOL, default https)",
    )
    group.addoption(
        "--wn-port",
        action="store",
        type=int,
        default=None,
        help="Порт (или env WORKERNET_PORT, default 443)",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: тесты против реального API (нужны --wn-host и --wn-apikey)",
    )


def _opt_or_env(config: pytest.Config, opt: str, env: str) -> Optional[str]:
    value = config.getoption(opt)
    if value:
        return str(value)
    return os.environ.get(env) or None


@pytest.fixture(scope="session")
def wn_credentials(pytestconfig: pytest.Config) -> dict:
    """
    Учётные данные для live-тестов.

    Приоритет: CLI > переменные окружения.
    Если host или apikey отсутствуют — integration-тесты skip.
    """
    host = _opt_or_env(pytestconfig, "--wn-host", "WORKERNET_HOST")
    apikey = _opt_or_env(pytestconfig, "--wn-apikey", "WORKERNET_APIKEY")
    protocol = (
        _opt_or_env(pytestconfig, "--wn-protocol", "WORKERNET_PROTOCOL") or "https"
    )
    port_opt = pytestconfig.getoption("--wn-port")
    if port_opt is not None:
        port = int(port_opt)
    else:
        port = int(os.environ.get("WORKERNET_PORT", "443"))

    return {
        "host": host,
        "apikey": apikey,
        "protocol": protocol,
        "port": port,
    }


@pytest.fixture(scope="session")
def live_client(wn_credentials):
    """
    Реальный WorkerNetClient (session-scoped).

    Skip, если не заданы host/apikey.
    """
    host = wn_credentials["host"]
    apikey = wn_credentials["apikey"]
    if not host or not apikey:
        pytest.skip(
            "Live API: укажите --wn-host и --wn-apikey "
            "или WORKERNET_HOST / WORKERNET_APIKEY"
        )

    from simpleworkernet import WorkerNetClient

    client = WorkerNetClient(
        host=host,
        apikey=apikey,
        protocol=wn_credentials["protocol"],
        port=wn_credentials["port"],
    )
    client.session()
    yield client
    client.closeSession()


@pytest.fixture
def sample_users():
    return [
        {"id": 1, "name": "Иван", "balance": 1500, "state_id": 2, "city": "Москва"},
        {"id": 2, "name": "Пётр", "balance": 500, "state_id": 2, "city": "СПб"},
        {"id": 3, "name": "Анна", "balance": 0, "state_id": 1, "city": "Москва"},
        {"id": 4, "name": "Олег", "balance": 3000, "state_id": 2, "city": "Казань"},
    ]
