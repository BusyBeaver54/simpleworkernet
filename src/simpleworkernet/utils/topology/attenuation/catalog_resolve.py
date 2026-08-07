# simpleworkernet/utils/topology/attenuation/catalog_resolve.py
"""splitter_port_db resolution with priority chain."""
from __future__ import annotations
import math
from .catalog_helpers import _as_db_pair, _pick_wl, guess_ratio_key, ports_from_ratio_key

class CatalogResolveMixin:
    def splitter_port_db(
        self, *, splitter_id=None, catalog_id=None, catalog_name=None, ratio_key=None,
        topology_type=None, port=None, port_name=None, port_count_out=0,
        wavelength_nm=1550, use_max=False,
    ):
        if splitter_id is not None:
            forced_node = self._data.get("force", {}).get("splitters", {}).get(str(splitter_id), {})
            if forced_node:
                val = None
                if port is not None and str(port) in forced_node:
                    val = forced_node[str(port)]
                elif port_name and isinstance(forced_node.get("by_name"), dict):
                    val = forced_node["by_name"].get(port_name)
                elif "all" in forced_node:
                    val = forced_node["all"]
                if val is not None:
                    if isinstance(val, (int, float)):
                        return float(val), "force"
                    pair = _as_db_pair(val)
                    if pair:
                        return (pair[1] if use_max else pair[0]), "force"
                    if isinstance(val, dict):
                        picked = _pick_wl(val, wavelength_nm, context=f"force splitter:{splitter_id}")
                        if picked:
                            return (picked[1] if use_max else picked[0]), "force"
            inst = self._find_splitter(splitter_id=splitter_id)
            if inst and inst.get("ports"):
                db = self._resolve_port_db(
                    inst["ports"], port=port, port_name=port_name,
                    wavelength_nm=wavelength_nm, use_max=use_max,
                    context=f"splitter instance:{splitter_id}",
                )
                if db is not None:
                    return db, "instance"
                if ratio_key is None:
                    ratio_key = inst.get("ratio") or guess_ratio_key(inst.get("name") or "")

        if catalog_id is not None:
            cat = self._find_splitter(catalog_id=catalog_id)
            if cat and cat.get("ports"):
                db = self._resolve_port_db(
                    cat["ports"], port=port, port_name=port_name,
                    wavelength_nm=wavelength_nm, use_max=use_max,
                    context=f"splitter catalog_id:{catalog_id}",
                )
                if db is not None:
                    return db, "catalog"
                if ratio_key is None:
                    ratio_key = cat.get("ratio") or guess_ratio_key(cat.get("name") or "")

        if catalog_name:
            cat = self._find_splitter(catalog_name=catalog_name)
            if cat and cat.get("ports"):
                db = self._resolve_port_db(
                    cat["ports"], port=port, port_name=port_name,
                    wavelength_nm=wavelength_nm, use_max=use_max,
                    context=f"splitter name:{catalog_name!r}",
                )
                if db is not None:
                    return db, "catalog_name"
            if ratio_key is None:
                ratio_key = guess_ratio_key(catalog_name)

        if ratio_key:
            ports = ports_from_ratio_key(ratio_key)
            if ports:
                db = self._resolve_port_db(
                    ports, port=port, port_name=port_name,
                    wavelength_nm=wavelength_nm, use_max=use_max,
                    context=f"splitter ratio:{ratio_key}",
                )
                if db is not None:
                    return db, "ratio"

        n = max(int(port_count_out or 0), 1)
        ideal = 10.0 * math.log10(n) if n > 1 else 0.0
        return ideal + self.splitter_excess_db(), "estimated"
