# simpleworkernet/utils/topology/attenuation/catalog_helpers.py
"""Helpers for attenuation catalog."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ....core.logger import log

_DEFAULTS_PATH = Path(__file__).with_name("defaults.json")


def _wl_key(wavelength_nm: int) -> str:
    return str(int(wavelength_nm))


def _as_db_pair(value: Any) -> Optional[Tuple[float, float]]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        v = float(value)
        return v, v
    if isinstance(value, dict) and "db" in value:
        db = float(value["db"])
        db_max = float(value["db_max"]) if value.get("db_max") is not None else db
        return db, db_max
    return None


def _pick_wl(
    table: Dict[str, Any],
    wavelength_nm: int,
    *,
    context: str = "",
) -> Optional[Tuple[float, float, int]]:
    if not table:
        return None
    k = _wl_key(wavelength_nm)
    if k in table:
        pair = _as_db_pair(table[k])
        if pair is None:
            return None
        return pair[0], pair[1], wavelength_nm
    keys: List[int] = []
    for x in table.keys():
        try:
            keys.append(int(x))
        except (TypeError, ValueError):
            continue
    if not keys:
        return None
    nearest = min(keys, key=lambda x: abs(x - wavelength_nm))
    pair = _as_db_pair(table[str(nearest)])
    if pair is None:
        return None
    ctx = f" ({context})" if context else ""
    log.info(
        "attenuation: λ=%s nm не найдена%s — используем ближайшую λ=%s nm "
        "(db=%.3f, db_max=%.3f)",
        wavelength_nm, ctx, nearest, pair[0], pair[1],
    )
    return pair[0], pair[1], nearest


def _port_entry_attenuation(entry: Any) -> Optional[Dict[str, Any]]:
    if entry is None or isinstance(entry, (int, float)):
        return None
    if isinstance(entry, dict):
        if "attenuation" in entry and isinstance(entry["attenuation"], dict):
            return entry["attenuation"]
        if any(str(k).isdigit() for k in entry.keys()):
            return entry
    return None


def _port_name(entry: Any, fallback: str = "") -> str:
    if isinstance(entry, dict) and entry.get("name"):
        return str(entry["name"])
    return fallback


_RATIO_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"(?:^|[^\d])5\s*[/x:]\s*95(?:[^\d]|$)", re.I), "1x2_5/95"),
    (re.compile(r"(?:^|[^\d])95\s*[/x:]\s*5(?:[^\d]|$)", re.I), "1x2_5/95"),
    (re.compile(r"(?:^|[^\d])10\s*[/x:]\s*90(?:[^\d]|$)", re.I), "1x2_10/90"),
    (re.compile(r"(?:^|[^\d])90\s*[/x:]\s*10(?:[^\d]|$)", re.I), "1x2_10/90"),
    (re.compile(r"(?:^|[^\d])15\s*[/x:]\s*85(?:[^\d]|$)", re.I), "1x2_15/85"),
    (re.compile(r"(?:^|[^\d])85\s*[/x:]\s*15(?:[^\d]|$)", re.I), "1x2_15/85"),
    (re.compile(r"(?:^|[^\d])20\s*[/x:]\s*80(?:[^\d]|$)", re.I), "1x2_20/80"),
    (re.compile(r"(?:^|[^\d])80\s*[/x:]\s*20(?:[^\d]|$)", re.I), "1x2_20/80"),
    (re.compile(r"(?:^|[^\d])30\s*[/x:]\s*70(?:[^\d]|$)", re.I), "1x2_30/70"),
    (re.compile(r"(?:^|[^\d])70\s*[/x:]\s*30(?:[^\d]|$)", re.I), "1x2_30/70"),
    (re.compile(r"(?:^|[^\d])40\s*[/x:]\s*60(?:[^\d]|$)", re.I), "1x2_40/60"),
    (re.compile(r"(?:^|[^\d])60\s*[/x:]\s*40(?:[^\d]|$)", re.I), "1x2_40/60"),
    (re.compile(r"(?:^|[^\d])50\s*[/x:]\s*50(?:[^\d]|$)", re.I), "1x2_50/50"),
    (re.compile(r"1\s*[x×*]\s*32\b", re.I), "1x32_equal"),
    (re.compile(r"1\s*[x×*]\s*16\b", re.I), "1x16_equal"),
    (re.compile(r"1\s*[x×*]\s*8\b", re.I), "1x8_equal"),
    (re.compile(r"1\s*[x×*]\s*4\b", re.I), "1x4_equal"),
    (re.compile(r"1\s*[x×*]\s*3\b|33\s*/\s*33\s*/\s*33", re.I), "1x3_equal"),
    (re.compile(r"1\s*[x×*]\s*2\b", re.I), "1x2_50/50"),
]


def guess_ratio_key(name: str) -> Optional[str]:
    """Определить ключ by_ratio по имени каталога / модели сплиттера."""
    if not name:
        return None
    for pat, key in _RATIO_PATTERNS:
        if pat.search(name):
            return key
    return None
