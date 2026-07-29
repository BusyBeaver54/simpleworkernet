# simpleworkernet/smartdata/core.py
"""
Основной класс SmartData - контейнер для данных от API с ленивым созданием моделей.

Этот модуль предоставляет класс SmartData, который является центральным элементом
для работы с данными, полученными от API. Он хранит сырые данные после структурных
преобразований и создаёт модели (экземпляры указанного класса) только при
непосредственном обращении к элементу (по индексу или при итерации).

Основные возможности:
- Хранение сырых данных (словарей, списков, примитивов) после структурной нормализации.
- Ленивое создание моделей: модели создаются только при первом доступе к элементу.
- Все операции фильтрации, сортировки, группировки и агрегации работают на сырых данных,
  что обеспечивает высокую производительность при работе с большими объёмами.
- Восстановление исходной структуры данных по метаданным (без создания моделей)
  для сериализации в JSON/Pickle/Gzip.
- Поддержка точечной нотации для доступа к полям всех элементов (возвращает список значений).
- Полная совместимость со статической типизацией и автодополнением в IDE.
"""

import json
import pickle
import gzip
from typing import (
    TypeVar, Generic, List, Dict, Tuple, Any, Union, Optional, Callable, Iterator,
    overload, Type
)
from pathlib import Path

from ..core.logger import log
from ..core.config import config_manager

from .metadata import MetaData, META_KEY, PathSegment, SegmentType
from .processor import DataProcessor, ProcessingResult

from ..models.operators import Operator, Where


T = TypeVar('T')

class SmartData(Generic[T]):
    """
    Контейнер для данных от API с ленивым созданием моделей.

    Generic-класс, параметризуемый типом модели (T). Позволяет IDE
    распознавать атрибуты модели при обращении через точечную нотацию.

    Атрибуты:
        _raw_items: List[Any] — список сырых элементов после структурных преобразований.
        _model_type: Type[T] — целевой класс модели.
        _cached_models: List[Optional[T]] — кэш уже созданных моделей (по индексам).
        _stats: Dict[str, int] — статистика обработки.
        _metadata_registry: Dict[int, MetaData] — регистр метаданных (не используется в текущей реализации).
    """

    __slots__ = ('_raw_items', '_model_type', '_cached_models', '_stats', '_metadata_registry')

    def __init__(self, data: Any, target_type: Type[T] = Any):
        """
        Инициализирует SmartData, выполняя структурные преобразования данных,
        но не создавая модели (кроме случаев, когда target_type == Any).

        Процесс:
        1. Вызывает DataProcessor.process с cast_to_models=False.
        2. Сохраняет структурированные сырые элементы в _raw_items.
        3. Инициализирует кэш моделей пустыми слотами.

        Args:
            data: Входные данные от API (словарь, список, примитив).
            target_type: Целевой тип модели для элементов. Если Any — модели не создаются.
        """
        smartdata_config = config_manager.get_smartdata_config()
        max_depth = smartdata_config.get('max_depth', 100)

        self._model_type = target_type
        self._cached_models: List[Optional[T]] = []
        self._stats: Dict[str, int] = {}
        self._metadata_registry: Dict[int, MetaData] = {}

        if data is not None:
            log.debug(f"SmartData инициализация (ленивая): data type={type(data)}, target={target_type}")

            processor = DataProcessor(max_depth=max_depth)
            result: ProcessingResult = processor.process(
                data=data,
                target_type=target_type,
                cache_func=self._is_valid_field_name,
                cast_to_models=False
            )

            self._raw_items = result.items
            self._stats = result.stats
            self._cached_models = [None] * len(self._raw_items)

            log.debug(f"SmartData инициализирован: {len(self._raw_items)} элементов (модели не созданы)")
        else:
            self._raw_items = []
            self._cached_models = []

    def _is_valid_field_name(self, name: str) -> bool:
        """Проверяет валидность имени поля с использованием глобального кэша."""
        return DataProcessor._cache.is_valid_field_name(name)

    # ------------------------------------------------------------------------
    # Внутренние методы для управления ленивой загрузкой моделей
    # ------------------------------------------------------------------------

    def _get_item(self, index: int) -> T:
        """
        Возвращает элемент по индексу, создавая модель при первом обращении.
        Если модель уже создана, возвращает её из кэша.

        Особое внимание уделяется метаданным: если сырой элемент — словарь,
        содержащий ключ META_KEY, то метаданные извлекаются и устанавливаются
        в создаваемую модель, чтобы CollapsedField и другие механизмы
        могли корректно работать.

        Args:
            index: Индекс элемента.

        Returns:
            Модель (или сырой элемент, если target_type == Any).

        Raises:
            IndexError: Если индекс вне допустимого диапазона.
        """
        if index < 0 or index >= len(self._raw_items):
            raise IndexError(f"Индекс {index} вне диапазона (0..{len(self._raw_items)-1})")

        cached = self._cached_models[index]
        if cached is not None:
            return cached

        raw_item = self._raw_items[index]

        # Если целевой тип Any, возвращаем сырой элемент без создания модели
        if self._model_type is Any:
            self._cached_models[index] = raw_item
            return raw_item

        try:
            # Если элемент уже является экземпляром нужного типа, просто сохраняем
            if isinstance(raw_item, self._model_type):
                model = raw_item
            elif isinstance(raw_item, dict):
                # Извлекаем метаданные из словаря, чтобы передать их в модель отдельно
                meta = raw_item.get(META_KEY)
                # Создаём копию словаря без ключа META_KEY, чтобы не передавать его как поле модели
                clean_data = {k: v for k, v in raw_item.items() if k != META_KEY}
                model = self._model_type(**clean_data)
                if meta is not None:
                    setattr(model, META_KEY, meta)
            else:
                # Для примитивов или других типов пробуем создать модель с одним аргументом
                model = self._model_type(raw_item)

            self._cached_models[index] = model
            return model
        except Exception as e:
            log.error(f"Ошибка создания модели для элемента {index}: {e}")
            # В случае ошибки сохраняем сырые данные как есть
            self._cached_models[index] = raw_item
            return raw_item

    def _ensure_all_processed(self) -> None:
        """Принудительно создаёт модели для всех элементов (используется для статистики и сериализации)."""
        if self._model_type is Any:
            return
        for i in range(len(self._raw_items)):
            self._get_item(i)

    def _derive(self, raw_items: List[Any]) -> 'SmartData[T]':
        """
        Создаёт новый экземпляр SmartData с теми же настройками, но с новым списком сырых данных.
        Используется в методах фильтрации, сортировки и т.д.

        Args:
            raw_items: Новый список сырых элементов.

        Returns:
            Новый объект SmartData.
        """
        new = self.__class__.__new__(self.__class__)
        new._model_type = self._model_type
        new._raw_items = raw_items
        new._cached_models = [None] * len(raw_items)
        new._stats = self._stats.copy()
        new._metadata_registry = self._metadata_registry
        return new

    # ------------------------------------------------------------------------
    # Методы работы с метаданными
    # ------------------------------------------------------------------------

    def get_metadata(self, item: Any) -> Optional[MetaData]:
        """
        Возвращает метаданные для элемента (если они есть).

        Args:
            item: Элемент (модель, словарь или примитив).

        Returns:
            Объект MetaData или None, если метаданные отсутствуют.
        """
        if hasattr(item, META_KEY):
            return getattr(item, META_KEY)
        if isinstance(item, dict) and META_KEY in item:
            return item[META_KEY]
        return None

    def get_item_path(self, item: Any) -> str:
        """
        Возвращает строковое представление пути к элементу в исходной структуре.

        Args:
            item: Элемент.

        Returns:
            Строка пути (например, "fld:data/idx:0/fld:name") или пустая строка.
        """
        meta = self.get_metadata(item)
        return meta.get_path_string() if meta else ''

    # ------------------------------------------------------------------------
    # Методы для работы с глобальным кэшем (прокси к DataProcessor)
    # ------------------------------------------------------------------------

    @classmethod
    def get_cache_path(cls) -> Path:
        """Возвращает путь к файлу глобального кэша."""
        return DataProcessor.get_cache_path()

    @classmethod
    def save_cache(cls, force: bool = False) -> bool:
        """Сохраняет глобальный кэш в файл."""
        return DataProcessor.save_cache(force)

    @classmethod
    def load_cache(cls, preload_only: bool = False) -> bool:
        """Загружает глобальный кэш из файла."""
        return DataProcessor.load_cache(preload_only)

    @classmethod
    def ensure_cache_saved(cls) -> bool:
        """Гарантирует сохранение глобального кэша (если были изменения)."""
        return DataProcessor.ensure_cache_saved()

    @classmethod
    def clear_cache(cls) -> None:
        """Полностью очищает глобальный кэш."""
        DataProcessor.clear_cache()

    @classmethod
    def preload_from_models(cls, *model_classes, recursive: bool = True, **kwargs) -> None:
        """Предзагружает поля моделей в глобальный кэш."""
        DataProcessor.preload_from_models(*model_classes, recursive=recursive, **kwargs)

    @classmethod
    def set_cache_max_size(cls, size: int) -> None:
        """Устанавливает максимальный размер глобального кэша."""
        DataProcessor.set_cache_max_size(size)

    @classmethod
    def get_cache_stats(cls) -> Dict[str, Any]:
        """Возвращает статистику использования глобального кэша."""
        return DataProcessor.get_cache_stats()

    # ------------------------------------------------------------------------
    # Fluent-интерфейс (работают на сырых данных)
    # ------------------------------------------------------------------------

    def filter(self, *conditions: Where, join: str = 'AND') -> 'SmartData[T]':
        """
        Фильтрует элементы по условиям Where (работает на сырых словарях).

        Args:
            *conditions: Условия фильтрации (объекты Where).
            join: Способ объединения условий ('AND' или 'OR').

        Returns:
            Новый SmartData с отфильтрованными данными.

        Пример:
            data.filter(Where('state_id', 2, Operator.EQ), Where('balance', 0, Operator.GT))
        """

        if join.upper() == 'AND':
            filtered = [
                item for item in self._raw_items
                if all(c.check(item) for c in conditions)
            ]
        else:  # OR
            filtered = [
                item for item in self._raw_items
                if any(c.check(item) for c in conditions)
            ]
        return self._derive(filtered)

    def where(self, key: str, value: Any = None, op: Operator = Operator.EQ) -> 'SmartData[T]':
        """
        Упрощённый фильтр по одному условию.

        Args:
            key: Имя поля.
            value: Значение для сравнения.
            op: Оператор сравнения (по умолчанию ==).

        Returns:
            Новый SmartData с отфильтрованными данными.
        """
        return self.filter(Where(key, value, op))

    def sort(self, key: Optional[Callable[[Any], Any]] = None, reverse: bool = False,
             key_field: Optional[str] = None) -> 'SmartData[T]':
        """
        Сортирует элементы.

        Args:
            key: Функция, возвращающая ключ для сортировки (принимает сырой элемент).
            reverse: Сортировать по убыванию.
            key_field: Имя поля для сортировки (если указано, параметр key игнорируется).

        Returns:
            Новый SmartData с отсортированными данными.

        Пример:
            data.sort(key_field='full_name')
            data.sort(key=lambda x: x.get('balance', 0), reverse=True)
        """
        if key_field is not None:
            def sort_key(item):
                return item.get(key_field) if isinstance(item, dict) else getattr(item, key_field, None)
            actual_key = sort_key
        else:
            actual_key = key

        if actual_key is None:
            sorted_items = sorted(self._raw_items, reverse=reverse)
        else:
            sorted_items = sorted(self._raw_items, key=actual_key, reverse=reverse)
        return self._derive(sorted_items)

    def limit(self, count: int) -> 'SmartData[T]':
        """Ограничивает количество элементов первыми `count`."""
        return self._derive(self._raw_items[:count])

    def skip(self, count: int) -> 'SmartData[T]':
        """Пропускает первые `count` элементов и возвращает остальные."""
        return self._derive(self._raw_items[count:])

    def map(self, func: Callable[[Any], Any]) -> List[Any]:
        """
        Применяет функцию к каждому элементу и возвращает список результатов.
        Если функция ожидает модель, то для сырых элементов она будет создана.

        Args:
            func: Функция, принимающая сырой элемент или модель (если нужна).

        Returns:
            Список результатов применения функции.

        Пример:
            data.map(lambda x: x.get('id'))  # работает на сырых словарях
            data.map(lambda x: x.full_name)  # требует модель, создаст её
        """
        result = []
        for i, raw in enumerate(self._raw_items):
            try:
                result.append(func(raw))
            except (TypeError, AttributeError):
                model = self._get_item(i)
                result.append(func(model))
        return result

    def group_by(self, key_func: Callable[[Any], Any]) -> Dict[Any, 'SmartData[T]']:
        """
        Группирует элементы по ключу, возвращая словарь {ключ: SmartData}.

        Args:
            key_func: Функция, возвращающая ключ группировки (принимает сырой элемент или модель).

        Returns:
            Словарь, где значения — новые SmartData с соответствующими элементами.

        Пример:
            groups = data.group_by(lambda x: x['state_id'])
        """
        groups = {}
        for i, raw in enumerate(self._raw_items):
            try:
                key = key_func(raw)
            except (TypeError, AttributeError):
                model = self._get_item(i)
                key = key_func(model)
            if key not in groups:
                groups[key] = self._derive([])
            groups[key]._raw_items.append(raw)
        return groups

    def unique(self, key_func: Optional[Callable[[Any], Any]] = None) -> 'SmartData[T]':
        """
        Возвращает уникальные элементы. Если key_func задана, уникальность
        определяется по возвращаемому значению.

        Args:
            key_func: Функция, возвращающая ключ уникальности (опционально).

        Returns:
            SmartData с уникальными элементами.
        """
        seen = set()
        unique_items = []

        if key_func is None:
            for item in self._raw_items:
                if item not in seen:
                    seen.add(item)
                    unique_items.append(item)
        else:
            for i, item in enumerate(self._raw_items):
                try:
                    key = key_func(item)
                except (TypeError, AttributeError):
                    model = self._get_item(i)
                    key = key_func(model)
                if key not in seen:
                    seen.add(key)
                    unique_items.append(item)

        return self._derive(unique_items)

    # ------------------------------------------------------------------------
    # Статистические методы
    # ------------------------------------------------------------------------

    def count(self) -> int:
        """Возвращает общее количество элементов."""
        return len(self._raw_items)

    def first(self) -> Optional[T]:
        """Возвращает первый элемент (создаёт модель)."""
        if not self._raw_items:
            return None
        return self._get_item(0)

    def last(self) -> Optional[T]:
        """Возвращает последний элемент (создаёт модель)."""
        if not self._raw_items:
            return None
        return self._get_item(-1)

    def min(self, key_func: Optional[Callable[[T], Any]] = None) -> Optional[T]:
        """
        Возвращает элемент с минимальным значением по ключу.
        Если key_func не задана, сравниваются сами элементы (должны быть сравнимыми).

        Args:
            key_func: Функция, возвращающая значение для сравнения (может принимать модель).

        Returns:
            Элемент с минимальным значением или None, если список пуст.
        """
        if not self._raw_items:
            return None

        if key_func is None:
            try:
                raw_min = min(self._raw_items)
                idx = self._raw_items.index(raw_min)
                return self._get_item(idx)
            except TypeError:
                self._ensure_all_processed()
                models = [m for m in self._cached_models if m is not None]
                if not models:
                    return None
                return min(models)

        best_idx = 0
        best_value = None
        for i, raw in enumerate(self._raw_items):
            try:
                val = key_func(raw)
            except (TypeError, AttributeError):
                model = self._get_item(i)
                val = key_func(model)
            if best_value is None or val < best_value:
                best_value = val
                best_idx = i
        return self._get_item(best_idx)

    def max(self, key_func: Optional[Callable[[T], Any]] = None) -> Optional[T]:
        """
        Возвращает элемент с максимальным значением по ключу.
        Аналогично методу min.
        """
        if not self._raw_items:
            return None

        if key_func is None:
            try:
                raw_max = max(self._raw_items)
                idx = self._raw_items.index(raw_max)
                return self._get_item(idx)
            except TypeError:
                self._ensure_all_processed()
                models = [m for m in self._cached_models if m is not None]
                if not models:
                    return None
                return max(models)

        best_idx = 0
        best_value = None
        for i, raw in enumerate(self._raw_items):
            try:
                val = key_func(raw)
            except (TypeError, AttributeError):
                model = self._get_item(i)
                val = key_func(model)
            if best_value is None or val > best_value:
                best_value = val
                best_idx = i
        return self._get_item(best_idx)

    def sum(self, key_func: Callable[[T], Union[int, float]]) -> Union[int, float]:
        """
        Вычисляет сумму значений, возвращаемых key_func для всех элементов.

        Args:
            key_func: Функция, возвращающая числовое значение (может принимать модель).

        Returns:
            Сумма.
        """
        total = 0
        for i, raw in enumerate(self._raw_items):
            try:
                val = key_func(raw)
            except (TypeError, AttributeError):
                model = self._get_item(i)
                val = key_func(model)
            total += val
        return total

    def avg(self, key_func: Callable[[T], Union[int, float]]) -> float:
        """
        Вычисляет среднее арифметическое значений key_func.

        Args:
            key_func: Функция, возвращающая числовое значение.

        Returns:
            Среднее значение (0.0, если список пуст).
        """
        if not self._raw_items:
            return 0.0
        return self.sum(key_func) / len(self._raw_items)

    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику по данным (количество, созданные модели, целевой тип и т.д.)."""
        return {
            'total_items': len(self._raw_items),
            'models_created': sum(1 for m in self._cached_models if m is not None),
            'target_type': getattr(self._model_type, '__name__', str(self._model_type)),
            'processor_stats': self._stats.copy()
        }

    # ------------------------------------------------------------------------
    # Восстановление структуры по метаданным (без создания моделей)
    # ------------------------------------------------------------------------

    @staticmethod
    def _dict_to_list(d: dict) -> list:
        """Словарь с (числовыми) ключами → список по возрастанию ключей."""
        keys = sorted(
            [k for k in d.keys() if k != META_KEY],
            key=lambda x: int(x) if isinstance(x, str) and x.isdigit() else x,
        )
        return [d[k] for k in keys if k in d]

    @staticmethod
    def _list_to_dict(lst: list) -> dict:
        """Список → словарь со строковыми индексами (пропуская None)."""
        return {str(i): v for i, v in enumerate(lst) if v is not None}

    @staticmethod
    def _replace_in_parent(parent: Any, key: Any, new_val: Any) -> Any:
        """
        Подменяет значение в родителе и возвращает new_val.
        parent=None означает корень (target) — тип корня не меняем,
        содержимое копируем в существующий контейнер, если возможно.
        """
        if parent is None:
            # Корень всегда dict (сигнатура target: Dict).
            # Если нужен list — храним как dict с индексными ключами нельзя
            # для list-операций; поэтому при необходимости list на корне
            # возвращаем new_val без привязки (вызывающий не использует корень как list
            # напрямую через target, только через current).
            # На практике корень — dict полей; IDX на корне редок.
            return new_val
        parent[key] = new_val
        return new_val

    @staticmethod
    def _ensure_list(current: Any, parent: Any, parent_key: Any) -> list:
        """Гарантирует, что current — list; при необходимости конвертирует dict."""
        if isinstance(current, list):
            return current
        if isinstance(current, dict):
            lst = SmartData._dict_to_list(current)
            return SmartData._replace_in_parent(parent, parent_key, lst)
        return SmartData._replace_in_parent(parent, parent_key, [])

    @staticmethod
    def _ensure_dict(current: Any, parent: Any, parent_key: Any) -> dict:
        """Гарантирует, что current — dict; при необходимости конвертирует list."""
        if isinstance(current, dict):
            return current
        if isinstance(current, list):
            d = SmartData._list_to_dict(current)
            return SmartData._replace_in_parent(parent, parent_key, d)
        return SmartData._replace_in_parent(parent, parent_key, {})

    @staticmethod
    def _insert_value(target: Dict, value: Any, path: List[PathSegment]) -> None:
        """
        Вставляет значение value в структуру target по пути path.
        Если по пути уже есть значение, они объединяются в список (сохраняя порядок).

        При смене типа контейнера (dict ↔ list) подмена идёт через родителя:
        in-place ``clear()`` + ``extend``/``update`` невозможны — тип объекта
        после ``clear()`` не меняется.

        Args:
            target: Словарь-приёмник.
            value: Вставляемое значение (может быть словарём, списком, примитивом).
            path: Список сегментов пути (PathSegment).
        """
        if not path:
            # Пустой путь — сливаем с корнем (глубокое слияние словарей)
            if isinstance(value, dict):
                for k, v in value.items():
                    if k in target:
                        if not isinstance(target[k], list):
                            target[k] = [target[k]]
                        target[k].append(v)
                    else:
                        target[k] = v
            else:
                target['_value'] = value
            return

        current: Any = target
        parent: Any = None
        parent_key: Any = None

        # Идём по пути, создавая структуру (все сегменты, кроме последнего)
        for i, seg in enumerate(path[:-1]):
            next_seg = path[i + 1]
            want_list = next_seg.type == SegmentType.IDX

            if seg.type == SegmentType.IDX:
                idx = int(seg.key)
                current = SmartData._ensure_list(current, parent, parent_key)
                if parent is None:
                    # IDX на корне: target — dict, нельзя сделать list.
                    # Используем строковые ключи как индексы внутри target.
                    key = str(idx)
                    if key not in target or target[key] is None:
                        target[key] = [] if want_list else {}
                    parent, parent_key, current = target, key, target[key]
                    continue

                while len(current) <= idx:
                    current.append(None)
                if current[idx] is None:
                    current[idx] = [] if want_list else {}
                parent, parent_key, current = current, idx, current[idx]
            else:
                key = seg.key
                current = SmartData._ensure_dict(current, parent, parent_key)
                if parent is None:
                    current = target  # корень
                if key not in current or current[key] is None:
                    current[key] = [] if want_list else {}
                parent, parent_key, current = current, key, current[key]

        # Последний сегмент
        last_seg = path[-1]
        if last_seg.type == SegmentType.IDX:
            idx = int(last_seg.key)
            current = SmartData._ensure_list(current, parent, parent_key)
            if parent is None:
                key = str(idx)
                if key in target and target[key] is not None:
                    if not isinstance(target[key], list):
                        target[key] = [target[key]]
                    target[key].append(value)
                else:
                    target[key] = value
                return

            while len(current) <= idx:
                current.append(None)
            if current[idx] is not None:
                if not isinstance(current[idx], list):
                    current[idx] = [current[idx]]
                current[idx].append(value)
            else:
                current[idx] = value
        else:
            key = last_seg.key
            current = SmartData._ensure_dict(current, parent, parent_key)
            if parent is None:
                current = target
            if key in current:
                if not isinstance(current[key], list):
                    current[key] = [current[key]]
                current[key].append(value)
            else:
                current[key] = value

    # ------------------------------------------------------------------------
    # Сериализация и доступ к данным
    # ------------------------------------------------------------------------

    def to_list(self) -> List[T]:
        """
        Возвращает список всех элементов в виде моделей.
        При первом вызове создаёт все модели (лениво) и кэширует их.
        Этот метод удобен для извлечения данных, когда нужны именно модели,
        например, для доступа к атрибутам через точечную нотацию.

        Returns:
            Список моделей (экземпляров типа T).
        """
        self._ensure_all_processed()
        return [m for m in self._cached_models if m is not None]

    def to_raw_list(self) -> List[Any]:
        """
        Возвращает список сырых элементов (без создания моделей).
        Полезно для быстрого доступа к исходным данным без накладных расходов
        на создание моделей.

        Returns:
            Список сырых элементов (словари, списки, примитивы).
        """
        return self._raw_items.copy()

    def to_dict(self) -> Dict[str, Any]:
        """
        Восстанавливает исходную структуру данных, используя метаданные из сырых элементов.

        Если у элементов есть метаданные (ключ __meta__ с путем), то функция
        собирает все элементы в единый словарь, вкладывая их в соответствии с путями.
        Если метаданных нет, возвращает словарь {'data': self._raw_items}.

        Этот метод не создаёт модели и работает только с сырыми словарями.
        Он полезен для сериализации данных в исходном (иерархическом) формате.

        Returns:
            Словарь с восстановленной структурой.
        """
        if not self._raw_items:
            return {}

        first_item = self._raw_items[0]
        if isinstance(first_item, dict) and META_KEY in first_item:
            # Есть метаданные — строим структуру
            result = {}
            for item in self._raw_items:
                if not isinstance(item, dict):
                    continue
                meta = item.get(META_KEY)
                data = {k: v for k, v in item.items() if k != META_KEY}
                if not meta or not meta.path:
                    self._insert_value(result, data, [])
                else:
                    self._insert_value(result, data, meta.path)
            return result
        else:
            # Нет метаданных — возвращаем как есть
            return {'data': self._raw_items}

    def to_file(self, filename: str, format: Optional[str] = None) -> None:
        """
        Сохраняет данные в файл, восстанавливая структуру по метаданным (без создания моделей).

        Args:
            filename: Имя файла (путь).
            format: Формат ('json', 'pkl', 'gz'). Если не указан, определяется по расширению.
        """
        data = self.to_dict()
        path = Path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)

        if format is None:
            format = path.suffix.lstrip('.') or 'json'

        if format == 'json':
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        elif format == 'pkl':
            with open(path, 'wb') as f:
                pickle.dump(data, f)
        elif format == 'gz':
            with gzip.open(path, 'wb') as f:
                pickle.dump(data, f)
        else:
            raise ValueError(f"Неподдерживаемый формат: {format}")

        log.info(f"Данные с восстановленной структурой сохранены в {path}")

    def save_raw(self, filename: str, format: Optional[str] = None) -> None:
        """
        Сохраняет сырые данные (без восстановления структуры) — быстро.

        Этот метод сохраняет список _raw_items как есть, без попытки
        восстановить иерархию. Полезно для быстрого сохранения промежуточных
        результатов или для отладки.

        Args:
            filename: Имя файла.
            format: Формат ('json', 'pkl', 'gz').
        """
        data = self._raw_items
        path = Path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)

        if format is None:
            format = path.suffix.lstrip('.') or 'json'

        if format == 'json':
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        elif format == 'pkl':
            with open(path, 'wb') as f:
                pickle.dump(data, f)
        elif format == 'gz':
            with gzip.open(path, 'wb') as f:
                pickle.dump(data, f)
        else:
            raise ValueError(f"Неподдерживаемый формат: {format}")

        log.info(f"Сырые данные сохранены в {path}")

    @classmethod
    def from_file(cls, filename: str, target_type: Type[T] = Any) -> 'SmartData[T]':
        """
        Загружает данные из файла и создаёт SmartData с указанным типом.

        Файл может содержать как восстановленную структуру (словарь), так и
        список сырых элементов. Данные передаются в конструктор, который
        выполнит структурные преобразования (без создания моделей).

        Args:
            filename: Имя файла.
            target_type: Целевой тип модели.

        Returns:
            Новый экземпляр SmartData.
        """
        path = Path(filename)
        if not path.exists():
            raise FileNotFoundError(f"Файл не найден: {filename}")

        if path.suffix == '.json':
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        elif path.suffix == '.pkl':
            with open(path, 'rb') as f:
                data = pickle.load(f)
        elif path.suffix == '.gz':
            with gzip.open(path, 'wb') as f:
                data = pickle.load(f)
        else:
            raise ValueError(f"Неподдерживаемый формат: {path.suffix}")

        return cls(data, target_type)

    # ------------------------------------------------------------------------
    # Магические методы
    # ------------------------------------------------------------------------

    def __len__(self) -> int:
        """Возвращает количество элементов."""
        return len(self._raw_items)

    @overload
    def __getitem__(self, key: int) -> T:
        """Доступ к элементу по индексу (создаёт модель)."""
        ...

    @overload
    def __getitem__(self, key: slice) -> 'SmartData[T]':
        """Срез возвращает новый SmartData с подмножеством сырых данных."""
        ...

    @overload
    def __getitem__(self, key: str) -> List[Any]:
        """Доступ к полю коллекции: возвращает список значений для всех элементов."""
        ...

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._get_item(key)
        if isinstance(key, slice):
            return self._derive(self._raw_items[key])
        if isinstance(key, str):
            result = []
            for i in range(len(self._raw_items)):
                item = self._get_item(i)
                if hasattr(item, key):
                    result.append(getattr(item, key))
                elif isinstance(item, dict):
                    result.append(item.get(key))
                else:
                    result.append(None)
            return result
        raise TypeError(f"Неподдерживаемый тип ключа: {type(key).__name__}")

    def __getattr__(self, name: str) -> List[Any]:
        """
        Позволяет обращаться к полям коллекции через точечную нотацию.
        Возвращает список значений этого поля для всех элементов.
        """
        if name.startswith('_'):
            return super().__getattribute__(name)
        return self[name]

    def __iter__(self) -> Iterator[T]:
        """Итератор, создающий модели по мере прохождения."""
        for i in range(len(self._raw_items)):
            yield self._get_item(i)

    def __contains__(self, item: Any) -> bool:
        """Проверяет наличие элемента (сравнивает с сырыми данными или моделями)."""
        if isinstance(item, self._model_type):
            self._ensure_all_processed()
            return item in self._cached_models
        return item in self._raw_items

    def __add__(self, other: Union['SmartData[T]', List[T]]) -> 'SmartData[T]':
        """Объединяет два SmartData (или список с сырыми данными) в новый SmartData."""
        if isinstance(other, SmartData):
            combined = self._raw_items + other._raw_items
            return self._derive(combined)
        raise TypeError(f"Нельзя сложить SmartData с {type(other)}")

    def __iadd__(self, other: Union['SmartData[T]', List[T]]) -> 'SmartData[T]':
        """Добавляет элементы из другого SmartData в текущий (изменяет текущий объект)."""
        if isinstance(other, SmartData):
            self._raw_items.extend(other._raw_items)
            self._cached_models.extend([None] * len(other._raw_items))
        else:
            raise TypeError("Можно добавлять только SmartData")
        return self

    def __bool__(self) -> bool:
        """Возвращает True, если есть хотя бы один элемент."""
        return bool(self._raw_items)

    def __eq__(self, other: Any) -> bool:
        """Сравнивает два SmartData по сырым данным."""
        if not isinstance(other, SmartData):
            return False
        return self._raw_items == other._raw_items

    def __repr__(self) -> str:
        """Строковое представление объекта."""
        return f"SmartData[{self._model_type}](count={len(self._raw_items)}, models_created={sum(1 for m in self._cached_models if m is not None)})"

