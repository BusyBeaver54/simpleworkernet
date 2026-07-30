# simpleworkernet/utils/topology/attenuation/catalog.py
"""Каталог профилей затухания (JSON / код / defaults)."""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

_DEFAULTS_PATH = Path(__file__).with_name("defaults.json")


def _wl_key(wavelength_nm: int) -> str:
    return str(int(wavelength_nm))


def _pick_wl(table: Dict[str, float], wavelength_nm: int) -> Optional[float]:
    if not table:
        return None
    k = _wl_key(wavelength_nm)
    if k in table:
        return float(table[k])
    # ближайшая длина волны
    keys = sorted(int(x) for x in table.keys())
    if not keys:
        return None
    nearest = min(keys, key=lambda x: abs(x - wavelength_nm))
    return float(table[str(nearest)])


class AttenuationCatalog:
    """
    Профили затуханий + force-overrides.

    Приоритет: force → specific profile → defaults.
    """

    def __init__(self, data: Optional[dict] = None) -> None:
        if data is None:
            data = json.loads(_DEFAULTS_PATH.read_text(encoding="utf-8"))
        self._data = data

    # ------------------------------------------------------------------
    # factory
    # ------------------------------------------------------------------

    @classmethod
    def with_defaults(cls) -> "AttenuationCatalog":
        return cls()

    @classmethod
    def from_json(cls, path: Union[str, Path]) -> "AttenuationCatalog":
        p = Path(path)
        return cls(json.loads(p.read_text(encoding="utf-8")))

    @classmethod
    def from_dict(cls, data: dict) -> "AttenuationCatalog":
        return cls(copy.deepcopy(data))

    def to_dict(self) -> dict:
        return copy.deepcopy(self._data)

    def save(self, path: Union[str, Path]) -> None:
        Path(path).write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # defaults helpers
    # ------------------------------------------------------------------

    @property
    def defaults(self) -> dict:
        return self._data.setdefault("defaults", {})

    def fiber_db_per_km(self, wavelength_nm: int) -> float:
        table = self.defaults.get("fiber_db_per_km", {})
        v = _pick_wl(table, wavelength_nm)
        return float(v) if v is not None else 0.25

    def splice_db(self) -> float:
        return float(self.defaults.get("splice_db", 0.05))

    def connector_db(self) -> float:
        return float(self.defaults.get("connector_db", 0.3))

    def adapter_db(self, adapter_type: Optional[str] = None) -> float:
        adapters = self._data.setdefault("cross_adapters", {})
        if adapter_type and adapter_type in adapters:
            return float(adapters[adapter_type])
        return float(adapters.get("default", self.defaults.get("adapter_db", 0.2)))

    def geo_slack_k(self) -> float:
        return float(self.defaults.get("geo_slack_k", 1.03))

    def splitter_excess_db(self) -> float:
        return float(self.defaults.get("splitter_excess_db", 0.5))

    # ------------------------------------------------------------------
    # fiber profiles
    # ------------------------------------------------------------------

    def set_cable(
        self,
        cabletype_id: Union[int, str],
        *,
        name: str = "",
        db_per_km: Optional[Dict[Union[int, str], float]] = None,
    ) -> None:
        cables = self._data.setdefault("cables", {})
        entry = cables.setdefault(str(cabletype_id), {})
        if name:
            entry["name"] = name
        if db_per_km is not None:
            entry["db_per_km"] = {str(k): float(v) for k, v in db_per_km.items()}

    def cable_db_per_km(
        self, cabletype_id: Optional[Union[int, str]], wavelength_nm: int
    ) -> float:
        if cabletype_id is not None:
            entry = self._data.get("cables", {}).get(str(cabletype_id))
            if entry and entry.get("db_per_km"):
                v = _pick_wl(entry["db_per_km"], wavelength_nm)
                if v is not None:
                    return float(v)
        return self.fiber_db_per_km(wavelength_nm)

    def force_fiber(self, fiber_id: Union[int, str], db_per_km: float) -> None:
        self._data.setdefault("force", {}).setdefault("fibers", {})[
            str(fiber_id)
        ] = float(db_per_km)

    def forced_fiber_db_per_km(
        self, fiber_id: Union[int, str]
    ) -> Optional[float]:
        v = self._data.get("force", {}).get("fibers", {}).get(str(fiber_id))
        return float(v) if v is not None else None

    # ------------------------------------------------------------------
    # splitter profiles
    # ------------------------------------------------------------------

    def set_splitter_by_catalog(
        self,
        catalog_id: Union[int, str],
        *,
        ports: Dict[Union[int, str], float],
        ratio: str = "",
        wavelength_nm: int = 1550,
    ) -> None:
        node = self._data.setdefault("splitters", {}).setdefault(
            "by_catalog_id", {}
        )
        node[str(catalog_id)] = {
            "ports": {str(k): float(v) for k, v in ports.items()},
            "ratio": ratio,
            "wavelength_nm": wavelength_nm,
        }

    def set_splitter_by_ratio(
        self,
        ratio_key: str,
        *,
        ports: Dict[Union[int, str], float],
        wavelength_nm: int = 1550,
    ) -> None:
        node = self._data.setdefault("splitters", {}).setdefault("by_ratio", {})
        node[ratio_key] = {
            "ports": {str(k): float(v) for k, v in ports.items()},
            "wavelength_nm": wavelength_nm,
        }

    def set_splitter_instance(
        self,
        splitter_id: Union[int, str],
        *,
        ports: Dict[Union[int, str], float],
        wavelength_nm: int = 1550,
    ) -> None:
        node = self._data.setdefault("splitters", {}).setdefault(
            "by_topology", {}
        )
        node[str(splitter_id)] = {
            "ports": {str(k): float(v) for k, v in ports.items()},
            "wavelength_nm": wavelength_nm,
        }

    def force_splitter_port(
        self,
        splitter_id: Union[int, str],
        port: int,
        db: float,
    ) -> None:
        node = self._data.setdefault("force", {}).setdefault("splitters", {})
        entry = node.setdefault(str(splitter_id), {})
        entry[str(port)] = float(db)

    def splitter_port_db(
        self,
        *,
        splitter_id: Optional[Union[int, str]] = None,
        catalog_id: Optional[Union[int, str]] = None,
        ratio_key: Optional[str] = None,
        topology_type: Optional[str] = None,
        port: int,
        port_count_out: int = 0,
        wavelength_nm: int = 1550,
    ) -> tuple[float, str]:
        """
        Возвращает (db, source).

        source: force | instance | catalog | ratio | estimated | default
        """
        # force
        if splitter_id is not None:
            forced = (
                self._data.get("force", {})
                .get("splitters", {})
                .get(str(splitter_id), {})
                .get(str(port))
            )
            if forced is not None:
                return float(forced), "force"

            inst = (
                self._data.get("splitters", {})
                .get("by_topology", {})
                .get(str(splitter_id))
            )
            if inst and str(port) in inst.get("ports", {}):
                return float(inst["ports"][str(port)]), "instance"

        if catalog_id is not None:
            cat = (
                self._data.get("splitters", {})
                .get("by_catalog_id", {})
                .get(str(catalog_id))
            )
            if cat and str(port) in cat.get("ports", {}):
                return float(cat["ports"][str(port)]), "catalog"

        if ratio_key:
            ratio = (
                self._data.get("splitters", {})
                .get("by_ratio", {})
                .get(ratio_key)
            )
            if ratio and str(port) in ratio.get("ports", {}):
                return float(ratio["ports"][str(port)]), "ratio"

        # оценка равномерного делителя
        n = max(int(port_count_out or 0), 1)
        ideal = 10.0 * math.log10(n) if n > 1 else 0.0
        return ideal + self.splitter_excess_db(), "estimated"

    # ------------------------------------------------------------------
    # generic force
    # ------------------------------------------------------------------

    def force_object(
        self, obj_type: str, obj_id: Union[int, str], db: float
    ) -> None:
        key = f"{obj_type}:{obj_id}"
        self._data.setdefault("force", {}).setdefault("objects", {})[
            key
        ] = float(db)

    def forced_object_db(
        self, obj_type: str, obj_id: Union[int, str]
    ) -> Optional[float]:
        key = f"{obj_type}:{obj_id}"
        v = self._data.get("force", {}).get("objects", {}).get(key)
        return float(v) if v is not None else None

    def force_edge(self, connect_id: int, db: float) -> None:
        self._data.setdefault("force", {}).setdefault("edges", {})[
            str(connect_id)
        ] = float(db)

    def forced_edge_db(self, connect_id: int) -> Optional[float]:
        v = self._data.get("force", {}).get("edges", {}).get(str(connect_id))
        return float(v) if v is not None else None

    # ------------------------------------------------------------------
    # template from live WorkerNet
    # ------------------------------------------------------------------

    def merge_cable_catalog(self, items: List[Any]) -> None:
        """items — Fiber.Catalog_cables_get."""
        for it in items:
            cid = getattr(it, "id", None)
            if cid is None:
                continue
            name = f"{getattr(it, 'brand', '')} {getattr(it, 'model', '')}".strip()
            cables = self._data.setdefault("cables", {})
            entry = cables.setdefault(str(cid), {})
            entry.setdefault("name", name or str(cid))
            entry.setdefault("fiber_count", getattr(it, "fiber_count", None))
            entry.setdefault(
                "cable_line_type_id", getattr(it, "cable_line_type_id", None)
            )
            entry.setdefault("db_per_km", None)  # заполнить пользователем

    def merge_splitter_inventory(
        self,
        splitters: List[Any],
        inventory_by_id: Dict[Any, Any],
        catalog_by_id: Dict[Any, Any],
    ) -> None:
        """
        Регистрирует сплиттеры из topology/API для заполнения шаблона.

        ports остаются пустыми — пользователь указывает dB.
        """
        by_cat = self._data.setdefault("splitters", {}).setdefault(
            "by_catalog_id", {}
        )
        by_topo = self._data.setdefault("splitters", {}).setdefault(
            "by_topology", {}
        )
        for sp in splitters:
            sid = getattr(sp, "id", None)
            inv_id = getattr(sp, "inventory_id", None)
            pin = getattr(sp, "port_count_in", 0) or 0
            pout = getattr(sp, "port_count_out", 0) or 0
            inv = inventory_by_id.get(inv_id) if inv_id else None
            catalog_id = getattr(inv, "catalog_id", None) if inv else None
            cat_name = ""
            if catalog_id is not None and catalog_id in catalog_by_id:
                cat_name = str(getattr(catalog_by_id[catalog_id], "name", ""))

            if catalog_id is not None:
                entry = by_cat.setdefault(
                    str(catalog_id),
                    {
                        "name": cat_name,
                        "topology": f"{pin}x{pout}",
                        "ports": {},
                        "wavelength_nm": 1550,
                    },
                )
                if cat_name and not entry.get("name"):
                    entry["name"] = cat_name

            if sid is not None:
                by_topo.setdefault(
                    str(sid),
                    {
                        "inventory_id": inv_id,
                        "catalog_id": catalog_id,
                        "name": cat_name or getattr(sp, "description", ""),
                        "topology": f"{pin}x{pout}",
                        "ports": {},
                        "wavelength_nm": 1550,
                    },
                )

    def fill_missing_with_defaults(self) -> None:
        """Подставить default fiber_db_per_km туда, где db_per_km is null."""
        default_table = self.defaults.get("fiber_db_per_km", {})
        for entry in self._data.get("cables", {}).values():
            if entry.get("db_per_km") is None:
                entry["db_per_km"] = dict(default_table)

    def unset_profiles(self) -> List[str]:
        """Список профилей без заполненных ports / db_per_km."""
        missing: List[str] = []
        for cid, entry in self._data.get("cables", {}).items():
            if not entry.get("db_per_km"):
                missing.append(f"cable:{cid}")
        for section in ("by_catalog_id", "by_topology"):
            for key, entry in (
                self._data.get("splitters", {}).get(section, {}) or {}
            ).items():
                if not entry.get("ports"):
                    missing.append(f"splitter.{section}:{key}")
        return missing
