"""Тесты примитивных типов."""

from simpleworkernet.models.primitives import (
    GeoPoint,
    vFlag,
    vINN,
    vKPP,
    vMoney,
    vOGRN,
    vPercent,
    vPhoneNumber,
    vSNILS,
    vStr,
)


def test_vstr_decode():
    s = vStr("Hello%20World&amp;Co")
    assert str(s) == "Hello World&Co"
    assert isinstance(s, str)


def test_vstr_concat():
    assert str(vStr("a") + "b") == "ab"
    assert str("x" + vStr("y")) == "xy"


def test_vstr_none():
    assert str(vStr(None)) == ""


def test_vflag():
    assert vFlag.from_bool(True) == vFlag.v1
    assert vFlag.from_bool(False) == vFlag.v0
    assert vFlag.v1.to_bool() is True
    assert vFlag.v0.to_bool() is False


def test_geopoint_formats():
    p1 = GeoPoint(55.75, 37.62)
    p2 = GeoPoint([55.75, 37.62])
    p3 = GeoPoint((55.75, 37.62))
    p4 = GeoPoint("55.75,37.62")
    p5 = GeoPoint(lat=55.75, lon=37.62)
    assert p1 == p2 == p3 == p4 == p5
    assert str(p1) == "55.75,37.62"
    assert p1.to_tuple() == (55.75, 37.62)
    assert p1.to_list() == [55.75, 37.62]
    assert p1.to_dict() == {"lat": 55.75, "lon": 37.62}


def test_geopoint_distance():
    a = GeoPoint(55.75, 37.62)
    b = GeoPoint(55.76, 37.63)
    d = a.distance_to(b)
    assert 0 < d < 5  # ~1–2 км в центре Москвы


def test_phone():
    phone = vPhoneNumber("+7 (123) 456-78-90")
    assert phone.normalized == "71234567890"
    assert phone.international == "+71234567890"
    assert phone.formatted == "+7 (123) 456-78-90"


def test_phone_from_8():
    phone = vPhoneNumber("8 999 111-22-33")
    assert phone.international == "+79991112233"


def test_inn():
    legal = vINN("1234567890")
    assert legal.is_valid and legal.is_legal and not legal.is_individual
    person = vINN("123456789012")
    assert person.is_valid and person.is_individual
    assert not vINN("123").is_valid


def test_kpp():
    assert vKPP("123456789").is_valid
    assert not vKPP("123").is_valid


def test_snils():
    s = vSNILS("123-456-789 01")
    assert s.normalized == "12345678901"
    assert s.is_valid
    assert s.formatted == "123-456-789 01"


def test_ogrn():
    assert vOGRN("1234567890123").is_legal
    assert vOGRN("123456789012345").is_individual
    assert not vOGRN("123").is_valid


def test_money_ops():
    m = vMoney(amount=100.50, currency="RUB")
    assert str(m) == "100.50 RUB"
    m2 = m + 50.25
    assert abs(m2.amount - 150.75) < 1e-9
    m3 = m - 0.5
    assert abs(m3.amount - 100.0) < 1e-9
    m4 = m * 2
    assert abs(m4.amount - 201.0) < 1e-9
    m5 = m / 2
    assert abs(m5.amount - 50.25) < 1e-9


def test_money_positional():
    m = vMoney(100.50, "RUB")
    assert abs(m.amount - 100.50) < 1e-9
    assert m.currency == "RUB"


def test_money_currency_mismatch():
    a = vMoney(amount=10, currency="RUB")
    b = vMoney(amount=10, currency="USD")
    try:
        _ = a + b
        assert False
    except ValueError:
        pass


def test_percent():
    p = vPercent(15.5)
    assert abs(p.of(1000) - 155.0) < 1e-9
    assert abs(p.add_to(100) - 115.5) < 1e-9
    assert abs(p.subtract_from(100) - 84.5) < 1e-9
    assert "%" in str(p)
