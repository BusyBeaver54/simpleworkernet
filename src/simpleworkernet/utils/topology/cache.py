"""
DataCache — слой загрузки и кэширования объектов/коммутаций API.

Не синглтон: создаётся явно (или через NetworkTopology).
Можно шарить один экземпляр между несколькими NetworkTopology.

Фоновая предзагрузка get_all_* — параллельные потоки (I/O-bound;
объекты API не pickle-ятся в отдельные процессы).

preload_async() только ставит задачи в ThreadPoolExecutor и сразу
возвращает управление. Ждать завершения нужно явно через wait_preload().
Точечные get_*/get_or_load_* НЕ ждут bulk-preload: если объекта ещё
нет в кэше — идёт одиночный API-запрос.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, Future
from contextlib import contextmanager
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from ...core.client import WorkerNetClient
from .constants import (
    DEVICE_TYPES,
    TYPE_CROSS,
    TYPE_CUSTOMER,
    TYPE_CWDM,
    TYPE_FIBER,
    TYPE_OLT,
    TYPE_SPLITTER,
    TYPE_SWITCH,
    TYPE_RADIO,
)

_logger = None
_tls = threading.local()


def _get_logger():
    global _logger
    if _logger is None:
        from ...core.logger import log

        _logger = log
    return _logger



def _infer_device_type(obj: Any) -> Optional[str]:
    """Тип устройства из api_obj, если есть (olt/switch/onu/radio)."""
    if obj is None:
        return None
    for attr in ("object_type", "type", "device_type", "obj_type"):
        val = getattr(obj, attr, None)
        if val is None and isinstance(obj, dict):
            val = obj.get(attr)
        if val is None:
            continue
        t = str(val).strip().lower()
        if t in DEVICE_TYPES:
            return t
    return None

def _loading_types() -> set:
    s = getattr(_tls, "loading_types", None)
    if s is None:
        s = set()
        _tls.loading_types = s
    return s


def _extract_obj_id(obj: Any) -> Optional[Union[int, str]]:
    if obj is None:
        return None
    if isinstance(obj, dict):
        for key in ("id", "code", "uuid"):
            val = obj.get(key)
            if val is not None and val != "":
                return val
        return None
    for key in ("id", "code", "uuid"):
        val = getattr(obj, key, None)
        if val is not None and val != "":
            return val
    return None


def _result_to_objects(result: Any) -> List[Any]:
    if result is None:
        return []
    if hasattr(result, "to_list") and callable(result.to_list):
        try:
            items = result.to_list()
            if items is not None:
                return list(items)
        except Exception as e:
            _get_logger().warning("to_list() failed: %s", e)
        if hasattr(result, "to_raw_list") and callable(result.to_raw_list):
            try:
                return list(result.to_raw_list() or [])
            except Exception:
                pass
        return []
    if isinstance(result, (list, tuple)):
        return list(result)
    return [result]


@contextmanager
def _temporary_timeout(seconds: Optional[int]):
    if seconds is None or seconds <= 0:
        yield
        return
    try:
        from ...core.config import config_manager
        old = config_manager.default_timeout
        config_manager.default_timeout = int(seconds)
        try:
            yield
        finally:
            config_manager.default_timeout = old
    except Exception:
        yield


class DataCache:
    def __init__(
        self,
        client: Optional[WorkerNetClient] = None,
        *,
        preload_types: Optional[Sequence[str]] = None,
        preload: Optional[bool] = None,
    ) -> None:
        """
        Args:
            client: клиент API (нужен для preload).
            preload_types: типы для фоновой предзагрузки (не блокирует).
            preload: игнорируется (совместимость со старым from_dict).
        """
        _ = preload
        self._objects: Dict[Tuple[str, Union[int, str]], Any] = {}
        self._commutations: Dict[Tuple[str, Union[int, str]], List[Any]] = {}
        self._all_objects: Dict[str, Dict[Union[int, str], Any]] = {}
        self._inventory: Dict[Union[int, str], Any] = {}
        self._inventory_catalog: Dict[Union[int, str], Any] = {}
        self._fiber_lengths: Dict[Union[int, str], Tuple[Optional[float], str]] = {}
        self._geo_lengths: Dict[int, Optional[float]] = {}
        self._cable_catalog: Optional[List[Any]] = None

        self._lock = threading.RLock()
        # Короткие критические секции вокруг одного HTTP-вызова.
        # Не держим на всём bulk, чтобы точечные get_* не ждали preload.
        self._api_lock = threading.RLock()
        self._preload_futures: Dict[str, Future] = {}
        self._preload_executor: Optional[ThreadPoolExecutor] = None

        types = list(preload_types) if preload_types else []
        if client is not None and types:
            self.preload_async(client, types=types)

    def _bulk_timeout(self, object_type: str) -> int:
        try:
            from ...core.config import config_manager
            if object_type == TYPE_CUSTOMER:
                return int(
                    config_manager.customer_list_timeout
                    or config_manager.bulk_timeout
                    or 300
                )
            return int(config_manager.bulk_timeout or 120)
        except Exception:
            return 120 if object_type != TYPE_CUSTOMER else 300

    @staticmethod
    def _id_variants(obj_id: Union[int, str]) -> List[Union[int, str]]:
        out: List[Union[int, str]] = [obj_id]
        if isinstance(obj_id, str) and obj_id.isdigit():
            out.append(int(obj_id))
        elif isinstance(obj_id, int):
            out.append(str(obj_id))
        return out

    def get_object(self, obj_type: str, obj_id: Union[int, str]) -> Optional[Any]:
        for oid in self._id_variants(obj_id):
            obj = self._objects.get((obj_type, oid))
            if obj is not None:
                return obj
            if obj_type in DEVICE_TYPES or obj_type == "device":
                obj = self._objects.get(("device", oid))
                if obj is not None:
                    return obj
                for dt in DEVICE_TYPES:
                    obj = self._objects.get((dt, oid))
                    if obj is not None:
                        return obj
        bulk_keys = [obj_type]
        if obj_type in DEVICE_TYPES or obj_type == "device":
            bulk_keys.extend(["device", *sorted(DEVICE_TYPES)])
        for bkey in bulk_keys:
            bulk = self._all_objects.get(bkey)
            if not bulk:
                continue
            for oid in self._id_variants(obj_id):
                if oid in bulk:
                    obj = bulk[oid]
                    self.set_object(obj_type if obj_type != "device" else (
                        _infer_device_type(obj) or "device"
                    ), obj_id, obj)
                    return obj
        return None

    def set_object(self, obj_type: str, obj_id: Union[int, str], obj: Any) -> None:
        with self._lock:
            for oid in self._id_variants(obj_id):
                self._objects[(obj_type, oid)] = obj
                if obj_type in DEVICE_TYPES or obj_type == "device":
                    self._objects[("device", oid)] = obj
                    inferred = _infer_device_type(obj)
                    if inferred:
                        self._objects[(inferred, oid)] = obj
                    elif obj_type in DEVICE_TYPES:
                        # явный тип при записи важнее, чем отсутствие поля в api_obj
                        self._objects[(obj_type, oid)] = obj

    def get_or_load_object(
        self, obj_type: str, obj_id: Union[int, str], loader: Callable[[], Any],
    ) -> Any:
        """Точечная загрузка. Не ждёт bulk-preload.

        Если preload уже положил объект в кэш — берём из кэша.
        Иначе одиночный API-запрос (параллельно с фоновым preload).
        """
        obj = self.get_object(obj_type, obj_id)
        if obj is not None:
            return obj
        with self._api_lock:
            obj = self.get_object(obj_type, obj_id)
            if obj is not None:
                return obj
            obj = loader()
            if obj is not None:
                self.set_object(obj_type, obj_id, obj)
        return obj

    def get_commutations(self, obj_type: str, obj_id: Union[int, str]) -> Optional[List[Any]]:
        return self._commutations.get((obj_type, obj_id))

    def set_commutations(self, obj_type: str, obj_id: Union[int, str], comms: List[Any]) -> None:
        with self._lock:
            self._commutations[(obj_type, obj_id)] = comms

    def get_or_load_commutations(
        self, obj_type: str, obj_id: Union[int, str], loader: Callable[[], List[Any]],
    ) -> List[Any]:
        for oid in self._id_variants(obj_id):
            comms = self._commutations.get((obj_type, oid))
            if comms is not None:
                return comms
        with self._api_lock:
            for oid in self._id_variants(obj_id):
                comms = self._commutations.get((obj_type, oid))
                if comms is not None:
                    return comms
            comms = loader()
            if comms is not None:
                self.set_commutations(obj_type, obj_id, comms)
            else:
                comms = []
        return comms

    def _preload_future_for(self, object_type: str):
        fut = self._preload_futures.get(object_type)
        if fut is not None:
            return fut
        if object_type in DEVICE_TYPES or object_type == "device":
            return self._preload_futures.get("device")
        return None

    def get_all_objects(self, object_type: str, loader: Callable[[], Any]) -> Dict[Union[int, str], Any]:
        """Полный список типа. Если идёт preload этого типа — ждём его
        (чтобы не дублировать bulk-запрос). Иначе грузим сами.
        """
        with self._lock:
            if object_type in self._all_objects:
                return self._all_objects[object_type]
        loading = _loading_types()
        # Мы сами в preload-потоке для этого типа — грузим без ожидания future.
        if object_type in loading or (object_type in DEVICE_TYPES and "device" in loading):
            return self._fetch_all_objects(object_type, loader)
        fut = self._preload_future_for(object_type)
        if fut is not None and not fut.done():
            try:
                fut.result()
            except Exception:
                pass
            with self._lock:
                if object_type in self._all_objects:
                    return self._all_objects[object_type]
        loading.add(object_type)
        try:
            return self._fetch_all_objects(object_type, loader)
        finally:
            loading.discard(object_type)

    def _fetch_all_objects(self, object_type: str, loader: Callable[[], Any]) -> Dict[Union[int, str], Any]:
        with self._lock:
            if object_type in self._all_objects:
                return self._all_objects[object_type]
        logger = _get_logger()
        timeout = self._bulk_timeout(object_type)
        objects: List[Any] = []
        # API-вызов под коротким lock; разбор ответа — без lock.
        with self._api_lock:
            with self._lock:
                if object_type in self._all_objects:
                    return self._all_objects[object_type]
            try:
                with _temporary_timeout(timeout):
                    result = loader()
                objects = _result_to_objects(result)
            except Exception as e:
                logger.error("Ошибка загрузки всех объектов типа %s: %s", object_type, e)
                objects = []
        obj_dict: Dict[Union[int, str], Any] = {}
        for obj in objects:
            obj_id = _extract_obj_id(obj)
            if obj_id is not None:
                for oid in self._id_variants(obj_id):
                    obj_dict[oid] = obj
                self.set_object(object_type, obj_id, obj)
        with self._lock:
            existing = self._all_objects.get(object_type)
            if existing:
                existing.update(obj_dict)
                obj_dict = existing
            else:
                self._all_objects[object_type] = obj_dict
        return obj_dict

    def preload_async(
        self, client: WorkerNetClient, *,
        types: Optional[Sequence[str]] = None,
        include_customers: Optional[bool] = None,
        workers: Optional[int] = None,
    ) -> Dict[str, Future]:
        """Запустить bulk-загрузку в фоне. Не блокирует вызывающий поток.

        Дождаться: ``cache.wait_preload()``.
        Статус: ``cache.preload_status()``.
        """
        try:
            from ...core.config import config_manager
            default_types = list(config_manager.preload_types)
            default_customers = bool(config_manager.preload_customers)
            default_workers = int(config_manager.preload_workers)
        except Exception:
            default_types = ["node", "device", "splitter", "cross", "cwdm", "fiber"]
            default_customers = False
            default_workers = 6
        if types is None:
            types = default_types
        if include_customers is None:
            include_customers = default_customers
        if include_customers and "customer" not in types:
            types = list(types) + ["customer"]
        n_workers = workers if workers is not None else default_workers
        n_workers = max(1, min(int(n_workers), max(1, len(list(types)))))
        jobs: Dict[str, Callable[[], Any]] = {
            "node": lambda: self.get_all_nodes(client),
            "device": lambda: self.get_all_devices(client),
            "splitter": lambda: self.get_all_splitters(client),
            "cross": lambda: self.get_all_crosses(client),
            "cwdm": lambda: self.get_all_cwdms(client),
            "fiber": lambda: self.get_all_fibers(client),
            "customer": lambda: self.get_all_customers(client),
        }
        cache_keys = {
            "node": ["node"],
            "device": ["device", *sorted(DEVICE_TYPES)],
            "splitter": [TYPE_SPLITTER],
            "cross": [TYPE_CROSS],
            "cwdm": [TYPE_CWDM],
            "fiber": [TYPE_FIBER],
            "customer": [TYPE_CUSTOMER],
        }
        if self._preload_executor is None:
            self._preload_executor = ThreadPoolExecutor(
                max_workers=n_workers, thread_name_prefix="DataCachePreload",
            )
        logger = _get_logger()
        started = {}
        for t in types:
            key = str(t).lower()
            if key not in jobs:
                logger.warning("DataCache.preload: неизвестный тип %s", t)
                continue
            keys = cache_keys.get(key, [key])
            if any(k in self._all_objects for k in keys):
                continue
            if key in self._preload_futures and not self._preload_futures[key].done():
                started[key] = self._preload_futures[key]
                continue

            def _run(k=key, fn=jobs[key], mark_keys=keys):
                loading = _loading_types()
                for mk in mark_keys:
                    loading.add(mk)
                loading.add(k)
                try:
                    return fn()
                except Exception as e:
                    _get_logger().error("preload %s failed: %s", k, e)
                    return {}
                finally:
                    for mk in mark_keys:
                        loading.discard(mk)
                    loading.discard(k)

            fut = self._preload_executor.submit(_run)
            self._preload_futures[key] = fut
            for mk in keys:
                self._preload_futures.setdefault(mk, fut)
            started[key] = fut
            logger.info("DataCache: фоновая загрузка %s…", key)
        return started

    def wait_preload(self, timeout: Optional[float] = None) -> None:
        """Явно дождаться завершения всех preload-задач."""
        for key, fut in list(self._preload_futures.items()):
            try:
                fut.result(timeout=timeout)
            except Exception as e:
                _get_logger().warning("preload %s: %s", key, e)

    def preload_status(self) -> Dict[str, str]:
        out = {}
        for key, fut in self._preload_futures.items():
            if not fut.done():
                out[key] = "pending"
            elif fut.exception() is not None:
                out[key] = f"error:{fut.exception()}"
            else:
                out[key] = "done"
        for key in self._all_objects:
            out.setdefault(key, "done")
        return out

    def get_inventory(self, client: WorkerNetClient, inventory_id: Union[int, str]) -> Optional[Any]:
        if inventory_id in self._inventory:
            return self._inventory[inventory_id]
        def loader() -> Optional[Any]:
            try:
                result = client.Inventory.get_inventory(id=int(inventory_id))
                return result[0] if result and len(result) > 0 else None
            except Exception as e:
                _get_logger().warning(f"Не удалось загрузить inventory {inventory_id}: {e}")
                return None
        inv = loader()
        if inv is not None:
            self._inventory[inventory_id] = inv
        return inv

    def get_inventory_catalog_item(self, client: WorkerNetClient, catalog_id: Union[int, str]) -> Optional[Any]:
        if catalog_id in self._inventory_catalog:
            return self._inventory_catalog[catalog_id]
        def loader() -> Optional[Any]:
            try:
                result = client.Inventory.get_inventory_catalog(id=int(catalog_id))
                return result[0] if result and len(result) > 0 else None
            except Exception as e:
                _get_logger().warning(f"Не удалось загрузить inventory catalog {catalog_id}: {e}")
                return None
        item = loader()
        if item is not None:
            self._inventory_catalog[catalog_id] = item
        return item

    def preload_splitter_inventory(self, client: WorkerNetClient) -> None:
        splitters = self.get_all_splitters(client)
        for sp in splitters.values():
            inv_id = getattr(sp, "inventory_id", None)
            if inv_id is not None:
                inv = self.get_inventory(client, inv_id)
                if inv is not None:
                    cid = getattr(inv, "catalog_id", None)
                    if cid is not None:
                        self.get_inventory_catalog_item(client, cid)

    def get_fiber_length_m(self, fiber_id: Union[int, str]) -> Optional[Tuple[Optional[float], str]]:
        return self._fiber_lengths.get(fiber_id)

    def set_fiber_length_m(self, fiber_id: Union[int, str], length_m: Optional[float], source: str) -> None:
        self._fiber_lengths[fiber_id] = (length_m, source)

    def get_geo_length(self, client: WorkerNetClient, fiber_id: int) -> Optional[float]:
        if fiber_id in self._geo_lengths:
            return self._geo_lengths[fiber_id]
        try:
            result = client.Fiber.get_geo_length(id=fiber_id)
            value: Optional[float] = None
            if result is None:
                value = None
            elif isinstance(result, (int, float)):
                value = float(result)
            elif hasattr(result, "__iter__") and not isinstance(result, (str, bytes)):
                try:
                    value = float(result[0])  # type: ignore[index]
                except Exception:
                    value = None
            else:
                try:
                    value = float(result)  # type: ignore[arg-type]
                except Exception:
                    value = None
            self._geo_lengths[fiber_id] = value
            return value
        except Exception as e:
            _get_logger().debug(f"get_geo_length({fiber_id}) failed: {e}")
            self._geo_lengths[fiber_id] = None
            return None

    def get_cable_catalog(self, client: WorkerNetClient) -> List[Any]:
        if self._cable_catalog is not None:
            return self._cable_catalog
        try:
            result = client.Fiber.catalog_cables_get()
            self._cable_catalog = _result_to_objects(result)
        except Exception as e:
            _get_logger().warning(f"catalog_cables_get failed: {e}")
            self._cable_catalog = []
        return self._cable_catalog

    def get_all_splitters(self, client: WorkerNetClient) -> Dict[int, Any]:
        return self.get_all_objects(TYPE_SPLITTER, lambda: client.Splitter.get())

    def get_all_crosses(self, client: WorkerNetClient) -> Dict[str, Any]:
        return self.get_all_objects(TYPE_CROSS, lambda: client.Cross.get_list())

    def get_all_cwdms(self, client: WorkerNetClient) -> Dict[int, Any]:
        return self.get_all_objects(TYPE_CWDM, lambda: client.Cwdm.get())

    def get_all_nodes(self, client: WorkerNetClient) -> Dict[int, Any]:
        return self.get_all_objects("node", lambda: client.Node.get())

    def get_all_fibers(self, client: WorkerNetClient) -> Dict[int, Any]:
        with self._lock:
            if TYPE_FIBER in self._all_objects:
                return self._all_objects[TYPE_FIBER]
        loading = _loading_types()
        if TYPE_FIBER in loading:
            return self._fetch_all_fibers(client)
        fut = self._preload_futures.get("fiber") or self._preload_futures.get(TYPE_FIBER)
        if fut is not None and not fut.done():
            try:
                fut.result()
            except Exception:
                pass
            with self._lock:
                if TYPE_FIBER in self._all_objects:
                    return self._all_objects[TYPE_FIBER]
        loading.add(TYPE_FIBER)
        try:
            return self._fetch_all_fibers(client)
        finally:
            loading.discard(TYPE_FIBER)

    def _fetch_all_fibers(self, client: WorkerNetClient) -> Dict[int, Any]:
        logger = _get_logger()
        timeout = self._bulk_timeout(TYPE_FIBER)
        result: Dict[Union[int, str], Any] = {}
        with self._lock:
            if TYPE_FIBER in self._all_objects:
                return self._all_objects[TYPE_FIBER]
        try:
            with self._api_lock:
                with _temporary_timeout(timeout):
                    catalog = client.Fiber.catalog_types_get()
            for cab_type in _result_to_objects(catalog):
                type_id = _extract_obj_id(cab_type)
                if type_id is None:
                    continue
                try:
                    # Каждый batch — отдельная секция lock, чтобы точечные
                    # get_fiber могли проходить между запросами preload.
                    with self._api_lock:
                        with _temporary_timeout(timeout):
                            batch = client.Fiber.get_list(cable_line_type_id=type_id)
                    objects = _result_to_objects(batch)
                except Exception as e:
                    logger.error("Ошибка загрузки fiber cable_line_type_id=%s: %s", type_id, e)
                    objects = []
                for obj in objects:
                    obj_id = _extract_obj_id(obj)
                    if obj_id is not None:
                        for oid in self._id_variants(obj_id):
                            result[oid] = obj
                        self.set_object(TYPE_FIBER, obj_id, obj)
        except Exception as e:
            logger.error("Ошибка загрузки всех fiber: %s", e)
        with self._lock:
            existing = self._all_objects.get(TYPE_FIBER)
            if existing:
                existing.update(result)
                result = existing
            else:
                self._all_objects[TYPE_FIBER] = result
        return result

    def get_all_devices(self, client: WorkerNetClient) -> Dict[int, Any]:
        """Все устройства (olt/switch/onu/radio). Кладём и в typed bulk, и в device."""
        result: Dict[int, Any] = {}
        for dev_type in sorted(DEVICE_TYPES):
            devices = self.get_all_objects(
                dev_type,
                lambda dt=dev_type: client.Device.get_data(object_type=dt),
            )
            result.update(devices)
        # единый индекс device → id
        with self._lock:
            bulk = self._all_objects.setdefault("device", {})
            for oid, obj in result.items():
                for v in self._id_variants(oid):
                    bulk[v] = obj
                self.set_object("device", oid, obj)
        return result

    def get_all_customers(self, client: WorkerNetClient) -> Dict[int, Any]:
        return self.get_all_objects(TYPE_CUSTOMER, lambda: client.Module.get_user_list())

    def get_device(
        self,
        client: WorkerNetClient,
        obj_type: Optional[str],
        obj_id: int,
    ) -> Optional[Any]:
        """Устройство по id.

        obj_type — olt/switch/onu/radio или None/"device" (тогда API: object_type=all).
        В кэше объект индексируется и как device, и по конкретному типу (если известен).
        """
        ot = (str(obj_type).strip().lower() if obj_type else "") or None
        if ot == "device":
            ot = None
        if ot is not None and ot not in DEVICE_TYPES:
            _get_logger().warning(
                "get_device: неизвестный object_type=%r, используем all", obj_type
            )
            ot = None

        # кэш: конкретный тип → device → остальные DEVICE_TYPES
        if ot:
            cached = self.get_object(ot, obj_id)
            if cached is not None:
                return cached
        cached = self.get_object("device", obj_id)
        if cached is not None:
            return cached
        for dt in DEVICE_TYPES:
            if ot and dt == ot:
                continue
            cached = self.get_object(dt, obj_id)
            if cached is not None:
                return cached

        api_type = ot if ot else "all"
        store_type = ot if ot else "device"

        def loader() -> Optional[Any]:
            try:
                result = client.Device.get_data(
                    object_type=api_type,  # type: ignore[arg-type]
                    object_id=int(obj_id),
                )
                items = _result_to_objects(result)
                return items[0] if items else None
            except Exception as e:
                _get_logger().warning(
                    "Не удалось загрузить устройство %s:%s: %s",
                    api_type, obj_id, e,
                )
                return None

        obj = self.get_or_load_object(store_type, obj_id, loader)
        if obj is not None:
            # гарантируем dual-index
            self.set_object("device", obj_id, obj)
            inferred = _infer_device_type(obj) or ot
            if inferred:
                self.set_object(inferred, obj_id, obj)
        return obj

    def get_cross(self, client: WorkerNetClient, obj_id: str) -> Optional[Any]:
        def loader() -> Optional[Any]:
            try:
                result = client.Cross.get_list(id=obj_id)
                return result[0] if result and len(result) > 0 else None
            except Exception as e:
                _get_logger().warning(f"Не удалось загрузить кросс {obj_id}: {e}")
                return None
        return self.get_or_load_object(TYPE_CROSS, obj_id, loader)

    def get_splitter(self, client: WorkerNetClient, obj_id: int) -> Optional[Any]:
        def loader() -> Optional[Any]:
            try:
                result = client.Splitter.get(id=obj_id)
                return result[0] if result and len(result) > 0 else None
            except Exception as e:
                _get_logger().warning(f"Не удалось загрузить сплиттер {obj_id}: {e}")
                return None
        return self.get_or_load_object(TYPE_SPLITTER, obj_id, loader)

    def get_fiber(self, client: WorkerNetClient, obj_id: int) -> Optional[Any]:
        def loader() -> Optional[Any]:
            try:
                result = client.Fiber.get_list(object_id=obj_id)
                return result[0] if result and len(result) > 0 else None
            except Exception as e:
                _get_logger().warning(f"Не удалось загрузить кабель {obj_id}: {e}")
                return None
        return self.get_or_load_object(TYPE_FIBER, obj_id, loader)

    def get_customer(self, client: WorkerNetClient, obj_id: int) -> Optional[Any]:
        def loader() -> Optional[Any]:
            try:
                result = client.Customer.get_data(customer_id=obj_id)
                return result[0] if result and len(result) > 0 else None
            except Exception as e:
                _get_logger().warning(f"Не удалось загрузить абонента {obj_id}: {e}")
                return None
        return self.get_or_load_object(TYPE_CUSTOMER, obj_id, loader)

    def get_node(self, client: WorkerNetClient, obj_id: int) -> Optional[Any]:
        def loader() -> Optional[Any]:
            try:
                result = client.Node.get(id=obj_id)
                return result[0] if result and len(result) > 0 else None
            except Exception as e:
                _get_logger().warning(f"Не удалось загрузить узел {obj_id}: {e}")
                return None
        return self.get_or_load_object("node", obj_id, loader)

    def get_cwdm(self, client: WorkerNetClient, obj_id: int) -> Optional[Any]:
        def loader() -> Optional[Any]:
            try:
                result = client.Cwdm.get(id=obj_id)
                return result[0] if result and len(result) > 0 else None
            except Exception as e:
                _get_logger().warning(f"Не удалось загрузить CWDM {obj_id}: {e}")
                return None
        return self.get_or_load_object(TYPE_CWDM, obj_id, loader)

    def get_commutations_by_object(
        self, client: WorkerNetClient, obj_type: str, obj_id: Union[int, str], is_finish_data: int = 1,
    ) -> List[Any]:
        """Коммутации объекта. Всегда грузим с is_finish_data=1 (в ответе есть
        и обычные, и finish-записи с clps_last='finish').

        Параметр is_finish_data оставлен для совместимости, но кэш один:
        иначе первый вызов с 0 «отравляет» кэш и finish_data в CGraph пустеет.
        Фильтрацию finish делает split_finish / вызывающий код.
        """
        # Commutation.get_data: customer|switch|radio|cross|fiber|splitter
        # olt/onu/switch → switch; radio → radio; остальные как есть
        if obj_type == TYPE_RADIO:
            actual_type = TYPE_RADIO
        elif obj_type in DEVICE_TYPES:
            actual_type = TYPE_SWITCH
        else:
            actual_type = obj_type

        def loader() -> List[Any]:
            api_type = actual_type
            api_id = str(obj_id) if api_type == TYPE_CROSS else int(obj_id)
            try:
                result = client.Commutation.get_data(
                    object_type=api_type,  # type: ignore[arg-type]
                    object_id=api_id,
                    is_finish_data=1,
                )
                return _result_to_objects(result)
            except Exception as e:
                _get_logger().error(
                    "Ошибка загрузки коммутаций для %s:%s: %s",
                    actual_type, obj_id, e,
                )
                return []
        return self.get_or_load_commutations(actual_type, obj_id, loader)


    def to_dict(self) -> dict:
        return {
            "objects": self._objects,
            "commutations": self._commutations,
            "all_objects": self._all_objects,
            "inventory": self._inventory,
            "inventory_catalog": self._inventory_catalog,
            "fiber_lengths": self._fiber_lengths,
            "geo_lengths": self._geo_lengths,
            "cable_catalog": self._cable_catalog,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DataCache":
        cache = cls()
        cache._objects = data.get("objects", {})
        cache._commutations = data.get("commutations", {})
        cache._all_objects = data.get("all_objects", {})
        cache._inventory = data.get("inventory", {})
        cache._inventory_catalog = data.get("inventory_catalog", {})
        cache._fiber_lengths = data.get("fiber_lengths", {})
        cache._geo_lengths = data.get("geo_lengths", {})
        cache._cable_catalog = data.get("cable_catalog")
        return cache

    def clear(self) -> None:
        with self._lock:
            self._objects.clear()
            self._commutations.clear()
            self._all_objects.clear()
            self._inventory.clear()
            self._inventory_catalog.clear()
            self._fiber_lengths.clear()
            self._geo_lengths.clear()
            self._cable_catalog = None

    def shutdown_preload(self) -> None:
        if self._preload_executor is not None:
            self._preload_executor.shutdown(wait=False, cancel_futures=True)
            self._preload_executor = None
