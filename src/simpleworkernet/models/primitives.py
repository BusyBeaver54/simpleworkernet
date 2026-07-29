# simpleworkernet/models/primitives.py
"""
Примитивные типы данных для SimpleWorkerNet
"""
import html
import math
from urllib.parse import unquote_plus
from enum import IntFlag
from typing import Any, Union, List, Tuple, Optional, Sequence

from .base import BaseModel, smart_model
from ..core.logger import log


class vStr(str):
    """
    Специальный строковый тип для декодирования URL-encoded и HTML-encoded строк
    
    Автоматически декодирует строки при создании:
    - URL-encoded символы (%20 -> пробел)
    - HTML entities (&amp; -> &)
    
    Пример:
        >>> s = vStr("Hello%20World&amp;Co")
        >>> print(s)  # "Hello World&Co"
    """
    
    def __new__(cls, value: Any) -> 'vStr':
        """
        Создает новый экземпляр vStr с декодированием
        
        Args:
            value: Исходное значение (будет преобразовано в строку)
            
        Returns:
            Декодированная строка
        """
        if value is None:
            value = ""
        
        # Преобразуем в строку и декодируем
        str_value = str(value)
        decoded = unquote_plus(
            string=html.unescape(str_value),
            encoding="utf-8"
        )
        
        return super().__new__(cls, decoded)
    
    def __repr__(self) -> str:
        """Представление для отладки"""
        return f"vStr('{super().__str__()}')"
    
    def __add__(self, other: Any) -> 'vStr':
        """Конкатенация строк"""
        return vStr(super().__str__() + str(other))
    
    def __radd__(self, other: Any) -> 'vStr':
        """Конкатенация справа"""
        return vStr(str(other) + super().__str__())


class vFlag(IntFlag):
    """
    Битовые флаги для API WorkerNet
    
    Поддерживает стандартные значения:
    - v0 = 0 (выключено/False)
    - v1 = 1 (включено/True)
    
    Пример:
        >>> flag = vFlag.v1
        >>> if flag & vFlag.v1:
        >>>     print("Флаг установлен")
    """
    
    v0 = 0
    """Значение 0 (False/выключено)"""
    
    v1 = 1
    """Значение 1 (True/включено)"""
    
    @classmethod
    def from_bool(cls, value: bool) -> 'vFlag':
        """
        Создает флаг из булева значения
        
        Args:
            value: True или False
            
        Returns:
            vFlag.v1 для True, vFlag.v0 для False
        """
        return cls.v1 if value else cls.v0
    
    def to_bool(self) -> bool:
        """
        Преобразует флаг в булево значение
        
        Returns:
            True для vFlag.v1, False для vFlag.v0
        """
        return bool(self.value)
    
    def __str__(self) -> str:
        """Строковое представление"""
        return str(self.value)
    
    def __repr__(self) -> str:
        """Представление для отладки"""
        return f"vFlag.{self.name if self.value else 'v0'}"


@smart_model
class GeoPoint(BaseModel):
    """
    Географические координаты (широта, долгота)
    
    Поддерживает различные форматы инициализации:
    - GeoPoint(lat=55.75, lon=37.62)
    - GeoPoint(55.75, 37.62)
    - GeoPoint([55.75, 37.62])
    - GeoPoint((55.75, 37.62))
    - GeoPoint("55.75,37.62")
    
    Пример:
        >>> point = GeoPoint(55.75, 37.62)
        >>> print(point)  # "55.75,37.62"
        >>> print(point.lat)  # 55.75
        >>> print(point.lon)  # 37.62
    """
    
    lat: float
    """Широта (от -90 до 90)"""
    
    lon: float
    """Долгота (от -180 до 180)"""
    
    def __init__(self, *args, **kwargs):
        """
        Инициализация координат
        
        Поддерживаются различные сигнатуры:
        - GeoPoint(lat=55.75, lon=37.62)
        - GeoPoint(55.75, 37.62)
        - GeoPoint([55.75, 37.62])
        - GeoPoint((55.75, 37.62))
        - GeoPoint("55.75,37.62")
        """
        # Если передан один позиционный аргумент
        if len(args) == 1:
            arg = args[0]
            
            # Список или кортеж [lat, lon] / (lat, lon)
            if isinstance(arg, Sequence) and not isinstance(arg, (str, bytes)) and len(arg) == 2:
                lat, lon = arg[0], arg[1]
                super().__init__(lat=float(lat), lon=float(lon))
                self._validate()
                return
            
            # Строка "lat,lon"
            if isinstance(arg, str):
                try:
                    parts = arg.split(',')
                    if len(parts) == 2:
                        lat, lon = map(float, parts)
                        super().__init__(lat=lat, lon=lon)
                        self._validate()
                        return
                except (ValueError, TypeError):
                    pass
            
            # Словарь {'lat': 55.75, 'lon': 37.62}
            if isinstance(arg, dict):
                super().__init__(**arg)
                self._validate()
                return
        
        # GeoPoint(55.75, 37.62)
        if len(args) == 2:
            lat, lon = args
            super().__init__(lat=float(lat), lon=float(lon))
            self._validate()
            return
        
        # Именованные аргументы
        super().__init__(*args, **kwargs)
        self._validate()
    
    def _validate(self):
        """Проверяет корректность координат"""
        if not -90 <= self.lat <= 90:
            log.warning(f"Широта {self.lat} выходит за допустимый диапазон [-90, 90]")
        
        if not -180 <= self.lon <= 180:
            log.warning(f"Долгота {self.lon} выходит за допустимый диапазон [-180, 180]")
    
    def to_tuple(self) -> Tuple[float, float]:
        """
        Возвращает координаты в виде кортежа (lat, lon)
        
        Returns:
            Кортеж (широта, долгота)
        """
        return (self.lat, self.lon)
    
    def to_list(self) -> List[float]:
        """
        Возвращает координаты в виде списка [lat, lon]
        
        Returns:
            Список [широта, долгота]
        """
        return [self.lat, self.lon]
    
    def to_dict(self) -> dict:
        """
        Возвращает координаты в виде словаря
            
        Returns:
            Словарь {'lat': широта, 'lon': долгота}
        """
        return {'lat': self.lat, 'lon': self.lon}
    
    def distance_to(self, other: 'GeoPoint') -> float:
        """
        Вычисляет расстояние до другой точки по формуле гаверсинуса (в километрах)
        
        Args:
            other: Другая точка GeoPoint
            
        Returns:
            Расстояние в километрах
        """
        R = 6371  # Радиус Земли в км
        
        lat1, lon1 = math.radians(self.lat), math.radians(self.lon)
        lat2, lon2 = math.radians(other.lat), math.radians(other.lon)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c
    
    def __str__(self) -> str:
        """Строковое представление для API"""
        return f"{self.lat},{self.lon}"
    
    def __repr__(self) -> str:
        """Представление для отладки"""
        return f"GeoPoint(lat={self.lat}, lon={self.lon})"
    
    def __eq__(self, other: Any) -> bool:
        """Сравнение с другой точкой"""
        if isinstance(other, GeoPoint):
            return abs(self.lat - other.lat) < 1e-10 and abs(self.lon - other.lon) < 1e-10
        return False


class vPhoneNumber(str):
    """
    Специальный тип для телефонных номеров
    
    Нормализует формат номера:
    - Удаляет все не-цифровые символы
    - Приводит к международному формату (если возможно)
    
    Пример:
        >>> phone = vPhoneNumber("+7 (123) 456-78-90")
        >>> print(phone.normalized)  # "71234567890"
        >>> print(phone.formatted)   # "+7 (123) 456-78-90"
    """
    
    def __new__(cls, value: Any) -> 'vPhoneNumber':
        """
        Создает новый экземпляр телефонного номера
        
        Args:
            value: Исходное значение (строка или число)
        """
        if value is None:
            value = ""
        
        # Сохраняем оригинал
        instance = super().__new__(cls, str(value))
        instance._original = str(value)
        return instance
    
    def __init__(self, value: Any):
        """Инициализация"""
        self._digits = self._extract_digits()
    
    def _extract_digits(self) -> str:
        """Извлекает только цифры из номера"""
        return ''.join(filter(str.isdigit, self._original))
    
    @property
    def normalized(self) -> str:
        """
        Нормализованный номер (только цифры)
        
        Returns:
            Строка, содержащая только цифры
        """
        return self._digits
    
    @property
    def formatted(self) -> str:
        """
        Форматированный номер (исходный)
        
        Returns:
            Исходная строка
        """
        return self._original
    
    @property
    def international(self) -> Optional[str]:
        """
        Номер в международном формате (если возможно)
        
        Returns:
            Номер в формате +7XXXXXXXXXX или None
        """
        if len(self._digits) == 10:
            # Российский номер без кода страны
            return f"+7{self._digits}"
        elif len(self._digits) == 11 and self._digits.startswith('7'):
            # Уже с кодом страны
            return f"+{self._digits}"
        elif len(self._digits) == 11 and self._digits.startswith('8'):
            # Российский номер с 8
            return f"+7{self._digits[1:]}"
        return None
    
    def __repr__(self) -> str:
        return f"vPhoneNumber('{self._original}')"


class vINN(str):
    """
    Специальный тип для ИНН (Идентификационный номер налогоплательщика)
    
    Проверяет корректность ИНН (10 или 12 цифр)
    
    Пример:
        >>> inn = vINN("1234567890")
        >>> print(inn.is_valid)  # True
    """
    
    def __new__(cls, value: Any) -> 'vINN':
        """Создает новый экземпляр ИНН"""
        if value is None:
            value = ""
        return super().__new__(cls, str(value))
    
    def __init__(self, value: Any):
        """Инициализация"""
        self._digits = ''.join(filter(str.isdigit, str(value)))
    
    @property
    def normalized(self) -> str:
        """
        Нормализованный ИНН (только цифры)
        
        Returns:
            Строка, содержащая только цифры
        """
        return self._digits
    
    @property
    def is_valid(self) -> bool:
        """
        Проверяет корректность ИНН
        
        Returns:
            True для 10 или 12 цифр
        """
        return len(self._digits) in (10, 12) and self._digits.isdigit()
    
    @property
    def is_legal(self) -> bool:
        """
        Проверяет, является ли ИНН юридического лица (10 цифр)
        
        Returns:
            True для ИНН юрлица
        """
        return len(self._digits) == 10
    
    @property
    def is_individual(self) -> bool:
        """
        Проверяет, является ли ИНН физического лица (12 цифр)
        
        Returns:
            True для ИНН физлица
        """
        return len(self._digits) == 12
    
    def __repr__(self) -> str:
        return f"vINN('{self._digits}')"


class vKPP(str):
    """
    Специальный тип для КПП (Код причины постановки на учет)
    
    Формат: 9 цифр (XXXXXXYYY)
    
    Пример:
        >>> kpp = vKPP("123456789")
        >>> print(kpp.is_valid)  # True
    """
    
    def __new__(cls, value: Any) -> 'vKPP':
        """Создает новый экземпляр КПП"""
        if value is None:
            value = ""
        return super().__new__(cls, str(value))
    
    def __init__(self, value: Any):
        """Инициализация"""
        self._digits = ''.join(filter(str.isdigit, str(value)))
    
    @property
    def normalized(self) -> str:
        """Нормализованный КПП (только цифры)"""
        return self._digits
    
    @property
    def is_valid(self) -> bool:
        """
        Проверяет корректность КПП
        
        Returns:
            True для 9 цифр
        """
        return len(self._digits) == 9 and self._digits.isdigit()
    
    def __repr__(self) -> str:
        return f"vKPP('{self._digits}')"


class vSNILS(str):
    """
    Специальный тип для СНИЛС (Страховой номер индивидуального лицевого счета)
    
    Формат: XXX-XXX-XXX YY (11 цифр)
    
    Пример:
        >>> snils = vSNILS("123-456-789 01")
        >>> print(snils.normalized)  # "12345678901"
    """
    
    def __new__(cls, value: Any) -> 'vSNILS':
        """Создает новый экземпляр СНИЛС"""
        if value is None:
            value = ""
        return super().__new__(cls, str(value))
    
    def __init__(self, value: Any):
        """Инициализация"""
        self._digits = ''.join(filter(str.isdigit, str(value)))
    
    @property
    def normalized(self) -> str:
        """
        Нормализованный СНИЛС (только цифры)
        
        Returns:
            Строка из 11 цифр
        """
        return self._digits
    
    @property
    def is_valid(self) -> bool:
        """
        Проверяет корректность СНИЛС
        
        Returns:
            True для 11 цифр
        """
        return len(self._digits) == 11 and self._digits.isdigit()
    
    @property
    def formatted(self) -> str:
        """
        Форматированный СНИЛС (XXX-XXX-XXX YY)
        
        Returns:
            Строка в формате "XXX-XXX-XXX YY"
        """
        if len(self._digits) == 11:
            return f"{self._digits[:3]}-{self._digits[3:6]}-{self._digits[6:9]} {self._digits[9:]}"
        return self._digits
    
    def __repr__(self) -> str:
        return f"vSNILS('{self._digits}')"


class vOGRN(str):
    """
    Специальный тип для ОГРН (Основной государственный регистрационный номер)
    
    Формат: 
    - ОГРН юрлица: 13 цифр
    - ОГРНИП: 15 цифр
    
    Пример:
        >>> ogrn = vOGRN("1234567890123")
        >>> print(ogrn.is_legal)  # True
    """
    
    def __new__(cls, value: Any) -> 'vOGRN':
        """Создает новый экземпляр ОГРН"""
        if value is None:
            value = ""
        return super().__new__(cls, str(value))
    
    def __init__(self, value: Any):
        """Инициализация"""
        self._digits = ''.join(filter(str.isdigit, str(value)))
    
    @property
    def normalized(self) -> str:
        """Нормализованный ОГРН (только цифры)"""
        return self._digits
    
    @property
    def is_valid(self) -> bool:
        """
        Проверяет корректность ОГРН
        
        Returns:
            True для 13 или 15 цифр
        """
        return len(self._digits) in (13, 15) and self._digits.isdigit()
    
    @property
    def is_legal(self) -> bool:
        """
        Проверяет, является ли ОГРН юридического лица (13 цифр)
        
        Returns:
            True для ОГРН юрлица
        """
        return len(self._digits) == 13
    
    @property
    def is_individual(self) -> bool:
        """
        Проверяет, является ли ОГРНИП (15 цифр)
        
        Returns:
            True для ОГРНИП
        """
        return len(self._digits) == 15
    
    def __repr__(self) -> str:
        return f"vOGRN('{self._digits}')"


@smart_model
class vMoney(BaseModel):
    """
    Денежная сумма с поддержкой разных валют
    
    Пример:
        >>> money = vMoney(amount=100.50, currency="RUB")
        >>> print(money)  # "100.50 RUB"
    """
    
    amount: float
    """Сумма"""
    
    currency: str = "RUB"
    """Валюта (RUB, USD, EUR и т.д.)"""

    def __init__(self, *args, **kwargs):
        """
        - vMoney(amount=100.5, currency="RUB")
        - vMoney(100.5, "RUB")
        - vMoney(100.5)
        """
        if args and "amount" not in kwargs:
            kwargs["amount"] = args[0]
            if len(args) > 1 and "currency" not in kwargs:
                kwargs["currency"] = args[1]
        super().__init__(**kwargs)
    
    def __str__(self) -> str:
        """Строковое представление"""
        return f"{self.amount:.2f} {self.currency}"
    
    def __repr__(self) -> str:
        return f"vMoney(amount={self.amount}, currency='{self.currency}')"
    
    def __add__(self, other: Union['vMoney', float, int]) -> 'vMoney':
        """Сложение с другой суммой"""
        if isinstance(other, vMoney):
            if other.currency != self.currency:
                raise ValueError(f"Нельзя складывать разные валюты: {self.currency} и {other.currency}")
            return vMoney(amount=self.amount + other.amount, currency=self.currency)
        return vMoney(amount=self.amount + float(other), currency=self.currency)
    
    def __sub__(self, other: Union['vMoney', float, int]) -> 'vMoney':
        """Вычитание"""
        if isinstance(other, vMoney):
            if other.currency != self.currency:
                raise ValueError(f"Нельзя вычитать разные валюты: {self.currency} и {other.currency}")
            return vMoney(amount=self.amount - other.amount, currency=self.currency)
        return vMoney(amount=self.amount - float(other), currency=self.currency)
    
    def __mul__(self, other: Union[float, int]) -> 'vMoney':
        """Умножение на число"""
        return vMoney(amount=self.amount * float(other), currency=self.currency)
    
    def __truediv__(self, other: Union[float, int]) -> 'vMoney':
        """Деление на число"""
        return vMoney(amount=self.amount / float(other), currency=self.currency)
    
    def to_dict(self, clear_meta: bool = True) -> dict:
        """Преобразует в словарь"""
        return {
            'amount': self.amount,
            'currency': self.currency
        }


class vPercent(float):
    """
    Процентное значение
    
    Пример:
        >>> p = vPercent(15.5)
        >>> print(p)  # "15.5%"
        >>> print(p.of(1000))  # 155.0
    """
    
    def __new__(cls, value: Any) -> 'vPercent':
        """Создает новый экземпляр процента"""
        return super().__new__(cls, float(value))
    
    def __str__(self) -> str:
        """Строковое представление"""
        return f"{self:.1f}%"
    
    def __repr__(self) -> str:
        return f"vPercent({super().__str__()})"
    
    def of(self, value: float) -> float:
        """
        Вычисляет процент от числа
        
        Args:
            value: Число
            
        Returns:
            Процент от числа
        """
        return (self / 100) * value
    
    def add_to(self, value: float) -> float:
        """
        Добавляет процент к числу
        
        Args:
            value: Число
            
        Returns:
            Число с добавленным процентом
        """
        return value * (1 + self / 100)
    
    def subtract_from(self, value: float) -> float:
        """
        Вычитает процент из числа
        
        Args:
            value: Число
            
        Returns:
            Число с вычтенным процентом
        """
        return value * (1 - self / 100)


@smart_model
class vPeriod(BaseModel):
    """
    Временной период (интервал)
    
    Пример:
        >>> period = vPeriod(start="2024-01-01", end="2024-12-31")
        >>> print(period.days)  # 365
    """
    
    start: str
    """Начало периода (строка даты)"""
    
    end: str
    """Конец периода (строка даты)"""
    
    def __post_init__(self):
        """Проверка периода"""
        try:
            from datetime import datetime
            self._start_date = datetime.strptime(self.start, "%Y-%m-%d")
            self._end_date = datetime.strptime(self.end, "%Y-%m-%d")
            
            if self._start_date > self._end_date:
                log.warning(f"Начало периода {self.start} позже конца {self.end}")
        except (ValueError, TypeError) as e:
            log.warning(f"Ошибка парсинга дат периода: {e}")
            self._start_date = None
            self._end_date = None
    
    @property
    def days(self) -> Optional[int]:
        """
        Количество дней в периоде
        
        Returns:
            Количество дней или None
        """
        if self._start_date and self._end_date:
            return (self._end_date - self._start_date).days
        return None
    
    @property
    def months(self) -> Optional[float]:
        """
        Количество месяцев в периоде (приблизительно)
        
        Returns:
            Количество месяцев или None
        """
        if self.days:
            return self.days / 30.44  # Среднее количество дней в месяце
        return None
    
    def contains(self, date: str) -> bool:
        """
        Проверяет, входит ли дата в период
        
        Args:
            date: Дата в формате YYYY-MM-DD
            
        Returns:
            True если дата в периоде
        """
        try:
            from datetime import datetime
            check_date = datetime.strptime(date, "%Y-%m-%d")
            return self._start_date <= check_date <= self._end_date
        except (ValueError, TypeError, AttributeError):
            return False
    
    def __str__(self) -> str:
        return f"{self.start} - {self.end}"


additional_field = lambda x: f"additional_field_{x}"
additional_data = lambda x: f"additional_data{x}"

# Экспорт
__all__ = [
    'vStr',
    'vFlag',
    'GeoPoint',
    'vPhoneNumber',
    'vINN',
    'vKPP',
    'vSNILS',
    'vOGRN',
    'vMoney',
    'vPercent',
    'vPeriod',
    'additional_field',
    'additional_data'
]
