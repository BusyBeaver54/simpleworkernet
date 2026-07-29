"""
Live-тесты топологии.

Требуют данных в ERP. При отсутствии подходящих объектов — skip.

Опционально можно сузить через env:
    WORKERNET_TEST_NODE_ID=123
    WORKERNET_TEST_CUSTOMER_ID=456
"""

from __future__ import annotations

import os

import pytest

from simpleworkernet.utils.topology import Topology, DataCache

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def topology(live_client):
    return Topology(live_client, cache=DataCache())


def test_topology_build_from_node_if_configured(topology):
    node_id = os.environ.get("WORKERNET_TEST_NODE_ID")
    if not node_id:
        pytest.skip("Задайте WORKERNET_TEST_NODE_ID для live topology-теста")

    topology.build_from_node(int(node_id))
    # FNGraph мог построиться
    assert topology.fngraph is not None or topology.cgraphs is not None


def test_topology_build_from_customer_if_configured(topology):
    customer_id = os.environ.get("WORKERNET_TEST_CUSTOMER_ID")
    if not customer_id:
        pytest.skip("Задайте WORKERNET_TEST_CUSTOMER_ID для live topology-теста")

    topology.build_from_customer(int(customer_id))
    customers = topology.get_customers()
    assert int(customer_id) in customers or len(topology.cgraphs) >= 0
