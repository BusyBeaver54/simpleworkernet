# simpleworkernet/utils/topology/attenuation/template.py
"""Генерация/обновление attenuation.json — общая папка для всех приложений.

    ~/.config/simpleworkernet/attenuation_<host>.json

    generate_template(client, ("PLC", "FBT"))
    update_template(client, ("PLC", "FBT"))
    load_attenuation_catalog(client)
"""
from __future__ import annotations
import copy
import os
import re
import sys
from pathlib import Path
from typing import Any, Optional, Sequence, Union
from urllib.parse import urlparse
from .catalog import AttenuationCatalog
from .catalog_helpers import guess_ratio_key
from .template_fetch import (
    fetch_cables, section_ids_by_names, fetch_catalog_items, fetch_topology_splitters,
)

def _shared_config_dir() -> Path:
    """Общий каталог simpleworkernet (без имени приложения)."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".config"
    return base / "simpleworkernet"

def _safe_key(key: str) -> str:
    s = re.sub(r"[^\w.\-]+", "_", str(key).strip(), flags=re.UNICODE)
    return s.strip("._") or "default"

def client_file_key(client: Any = None, client_key: Optional[str] = None) -> str:
    """Ключ файла: явный client_key → host из WorkerNetClient → default."""
    if client_key:
        return _safe_key(client_key)
    if client is None:
        return "default"
    host = getattr(client, "host", None) or getattr(client, "_host", None)
    if not host and hasattr(client, "_url"):
        try:
            host = urlparse(str(client._url)).hostname
        except Exception:
            host = None
    return _safe_key(host or "default")

def attenuation_json_path(
    client: Any = None,
    *,
    path: Optional[Union[str, Path]] = None,
    client_key: Optional[str] = None,
) -> Path:
    """Путь: <shared>/attenuation_<host>.json (или явный path/client_key)."""
    if path is not None:
        return Path(path)
    key = client_file_key(client, client_key)
    return _shared_config_dir() / f"attenuation_{key}.json"

def load_attenuation_catalog(
    client: Any = None,
    *,
    path: Optional[Union[str, Path]] = None,
    client_key: Optional[str] = None,
) -> AttenuationCatalog:
    p = attenuation_json_path(client, path=path, client_key=client_key)
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
                ports = {"all": {"name": "equal", "attenuation": copy.deepcopy(r["equal_db"])}}
        entry = by_cat.setdefault(str(cid), {
            "name": name, "ratio": ratio or "", "ports": {},
        })
        if name and not entry.get("name"):
            entry["name"] = name
        if ratio and not entry.get("ratio"):
            entry["ratio"] = ratio
        if ports and not entry.get("ports"):
            entry["ports"] = ports
        if name:
            nentry = by_name.setdefault(name, {
                "catalog_id": str(cid), "ratio": ratio or "", "ports": {},
            })
            if ratio and not nentry.get("ratio"):
                nentry["ratio"] = ratio
            if ports and not nentry.get("ports"):
                nentry["ports"] = ports

def _apply_db(cat, client, *, splitter_catalog_names, cache=None,
              include_topology_splitters=False, fill_defaults=True, auto_fill_ratio=True):
    cat.merge_cable_catalog(fetch_cables(client))
    section_ids = section_ids_by_names(client, splitter_catalog_names)
    items = fetch_catalog_items(client, section_ids)
    _merge_catalog_items(cat, items, auto_fill_ratio=auto_fill_ratio)
    try:
        from ....core.logger import log
        log.info(
            "attenuation: секции %s → %s позиций",
            list(splitter_catalog_names), len(items),
        )
    except Exception:
        pass
    if include_topology_splitters:
        sp_list, inv, cats = fetch_topology_splitters(client, cache)
        cat.merge_splitter_inventory(sp_list, inv, cats, auto_fill_ratio=auto_fill_ratio)
    if fill_defaults:
        cat.fill_missing_with_defaults()

def generate_template(
    client,
    splitter_catalog_names: Sequence[str],
    *,
    cache=None,
    path=None,
    client_key: Optional[str] = None,
    fill_defaults=True,
    auto_fill_ratio=True,
    include_topology_splitters=False,
    overwrite=False,
) -> AttenuationCatalog:
    """Создать attenuation_<host>.json.

    splitter_catalog_names — обязательный: имена секций ТМЦ, напр. (\"PLC\", \"FBT\").
    """
    if not splitter_catalog_names:
        raise ValueError(
            "splitter_catalog_names обязателен, например (\"PLC\", \"FBT\")"
        )
    p = attenuation_json_path(client, path=path, client_key=client_key)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists() and not overwrite:
        return update_template(
            client, splitter_catalog_names,
            cache=cache, path=p, client_key=client_key,
            fill_defaults=fill_defaults, auto_fill_ratio=auto_fill_ratio,
            include_topology_splitters=include_topology_splitters,
        )
    cat = AttenuationCatalog.with_defaults()
    _apply_db(
        cat, client, splitter_catalog_names=splitter_catalog_names, cache=cache,
        include_topology_splitters=include_topology_splitters,
        fill_defaults=fill_defaults, auto_fill_ratio=auto_fill_ratio,
    )
    cat.save(p)
    return cat

def update_template(
    client,
    splitter_catalog_names: Sequence[str],
    *,
    cache=None,
    path=None,
    client_key: Optional[str] = None,
    fill_defaults=True,
    auto_fill_ratio=True,
    include_topology_splitters=False,
) -> AttenuationCatalog:
    """Дописать новые объекты из БД этого клиента (не затирая правки).

    splitter_catalog_names — обязательный: имена секций ТМЦ, напр. (\"PLC\", \"FBT\").
    """
    if not splitter_catalog_names:
        raise ValueError(
            "splitter_catalog_names обязателен, например (\"PLC\", \"FBT\")"
        )
    p = attenuation_json_path(client, path=path, client_key=client_key)
    p.parent.mkdir(parents=True, exist_ok=True)
    cat = (
        AttenuationCatalog.from_json(p)
        if p.exists()
        else AttenuationCatalog.with_defaults()
    )
    before = set(cat.unset_profiles())
    _apply_db(
        cat, client, splitter_catalog_names=splitter_catalog_names, cache=cache,
        include_topology_splitters=include_topology_splitters,
        fill_defaults=fill_defaults, auto_fill_ratio=auto_fill_ratio,
    )
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
