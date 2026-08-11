"""
DataCache — слой загрузки и кэширования объектов/коммутаций API.

Не синглтон: создаётся явно (или через NetworkTopology).
Можно шарить один экземпляр между несколькими NetworkTopology.

Фоновая предзагрузка get_all_* — параллельные потоки (I/O-bound;
объекты API не pickle-ятся в отдельные процессы). Основной код
продолжает работу; результат подхватывается из _all_objects.
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
)

_logger = None
_tls = threading.local()


def _get_logger():
    global _logger
    if _logger is None:
        from ...core.logger import log

        _logger = log
    return _logger


def _loading_types() -> set:
    """Типы, которые текущий поток уже загружает (защита от deadlock preload)."""
    s = getattr(_tls, "loading_types", None)
    if s is None:
        s = set()
        _tls.loading_types = s
    return s


def _extract_obj_id(obj: Any) -> Optional[Union[int, str]]:
    """id / code / uuid — и у model, и у dict."""
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
    """SmartData.to_list() / list / одиночный объект / None."""
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
    """Временно поднять default_timeout клиента для долгих get_all_*."""
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
    """
    Кэш объектов и коммутаций.

    Хранит:
    - _objects: {(тип, id): объект}
    - _commutations: {(тип, id): [коммутации]}
    - _all_objects: {тип: {id: объект}} — массовая загрузка
    - _inventory / _inventory_catalog — ТМЦ для сплиттеров
    - _fiber_lengths: {fiber_id: (length_m, source)}
    - _geo_lengths: {fiber_id: m}
    - _cable_catalog: catalog_cables_get
    """

    def __init__(
        self,
        client: Optional[WorkerNetClient] = None,
        *,
        preload_types: Optional[Sequence[str]] = None,
    ) -> None:
        """
        Args:
            client: клиент API (нужен для preload).
            preload_types: типы для фоновой предзагрузки
                (node, device, splitter, cross, cwdm, fiber, customer).
                Если не указан или пустой — preload не запускается.
        """
        self._objects: Dict[Tuple[str, Union[int, str]], Any] = {}
        self._commutations: Dict[Tuple[str, Union[int, str]], List[Any]] = {}
        self._all_objects: Dict[str, Dict[Union[int, str], Any]] = {}
        self._inventory: Dict[Union[int, str], Any] = {}
        self._inventory_catalog: Dict[Union[int, str], Any] = {}
        self._fiber_lengths: Dict[Union[int, str], Tuple[Optional[float], str]] = {}
        self._geo_lengths: Dict[int, Optional[float]] = {}
        self._cable_catalog: Optional[List[Any]] = None

        self._lock = threading.RLock()
        # requests.Session клиента НЕ потокобезопасен — все API через этот lock
        self._api_lock = threading.RLock()
        self._preload_futures: Dict[str, Future] = {}
        self._preload_executor: Optional[ThreadPoolExecutor] = None

        types = list(preload_types) if preload_types else []
        if client is not None and types:
            self.preload_async(client, types=types)

    # ------------------------------------------------------------------
    # timeout helpers
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # objects / commutations
    # ------------------------------------------------------------------

    @staticmethod
    def _id_variants(obj_id: Union[int, str]) -> List[Union[int, str]]:
        """Варианты ключа id (int/str), чтобы lookup после preload не промахивался."""
        out: List[Union[int, str]] = [obj_id]
        if isinstance(obj_id, str) and obj_id.isdigit():
            out.append(int(obj_id))
        elif isinstance(obj_id, int):
            out.append(str(obj_id))
        return out

    def get_object(self, obj_type: str, obj_id: Union[int, str]) -> Optional[Any]:
        """Сначала _objects, затем bulk _all_objects (после preload)."""
        for oid in self._id_variants(obj_id):
            obj = self._objects.get((obj_type, oid))
            if obj is not None:
                return obj
            if obj_type in DEVICE_TYPES:
                obj = self._objects.get(("device", oid))
                if obj is not None:
                    return obj

        # bulk-кэш от get_all_* / preload
        bulk_keys = [obj_type]
        if obj_type in DEVICE_TYPES:
            bulk_keys.extend(["device", TYPE_OLT, TYPE_SWITCH])
        if obj_type == "device":
            bulk_keys.extend([TYPE_OLT, TYPE_SWITCH])

        for bkey in bulk_keys:
            bulk = self._all_objects.get(bkey)
            if not bulk:
                continue
            for oid in self._id_variants(obj_id):
                if oid in bulk:
                    obj = bulk[oid]
                    # промоутим в _objects для быстрых следующих lookup
                    self.set_object(obj_type, obj_id, obj)
                    return obj
        return None

    def set_object(self, obj_type: str, obj_id: Union[int, str], obj: Any) -> None:
        with self._lock:
            for oid in self._id_variants(obj_id):
                self._objects[(obj_type, oid)] = obj
                if obj_type in DEVICE_TYPES:
                    self._objects[("device", oid)] = obj

    def get_or_load_object(
        self,
        obj_type: str,
        obj_id: Union[int, str],
        loader: Callable[[], Any],
    ) -> Any:
        obj = self.get_object(obj_type, obj_id)
        if obj is not None:
            return obj

        # если идёт фоновый preload этого типа — дождаться, не бить API по одному
        loading = _loading_types()
        fut = self._preload_future_for(obj_type)
        if (
            fut is not None
            and not fut.done()
            and obj_type not in loading
            and "device" not in loading
        ):
            try:
                fut.result()
            except Exception:
                pass
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

    def get_commutations(
        self, obj_type: str, obj_id: Union[int, str]
    ) -> Optional[List[Any]]:
        return self._commutations.get((obj_type, obj_id))

    def set_commutations(
        self, obj_type: str, obj_id: Union[int, str], comms: List[Any]
    ) -> None:
        with self._lock:
            self._commutations[(obj_type, obj_id)] = comms

    def get_or_load_commutations(
        self,
        obj_type: str,
        obj_id: Union[int, str],
        loader: Callable[[], List[Any]],
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
        """Future фоновой загрузки для object_type (с учётом job-ключей device)."""
        fut = self._preload_futures.get(object_type)
        if fut is not None:
            return fut
        # job "device" грузит olt+switch
        if object_type in (TYPE_OLT, TYPE_SWITCH, "device"):
            return self._preload_futures.get("device")
        return None

    def get_all_objects(
        self, object_type: str, loader: Callable[[], Any]
    ) -> Dict[Union[int, str], Any]:
        with self._lock:
            if object_type in self._all_objects:
                return self._all_objects[object_type]

        loading = _loading_types()
        # дождаться фоновой загрузки, но не ждать самих себя (иначе deadlock)
        fut = self._preload_future_for(object_type)
        if (
            fut is not None
            and not fut.done()
            and object_type not in loading
            and "device" not in loading  # device job covers olt/switch
        ):
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

    def _fetch_all_objects(
        self, object_type: str, loader: Callable[[], Any]
    ) -> Dict[Union[int, str], Any]:
        """Фактическая загрузка без ожидания Future (для preload и get_all_objects)."""
        with self._lock:
            if object_type in self._all_objects:
                return self._all_objects[object_type]

        logger = _get_logger()
        timeout = self._bulk_timeout(object_type)
        objects: List[Any] = []
        with self._api_lock:
            with self._lock:
                if object_type in self._all_objects:
                    return self._all_objects[object_type]
            try:
                with _temporary_timeout(timeout):
                    result = loader()
                objects = _result_to_objects(result)
            except Exception as e:
                logger.error(
                    "Ошибка загрузки всех объектов типа %s: %s", object_type, e
                )
                objects = []

        obj_dict: Dict[Union[int, str], Any] = {}
        skipped = 0
        for obj in objects:
            obj_id = _extract_obj_id(obj)
            if obj_id is not None:
                for oid in self._id_variants(obj_id):
                    obj_dict[oid] = obj
                self.set_object(object_type, obj_id, obj)
            else:
                skipped += 1

        with self._lock:
            existing = self._all_objects.get(object_type)
            if existing:
                existing.update(obj_dict)
                obj_dict = existing
            else:
                self._all_objects[object_type] = obj_dict
        logger.info(
            "DataCache: загружено %s объектов типа %s (timeout=%ss, skipped_no_id=%s)",
            len({k: v for k, v in obj_dict.items() if not isinstance(k, str) or not k.isdigit()}),
            object_type,
            timeout,
            skipped,
        )
        # log count of unique objects better
        logger.info(
            "DataCache: unique ids type %s ≈ %s (raw keys=%s)",
            object_type,
            len({id(v) for v in obj_dict.values()}),
            len(obj_dict),
        )
        return obj_dict

    # ------------------------------------------------------------------
    # фоновая предзагрузка
    # ------------------------------------------------------------------

    def preload_async(
        self,
        client: WorkerNetClient,
        *,
        types: Optional[Sequence[str]] = None,
        include_customers: Optional[bool] = None,
        workers: Optional[int] = None,
    ) -> Dict[str, Future]:
        """Запустить get_all_* в фоне (по одному потоку на тип).

        Основной поток не блокируется. Повторный вызов get_all_* /
        get_all_customers дождётся соответствующего Future.

        types: список ключей — node, device, splitter, cross, cwdm, fiber, customer
        """
        try:
            from ...core.config import config_manager
            default_types = list(config_manager.preload_types)
            default_customers = bool(config_manager.preload_customers)
            default_workers = int(config_manager.preload_workers)
        except Exception:
            default_types = [
                "node", "device", "splitter", "cross", "cwdm", "fiber",
            ]
            default_customers = False
            default_workers = 6

        if types is None:
            types = default_types
        if include_customers is None:
            include_customers = default_customers
        if include_customers and "customer" not in types:
            types = list(types) + ["customer"]

        # default 1: Session клиента не thread-safe; под _api_lock всё равно сериализуется
        n_workers = workers if workers is not None else 1
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
        # ключи, под которыми get_all_objects хранит данные
        cache_keys = {
            "node": ["node"],
            "device": [TYPE_OLT, TYPE_SWITCH, "device"],
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
            # уже в кэше?
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
        """Дождаться завершения всех фоновых загрузок."""
        for key, fut in list(self._preload_futures.items()):
            try:
                fut.result(timeout=timeout)
            except Exception as e:
                _get_logger().warning("preload %s: %s", key, e)

    def preload_status(self) -> Dict[str, str]:
        """Статус фоновых задач: pending / done / error."""
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

    # ------------------------------------------------------------------
    # inventory / lengths / catalog
    # ------------------------------------------------------------------

    def get_inventory(
        self, client: WorkerNetClient, inventory_id: Union[int, str]
    ) -> Optional[Any]:
        if inventory_id in self._inventory:
            return self._inventory[inventory_id]

        def loader() -> Optional[Any]:
            try:
                result = client.Inventory.get_inventory(id=int(inventory_id))
                return result[0] if result and len(result) > 0 else None
            except Exception as e:
                _get_logger().warning(
                    f"Не удалось загрузить inventory {inventory_id}: {e}"
                )
                return None

        inv = loader()
        if inv is not None:
            self._inventory[inventory_id] = inv
        return inv

    def get_inventory_catalog_item(
        self, client: WorkerNetClient, catalog_id: Union[int, str]
    ) -> Optional[Any]:
        if catalog_id in self._inventory_catalog:
            return self._inventory_catalog[catalog_id]

        def loader() -> Optional[Any]:
            try:
                result = client.Inventory.get_inventory_catalog(id=int(catalog_id))
                return result[0] if result and len(result) > 0 else None
            except Exception as e:
                _get_logger().warning(
                    f"Не удалось загрузить inventory catalog {catalog_id}: {e}"
                )
                return None

        item = loader()
        if item is not None:
            self._inventory_catalog[catalog_id] = item
        return item

    def preload_splitter_inventory(self, client: WorkerNetClient) -> None:
        """Подтянуть inventory для всех известных сплиттеров."""
        splitters = self.get_all_splitters(client)
        for sp in splitters.values():
            inv_id = getattr(sp, "inventory_id", None)
            if inv_id is not None:
                inv = self.get_inventory(client, inv_id)
                if inv is not None:
                    cid = getattr(inv, "catalog_id", None)
                    if cid is not None:
                        self.get_inventory_catalog_item(client, cid)

    def get_fiber_length_m(
        self, fiber_id: Union[int, str]
    ) -> Optional[Tuple[Optional[float], str]]:
        return self._fiber_lengths.get(fiber_id)

    def set_fiber_length_m(
        self,
        fiber_id: Union[int, str],
        length_m: Optional[float],
        source: str,
    ) -> None:
        self._fiber_lengths[fiber_id] = (length_m, source)

    def get_geo_length(
        self, client: WorkerNetClient, fiber_id: int
    ) -> Optional[float]:
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
        """Все кабели по всем типам линий. Один проход, один ключ TYPE_FIBER."""
        with self._lock:
            if TYPE_FIBER in self._all_objects:
                return self._all_objects[TYPE_FIBER]

        loading = _loading_types()
        fut = self._preload_futures.get("fiber") or self._preload_futures.get(TYPE_FIBER)
        if fut is not None and not fut.done() and TYPE_FIBER not in loading:
            try:
                fut.result()
            except Exception:
                pass
            with self._lock:
                if TYPE_FIBER in self._all_objects:
                    return self._all_objects[TYPE_FIBER]

        loading.add(TYPE_FIBER)
        try:
            logger = _get_logger()
            timeout = self._bulk_timeout(TYPE_FIBER)
            result: Dict[Union[int, str], Any] = {}
            with self._api_lock:
                with self._lock:
                    if TYPE_FIBER in self._all_objects:
                        return self._all_objects[TYPE_FIBER]
                try:
                    with _temporary_timeout(timeout):
                        catalog = client.Fiber.catalog_types_get()
                    for cab_type in _result_to_objects(catalog):
                        type_id = _extract_obj_id(cab_type)
                        if type_id is None:
                            continue
                        try:
                            with _temporary_timeout(timeout):
                                batch = client.Fiber.get_list(
                                    cable_line_type_id=type_id
                                )
                            objects = _result_to_objects(batch)
                        except Exception as e:
                            logger.error(
                                "Ошибка загрузки fiber cable_line_type_id=%s: %s",
                                type_id, e,
                            )
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
                self._all_objects[TYPE_FIBER] = result
            logger.info(
                "DataCache: загружено %s fiber (timeout=%ss)",
                len({id(v) for v in result.values()}),
                timeout,
            )
            return result
        finally:
            loading.discard(TYPE_FIBER)

    def get_all_devices(self, client: WorkerNetClient) -> Dict[int, Any]:
        result: Dict[int, Any] = {}
        for dev_type in [TYPE_OLT, TYPE_SWITCH]:
            devices = self.get_all_objects(
                dev_type,
                lambda dt=dev_type: client.Device.get_data(object_type=dt),
            )
            result.update(devices)
        return result

    def get_all_customers(self, client: WorkerNetClient) -> Dict[int, Any]:
        """Список абонентов — долгий запрос, таймаут customer_list_timeout."""
        return self.get_all_objects(
            TYPE_CUSTOMER, lambda: client.Module.get_user_list()
        )

    def get_device(
        self, client: WorkerNetClient, obj_type: str, obj_id: int
    ) -> Optional[Any]:
        def loader() -> Optional[Any]:
            try:
                result = client.Device.get_data(
                    object_type=obj_type, object_id=obj_id
                )
                return result[0] if result and len(result) > 0 else None
            except Exception as e:
                _get_logger().warning(
                    f"Не удалось загрузить устройство {obj_type}:{obj_id}: {e}"
                )
                return None

        return self.get_or_load_object(obj_type, obj_id, loader)

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
                _get_logger().warning(
                    f"Не удалось загрузить сплиттер {obj_id}: {e}"
                )
                return None

        return self.get_or_load_object(TYPE_SPLITTER, obj_id, loader)

    def get_fiber(self, client: WorkerNetClient, obj_id: int) -> Optional[Any]:
        def loader() -> Optional[Any]:
            try:
                result = client.Fiber.get_list(object_id=obj_id)
                return result[0] if result and len(result) > 0 else None
            except Exception as e:
                _get_logger().warning(
                    f"Не удалось загрузить кабель {obj_id}: {e}"
                )
                return None

        return self.get_or_load_object(TYPE_FIBER, obj_id, loader)

    def get_customer(self, client: WorkerNetClient, obj_id: int) -> Optional[Any]:
        def loader() -> Optional[Any]:
            try:
                result = client.Customer.get_data(customer_id=obj_id)
                return result[0] if result and len(result) > 0 else None
            except Exception as e:
                _get_logger().warning(
                    f"Не удалось загрузить абонента {obj_id}: {e}"
                )
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
        self,
        client: WorkerNetClient,
        obj_type: str,
        obj_id: Union[int, str],
        is_finish_data: int = 0,
    ) -> List[Any]:
        actual_type = TYPE_SWITCH if obj_type in DEVICE_TYPES else obj_type

        def loader() -> List[Any]:
            api_type = actual_type
            api_id = str(obj_id) if api_type == TYPE_CROSS else int(obj_id)
            try:
                result = client.Commutation.get_data(
                    object_type=api_type,
                    object_id=api_id,
                    is_finish_data=is_finish_data,
                )
                return result.to_list() if result else []
            except Exception as e:
                _get_logger().error(
                    f"Ошибка загрузки коммутаций для {actual_type}:{obj_id}: {e}"
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
        cache = cls(preload=False)
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
        """Остановить пул фоновых загрузок."""
        if self._preload_executor is not None:
            self._preload_executor.shutdown(wait=False, cancel_futures=True)
            self._preload_executor = None
