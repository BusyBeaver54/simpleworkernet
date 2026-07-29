# simpleworkernet/utils/__init__.py
"""
Утилиты и декораторы для SimpleWorkerNet
"""

from .decorators import (
    api_method,
    logged_method,
    log_method,
    retry,
    cache_result,
    deprecated,
    synchronized,
    singleton,
    async_method,
    validate_args,
    timer,
    ensure_session,
    memoize,
    abstract_method,
)

from .app_name import (
    get_app_name,
    get_caller_info,
)

from .graphics import (
    SVGHandler,
    ImageHandler,
    save_svg,
    load_svg,
    is_svg,
    svg_to_png,
)

# Новый модульный пакет topology (предпочтительный импорт)
from .topology import CGraph, FNGraph, Topology

from .coordinates import geo_to_xy, geo_to_xyz, xy_to_geo

__all__ = [
    "api_method",
    "logged_method",
    "log_method",
    "retry",
    "cache_result",
    "deprecated",
    "synchronized",
    "singleton",
    "async_method",
    "validate_args",
    "timer",
    "ensure_session",
    "memoize",
    "abstract_method",
    "get_app_name",
    "get_caller_info",
    "SVGHandler",
    "ImageHandler",
    "save_svg",
    "load_svg",
    "is_svg",
    "svg_to_png",
    "CGraph",
    "FNGraph",
    "Topology",
    "geo_to_xy",
    "geo_to_xyz",
    "xy_to_geo",
]
