# simpleworkernet/utils/topology/attenuation/catalog.py
"""Каталог профилей затухания."""
from __future__ import annotations
from .catalog_core import CatalogCoreMixin
from .catalog_splitters import CatalogSplittersMixin
from .catalog_resolve import CatalogResolveMixin
from .catalog_merge import CatalogMergeMixin
from .catalog_fill import CatalogFillMixin
from .catalog_force import CatalogForceMixin
from .catalog_io import CatalogIOMixin
from .catalog_helpers import guess_ratio_key

__all__ = ["AttenuationCatalog", "guess_ratio_key"]


class AttenuationCatalog(
    CatalogCoreMixin,
    CatalogSplittersMixin,
    CatalogResolveMixin,
    CatalogMergeMixin,
    CatalogFillMixin,
    CatalogForceMixin,
    CatalogIOMixin,
):
    """force(id) → name → instance → catalog → ratio → estimated."""
    pass
