# simpleworkernet/smartdata/core.py
"""SmartData container."""

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
    __slots__ = ('_raw_items', '_model_type', '_cached_models', '_stats', '_metadata_registry')

    def __init__(self, data: Any, target_type: Type[T] = Any):
        smartdata_config = config_manager.get_smartdata_config()
        max_depth = smartdata_config.get('max_depth', 100)

        self._model_type = target_type
        self._cached_models: List[Optional[T]] = []
        self._stats: Dict[str, int] = {}
        self._metadata_registry: Dict[int, MetaData] = {}

        if data is not None:
            log.debug(f"SmartData init: data type={type(data)}, target={target_type}")
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
        else:
            self._raw_items = []
            self._cached_models = []

    def _is_valid_field_name(self, name: str) -> bool:
        return DataProcessor._cache.is_valid_field_name(name)

    def _get_item(self, index: int) -> T:
        if index < 0 or index >= len(self._raw_items):
            raise IndexError(f"Индекс {index} вне диапазона (0..{len(self._raw_items)-1})")

        cached = self._cached_models[index]
        if cached is not None:
            return cached

        raw_item = self._raw_items[index]

        if self._model_type is Any:
            self._cached_models[index] = raw_item
            return raw_item

        try:
            if isinstance(raw_item, self._model_type):
                model = raw_item
            elif isinstance(raw_item, dict):
                meta = raw_item.get(META_KEY)
                clean_data = {k: v for k, v in raw_item.items() if k != META_KEY}
                model = self._model_type(**clean_data)
                if meta is not None:
                    setattr(model, META_KEY, meta)
            else:
                model = self._model_type(raw_item)

            self._cached_models[index] = model
            return model
        except Exception as e:
            log.error(f"Ошибка создания модели для элемента {index}: {e}")
            self._cached_models[index] = raw_item
            return raw_item

    def _ensure_all_processed(self) -> None:
        if self._model_type is Any:
            return
        for i in range(len(self._raw_items)):
            self._get_item(i)

    def _derive(self, raw_items: List[Any]) -> 'SmartData[T]':
        new = self.__class__.__new__(self.__class__)
        new._model_type = self._model_type
        new._raw_items = raw_items
        new._cached_models = [None] * len(raw_items)
        new._stats = self._stats.copy()
        new._metadata_registry = self._metadata_registry
        return new

    def get_metadata(self, item: Any) -> Optional[MetaData]:
        if hasattr(item, META_KEY):
            return getattr(item, META_KEY)
        if isinstance(item, dict) and META_KEY in item:
            return item[META_KEY]
        return None

    def get_item_path(self, item: Any) -> str:
        meta = self.get_metadata(item)
        return meta.get_path_string() if meta else ''

    @classmethod
    def get_cache_path(cls) -> Path:
        return DataProcessor.get_cache_path()

    @classmethod
    def save_cache(cls, force: bool = False) -> bool:
        return DataProcessor.save_cache(force)

    @classmethod
    def load_cache(cls, preload_only: bool = False) -> bool:
        return DataProcessor.load_cache(preload_only)

    @classmethod
    def ensure_cache_saved(cls) -> bool:
        return DataProcessor.ensure_cache_saved()

    @classmethod
    def clear_cache(cls) -> None:
        DataProcessor.clear_cache()

    @classmethod
    def preload_from_models(cls, *model_classes, recursive: bool = True, **kwargs) -> None:
        DataProcessor.preload_from_models(*model_classes, recursive=recursive, **kwargs)

    @classmethod
    def set_cache_max_size(cls, size: int) -> None:
        DataProcessor.set_cache_max_size(size)

    @classmethod
    def get_cache_stats(cls) -> Dict[str, Any]:
        return DataProcessor.get_cache_stats()

    def filter(self, *conditions: Where, join: str = 'AND') -> 'SmartData[T]':
        if join.upper() == 'AND':
            filtered = [
                item for item in self._raw_items
                if all(c.check(item) for c in conditions)
            ]
        else:
            filtered = [
                item for item in self._raw_items
                if any(c.check(item) for c in conditions)
            ]
        return self._derive(filtered)

    def where(self, key: str, value: Any = None, op: Operator = Operator.EQ) -> 'SmartData[T]':
        return self.filter(Where(key, value, op))

    def sort(self, key: Optional[Callable[[Any], Any]] = None, reverse: bool = False,
             key_field: Optional[str] = None) -> 'SmartData[T]':
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
        return self._derive(self._raw_items[:count])

    def skip(self, count: int) -> 'SmartData[T]':
        return self._derive(self._raw_items[count:])

    def map(self, func: Callable[[Any], Any]) -> List[Any]:
        result = []
        for i, raw in enumerate(self._raw_items):
            try:
                result.append(func(raw))
            except (TypeError, AttributeError):
                model = self._get_item(i)
                result.append(func(model))
        return result

    def group_by(self, key_func: Callable[[Any], Any]) -> Dict[Any, 'SmartData[T]']:
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

    def count(self) -> int:
        return len(self._raw_items)

    def first(self) -> Optional[T]:
        if not self._raw_items:
            return None
        return self._get_item(0)

    def last(self) -> Optional[T]:
        if not self._raw_items:
            return None
        return self._get_item(-1)

    def min(self, key_func: Optional[Callable[[T], Any]] = None) -> Optional[T]:
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
        if not self._raw_items:
            return 0.0
        return self.sum(key_func) / len(self._raw_items)

    def get_stats(self) -> Dict[str, Any]:
        return {
            'total_items': len(self._raw_items),
            'models_created': sum(1 for m in self._cached_models if m is not None),
            'target_type': getattr(self._model_type, '__name__', str(self._model_type)),
            'processor_stats': self._stats.copy()
        }

    @staticmethod
    def _dict_to_list(d: dict) -> list:
        keys = sorted(
            [k for k in d.keys() if k != META_KEY],
            key=lambda x: int(x) if isinstance(x, str) and x.isdigit() else x,
        )
        return [d[k] for k in keys if k in d]

    @staticmethod
    def _list_to_dict(lst: list) -> dict:
        return {str(i): v for i, v in enumerate(lst) if v is not None}

    @staticmethod
    def _replace_in_parent(parent: Any, key: Any, new_val: Any) -> Any:
        if parent is None:
            return new_val
        parent[key] = new_val
        return new_val

    @staticmethod
    def _ensure_list(current: Any, parent: Any, parent_key: Any) -> list:
        if isinstance(current, list):
            return current
        if isinstance(current, dict):
            lst = SmartData._dict_to_list(current)
            return SmartData._replace_in_parent(parent, parent_key, lst)
        return SmartData._replace_in_parent(parent, parent_key, [])

    @staticmethod
    def _ensure_dict(current: Any, parent: Any, parent_key: Any) -> dict:
        if isinstance(current, dict):
            return current
        if isinstance(current, list):
            d = SmartData._list_to_dict(current)
            return SmartData._replace_in_parent(parent, parent_key, d)
        return SmartData._replace_in_parent(parent, parent_key, {})

    @staticmethod
    def _insert_value(target: Dict, value: Any, path: List[PathSegment]) -> None:
        if not path:
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

        for i, seg in enumerate(path[:-1]):
            next_seg = path[i + 1]
            want_list = next_seg.type == SegmentType.IDX

            if seg.type == SegmentType.IDX:
                idx = int(seg.key)
                current = SmartData._ensure_list(current, parent, parent_key)
                if parent is None:
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
                    current = target
                if key not in current or current[key] is None:
                    current[key] = [] if want_list else {}
                parent, parent_key, current = current, key, current[key]

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

    def to_list(self) -> List[T]:
        self._ensure_all_processed()
        return [m for m in self._cached_models if m is not None]

    def to_raw_list(self) -> List[Any]:
        return self._raw_items.copy()

    def to_dict(self) -> Dict[str, Any]:
        """
        Восстанавливает структуру по метаданным.

        - нет meta → {'data': items}
        - meta.path только IDX (плоский список) → {'data': items без meta}
        - иначе иерархия; если получились ключи '0','1',... → тоже {'data': ...}
        """
        if not self._raw_items:
            return {}

        def _strip_meta(item: Any) -> Any:
            if isinstance(item, dict):
                return {k: v for k, v in item.items() if k != META_KEY}
            return item

        def _paths_are_index_only() -> bool:
            for item in self._raw_items:
                if not isinstance(item, dict) or META_KEY not in item:
                    return False
                meta = item.get(META_KEY)
                if not meta or not meta.path:
                    return False
                if any(seg.type != SegmentType.IDX for seg in meta.path):
                    return False
            return True

        first_item = self._raw_items[0]
        has_meta = isinstance(first_item, dict) and META_KEY in first_item

        if not has_meta:
            return {'data': self._raw_items}

        if _paths_are_index_only():
            return {'data': [_strip_meta(item) for item in self._raw_items]}

        result: Dict[str, Any] = {}
        for item in self._raw_items:
            if not isinstance(item, dict):
                continue
            meta = item.get(META_KEY)
            data = _strip_meta(item)
            if not meta or not meta.path:
                self._insert_value(result, data, [])
            else:
                self._insert_value(result, data, meta.path)

        if result and all(isinstance(k, str) and k.isdigit() for k in result.keys()):
            keys = sorted(result.keys(), key=int)
            return {'data': [result[k] for k in keys]}

        return result

    def to_file(self, filename: str, format: Optional[str] = None) -> None:
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
            with gzip.open(path, 'rb') as f:
                data = pickle.load(f)
        else:
            raise ValueError(f"Неподдерживаемый формат: {path.suffix}")

        return cls(data, target_type)

    def __len__(self) -> int:
        return len(self._raw_items)

    @overload
    def __getitem__(self, key: int) -> T: ...

    @overload
    def __getitem__(self, key: slice) -> 'SmartData[T]': ...

    @overload
    def __getitem__(self, key: str) -> List[Any]: ...

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
        if name.startswith('_'):
            return super().__getattribute__(name)
        return self[name]

    def __iter__(self) -> Iterator[T]:
        for i in range(len(self._raw_items)):
            yield self._get_item(i)

    def __contains__(self, item: Any) -> bool:
        if isinstance(item, self._model_type):
            self._ensure_all_processed()
            return item in self._cached_models
        return item in self._raw_items

    def __add__(self, other: Union['SmartData[T]', List[T]]) -> 'SmartData[T]':
        if isinstance(other, SmartData):
            return self._derive(self._raw_items + other._raw_items)
        raise TypeError(f"Нельзя сложить SmartData с {type(other)}")

    def __iadd__(self, other: Union['SmartData[T]', List[T]]) -> 'SmartData[T]':
        if isinstance(other, SmartData):
            self._raw_items.extend(other._raw_items)
            self._cached_models.extend([None] * len(other._raw_items))
        else:
            raise TypeError("Можно добавлять только SmartData")
        return self

    def __bool__(self) -> bool:
        return bool(self._raw_items)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, SmartData):
            return False
        return self._raw_items == other._raw_items

    def __repr__(self) -> str:
        return (
            f"SmartData[{self._model_type}]("
            f"count={len(self._raw_items)}, "
            f"models_created={sum(1 for m in self._cached_models if m is not None)})"
        )
