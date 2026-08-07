# simpleworkernet/utils/topology/attenuation/template.py
"""Генерация и обновление пользовательского JSON затуханий.

Файл живёт рядом с config.json:
    ~/.config/simpleworkernet/<app>/attenuation.json

Сценарий:
    from simpleworkernet.utils.topology.attenuation.template import (
        generate_template, update_template, load_attenuation_catalog,
        attenuation_json_path,
    )

    # первый раз — создать из БД + дефолты ratio/α
    cat = generate_template(client, cache=cache)

    # позже — подтянуть новые кабели/сплиттеры, не затирая правки
    cat = update_template(client, cache=cache)

    # загрузить для расчёта
    cat = load_attenuation_catalog()
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Union

from .catalog import AttenuationCatalog

_DEFAULT_FILENAME = "attenuation.json"


def attenuation_json_path(
    path: Optional[Union[str, Path]] = None,
) -> Path:
    """Путь к attenuation.json (по умолчанию — каталог config приложения)."""
    if path is not None:
        return Path(path)
    try:
        from ....core.config import config_manager
        return config_manager.config_dir / _DEFAULT_FILENAME
    except Exception:
        return Path.cwd() / _DEFAULT_FILENAME


def load_attenuation_catalog(
    path: Optional[Union[str, Path]] = None,
) -> AttenuationCatalog:
    """
    Загрузить пользовательский JSON.
    Если файла нет — встроенные defaults (ratio + α), без записей из БД.
    """
    p = attenuation_json_path(path)
    if p.exists():
        return AttenuationCatalog.from_json(p)
    return AttenuationCatalog.with_defaults()


def _fetch_cables(client: Any) -> list:
    try:
        cables = client.Fiber.catalog_cables_get()
        return cables.to_list() if cables else []
    except Exception:
        return []


def _fetch_splitters(client: Any, cache: Any = None):
    try:
        splitters = client.Splitter.get()
        sp_list = splitters.to_list() if splitters else []
    except Exception:
        sp_list = []

    inventory_by_id = {}
    catalog_by_id = {}

    if cache is not None and hasattr(cache, "get_inventory"):
        for sp in sp_list:
            inv_id = getattr(sp, "inventory_id", None)
            if inv_id is None:
                continue
            inv = cache.get_inventory(client, inv_id)
            if inv is None:
                continue
            inventory_by_id[inv_id] = inv
            cid = getattr(inv, "catalog_id", None)
            if cid is not None and hasattr(cache, "get_inventory_catalog_item"):
                item = cache.get_inventory_catalog_item(client, cid)
                if item is not None:
                    catalog_by_id[cid] = item
        return sp_list, inventory_by_id, catalog_by_id

    for sp in sp_list:
        inv_id = getattr(sp, "inventory_id", None)
        if inv_id is None:
            continue
        try:
            inv_res = client.Inventory.get_inventory(id=inv_id)
            inv = inv_res[0] if inv_res and len(inv_res) > 0 else None
        except Exception:
            inv = None
        if inv is None:
            continue
        inventory_by_id[inv_id] = inv
        cid = getattr(inv, "catalog_id", None)
        if cid is None:
            continue
        try:
            cat_res = client.Inventory.get_inventory_catalog(id=cid)
            item = cat_res[0] if cat_res and len(cat_res) > 0 else None
            if item is not None:
                catalog_by_id[cid] = item
        except Exception:
            pass
    return sp_list, inventory_by_id, catalog_by_id


def generate_template(
    client: Any,
    *,
    cache: Any = None,
    path: Optional[Union[str, Path]] = None,
    fill_defaults: bool = True,
    auto_fill_ratio: bool = True,
    overwrite: bool = False,
) -> AttenuationCatalog:
    """
    Создать attenuation.json из БД + встроенные ratio/α.

    path=None → config_dir/attenuation.json
    overwrite=False: если файл уже есть — загрузить и только дописать новое
      (эквивалент update_template).
    """
    p = attenuation_json_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    if p.exists() and not overwrite:
        return update_template(
            client, cache=cache, path=p,
            fill_defaults=fill_defaults, auto_fill_ratio=auto_fill_ratio,
        )

    cat = AttenuationCatalog.with_defaults()
    cat.merge_cable_catalog(_fetch_cables(client))
    sp_list, inv, cats = _fetch_splitters(client, cache)
    cat.merge_splitter_inventory(
        sp_list, inv, cats, auto_fill_ratio=auto_fill_ratio
    )
    if fill_defaults:
        cat.fill_missing_with_defaults()
    cat.save(p)
    return cat


def update_template(
    client: Any,
    *,
    cache: Any = None,
    path: Optional[Union[str, Path]] = None,
    fill_defaults: bool = True,
    auto_fill_ratio: bool = True,
) -> AttenuationCatalog:
    """
    Обновить attenuation.json из БД: добавить новые кабели/сплиттеры.
    Уже заполненные ports / db_per_km не затираются.
    Если файла нет — создаёт как generate_template.
    """
    p = attenuation_json_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    if p.exists():
        cat = AttenuationCatalog.from_json(p)
    else:
        cat = AttenuationCatalog.with_defaults()

    before = set(cat.unset_profiles())
    cat.merge_cable_catalog(_fetch_cables(client))
    sp_list, inv, cats = _fetch_splitters(client, cache)
    cat.merge_splitter_inventory(
        sp_list, inv, cats, auto_fill_ratio=auto_fill_ratio
    )
    if fill_defaults:
        cat.fill_missing_with_defaults()
    cat.save(p)

    try:
        from ....core.logger import log
        after = set(cat.unset_profiles())
        added = after - before
        if added:
            log.info(
                "attenuation: добавлено незаполненных профилей: %s",
                len(added),
            )
        log.info("attenuation: каталог сохранён в %s", p)
    except Exception:
        pass
    return cat
