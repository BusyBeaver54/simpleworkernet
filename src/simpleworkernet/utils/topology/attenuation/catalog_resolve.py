# simpleworkernet/utils/topology/attenuation/catalog_resolve.py
"""splitter_port_db: force → name → instance → catalog → ratio → estimated."""
from __future__ import annotations
import math
import re
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


class CatalogResolveMixin:
    def splitter_port_db(
        self, *,
        splitter_id=None, catalog_id=None, catalog_name=None, ratio_key=None,
        topology_type=None, port=None, port_name=None, port_count_out=0,
        wavelength_nm=1550, use_max=False, prefer_name: bool = True,
    ):
        """Затухание порта сплиттера.

        Порядок (prefer_name=True, по умолчанию):
        force(id) → JSON по **name** → JSON по id → catalog_id → ratio → estimated
        """
        # 1. force по id
        if splitter_id is not None:
            forced = self._data.get("force", {}).get("splitters", {}).get(str(splitter_id))
            if forced:
                db = self._force_port_db(
                    forced, port=port, port_name=port_name,
                    wavelength_nm=wavelength_nm, use_max=use_max,
                    context=f"force splitter:{splitter_id}",
                )
                if db is not None:
                    return db, "force"

        # 2. поиск записи: сначала по name, потом по id
        inst = None
        if prefer_name and catalog_name:
            inst = self._find_splitter(catalog_name=catalog_name)
        if inst is None and splitter_id is not None:
            inst = self._find_splitter(splitter_id=splitter_id)
        if inst is None and catalog_name:
            inst = self._find_splitter(catalog_name=catalog_name)
        if inst is None and catalog_id is not None:
            inst = self._find_splitter(catalog_id=catalog_id)

        if inst and inst.get("ports"):
            ctx = f"splitter name={inst.get('name') or catalog_name or splitter_id}"
            db = self._resolve_port_db(
                inst["ports"], port=port, port_name=port_name,
                wavelength_nm=wavelength_nm, use_max=use_max, context=ctx,
            )
            if db is not None:
                src = "name" if (catalog_name and str(inst.get("name") or "") == str(catalog_name)) else "instance"
                return db, src

        # 3. ratio / topology
        rk = ratio_key or _topology_to_ratio_key(topology_type)
        if not rk and catalog_name:
            rk = guess_ratio_key(str(catalog_name))
        if rk:
            ports = ports_from_ratio_key(rk)
            if ports:
                db = self._resolve_port_db(
                    ports, port=port, port_name=port_name,
                    wavelength_nm=wavelength_nm, use_max=use_max,
                    context=f"ratio:{rk}",
                )
                if db is not None:
                    return db, f"ratio:{rk}"

        # 4. оценка по числу выходов
        n = int(port_count_out or 0)
        if n <= 1 and topology_type:
            m = re.match(r"^(\d+)x(\d+)$", str(topology_type).strip().lower())
            if m:
                n = max(int(m.group(1)), int(m.group(2)))
        n = max(n, 1)
        ideal = 10.0 * math.log10(n) if n > 1 else 0.0
        return ideal + self.splitter_excess_db(), "estimated"

    def _force_port_db(self, forced_node, *, port, port_name, wavelength_nm, use_max, context):
        val = None
        if port is not None and str(port) in forced_node:
            val = forced_node[str(port)]
        elif port_name and isinstance(forced_node.get("by_name"), dict):
            val = forced_node["by_name"].get(port_name)
        elif "all" in forced_node:
            val = forced_node["all"]
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val)
        pair = _as_db_pair(val)
        if pair:
            return pair[1] if use_max else pair[0]
        if isinstance(val, dict):
            # может быть attenuation map или port entry
            from .catalog_helpers import _port_entry_attenuation
            att = _port_entry_attenuation(val)
            if att:
                picked = _pick_wl(att, wavelength_nm, context=context)
                if picked:
                    return picked[1] if use_max else picked[0]
            picked = _pick_wl(val, wavelength_nm, context=context)
            if picked:
                return picked[1] if use_max else picked[0]
        return None

    def _resolve_port_db(
        self, ports, *, port, port_name, wavelength_nm, use_max, context,
    ):
        from .catalog_helpers import _pick_wl, _port_entry_attenuation
        if not ports:
            return None
        ports = {str(k): v for k, v in ports.items()}
        entry = None
        if port is not None and str(port) in ports:
            entry = ports[str(port)]
        if entry is None and port_name:
            for p in ports.values():
                if isinstance(p, dict) and str(p.get("name", "")).lower() == str(port_name).lower():
                    entry = p
                    break
            if entry is None and str(port_name) in ports:
                entry = ports[str(port_name)]
        if entry is None and "all" in ports:
            entry = ports["all"]
        if entry is None and len(ports) == 1:
            entry = next(iter(ports.values()))
        if entry is None:
            return None
        if isinstance(entry, (int, float)):
            return float(entry)
        att = _port_entry_attenuation(entry)
        if att is None:
            pair = _as_db_pair(entry)
            return (pair[1] if use_max else pair[0]) if pair else None
        picked = _pick_wl(att, wavelength_nm, context=context)
        if picked is None:
            return None
        return picked[1] if use_max else picked[0]
