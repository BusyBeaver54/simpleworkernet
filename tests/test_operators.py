"""Тесты Operator и Where."""

from simpleworkernet.models.operators import Operator, Where


def test_operator_values():
    assert Operator.EQ == "=="
    assert Operator.NE == "!="
    assert Operator.GT == ">"
    assert Operator.LT == "<"
    assert Operator.GTE == ">="
    assert Operator.LTE == "<="
    assert Operator.LIKE == "LIKE"
    assert Operator.IN == "IN"
    assert Operator.BETWEEN == "BETWEEN"
    assert Operator.REGEX == "REGEX"


def test_where_eq_dict():
    item = {"state_id": 2, "name": "Иван"}
    assert Where("state_id", 2).check(item) is True
    assert Where("state_id", 1).check(item) is False


def test_where_ne():
    assert Where("state_id", 1, Operator.NE).check({"state_id": 2}) is True
    assert Where("state_id", 2, Operator.NE).check({"state_id": 2}) is False


def test_where_comparisons():
    item = {"balance": 1000}
    assert Where("balance", 500, Operator.GT).check(item) is True
    assert Where("balance", 1000, Operator.GTE).check(item) is True
    assert Where("balance", 1500, Operator.LT).check(item) is True
    assert Where("balance", 1000, Operator.LTE).check(item) is True


def test_where_like():
    item = {"name": "Иван Петров"}
    assert Where("name", "иван", Operator.LIKE).check(item) is True
    assert Where("name", "сидор", Operator.LIKE).check(item) is False


def test_where_in():
    item = {"city": "Москва"}
    assert Where("city", ["Москва", "СПб"], Operator.IN).check(item) is True
    assert Where("city", ["Казань"], Operator.IN).check(item) is False


def test_where_between():
    item = {"age": 30}
    assert Where("age", [25, 35], Operator.BETWEEN).check(item) is True
    assert Where("age", [35, 25], Operator.BETWEEN).check(item) is True  # любой порядок
    assert Where("age", [40, 50], Operator.BETWEEN).check(item) is False


def test_where_regex():
    item = {"name": "Иван"}
    assert Where("name", r"^Ив", Operator.REGEX).check(item) is True
    assert Where("name", r"^Пет", Operator.REGEX).check(item) is False


def test_where_attr_object():
    class Obj:
        balance = 100

    assert Where("balance", 100).check(Obj()) is True
    assert Where("balance", 50, Operator.GT).check(Obj()) is True
