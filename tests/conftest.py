"""Корневые фикстуры."""

import pytest


@pytest.fixture
def sample_users():
    return [
        {"id": 1, "name": "Иван", "balance": 1500, "state_id": 2, "city": "Москва"},
        {"id": 2, "name": "Пётр", "balance": 500, "state_id": 2, "city": "СПб"},
        {"id": 3, "name": "Анна", "balance": 0, "state_id": 1, "city": "Москва"},
        {"id": 4, "name": "Олег", "balance": 3000, "state_id": 2, "city": "Казань"},
    ]
