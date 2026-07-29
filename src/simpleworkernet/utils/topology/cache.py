# simpleworkernet/utils/topology/cache.py
"""
DataCache — слой загрузки и кэширования объектов/коммутаций API.

Не синглтон: создаётся явно (или через Topology).
Можно шарить один экземпляр между несколькими Topology.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple, Union

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


def _get_logger():
    global _logger
    if _logger is None:
        from ...core.logger import log

        _logger = log
    return _logger


class DataCache:
    """
    Кэш объектов и коммутаций.

    Хранит:
    - _objects: {(тип, id): объект}
    - _commutations: {(тип, id): [коммутации]}
    - _all_objects: {тип: {id: объект}} — массовая загрузка
    - _inventory / _inventory_catalog — ТМЦ для сплиттеров
    - _fiber_lengths: {fiber_id: (length_m, source)}
    - _geo_lengths: {fiber_id: m} — ответ Fiber.get_geo_length
    - _cable_catalog: catalog_cables_get
    """

    def __init__(self) -> None:
        self._objects: Dict[Tuple[str, Union[int, str]], Any] = {}
        self._commutations: Dict[Tuple[str, Union[int, str]], List[Any]] = {}
        self._all_objects: Dict[str, Dict[Union[int, str], Any]] = {}
        self._inventory: Dict[Union[int, str], Any] = {}
        self._inventory_catalog: Dict[Union[int, str], Any] = {}
        self._fiber_lengths: Dict[Union[int, str], Tuple[Optional[float], str]] = {}
        self._geo_lengths: Dict[int, Optional[float]] = {}
        self._cable_catalog: Optional[List[Any]] = None

    # ------------------------------------------------------------------
    # Базовые методы
    # ------------------------------------------------------------------

    def get_object(self, obj_type: str, obj_id: Union[int, str]) -> Optional[Any]:
        obj = self._objects.get((obj_type, obj_id))
        if obj is None and obj_type in DEVICE_TYPES:
            obj = self._objects.get(("device", obj_id))
        return obj

    def set_object(self, obj_type: str, obj_id: Union[int, str], obj: Any) -> None:
        self._objects[(obj_type, obj_id)] = obj
        if obj_type in DEVICE_TYPES:
            self._objects[("device", obj_id)] = obj

    def get_or_load_object(
        self,
        obj_type: str,
        obj_id: Union[int, str],
        loader: Callable[[], Any],
    ) -> Any:
        obj = self.get_object(obj_type, obj_id)
        if obj is None:
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
        self._commutations[(obj_type, obj_id)] = comms

    def get_or_load_commutations(
        self,
        obj_type: str,
        obj_id: Union[int, str],
        loader: Callable[[], List[Any]],
    ) -> List[Any]:
        key = (obj_type, obj_id)
        comms = self._commutations.get(key)
        if comms is None:
            comms = loader()
            if comms is not None:
                self._commutations[key] = comms
            else:
                comms = []
        return comms

    def get_all_objects(
        self, object_type: str, loader: Callable[[], List[Any]]
    ) -> Dict[Union[int, str], Any]:
        if object_type in self._all_objects:
            return self._all_objects[object_type]

        logger = _get_logger()
        try:
            result = loader()
            objects = result.to_list() if result else []
        except Exception as e:
            logger.error(f"Ошибка загрузки всех объектов типа {object_type}: {e}")
            objects = []

        obj_dict: Dict[Union[int, str], Any] = {}
        for obj in objects:
            obj_id = (
                getattr(obj, "id", None)
                or getattr(obj, "code", None)
                or getattr(obj, "uuid", None)
            )
            if obj_id is not None:
                obj_dict[obj_id] = obj
                self.set_object(object_type, obj_id, obj)

        self._all_objects[object_type] = obj_dict
        return obj_dict

    # ------------------------------------------------------------------
    # Inventory / catalog (для attenuation сплиттеров)
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

    # ------------------------------------------------------------------
    # Fiber length cache
    # ------------------------------------------------------------------

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
            # ApiRetSData[int] — может быть число или обёртка
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
            self._cable_catalog = result.to_list() if result else []
        except Exception as e:
            _get_logger().warning(f"catalog_cables_get failed: {e}")
            self._cable_catalog = []
        return self._cable_catalog

    # ------------------------------------------------------------------
    # Массовые загрузчики
    # ------------------------------------------------------------------

    def get_all_splitters(self, client: WorkerNetClient) -> Dict[int, Any]:
        return self.get_all_objects(TYPE_SPLITTER, lambda: client.Splitter.get())

    def get_all_crosses(self, client: WorkerNetClient) -> Dict[str, Any]:
        return self.get_all_objects(TYPE_CROSS, lambda: client.Cross.get_list())

    def get_all_cwdms(self, client: WorkerNetClient) -> Dict[int, Any]:
        return self.get_all_objects(TYPE_CWDM, lambda: client.Cwdm.get())

    def get_all_nodes(self, client: WorkerNetClient) -> Dict[int, Any]:
        return self.get_all_objects("node", lambda: client.Node.get())

    def get_all_fibers(self, client: WorkerNetClient) -> Dict[int, Any]:
        catalog = client.Fiber.catalog_types_get()
        result: Dict[int, Any] = {}
        for cab_type in catalog.to_list() if catalog else []:
            type_id = getattr(cab_type, "id", None)
            if type_id is not None:
                fibers = self.get_all_objects(
                    TYPE_FIBER,
                    lambda tid=type_id: client.Fiber.get_list(cable_line_type_id=tid),
                )
                result.update(fibers)
        return result

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
        return self.get_all_objects(
            TYPE_CUSTOMER, lambda: client.Module.get_user_list()
        )

    # ------------------------------------------------------------------
    # Одиночные загрузчики
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Сериализация
    # ------------------------------------------------------------------

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
        self._objects.clear()
        self._commutations.clear()
        self._all_objects.clear()
        self._inventory.clear()
        self._inventory_catalog.clear()
        self._fiber_lengths.clear()
        self._geo_lengths.clear()
        self._cable_catalog = None
