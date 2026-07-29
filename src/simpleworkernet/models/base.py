# simpleworkernet/models/base.py
"""
Базовые модели данных с поддержкой метаданных и кастинга типов.
"""
import json
import pickle
import gzip
from pathlib import Path
from typing import Any, Dict, List, Optional, get_type_hints, dataclass_transform
from dataclasses import dataclass, is_dataclass

from ..core.logger import log
from ..smartdata.metadata import META_KEY, MetaData, SegmentType, PathSegment
from ..smartdata import helpers


class CollapsedField:
    """
    Дескриптор для доступа к схлопнутым ключам из метаданных.
    
    Args:
        type_filter: Тип сегмента для поиска (SegmentType)
        pos: Позиция с конца (-1 - последний)
        default: Значение по умолчанию
    """
    
    __slots__ = ('type_filter', 'pos', 'default', 'name')
    
    def __init__(self, type_filter: Optional[SegmentType] = None, 
                 pos: int = -1, default: Any = None):
        self.type_filter = type_filter
        self.pos = pos
        self.default = default
        self.name = None
    
    def __set_name__(self, owner, name):
        self.name = name
    
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        
        meta = getattr(obj, META_KEY, None)
        if not meta or not meta.path:
            return self.default
        
        segments = meta.path
        if self.type_filter:
            segments = [s for s in segments if s.type == self.type_filter]
        
        if not segments:
            return self.default
        
        if self.pos == -1:
            return segments[-1].key
        if 0 <= self.pos < len(segments):
            return segments[self.pos].key
        return self.default


@dataclass_transform()
def smart_model(cls=None, **kwargs):
    """Декоратор для создания dataclass модели."""
    params = {"init": False, "repr": False}
    params.update(kwargs)
    if cls is None:
        return lambda c: dataclass(c, **params)
    return dataclass(cls, **params)


class BaseModel:
    """
    Базовый класс для всех моделей данных.
    
    Метаданные хранятся в поле __meta__ (META_KEY).
    """
    
    __slots__ = ('__dict__',)

    _annotations_cache = {}
    
    def __init__(self, *args, **kwargs):
        # log.debug(f"Создание {self.__class__.__name__}")
        
        self._meta = kwargs.pop(META_KEY, None)
        hints = self._get_annotations()
        
        for name, value in kwargs.items():
            if name in hints:
                try:
                    setattr(self, name, self._deep_cast(hints[name], value, name))
                except Exception:
                    setattr(self, name, value)
            else:
                setattr(self, name, value)
    
    # ------------------------------------------------------------------------
    # Работа с аннотациями
    # ------------------------------------------------------------------------
    
    def _get_annotations(self) -> Dict[str, Any]:
        """Возвращает аннотации полей модели."""
        cls = self.__class__
        if cls not in self._annotations_cache:
            base_hints = get_type_hints(cls)
            if META_KEY not in base_hints:
                base_hints[META_KEY] = Optional[MetaData]
            self._annotations_cache[cls] = base_hints
        return self._annotations_cache[cls]
    
    # ------------------------------------------------------------------------
    # Глубокий кастинг
    # ------------------------------------------------------------------------
    
    def _deep_cast(self, target_t: Any, val: Any, field_name: str = None) -> Any:
        """
        Глубокое рекурсивное приведение значения к целевому типу.

        1. Обработка Union/Optional
        2. Обработка списков с учётом вложенности
        3. Обработка моделей и датаклассов
        4. Базовое приведение
        """
        
        if target_t is Any or target_t is type(None) or val is None:
            return val
        
        # 1. Обработка Union (Optional)
        if helpers.is_union_type(target_t):
            return self._process_union(target_t, val, field_name)
        
        # 2. Обработка списков
        if helpers.is_list_type(target_t):
            return self._process_list(target_t, val, field_name)
        
        # 3. Обработка классов (модели и датаклассы)
        if isinstance(target_t, type):
            return self._process_class(target_t, val, field_name)
        
        # 4. Базовое приведение
        return self._process_primitive(target_t, val)
    
    def _process_union(self, target_t: Any, val: Any, field_name: str) -> Any:
        """Обрабатывает Union типы."""
        for t in helpers.get_union_types(target_t):
            try:
                return self._deep_cast(t, val, field_name)
            except Exception:
                continue
        if helpers.is_optional_type(target_t):
            return None
        return val
    
    def _process_list(self, target_t: Any, val: Any, field_name: str) -> Any:
        """Обрабатывает списки."""

        if isinstance(val, list) and len(val) == 0: return val

        inner_t = helpers.get_list_inner_type(target_t)
        
        if not isinstance(val, list):
            return [self._deep_cast(inner_t, val, field_name)]

        # Если внутри списка лежат структуры (словари/списки)
        if len(val) > 0 and isinstance(val[0], (dict, list)):
            return self._process_nested_list(inner_t, val, field_name)
        
        # Проверка на возможность создания объекта из всего списка
        result = self._try_create_from_whole_list(inner_t, val, field_name)
        if result is not None:
            return result
        
        # Стандартная обработка
        return self._process_flat_list(inner_t, val, field_name)
    
    def _process_nested_list(self, inner_t: Any, val: List, field_name: str) -> List:
        """Обрабатывает вложенные списки."""
        result = []
        for i, x in enumerate(val):
            item_field = f"{field_name}[{i}]" if field_name else f"[{i}]"
            result.append(self._deep_cast(inner_t, x, item_field))
        return helpers.collapse_list(result)
    
    def _try_create_from_whole_list(self, inner_t: Any, val: List, field_name: str) -> Optional[List]:
        """Пытается создать объект из всего списка."""
        try:
            if isinstance(inner_t, type) and hasattr(inner_t, '__base__'):
                try:
                    if issubclass(inner_t, BaseModel):
                        return [self._deep_cast(inner_t, val, field_name)]
                except (TypeError, Exception):
                    pass
        except Exception:
            pass
        return None
    
    def _process_flat_list(self, inner_t: Any, val: List, field_name: str) -> List:
        """Обрабатывает плоский список."""
        result = []
        for i, x in enumerate(val):
            item_field = f"{field_name}[{i}]" if field_name else f"[{i}]"
            result.append(self._deep_cast(inner_t, x, item_field))
        return helpers.collapse_list(result)
    
    def _process_class(self, target_t: type, val: Any, field_name: str) -> Any:
        """Обрабатывает классы (модели и датаклассы)."""
        
        # Словарь -> модель/датакласс
        if isinstance(val, dict):
            return self._process_dict_to_class(target_t, val)
        
        # Список / кортеж -> модель (напр. GeoPoint([lat, lon]) / GeoPoint((lat, lon)))
        if isinstance(val, (list, tuple)):
            return self._process_list_to_class(target_t, val, field_name)
        
        # Примитив -> простой тип
        if helpers.is_primitive(val):
            return self._process_primitive(target_t, val)
        
        return val
    
    def _process_dict_to_class(self, target_t: type, val: Dict) -> Any:
        """Преобразует словарь в класс."""
        
        # BaseModel
        try:
            if issubclass(target_t, BaseModel):
                meta = val.pop(META_KEY, None) if META_KEY in val else None
                instance = target_t(**val)
                if meta:
                    setattr(instance, META_KEY, meta)
                return instance
        except (TypeError, Exception):
            pass
        
        # Датакласс
        if is_dataclass(target_t):
            try:
                return target_t(**val)
            except Exception:
                pass
        
        return val
    
    def _process_list_to_class(self, target_t: type, val, field_name: str) -> Any:
        """Преобразует список/кортеж в объект класса или список объектов."""
        # Пытаемся создать объект из последовательности напрямую (например, GeoPoint([1,2]))
        try:
            return target_t(val)
        except Exception:
            # Если не вышло - считаем, что это список таких объектов
            result = []
            for i, x in enumerate(val):
                item_field = f"{field_name}[{i}]" if field_name else f"[{i}]"
                result.append(self._deep_cast(target_t, x, item_field))
            return helpers.collapse_list(result)
    
    def _process_primitive(self, target_t: Any, val: Any) -> Any:
        """Базовое приведение примитивных типов."""
        try:
            if isinstance(val, target_t):
                return val
            
            # Специальная обработка для bool
            if target_t is bool and isinstance(val, str):
                if val.lower() in ('false', '0', 'no', 'off'):
                    return False
                if val.lower() in ('true', '1', 'yes', 'on'):
                    return True
            
            return target_t(val) if val is not None else val
        except Exception:
            return val
    
    # ------------------------------------------------------------------------
    # Доступ к метаданным
    # ------------------------------------------------------------------------
    
    @property
    def meta(self) -> Optional[MetaData]:
        """Возвращает метаданные объекта."""
        return getattr(self, META_KEY, None)
    
    def get_path(self) -> str:
        """Возвращает строковое представление пути."""
        meta = self.meta
        return meta.get_path_string() if meta else ""
    
    def get_collapsed_keys(self, type_filter: Optional[SegmentType] = None) -> List[str]:
        """Возвращает список схлопнутых ключей из метаданных."""
        meta = self.meta
        if not meta:
            return []
        
        if type_filter is None:
            return [seg.key for seg in meta.path]
        
        return [seg.key for seg in meta.path if seg.type == type_filter]
    
    # ------------------------------------------------------------------------
    # Сериализация
    # ------------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """
        Преобразует модель в словарь, применяя собственные метаданные.
        
        Алгоритм:
        1. Создает начальную структуру из собственных метаданных
        2. Рекурсивно обходит структуру, запоминая путь
        3. При обнаружении объекта-модели:
        - Сравнивает его метаданные с текущим путем (без корневого ключа)
        - Применяет только уникальную часть метаданных
        """
        from ..smartdata.metadata import META_KEY, SegmentType
        
        def _apply_metadata(data: Any, meta_path: List) -> Any:
            """Применяет метаданные к данным."""
            if not meta_path:
                return data
            
            result = data
            for segment in reversed(meta_path):
                if segment.type == SegmentType.IDX:
                    idx = int(segment.key)
                    lst = []
                    while len(lst) <= idx:
                        lst.append(None)
                    lst[idx] = result
                    result = lst
                else:
                    result = {segment.key: result}
            
            # Если последний сегмент был не IDX, и результат - список из одного элемента,
            # разворачиваем его (это был искусственный список)
            if meta_path and meta_path[-1].type != SegmentType.IDX:
                if isinstance(result, list) and len(result) == 1:
                    result = result[0]
            
            return result
        
        def _find_matching_prefix(path1: List, path2: List) -> int:
            """Находит длину общего префикса двух путей (без корневого ключа)."""
            # Отбрасываем первый сегмент из path1 (корневой ключ)
            adjusted_path1 = path1[1:] if path1 else []
            
            min_len = min(len(adjusted_path1), len(path2))
            for i in range(min_len):
                if (adjusted_path1[i].type != path2[i].type or 
                    adjusted_path1[i].key != path2[i].key):
                    return i
            return min_len
        
        def _process_structure(data: Any, current_path: List = None) -> Any:
            """
            Рекурсивно обрабатывает структуру.
            current_path - путь от корня до текущего элемента
            """
            if current_path is None:
                current_path = []
            
            # Список
            if isinstance(data, list):
                result = []
                for i, item in enumerate(data):
                    item_path = current_path + [PathSegment(SegmentType.IDX, str(i))]
                    result.append(_process_structure(item, item_path))
                return result
            
            # Словарь
            if isinstance(data, dict):
                # Проверяем, есть ли метаданные в словаре
                if META_KEY in data:
                    meta = data[META_KEY]
                    # Удаляем метаданные из словаря
                    clean_data = {k: v for k, v in data.items() if k != META_KEY}
                    
                    # Обрабатываем значения
                    processed_data = {}
                    for key, value in clean_data.items():
                        key_type = SegmentType.FLD if key.isidentifier() else SegmentType.COL
                        item_path = current_path + [PathSegment(key_type, key)]
                        processed_data[key] = _process_structure(value, item_path)
                    
                    # Применяем метаданные
                    if meta and meta.path:
                        return _apply_metadata(processed_data, meta.path)
                    return processed_data
                
                # Обычный словарь без метаданных
                result = {}
                for key, value in data.items():
                    if key == META_KEY:
                        continue
                    key_type = SegmentType.FLD if key.isidentifier() else SegmentType.COL
                    item_path = current_path + [PathSegment(key_type, key)]
                    result[key] = _process_structure(value, item_path)
                return result
            
            # Объект-модель
            if (hasattr(data, '__class__') and 
                hasattr(data.__class__, '__base__') and 
                data.__class__.__base__.__name__ == 'BaseModel'):
                
                # Получаем метаданные объекта
                obj_meta = getattr(data, META_KEY, None)
                
                if not obj_meta or not obj_meta.path:
                    # Нет метаданных - просто собираем поля
                    obj_data = {}
                    for key, value in data.__dict__.items():
                        if key.startswith('_') or key == META_KEY:
                            continue
                        key_type = SegmentType.FLD if key.isidentifier() else SegmentType.COL
                        item_path = current_path + [PathSegment(key_type, key)]
                        obj_data[key] = _process_structure(value, item_path)
                    return obj_data
                
                # Находим общий префикс с текущим путем
                common_len = _find_matching_prefix(current_path, obj_meta.path)
                
                # Оставшиеся метаданные для применения
                remaining_path = obj_meta.path[common_len:]
                
                # Собираем данные объекта
                obj_data = {}
                for key, value in data.__dict__.items():
                    if key.startswith('_') or key == META_KEY:
                        continue
                    key_type = SegmentType.FLD if key.isidentifier() else SegmentType.COL
                    item_path = current_path + [PathSegment(key_type, key)]
                    obj_data[key] = _process_structure(value, item_path)
                
                # Применяем оставшиеся метаданные
                if remaining_path:
                    return _apply_metadata(obj_data, remaining_path)
                return obj_data
            
            # Примитив
            return data
        
        # Шаг 1: Создаем начальную структуру из собственных метаданных
        self_meta = getattr(self, META_KEY, None)
        
        # Собираем данные всех полей
        raw_data = {}
        for key, value in self.__dict__.items():
            if key.startswith('_') or key == META_KEY:
                continue
            raw_data[key] = value
        
        # Применяем свои метаданные для создания корневой структуры
        if self_meta and self_meta.path:
            initial_structure = _apply_metadata(raw_data, self_meta.path)
        else:
            initial_structure = raw_data
        
        # Шаг 2: Рекурсивно обрабатываем структуру
        return _process_structure(initial_structure)

    def to_file(self, filename: str, format: Optional[str] = None, indent: int = 2) -> None:
        """
        Сохраняет модель в файл.
        
        Args:
            filename: Имя файла
            format: Формат файла ('json', 'pkl', 'gz'). Если не указан, определяется по расширению
            indent: Отступы для JSON (только для json формата)
        """
        
        path = Path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        if format is None:
            format = path.suffix.lstrip('.').lower() or 'json'
        
        # Получаем словарь с данными
        data = self.to_dict()
        
        if format == 'json':
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=indent, ensure_ascii=False, default=str)
        elif format == 'pkl':
            with open(path, 'wb') as f:
                pickle.dump(data, f)
        elif format == 'gz':
            with gzip.open(path, 'wb') as f:
                pickle.dump(data, f)
        else:
            raise ValueError(f"Неподдерживаемый формат: {format}")

        log.debug(f"Модель {self.__class__.__name__} сохранена в {path}")

    @classmethod
    def from_file(cls, filename: str, format: Optional[str] = None) -> 'BaseModel':
        """
        Загружает модель из файла.
        
        Args:
            filename: Имя файла
            format: Формат файла ('json', 'pkl', 'gz'). Если не указан, определяется по расширению
            
        Returns:
            Экземпляр модели
        """
        
        path = Path(filename)
        if not path.exists():
            raise FileNotFoundError(f"Файл не найден: {filename}")
        
        if format is None:
            format = path.suffix.lstrip('.').lower()
        
        if format == 'json':
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        elif format == 'pkl':
            with open(path, 'rb') as f:
                data = pickle.load(f)
        elif format == 'gz':
            with gzip.open(path, 'rb') as f:
                data = pickle.load(f)
        else:
            raise ValueError(f"Неподдерживаемый формат: {format}")

        from ..smartdata.core import SmartData

        # Создаем SmartData для обработки данных
        sd = SmartData(data, target_type=cls)
        
        log.debug(f"Модель {cls.__name__} загружена из {path}")
        return sd[0]

    # ------------------------------------------------------------------------
    # Магические методы
    # ------------------------------------------------------------------------
    
    def __getattr__(self, name: str) -> Any:
        if name.startswith('__') and name.endswith('__'):
            raise AttributeError(name)
        
        if name in self._get_annotations():
            return None
        
        raise AttributeError(f"'{self.__class__.__name__}' не имеет атрибута '{name}'")
    
    def __repr__(self) -> str:
        attrs = []
        for k, v in self.__dict__.items():
            if not k.startswith('_'):
                if k == META_KEY and v:
                    attrs.append(f"meta={v.get_path_string()}")
                elif k != META_KEY:
                    if isinstance(v, list) and len(v) > 3:
                        attrs.append(f"{k}=[{len(v)} элементов]")
                    else:
                        attrs.append(f"{k}={v!r}")
        return f"{self.__class__.__name__}({', '.join(attrs)})"


class BaseCategory:
    """Базовый класс для всех категорий API"""
    
    __slots__ = ('_client', '_category')
    
    _is_ret_origin = False

    @staticmethod
    def _return_original_response(is_ret_origin: bool = True):
        """Устанавливает флаг возврата оригинального ответа."""
        BaseCategory._is_ret_origin = is_ret_origin

    def __init__(self, client: Any):
        self._client = client
        self._category = self.__class__.__name__.lower()
    
    @classmethod
    def get_link(cls, client, object_id):
        try:
            if hasattr(cls, 'link_cat') and cls.link_cat:
                return f"{str(client._url.rstrip('/')).rsplit('/', 1)[0]}/{cls.link_cat}/{object_id}"
        except: pass
        return None
    
    def _request(self, action: str, **params) -> Any:
        """Выполняет запрос к API."""
        self._client._current_category = self._category
        return self._client._exec(action, **params)
    
    def __getattr__(self, name: str):
        """Динамически создает методы для API действий."""
        def method(**kwargs):
            return self._request(name, **kwargs)
        return method

from .primitives import vStr

@smart_model
class BaseItem(BaseModel):
    id: int
    name: vStr
