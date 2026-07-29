# simpleworkernet/utils/topology/keys.py
"""Идентификаторы объектов и интерфейсов графа."""

from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True)
class ObjKey:
    """Уникальный ключ объекта сети (тип + ID)."""

    obj_type: str
    id: Union[int, str]

    def __str__(self) -> str:
        return f"{self.obj_type}:{self.id}"


@dataclass(frozen=True)
class Interface:
    """
    Вершина графа коммутаций — интерфейс объекта.

    Для устройств (OLT, switch, ONU) и абонентов сторона не имеет
    смысла, но для единообразия используется side=1.
    """

    obj: ObjKey
    side: int
    port: int

    def __str__(self) -> str:
        return f"{self.obj} side={self.side} port={self.port}"
