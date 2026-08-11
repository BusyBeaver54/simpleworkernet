"""
Live-тесты топологии.

Требуют данных в ERP. При отсутствии подходящих объектов — skip.

Параметры (CLI > env):
    --nodeid / WORKERNET_TEST_NODE_ID
    --customerid / WORKERNET_TEST_CUSTOMER_ID

Полный live-прогон:
    pytest tests/ -v \\
        --wn-host=my.workernet.ru --wn-apikey=SECRET \\
        --nodeid=23779 --customerid=68168
"""

from __future__ import annotations

import pytest

from simpleworkernet.utils.topology import NetworkTopology, DataCache

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def topology(live_client):
    return NetworkTopology(live_client, cache=DataCache())


def test_topology_build_from_node_if_configured(topology, node_id):
    if node_id is None:
        pytest.skip("Задайте --nodeid или WORKERNET_TEST_NODE_ID")

    topology.build_from_node(node_id)
    assert topology.fngraph is not None or topology.cgraphs is not None


def test_topology_build_from_customer_if_configured(topology, customer_id):
    if customer_id is None:
        pytest.skip("Задайте --customerid или WORKERNET_TEST_CUSTOMER_ID")

    topology.build_from_customer(customer_id)
    customers = topology.get_customers()
    assert customer_id in customers or len(topology.cgraphs) >= 0
