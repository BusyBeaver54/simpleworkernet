# simpleworkernet/utils/topology/attenuation/length.py
"""Определение длины кабельной линии."""

from __future__ import annotations

import math
from typing import Any, Optional, Tuple

from ....models.primitives import GeoPoint


def _as_positive(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        v = float(value)
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


def path_length_m(path: Any, slack_k: float = 1.0) -> Optional[float]:
    """Сумма расстояний по List[GeoPoint] / tuple, км→м через haversine * 1000."""
    if not path:
        return None
    try:
        points = list(path)
    except TypeError:
        return None
    if len(points) < 2:
        return None

    total_km = 0.0
    prev: Optional[GeoPoint] = None
    for p in points:
        try:
            gp = p if isinstance(p, GeoPoint) else GeoPoint(p)
        except Exception:
            continue
        if prev is not None:
            total_km += prev.distance_to(gp)
        prev = gp
    if total_km <= 0:
        return None
    return total_km * 1000.0 * float(slack_k)


def resolve_fiber_length_m(
    fiber_obj: Any,
    *,
    slack_k: float = 1.03,
    geo_length_api: Optional[float] = None,
) -> Tuple[Optional[float], str]:
    """
    Цепочка:
        opticalen2 (по волокну) → opticalen (по кабелю) → path×k → geo_api

    Returns:
        (length_m, source)
    """
    if fiber_obj is None:
        return None, "none"

    for attr, source in (("opticalen2", "opticalen2"), ("opticalen", "opticalen")):
        v = _as_positive(getattr(fiber_obj, attr, None))
        if v is not None:
            return v, source

    path = getattr(fiber_obj, "path", None)
    geo = path_length_m(path, slack_k=slack_k)
    if geo is not None:
        return geo, "geo"

    api = _as_positive(geo_length_api)
    if api is not None:
        return api * slack_k, "geo_api"

    return None, "none"
