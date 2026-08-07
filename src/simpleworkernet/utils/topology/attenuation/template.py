# simpleworkernet/utils/topology/attenuation/template.py
"""Генерация/обновление attenuation.json в config_dir.

    generate_template(client, catalog_names=("PLC", "FBT"), cache=cache)
    update_template(client, catalog_names=("PLC", "FBT"))
    load_attenuation_catalog()
"""
from __future__ import annotations
import copy
from pathlib import Path
from typing import Any, Optional, Sequence, Union
from .catalog import AttenuationCatalog
from .catalog_helpers import guess_ratio_key
from .template_fetch import (
    fetch_cables, section_ids_by_names, fetch_catalog_items, fetch_topology_splitters,
)

_DEFAULT_FILENAME = "attenuation.json"

def attenuation_json_path(path: Optional[Union[str, Path]] = None) -> Path:
    if path is not None:
        return Path(path)
    try:
        from ....core.config import config_manager
        return config_manager.config_dir / _DEFAULT_FILENAME
    except Exception:
        return Path.cwd() / _DEFAULT_FILENAME

def load_attenuation_catalog(path: Optional[Union[str, Path]] = None) -> AttenuationCatalog:
    p = attenuation_json_path(path)
    if p.exists():
        return AttenuationCatalog.from_json(p)
    return AttenuationCatalog.with_defaults()

def _merge_catalog_items(cat, items, *, auto_fill_ratio=True):
    by_cat = cat._data.setdefault("splitters", {}).setdefault("by_catalog_id", {})
    by_name = cat._data.setdefault("splitters", {}).setdefault("by_catalog_name", {})
    by_ratio = cat._data.get("splitters", {}).get("by_ratio", {})
    for it in items:
        cid = getattr(it, "id", None)
        if cid is None:
            continue
        name = str(getattr(it, "name", "") or "").strip()
        ratio = guess_ratio_key(name) if name else None
        ports = {}
        if auto_fill_ratio and ratio and ratio in by_ratio:
            r = by_ratio[ratio]
            if r.get("ports"):
                ports = copy.deepcopy(r["ports"])
            elif r.get("equal_db"):
                n = int(r.get("port_count") or 0)
                eq = r["equal_db"]
                ports = {str(i): {"name": f"out{i}", "attenuation": copy.deepcopy(eq)}
                         for i in range(1, max(n, 1) + 1)}
        entry = by_cat.setdefault(str(cid), {
            "name": name, "ratio": ratio or "", "ports": {}, "wavelength_nm": 1550,
        })
        if name and not entry.get("name"):
            entry["name"] = name
        if ratio and not entry.get("ratio"):
            entry["ratio"] = ratio
        if ports and not entry.get("ports"):
            entry["ports"] = ports
        if name:
            nentry = by_name.setdefault(name, {
                "catalog_id": str(cid), "ratio": ratio or "", "ports": {}, "wavelength_nm": 1550,
            })
            if ratio and not nentry.get("ratio"):
                nentry["ratio"] = ratio
            if ports and not nentry.get("ports"):
                nentry["ports"] = ports

def _apply_db(cat, client, *, cache=None, catalog_names=None,
              include_topology_splitters=False, fill_defaults=True, auto_fill_ratio=True):
    cat.merge_cable_catalog(fetch_cables(client))
    if catalog_names:
        section_ids = section_ids_by_names(client, catalog_names)
        items = fetch_catalog_items(client, section_ids)
        _merge_catalog_items(cat, items, auto_fill_ratio=auto_fill_ratio)
        try:
            from ....core.logger import log
            log.info("attenuation: секции %s → %s позиций", list(catalog_names), len(items))
        except Exception:
            pass
    if include_topology_splitters:
        sp_list, inv, cats = fetch_topology_splitters(client, cache)
        cat.merge_splitter_inventory(sp_list, inv, cats, auto_fill_ratio=auto_fill_ratio)
    if fill_defaults:
        cat.fill_missing_with_defaults()

def generate_template(
    client, *, catalog_names: Optional[Sequence[str]] = None, cache=None,
    path=None, fill_defaults=True, auto_fill_ratio=True,
    include_topology_splitters=False, overwrite=False,
) -> AttenuationCatalog:
    """Создать attenuation.json. catalog_names=(\"PLC\",\"FBT\") — секции каталога ТМЦ."""
    p = attenuation_json_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists() and not overwrite:
        return update_template(
            client, catalog_names=catalog_names, cache=cache, path=p,
            fill_defaults=fill_defaults, auto_fill_ratio=auto_fill_ratio,
            include_topology_splitters=include_topology_splitters,
        )
    cat = AttenuationCatalog.with_defaults()
    _apply_db(cat, client, cache=cache, catalog_names=catalog_names,
              include_topology_splitters=include_topology_splitters,
              fill_defaults=fill_defaults, auto_fill_ratio=auto_fill_ratio)
    cat.save(p)
    return cat

def update_template(
    client, *, catalog_names: Optional[Sequence[str]] = None, cache=None,
    path=None, fill_defaults=True, auto_fill_ratio=True,
    include_topology_splitters=False,
) -> AttenuationCatalog:
    """Дописать новые кабели/сплиттеры из БД (не затирая ports/db_per_km)."""
    p = attenuation_json_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    cat = AttenuationCatalog.from_json(p) if p.exists() else AttenuationCatalog.with_defaults()
    before = set(cat.unset_profiles())
    _apply_db(cat, client, cache=cache, catalog_names=catalog_names,
              include_topology_splitters=include_topology_splitters,
              fill_defaults=fill_defaults, auto_fill_ratio=auto_fill_ratio)
    cat.save(p)
    try:
        from ....core.logger import log
        added = set(cat.unset_profiles()) - before
        if added:
            log.info("attenuation: незаполненных профилей: %s", len(added))
        log.info("attenuation: каталог сохранён в %s", p)
    except Exception:
        pass
    return cat
