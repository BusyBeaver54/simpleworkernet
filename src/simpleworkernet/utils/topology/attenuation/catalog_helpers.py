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
    """Обратная совместимость: (db_calc, db_max)."""
    t = _as_db_triple(value)
    if t is None:
        return None
    return t[1], t[2]


def _as_db_triple(value: Any) -> Optional[Tuple[float, float, float]]:
    """(db_min, db_calc, db_max) из числа или dict."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        v = float(value)
        return v, v, v
    if isinstance(value, dict):
        if "db" in value or "db_min" in value or "db_max" in value:
            calc = value.get("db")
            mn = value.get("db_min")
            mx = value.get("db_max")
            if calc is None and mn is not None and mx is not None:
                calc = (float(mn) + float(mx)) / 2.0
            if calc is None and mn is not None:
                calc = float(mn)
            if calc is None and mx is not None:
                calc = float(mx)
            if calc is None:
                return None
            calc = float(calc)
            mn = float(mn) if mn is not None else calc
            mx = float(mx) if mx is not None else calc
            if mn > calc:
                mn = calc
            if mx < calc:
                mx = calc
            return mn, calc, mx
        # вложенный attenuation уже развёрнут снаружи
    return None


def _pick_wl(table: Dict[str, Any], wavelength_nm: int, *, context: str = ""):
    """Вернуть (db_min, db_calc, db_max, used_wavelength) или None."""
    if not table:
        return None
    k = _wl_key(wavelength_nm)
    if k in table:
        triple = _as_db_triple(table[k])
        if triple is None:
            return None
        return triple[0], triple[1], triple[2], wavelength_nm
    keys: List[int] = []
    for x in table.keys():
        try:
            keys.append(int(x))
        except (TypeError, ValueError):
            continue
    if not keys:
        return None
    nearest = min(keys, key=lambda x: abs(x - wavelength_nm))
    triple = _as_db_triple(table[str(nearest)])
    if triple is None:
        return None
    ctx = f" ({context})" if context else ""
    log.info(
        "attenuation: λ=%s nm не найдена%s — используем ближайшую λ=%s nm "
        "(min=%.3f, db=%.3f, max=%.3f)",
        wavelength_nm, ctx, nearest, triple[0], triple[1], triple[2],
    )
    return triple[0], triple[1], triple[2], nearest


def _pick_wl_mode(table, wavelength_nm, *, use_max=False, use_min=False, context=""):
    """Одно значение: min / calc / max."""
    picked = _pick_wl(table, wavelength_nm, context=context)
    if picked is None:
        return None
    mn, calc, mx, _wl = picked
    if use_min:
        return mn
    if use_max:
        return mx
    return calc


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


_RATIO_DEFAULTS_CACHE = None


def load_ratio_defaults() -> dict:
    """Шаблоны ratio из package defaults.json (не в user JSON)."""
    global _RATIO_DEFAULTS_CACHE
    if _RATIO_DEFAULTS_CACHE is not None:
        return _RATIO_DEFAULTS_CACHE
    try:
        import json
        data = json.loads(_DEFAULTS_PATH.read_text(encoding="utf-8"))
        sp = data.get("splitters") or {}
        if isinstance(sp, dict):
            _RATIO_DEFAULTS_CACHE = sp.get("ratio_defaults") or {}
        else:
            _RATIO_DEFAULTS_CACHE = {}
    except Exception:
        _RATIO_DEFAULTS_CACHE = {}
    return _RATIO_DEFAULTS_CACHE


def ports_from_ratio_key(ratio_key: Optional[str]) -> dict:
    if not ratio_key:
        return {}
    rd = load_ratio_defaults()
    # алиасы: 1x2_equal → симметричный 50/50 (в defaults нет 1x2_equal)
    aliases = {
        "1x2_equal": "1x2_50/50",
        "1x2": "1x2_50/50",
    }
    key = aliases.get(str(ratio_key).strip(), ratio_key)
    entry = rd.get(key) or rd.get(ratio_key) or {}
    return dict(entry.get("ports") or {})


def guess_ratio_key(name: str) -> Optional[str]:
    """Определить ключ ratio по имени каталога / модели сплиттера."""
    if not name:
        return None
    for pat, key in _RATIO_PATTERNS:
        if pat.search(name):
            return key
    return None


_RATIO_PATTERNS = [
    (re.compile(r"(?:^|[^\d])5\s*[/x:]\s*95(?:[^\d]|$)", re.I), "1x2_5/95"),
    (re.compile(r"(?:^|[^\d])95\s*[/x:]\s*5(?:[^\d]|$)", re.I), "1x2_5/95"),
    (re.compile(r"(?:^|[^\d])10\s*[/x:]\s*90(?:[^\d]|$)", re.I), "1x2_10/90"),
    (re.compile(r"(?:^|[^\d])90\s*[/x:]\s*10(?:[^\d]|$)", re.I), "1x2_10/90"),
    (re.compile(r"(?:^|[^\d])15\s*[/x:]\s*85(?:[^\d]|$)", re.I), "1x2_15/85"),
    (re.compile(r"(?:^|[^\d])85\s*[/x:]\s*15(?:[^\d]|$)", re.I), "1x2_15/85"),
    (re.compile(r"(?:^|[^\d])20\s*[/x:]\s*80(?:[^\d]|$)", re.I), "1x2_20/80"),
    (re.compile(r"(?:^|[^\d])80\s*[/x:]\s*20(?:[^\d]|$)", re.I), "1x2_20/80"),
    (re.compile(r"(?:^|[^\d])25\s*[/x:]\s*75(?:[^\d]|$)", re.I), "1x2_25/75"),
    (re.compile(r"(?:^|[^\d])75\s*[/x:]\s*25(?:[^\d]|$)", re.I), "1x2_25/75"),
    (re.compile(r"(?:^|[^\d])30\s*[/x:]\s*70(?:[^\d]|$)", re.I), "1x2_30/70"),
    (re.compile(r"(?:^|[^\d])70\s*[/x:]\s*30(?:[^\d]|$)", re.I), "1x2_30/70"),
    (re.compile(r"(?:^|[^\d])35\s*[/x:]\s*65(?:[^\d]|$)", re.I), "1x2_35/65"),
    (re.compile(r"(?:^|[^\d])65\s*[/x:]\s*35(?:[^\d]|$)", re.I), "1x2_35/65"),
    (re.compile(r"(?:^|[^\d])40\s*[/x:]\s*60(?:[^\d]|$)", re.I), "1x2_40/60"),
    (re.compile(r"(?:^|[^\d])60\s*[/x:]\s*40(?:[^\d]|$)", re.I), "1x2_40/60"),
    (re.compile(r"(?:^|[^\d])45\s*[/x:]\s*55(?:[^\d]|$)", re.I), "1x2_45/55"),
    (re.compile(r"(?:^|[^\d])55\s*[/x:]\s*45(?:[^\d]|$)", re.I), "1x2_45/55"),
    (re.compile(r"(?:^|[^\d])50\s*[/x:]\s*50(?:[^\d]|$)", re.I), "1x2_50/50"),
    (re.compile(r"1\s*[x×*]\s*64\b", re.I), "1x64_equal"),
    (re.compile(r"1\s*[x×*]\s*32\b", re.I), "1x32_equal"),
    (re.compile(r"1\s*[x×*]\s*24\b", re.I), "1x24_equal"),
    (re.compile(r"1\s*[x×*]\s*16\b", re.I), "1x16_equal"),
    (re.compile(r"1\s*[x×*]\s*12\b", re.I), "1x12_equal"),
    (re.compile(r"1\s*[x×*]\s*8\b", re.I), "1x8_equal"),
    (re.compile(r"1\s*[x×*]\s*6\b", re.I), "1x6_equal"),
    (re.compile(r"1\s*[x×*]\s*4\b", re.I), "1x4_equal"),
    (re.compile(r"1\s*[x×*]\s*3\b", re.I), "1x3_equal"),
    (re.compile(r"1\s*[x×*]\s*2\b", re.I), "1x2_50/50"),
]
