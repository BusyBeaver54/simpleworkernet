# simpleworkernet/utils/topology/attenuation/catalog.py
"""Каталог профилей затухания.

Встроенный defaults.json — базовые ratio и α волокна.
Пользовательский JSON:
    cat = generate_template(client, path="attenuation.json")
    # правит ports / db_per_km вручную
    cat = AttenuationCatalog.from_json("attenuation.json")
    # новые объекты из API без затирания уже заполненных:
    cat.merge_cable_catalog(...); cat.merge_splitter_inventory(...)
    cat.save("attenuation.json")
"""
from __future__ import annotations
from .catalog_core import CatalogCoreMixin
from .catalog_splitters import CatalogSplittersMixin
from .catalog_merge import CatalogMergeMixin
from .catalog_helpers import guess_ratio_key

__all__ = ["AttenuationCatalog", "guess_ratio_key"]


class AttenuationCatalog(CatalogCoreMixin, CatalogSplittersMixin, CatalogMergeMixin):
    """force(id) → topology → catalog_id → catalog_name → ratio → estimated."""
    pass
