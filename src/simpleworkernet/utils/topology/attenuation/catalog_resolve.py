# simpleworkernet/utils/topology/attenuation/catalog_resolve.py
"""splitter_port_db: force → name → instance → catalog → ratio → estimated."""
from __future__ import annotations
import math
import re
from typing import Any, Optional, Tuple
from .catalog_helpers import (
    _as_db_pair, _pick_wl, guess_ratio_key, ports_from_ratio_key,
)


def _topology_to_ratio_key(topology_type):
    if not topology_type:
        return None
    s = str(topology_type).strip().lower().replace(" ", "")
    m = re.match(r"^(\d+)x(\d+)$", s)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if a == 1 and b >= 2:
            return f"1x{b}_equal"
        if b == 1 and a >= 2:
            return f"1x{a}_equal"
    return guess_ratio_key(str(topology_type)) or None


def _port_name_from_entry(entry: Any, port=None) -> Optional[str]:
    """Имя порта из записи ports[N] каталога."""
    if entry is None:
        return None
    if isinstance(entry, dict):
        n = entry.get("name") or entry.get("title") or entry.get("label")
        if n not in (None, ""):
            return str(n)
    return None


def _lookup_port_entry(ports: dict, *, port=None, port_name=None):
    """Найти entry порта; возвращает (entry, resolved_port_name)."""
    if not ports:
        return None, None
    ports = {str(k): v for k, v in ports.items()}
    entry = None
    resolved_name = None

    if port is not None and str(port) in ports:
        entry = ports[str(port)]
        resolved_name = _port_name_from_entry(entry, port=port)

    if entry is None and port_name:
        pn = str(port_name).strip().lower()
        for k, p in ports.items():
            if isinstance(p, dict) and str(p.get("name", "")).strip().lower() == pn:
                entry = p
                resolved_name = str(p.get("name"))
                break
        if entry is None and str(port_name) in ports:
            entry = ports[str(port_name)]
            resolved_name = _port_name_from_entry(entry) or str(port_name)

    if entry is None and "all" in ports:
        entry = ports["all"]
        resolved_name = _port_name_from_entry(entry) or resolved_name or "all"

    if entry is None and len(ports) == 1:
        k, entry = next(iter(ports.items()))
        resolved_name = _port_name_from_entry(entry) or resolved_name

    return entry, resolved_name


class CatalogResolveMixin:
    def splitter_port_db(
        self, *,
        splitter_id=None, catalog_id=None, catalog_name=None, ratio_key=None,
        topology_type=None, port=None, port_name=None, port_count_out=0,
        wavelength_nm=1550, use_max=False, prefer_name: bool = True,
    ) -> Tuple[float, str, Optional[str]]:
        """Затухание порта сплиттера.

        Returns:
            (db, source, port_name)
            source: force | name | instance | catalog | ratio:<key> | estimated
            port_name: имя порта из JSON (например "50%", "95%") или None

        Порядок (prefer_name=True):
        force(id) → JSON по **name** → JSON по id → catalog_id → ratio → estimated
        """
        # 1. force по id
        if splitter_id is not None:
            forced = self._data.get("force", {}).get("splitters", {}).get(str(splitter_id))
            if forced:
                db, pn = self._force_port_db(
                    forced, port=port, port_name=port_name,
                    wavelength_nm=wavelength_nm, use_max=use_max,
                    context=f"force splitter:{splitter_id}",
                )
                if db is not None:
                    return db, "force", pn or port_name

        # 2. поиск записи: сначала по name, потом по id / catalog_id
        inst = None
        match_kind = None  # name | instance | catalog
        if prefer_name and catalog_name:
            inst = self._find_splitter(catalog_name=catalog_name)
            if inst is not None:
                match_kind = "name"
        if inst is None and splitter_id is not None:
            inst = self._find_splitter(splitter_id=splitter_id)
            if inst is not None:
                match_kind = "instance"
        if inst is None and catalog_name:
            inst = self._find_splitter(catalog_name=catalog_name)
            if inst is not None:
                match_kind = "name"
        if inst is None and catalog_id is not None:
            inst = self._find_splitter(catalog_id=catalog_id)
            if inst is not None:
                match_kind = "catalog"

        if inst is not None:
            ports = inst.get("ports") or {}
            # если ports пуст — подтянуть из ratio записи / имени
            if not ports:
                rk = inst.get("ratio") or ratio_key
                if not rk and inst.get("name"):
                    rk = guess_ratio_key(str(inst["name"]))
                if not rk and catalog_name:
                    rk = guess_ratio_key(str(catalog_name))
                if rk:
                    ports = ports_from_ratio_key(rk) or {}
            if ports:
                ctx = f"splitter name={inst.get('name') or catalog_name or splitter_id}"
                db, pn = self._resolve_port_db(
                    ports, port=port, port_name=port_name,
                    wavelength_nm=wavelength_nm, use_max=use_max, context=ctx,
                )
                if db is not None:
                    src = match_kind or "instance"
                    return db, src, pn or port_name

        # 3. ratio / topology (имя не найдено в JSON, но ratio угадан)
        rk = ratio_key or _topology_to_ratio_key(topology_type)
        if not rk and catalog_name:
            rk = guess_ratio_key(str(catalog_name))
        if rk:
            ports = ports_from_ratio_key(rk)
            if ports:
                db, pn = self._resolve_port_db(
                    ports, port=port, port_name=port_name,
                    wavelength_nm=wavelength_nm, use_max=use_max,
                    context=f"ratio:{rk}",
                )
                if db is not None:
                    return db, f"ratio:{rk}", pn or port_name

        # 4. оценка по числу выходов
        n = int(port_count_out or 0)
        if n <= 1 and topology_type:
            m = re.match(r"^(\d+)x(\d+)$", str(topology_type).strip().lower())
            if m:
                n = max(int(m.group(1)), int(m.group(2)))
        n = max(n, 1)
        ideal = 10.0 * math.log10(n) if n > 1 else 0.0
        return ideal + self.splitter_excess_db(), "estimated", port_name

    def _force_port_db(
        self, forced_node, *, port, port_name, wavelength_nm, use_max, context,
    ):
        """Returns (db, port_name)."""
        val = None
        pn = None
        if port is not None and str(port) in forced_node:
            val = forced_node[str(port)]
        elif port_name and isinstance(forced_node.get("by_name"), dict):
            val = forced_node["by_name"].get(port_name)
            pn = port_name
        elif port_name and port_name in forced_node:
            val = forced_node[port_name]
            pn = port_name
        elif "all" in forced_node:
            val = forced_node["all"]
            pn = "all"
        if val is None:
            return None, None
        if isinstance(val, (int, float)):
            return float(val), pn
        pair = _as_db_pair(val)
        if pair:
            return (pair[1] if use_max else pair[0]), pn
        if isinstance(val, dict):
            from .catalog_helpers import _port_entry_attenuation
            pn = pn or _port_name_from_entry(val)
            att = _port_entry_attenuation(val)
            if att:
                picked = _pick_wl(att, wavelength_nm, context=context)
                if picked:
                    return (picked[1] if use_max else picked[0]), pn
            picked = _pick_wl(val, wavelength_nm, context=context)
            if picked:
                return (picked[1] if use_max else picked[0]), pn
        return None, None

    def _resolve_port_db(
        self, ports, *, port, port_name, wavelength_nm, use_max, context,
    ):
        """Returns (db, resolved_port_name)."""
        from .catalog_helpers import _pick_wl, _port_entry_attenuation
        entry, resolved_name = _lookup_port_entry(
            ports, port=port, port_name=port_name,
        )
        if entry is None:
            return None, None
        if isinstance(entry, (int, float)):
            return float(entry), resolved_name
        att = _port_entry_attenuation(entry)
        if att is None:
            pair = _as_db_pair(entry)
            if pair:
                return (pair[1] if use_max else pair[0]), resolved_name
            return None, resolved_name
        picked = _pick_wl(att, wavelength_nm, context=context)
        if picked is None:
            return None, resolved_name
        return (picked[1] if use_max else picked[0]), resolved_name
