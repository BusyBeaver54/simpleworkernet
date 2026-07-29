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
    """

    def __init__(self) -> None:
        self._objects: Dict[Tuple[str, Union[int, str]], Any] = {}
        self._commutations: Dict[Tuple[str, Union[int, str]], List[Any]] = {}
        self._all_objects: Dict[str, Dict[Union[int, str], Any]] = {}

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
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DataCache":
        cache = cls()
        cache._objects = data.get("objects", {})
        cache._commutations = data.get("commutations", {})
        cache._all_objects = data.get("all_objects", {})
        return cache

    def clear(self) -> None:
        self._objects.clear()
        self._commutations.clear()
        self._all_objects.clear()
