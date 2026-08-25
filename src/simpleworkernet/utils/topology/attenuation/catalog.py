# simpleworkernet/utils/topology/attenuation/catalog.py
"""AttenuationCatalog — коэффициенты и правила затуханий (единый модуль)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from ....core.logger import log
import copy, json
from typing import Any, Optional
import math
from typing import Any, Optional, Tuple
import copy
import json
from typing import Union

# === catalog_helpers.py ===
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

# === catalog_core.py ===
class CatalogCoreMixin:
    def __init__(self, data=None):
        if data is None:
            data = json.loads(_DEFAULTS_PATH.read_text(encoding="utf-8"))
        self._data = data
        self._normalize_structure()

    def _normalize_structure(self):
        cables = self._data.get("cables")
        if isinstance(cables, dict) and ("by_id" in cables or "by_name" in cables):
            items, seen = [], set()
            for cid, entry in (cables.get("by_id") or {}).items():
                e = dict(entry); e["id"] = str(cid); items.append(e); seen.add(str(cid))
            for name, entry in (cables.get("by_name") or {}).items():
                cid = str(entry.get("cabletype_id") or entry.get("id") or "")
                if cid and cid in seen: continue
                e = dict(entry); e.setdefault("name", name)
                if cid: e["id"] = cid
                items.append(e)
            self._data["cables"] = items
        elif not isinstance(self._data.get("cables"), list):
            self._data["cables"] = []

        sp = self._data.get("splitters")
        if isinstance(sp, list):
            pass
        elif isinstance(sp, dict):
            items, seen_c = [], set()
            for cid, entry in (sp.pop("by_catalog_id", None) or {}).items():
                e = dict(entry); e["catalog_id"] = str(cid)
                items.append(e); seen_c.add(str(cid))
            for name, entry in (sp.pop("by_catalog_name", None) or {}).items():
                cid = str(entry.get("catalog_id") or "")
                if cid and cid in seen_c: continue
                e = dict(entry); e.setdefault("name", name)
                if cid: e["catalog_id"] = cid
                items.append(e)
            for sid, entry in (sp.pop("by_topology", None) or {}).items():
                e = dict(entry); e["id"] = str(sid); items.append(e)
            if isinstance(sp.get("items"), list):
                items.extend(sp["items"])
            self._data["splitters"] = items
        else:
            self._data["splitters"] = []

    @classmethod
    def with_defaults(cls):
        return cls()

    @classmethod
    def from_json(cls, path):
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def to_json(self, path):
        Path(path).write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    def copy(self):
        return type(self)(copy.deepcopy(self._data))

    @property
    def defaults(self):
        return self._data.setdefault("defaults", {})

    def fiber_db_per_km(self, wavelength_nm=1550, *, use_max=False, use_min=False):
        table = self.defaults.get("fiber_db_per_km", {})
        picked = _pick_wl(table, wavelength_nm, context="defaults.fiber_db_per_km")
        if picked is None:
            return 0.2
        mn, calc, mx = picked[0], picked[1], picked[2]
        if use_min:
            return mn
        if use_max:
            return mx
        return calc

    def fiber_db_triple(self, wavelength_nm=1550):
        table = self.defaults.get("fiber_db_per_km", {})
        picked = _pick_wl(table, wavelength_nm, context="defaults.fiber_db_per_km")
        if picked is None:
            return 0.2, 0.2, 0.2
        return picked[0], picked[1], picked[2]


    def set_default_wavelength(
        self, wavelength_nm: int, *, fiber_db=None, splice_db=None,
        connector_db=None, adapter_db=None,
    ) -> None:
        """Добавить/обновить значения для произвольной длины волны в defaults.

        fiber_db / splice_db / connector_db / adapter_db — число или
        {db_min, db, db_max}. Отсутствующие блоки не трогаются.
        """
        wl = _wl_key(wavelength_nm)
        if fiber_db is not None:
            table = self.defaults.setdefault("fiber_db_per_km", {})
            t = _as_db_triple(fiber_db)
            if t:
                table[wl] = {"db_min": t[0], "db": t[1], "db_max": t[2]}
        for key, val in (
            ("splice_db", splice_db),
            ("connector_db", connector_db),
            ("adapter_db", adapter_db),
        ):
            if val is None:
                continue
            cur = self.defaults.get(key)
            t = _as_db_triple(val)
            if t is None:
                continue
            entry = {"db_min": t[0], "db": t[1], "db_max": t[2]}
            # promote flat → table if needed
            if cur is None or not isinstance(cur, dict) or any(k in cur for k in ("db", "db_min", "db_max")):
                # was flat triple → convert
                base = _as_db_triple(cur) if cur is not None else t
                table = {}
                if base:
                    for default_wl in ("1270", "1310", "1490", "1550", "1610"):
                        table[default_wl] = {
                            "db_min": base[0], "db": base[1], "db_max": base[2],
                        }
                table[wl] = entry
                self.defaults[key] = table
            else:
                cur[wl] = entry


    def splice_db(self, wavelength_nm: Optional[int] = None, *, use_max=False, use_min=False):
        t = _joint_table_or_triple(self.defaults.get("splice_db", 0.05), wavelength_nm)
        if not t:
            return 0.05
        if use_min:
            return t[0]
        if use_max:
            return t[2]
        return t[1]

    def splice_db_triple(self, wavelength_nm: Optional[int] = None):
        t = _joint_table_or_triple(self.defaults.get("splice_db", 0.05), wavelength_nm)
        return t if t else (0.05, 0.05, 0.05)

    def connector_db(self, wavelength_nm: Optional[int] = None, *, use_max=False, use_min=False):
        t = _joint_table_or_triple(self.defaults.get("connector_db", 0.15), wavelength_nm)
        if not t:
            return 0.15
        if use_min:
            return t[0]
        if use_max:
            return t[2]
        return t[1]

    def connector_db_triple(self, wavelength_nm: Optional[int] = None):
        t = _joint_table_or_triple(self.defaults.get("connector_db", 0.15), wavelength_nm)
        return t if t else (0.15, 0.15, 0.15)

    def adapter_db(self, adapter_type=None, wavelength_nm: Optional[int] = None, *, use_max=False, use_min=False):
        adapters = self._data.get("cross_adapters") or {}
        raw = None
        if adapter_type:
            raw = adapters.get(adapter_type)
        if raw is None:
            raw = self.defaults.get("adapter_db")
        if raw is None:
            raw = adapters.get("default")
        if raw is None:
            raw = 0.3
        t = _joint_table_or_triple(raw, wavelength_nm)
        if not t:
            return 0.3
        if use_min:
            return t[0]
        if use_max:
            return t[2]
        return t[1]

    def adapter_db_triple(self, adapter_type=None, wavelength_nm: Optional[int] = None):
        adapters = self._data.get("cross_adapters") or {}
        raw = None
        if adapter_type:
            raw = adapters.get(adapter_type)
        if raw is None:
            raw = self.defaults.get("adapter_db")
        if raw is None:
            raw = adapters.get("default")
        if raw is None:
            raw = 0.3
        t = _joint_table_or_triple(raw, wavelength_nm)
        return t if t else (0.3, 0.3, 0.3)

    def cross_loss_mode(self) -> str:
        mode = self.defaults.get("cross_loss_mode", "adapter")
        return mode if mode in ("adapter", "connectors") else "adapter"

    def geo_slack_k(self, cabletype_id=None, *, name=None):
        """Коэффициент удлинения кабеля.

        Если для кабеля не задан — defaults.geo_slack_k (по умолчанию 1.03).
        """
        if cabletype_id is not None or name is not None:
            entry = self._find_cable(cabletype_id=cabletype_id, name=name)
            if entry is not None and entry.get("geo_slack_k") is not None:
                try:
                    return float(entry["geo_slack_k"])
                except (TypeError, ValueError):
                    pass
        return float(self.defaults.get("geo_slack_k", 1.03))

    def cable_manufacturer(self, cabletype_id=None, *, name=None) -> Optional[str]:
        entry = self._find_cable(cabletype_id=cabletype_id, name=name)
        if not entry:
            return None
        m = entry.get("manufacturer") or entry.get("vendor") or entry.get("brand")
        if m is None or m == "":
            return None
        return str(m).strip()

    def splitter_excess_db(self):
        return float(self.defaults.get("splitter_excess_db", 0.5))

    def _cables(self) -> list:
        if not isinstance(self._data.get("cables"), list):
            self._normalize_structure()
        return self._data["cables"]

    def _splitters(self) -> list:
        if not isinstance(self._data.get("splitters"), list):
            self._normalize_structure()
        return self._data["splitters"]

    def _find_cable(self, *, cabletype_id=None, name=None):
        for entry in self._cables():
            if cabletype_id is not None and str(entry.get("id")) == str(cabletype_id):
                return entry
            if name and str(entry.get("name") or "") == str(name):
                return entry
        return None

    def set_cable(
        self, cabletype_id=None, *, name="", manufacturer=None,
        geo_slack_k=None, db_per_km=None,
    ):
        """Добавить/обновить кабель.

        manufacturer — производитель (марка/бренд).
        geo_slack_k — коэффициент удлинения (если None, берётся defaults.geo_slack_k).
        db_per_km — {wavelength: db|{db_min,db,db_max}, ...}; любая λ допустима.
        """
        entry = self._find_cable(cabletype_id=cabletype_id, name=name if not cabletype_id else None)
        if entry is None:
            entry = {}
            if cabletype_id is not None:
                entry["id"] = str(cabletype_id)
            if name:
                entry["name"] = name
            self._cables().append(entry)
        if name:
            entry["name"] = name
        if cabletype_id is not None:
            entry["id"] = str(cabletype_id)
        if manufacturer is not None:
            entry["manufacturer"] = str(manufacturer).strip() or None
        if geo_slack_k is not None:
            entry["geo_slack_k"] = float(geo_slack_k)
        if db_per_km is not None:
            norm = {}
            for k, v in db_per_km.items():
                triple = _as_db_triple(v)
                if triple:
                    norm[str(k)] = {"db_min": triple[0], "db": triple[1], "db_max": triple[2]}
            entry["db_per_km"] = norm

    def cable_db_per_km(self, cabletype_id=None, wavelength_nm=1550, *, name=None, use_max=False, use_min=False):
        entry = self._find_cable(cabletype_id=cabletype_id, name=name)
        if entry and entry.get("db_per_km"):
            picked = _pick_wl(
                entry["db_per_km"], wavelength_nm,
                context=f"cable id={cabletype_id} name={name!r}",
            )
            if picked is not None:
                mn, calc, mx = picked[0], picked[1], picked[2]
                if use_min:
                    return mn
                if use_max:
                    return mx
                return calc
        return self.fiber_db_per_km(wavelength_nm, use_max=use_max, use_min=use_min)

    def cable_db_triple(self, cabletype_id=None, wavelength_nm=1550, *, name=None):
        entry = self._find_cable(cabletype_id=cabletype_id, name=name)
        if entry and entry.get("db_per_km"):
            picked = _pick_wl(
                entry["db_per_km"], wavelength_nm,
                context=f"cable id={cabletype_id} name={name!r}",
            )
            if picked is not None:
                return picked[0], picked[1], picked[2]
        return self.fiber_db_triple(wavelength_nm)

    def fiber_db_per_km_for_cable(self, cable_name=None, wavelength_nm=1550, *, use_max=False):
        return self.cable_db_per_km(name=cable_name, wavelength_nm=wavelength_nm, use_max=use_max)

    def forced_edge_db(self, connect_id):
        if connect_id is None:
            return None
        edges = self._data.get("force", {}).get("edges", {})
        val = edges.get(str(connect_id))
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val)
        t = _as_db_triple(val)
        return t[1] if t else None

# === catalog_splitters.py ===
class CatalogSplittersMixin:
    def _splitter_items(self) -> list:
        return self._splitters()

    def _find_splitter(
        self, *,
        splitter_id=None, catalog_id=None, catalog_name=None,
        inventory_id=None,
    ) -> Optional[dict]:
        items = self._splitters()

        # inventory_id — основной ключ из Splitter.inventory_id → JSON
        if inventory_id is not None:
            iid = str(inventory_id)
            for entry in items:
                if str(entry.get("inventory_id") or "") == iid:
                    return entry

        # name — case-insensitive, strip
        if catalog_name:
            cn = str(catalog_name).strip().lower()
            for entry in items:
                en = str(entry.get("name") or "").strip().lower()
                if en and en == cn:
                    return entry

        if splitter_id is not None:
            sid = str(splitter_id)
            for entry in items:
                if str(entry.get("id") or "") == sid:
                    return entry

        if catalog_id is not None:
            cid = str(catalog_id)
            # предпочтительно запись без instance id (каталожная)
            fallback = None
            for entry in items:
                if str(entry.get("catalog_id") or "") != cid:
                    continue
                if entry.get("id") is None:
                    return entry
                if fallback is None:
                    fallback = entry
            if fallback is not None:
                return fallback

        return None

    def _normalize_ports(self, ports) -> dict:
        if not ports:
            return {}
        if not isinstance(ports, dict):
            return {}
        out = {}
        for k, v in ports.items():
            key = str(k)
            if isinstance(v, (int, float)):
                out[key] = float(v)
            elif isinstance(v, dict):
                out[key] = dict(v)
            else:
                out[key] = v
        return out

    def set_splitter_by_catalog(self, catalog_id, *, ports, name="", ratio=""):
        entry = self._find_splitter(catalog_id=catalog_id)
        if entry is None:
            entry = {"catalog_id": str(catalog_id), "ports": {}}
            self._splitters().append(entry)
        entry["ports"] = self._normalize_ports(ports)
        if ratio:
            entry["ratio"] = ratio
        if name:
            entry["name"] = name

    def set_splitter_by_name(self, name, *, ports, catalog_id=None, ratio=""):
        if catalog_id is not None:
            self.set_splitter_by_catalog(catalog_id, ports=ports, name=name, ratio=ratio)
            return
        entry = self._find_splitter(catalog_name=name)
        if entry is None:
            entry = {"name": name, "ports": {}, "ratio": ratio}
            self._splitters().append(entry)
        entry["ports"] = self._normalize_ports(ports)
        if ratio:
            entry["ratio"] = ratio
        if name:
            entry["name"] = name

    def set_splitter_instance(self, splitter_id, *, ports):
        entry = self._find_splitter(splitter_id=splitter_id)
        if entry is None:
            entry = {"id": str(splitter_id), "ports": {}}
            self._splitters().append(entry)
        entry["ports"] = self._normalize_ports(ports)

    def force_splitter_port(self, splitter_id, port, db, *, port_name=None):
        entry = (
            self._data.setdefault("force", {})
            .setdefault("splitters", {})
            .setdefault(str(splitter_id), {})
        )
        val = float(db) if isinstance(db, (int, float)) else db
        entry[str(port)] = val
        if port_name:
            entry.setdefault("by_name", {})[port_name] = val

# === catalog_resolve.py ===
def _topology_to_ratio_key(topology_type):
    """topology '1xN' → ключ ratio_defaults.

    Для 1x2 в defaults нет 1x2_equal, есть 1x2_50/50 (симметричный).
    Для N>=3 — 1xN_equal.
    """
    if not topology_type:
        return None
    s = str(topology_type).strip().lower().replace(" ", "")
    m = re.match(r"^(\d+)x(\d+)$", s)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        n = b if a == 1 else (a if b == 1 else max(a, b))
        if n == 2:
            return "1x2_50/50"
        if n >= 3:
            return f"1x{n}_equal"
    return guess_ratio_key(str(topology_type)) or None


def _port_name_from_entry(entry: Any, port=None) -> Optional[str]:
    if entry is None:
        return None
    if isinstance(entry, dict):
        n = entry.get("name") or entry.get("title") or entry.get("label")
        if n not in (None, ""):
            return str(n)
    return None


def _lookup_port_entry(ports: dict, *, port=None, port_name=None):
    if not ports:
        return None, None
    ports = {str(k): v for k, v in ports.items()}
    entry = None
    resolved_name = None
    if port is not None and str(port) in ports:
        entry = ports[str(port)]
        resolved_name = _port_name_from_entry(entry, port=port)
    if entry is None and port_name:
        pn = str(port_name).strip().lower()
        for k, p in ports.items():
            if isinstance(p, dict) and str(p.get("name", "")).strip().lower() == pn:
                entry = p
                resolved_name = str(p.get("name"))
                break
        if entry is None and str(port_name) in ports:
            entry = ports[str(port_name)]
            resolved_name = _port_name_from_entry(entry) or str(port_name)
    if entry is None and "all" in ports:
        entry = ports["all"]
        resolved_name = _port_name_from_entry(entry) or resolved_name or "all"
    if entry is None and len(ports) == 1:
        k, entry = next(iter(ports.items()))
        resolved_name = _port_name_from_entry(entry) or resolved_name
    return entry, resolved_name


def _select_mode(mn, calc, mx, *, use_max=False, use_min=False):
    if use_min:
        return mn
    if use_max:
        return mx
    return calc


class CatalogResolveMixin:
    def splitter_port_db(
        self, *,
        splitter_id=None, catalog_id=None, catalog_name=None, ratio_key=None,
        topology_type=None, port=None, port_name=None, port_count_out=0,
        wavelength_nm=1550, use_max=False, use_min=False, prefer_name: bool = True,
        inventory_id=None,
    ) -> Tuple[float, str, Optional[str]]:
        triple = self.splitter_port_db_triple(
            splitter_id=splitter_id, catalog_id=catalog_id,
            catalog_name=catalog_name, ratio_key=ratio_key,
            topology_type=topology_type, port=port, port_name=port_name,
            port_count_out=port_count_out, wavelength_nm=wavelength_nm,
            prefer_name=prefer_name,
        )
        mn, calc, mx, source, pn = triple
        db = _select_mode(mn, calc, mx, use_max=use_max, use_min=use_min)
        return db, source, pn

    def splitter_port_db_triple(
        self, *,
        splitter_id=None, catalog_id=None, catalog_name=None, ratio_key=None,
        topology_type=None, port=None, port_name=None, port_count_out=0,
        wavelength_nm=1550, prefer_name: bool = True,
        inventory_id=None,
    ) -> Tuple[float, float, float, str, Optional[str]]:
        if splitter_id is not None:
            forced = self._data.get("force", {}).get("splitters", {}).get(str(splitter_id))
            if forced:
                t, pn = self._force_port_db_triple(
                    forced, port=port, port_name=port_name,
                    wavelength_nm=wavelength_nm,
                    context=f"force splitter:{splitter_id}",
                )
                if t is not None:
                    return t[0], t[1], t[2], "force", pn or port_name

        inst = None
        match_kind = None
        # force → name → instance → catalog_id → ratio → estimated
        if prefer_name and catalog_name:
            inst = self._find_splitter(catalog_name=catalog_name)
            if inst is not None:
                match_kind = "name"
        if inst is None and splitter_id is not None:
            inst = self._find_splitter(splitter_id=splitter_id)
            if inst is not None:
                match_kind = "instance"
        if inst is None and catalog_name:
            inst = self._find_splitter(catalog_name=catalog_name)
            if inst is not None:
                match_kind = "name"
        if inst is None and catalog_id is not None:
            inst = self._find_splitter(catalog_id=catalog_id)
            if inst is not None:
                match_kind = "catalog"

        if inst is not None:
            ports = inst.get("ports") or {}
            if not ports:
                rk = inst.get("ratio") or ratio_key
                if not rk and inst.get("name"):
                    rk = guess_ratio_key(str(inst["name"]))
                if not rk and catalog_name:
                    rk = guess_ratio_key(str(catalog_name))
                if rk:
                    ports = ports_from_ratio_key(rk) or {}
            if ports:
                ctx = f"splitter name={inst.get('name') or catalog_name or splitter_id}"
                t, pn = self._resolve_port_db_triple(
                    ports, port=port, port_name=port_name,
                    wavelength_nm=wavelength_nm, context=ctx,
                )
                if t is not None:
                    return t[0], t[1], t[2], (match_kind or "instance"), pn or port_name

        rk = ratio_key or _topology_to_ratio_key(topology_type)
        if not rk and catalog_name:
            rk = guess_ratio_key(str(catalog_name))
        if rk:
            ports = ports_from_ratio_key(rk)
            if ports:
                t, pn = self._resolve_port_db_triple(
                    ports, port=port, port_name=port_name,
                    wavelength_nm=wavelength_nm, context=f"ratio:{rk}",
                )
                if t is not None:
                    return t[0], t[1], t[2], f"ratio:{rk}", pn or port_name

        n = int(port_count_out or 0)
        if n <= 1 and topology_type:
            m = re.match(r"^(\d+)x(\d+)$", str(topology_type).strip().lower())
            if m:
                n = max(int(m.group(1)), int(m.group(2)))
        n = max(n, 1)
        ideal = 10.0 * math.log10(n) if n > 1 else 0.0
        excess = self.splitter_excess_db()
        calc = ideal + excess
        return ideal, calc, ideal + 2.0 * excess, "estimated", port_name

    def _force_port_db_triple(self, forced_node, *, port, port_name, wavelength_nm, context):
        val = None
        pn = None
        if port is not None and str(port) in forced_node:
            val = forced_node[str(port)]
        elif port_name and isinstance(forced_node.get("by_name"), dict):
            val = forced_node["by_name"].get(port_name)
            pn = port_name
        elif port_name and port_name in forced_node:
            val = forced_node[port_name]
            pn = port_name
        elif "all" in forced_node:
            val = forced_node["all"]
            pn = "all"
        if val is None:
            return None, None
        if isinstance(val, (int, float)):
            v = float(val)
            return (v, v, v), pn
        if isinstance(val, dict):
            pn = pn or _port_name_from_entry(val)
            att = _port_entry_attenuation(val)
            if att:
                picked = _pick_wl(att, wavelength_nm, context=context)
                if picked:
                    return (picked[0], picked[1], picked[2]), pn
            triple = _as_db_triple(val)
            if triple:
                return triple, pn
            picked = _pick_wl(val, wavelength_nm, context=context)
            if picked:
                return (picked[0], picked[1], picked[2]), pn
        triple = _as_db_triple(val)
        if triple:
            return triple, pn
        return None, None

    def _resolve_port_db_triple(self, ports, *, port, port_name, wavelength_nm, context):
        entry, resolved_name = _lookup_port_entry(ports, port=port, port_name=port_name)
        if entry is None:
            return None, None
        if isinstance(entry, (int, float)):
            v = float(entry)
            return (v, v, v), resolved_name
        att = _port_entry_attenuation(entry)
        if att is not None:
            picked = _pick_wl(att, wavelength_nm, context=context)
            if picked is not None:
                return (picked[0], picked[1], picked[2]), resolved_name
        triple = _as_db_triple(entry)
        if triple:
            return triple, resolved_name
        return None, resolved_name

    def _force_port_db(self, forced_node, *, port, port_name, wavelength_nm, use_max, context):
        t, pn = self._force_port_db_triple(
            forced_node, port=port, port_name=port_name,
            wavelength_nm=wavelength_nm, context=context,
        )
        if t is None:
            return None, None
        return (_select_mode(t[0], t[1], t[2], use_max=use_max)), pn

    def _resolve_port_db(self, ports, *, port, port_name, wavelength_nm, use_max, context):
        t, pn = self._resolve_port_db_triple(
            ports, port=port, port_name=port_name,
            wavelength_nm=wavelength_nm, context=context,
        )
        if t is None:
            return None, None
        return (_select_mode(t[0], t[1], t[2], use_max=use_max)), pn

# === catalog_merge.py ===
class CatalogMergeMixin:
    def merge_cable_catalog(self, items):
        """name = model (марка), без brand."""
        default_table = self.defaults.get("fiber_db_per_km", {})
        cables = self._cables()
        by_id = {str(e.get("id")): e for e in cables if e.get("id") is not None}
        for it in items:
            cid = getattr(it, "id", None)
            if cid is None:
                continue
            name = (
                str(getattr(it, "model", "") or "").strip()
                or str(getattr(it, "name", "") or "").strip()
                or str(cid)
            )
            entry = by_id.get(str(cid))
            if entry is None:
                entry = {"id": str(cid), "name": name}
                cables.append(entry)
                by_id[str(cid)] = entry
            entry.setdefault("name", name)
            if not entry.get("name"):
                entry["name"] = name
            entry.setdefault("fiber_count", getattr(it, "fiber_count", None))
            entry.setdefault("cable_line_type_id", getattr(it, "cable_line_type_id", None))
            if not entry.get("db_per_km"):
                entry["db_per_km"] = copy.deepcopy(default_table)
            else:
                _backfill_att_wl(entry["db_per_km"], default_table)

    def merge_splitter_inventory(
        self, splitters, inventory_by_id, catalog_by_id, *, auto_fill_ratio=True
    ):
        items = self._splitters()
        by_cat = {str(e.get("catalog_id")): e for e in items if e.get("catalog_id") and not e.get("id")}
        by_topo = {str(e.get("id")): e for e in items if e.get("id")}

        for sp in splitters:
            sid = getattr(sp, "id", None)
            inv_id = getattr(sp, "inventory_id", None)
            pin = getattr(sp, "port_count_in", 0) or 0
            pout = getattr(sp, "port_count_out", 0) or 0
            inv = inventory_by_id.get(inv_id) if inv_id else None
            catalog_id = getattr(inv, "catalog_id", None) if inv else None
            cat_name = ""
            if catalog_id is not None and catalog_id in catalog_by_id:
                cat_name = str(getattr(catalog_by_id[catalog_id], "name", ""))
            ratio = guess_ratio_key(cat_name) if cat_name else None
            ports = ports_from_ratio_key(ratio) if auto_fill_ratio and ratio else {}

            if catalog_id is not None:
                entry = by_cat.get(str(catalog_id))
                if entry is None:
                    entry = {
                        "catalog_id": str(catalog_id), "name": cat_name,
                        "topology": f"{pin}x{pout}", "ratio": ratio or "", "ports": {},
                    }
                    items.append(entry)
                    by_cat[str(catalog_id)] = entry
                if cat_name and not entry.get("name"):
                    entry["name"] = cat_name
                if ratio and not entry.get("ratio"):
                    entry["ratio"] = ratio
                if ports and not entry.get("ports"):
                    entry["ports"] = ports

            if sid is not None:
                tentry = by_topo.get(str(sid))
                if tentry is None:
                    tentry = {
                        "id": str(sid), "inventory_id": inv_id,
                        "catalog_id": str(catalog_id) if catalog_id is not None else None,
                        "name": cat_name or getattr(sp, "description", ""),
                        "topology": f"{pin}x{pout}", "ratio": ratio or "", "ports": {},
                    }
                    items.append(tentry)
                    by_topo[str(sid)] = tentry
                if ports and not tentry.get("ports"):
                    tentry["ports"] = copy.deepcopy(ports)

# === catalog_fill.py ===
def _backfill_att_wl(dst_att, src_att) -> int:
    if not isinstance(dst_att, dict) or not isinstance(src_att, dict):
        return 0
    n = 0
    for wl, val in src_att.items():
        if wl not in dst_att or not dst_att[wl]:
            dst_att[wl] = copy.deepcopy(val)
            n += 1
    return n

class CatalogFillMixin:
    def fill_missing_wavelengths(self) -> int:
        added = 0
        default_fiber = self.defaults.get("fiber_db_per_km", {})
        pkg = json.loads(_DEFAULTS_PATH.read_text(encoding="utf-8"))
        src_fiber = (pkg.get("defaults") or {}).get("fiber_db_per_km") or {}
        _backfill_att_wl(self.defaults.setdefault("fiber_db_per_km", {}), src_fiber)
        for entry in self._cables():
            if entry.get("db_per_km"):
                added += _backfill_att_wl(entry["db_per_km"], default_fiber or src_fiber)
            else:
                entry["db_per_km"] = copy.deepcopy(default_fiber or src_fiber)
                added += len(entry["db_per_km"])
        for entry in self._splitters():
            ratio = entry.get("ratio") or ""
            if not ratio and entry.get("name"):
                ratio = guess_ratio_key(entry["name"]) or ""
            src_ports = ports_from_ratio_key(ratio) if ratio else {}
            ports = entry.setdefault("ports", {})
            if not ports and src_ports:
                entry["ports"] = copy.deepcopy(src_ports)
                added += sum(len((p.get("attenuation") or {})) for p in src_ports.values() if isinstance(p, dict))
                continue
            for pk, pv in list(ports.items()):
                if not isinstance(pv, dict):
                    continue
                att = pv.setdefault("attenuation", {})
                src = None
                if pk in src_ports and isinstance(src_ports[pk], dict):
                    src = src_ports[pk].get("attenuation")
                elif "all" in src_ports:
                    src = (src_ports["all"] or {}).get("attenuation")
                if src:
                    added += _backfill_att_wl(att, src)
        return added

    def fill_missing_with_defaults(self):
        default_table = self.defaults.get("fiber_db_per_km", {})
        if not default_table:
            pkg = json.loads(_DEFAULTS_PATH.read_text(encoding="utf-8"))
            default_table = (pkg.get("defaults") or {}).get("fiber_db_per_km") or {}
            self.defaults["fiber_db_per_km"] = copy.deepcopy(default_table)
        for entry in self._cables():
            if not entry.get("db_per_km"):
                entry["db_per_km"] = copy.deepcopy(default_table)
        self.fill_missing_wavelengths()

    def unset_profiles(self):
        missing = []
        for entry in self._cables():
            if not entry.get("db_per_km"):
                missing.append(f"cable:{entry.get('id') or entry.get('name')}")
        for entry in self._splitters():
            if not entry.get("ports"):
                key = entry.get("id") or entry.get("catalog_id") or entry.get("name")
                missing.append(f"splitter:{key}")
        return missing

# === catalog_force.py ===
class CatalogForceMixin:
    def force_fiber(self, fiber_id, db_per_km):
        node = self._data.setdefault("force", {}).setdefault("fibers", {})
        if isinstance(db_per_km, (int, float)):
            node[str(fiber_id)] = float(db_per_km)
            return
        norm = {}
        for k, v in db_per_km.items():
            pair = _as_db_pair(v)
            if pair:
                norm[str(k)] = {"db": pair[0], "db_max": pair[1]}
        node[str(fiber_id)] = norm

    def forced_fiber_db_per_km(self, fiber_id, wavelength_nm=1550, *, use_max=False):
        raw = self._data.get("force", {}).get("fibers", {}).get(str(fiber_id))
        if raw is None:
            return None
        if isinstance(raw, (int, float)):
            return float(raw)
        if isinstance(raw, dict):
            picked = _pick_wl(raw, wavelength_nm, context=f"force fiber:{fiber_id}")
            if picked is None:
                return None
            # _pick_wl → (db_min, db_calc, db_max, used_wl)
            return picked[2] if use_max else picked[1]
        return None

    def force_object(self, obj_type, obj_id, db):
        self._data.setdefault("force", {}).setdefault("objects", {})[f"{obj_type}:{obj_id}"] = float(db)

    def forced_object_db(self, obj_type, obj_id):
        v = self._data.get("force", {}).get("objects", {}).get(f"{obj_type}:{obj_id}")
        return float(v) if v is not None else None

    def force_edge(self, connect_id, db):
        self._data.setdefault("force", {}).setdefault("edges", {})[str(connect_id)] = float(db)

    def forced_edge_db(self, connect_id):
        v = self._data.get("force", {}).get("edges", {}).get(str(connect_id))
        return float(v) if v is not None else None

    def force_cross(self, cross_id, db):
        self._data.setdefault("force", {}).setdefault("crosses", {})[str(cross_id)] = float(db)

    def forced_cross_db(self, cross_id):
        v = self._data.get("force", {}).get("crosses", {}).get(str(cross_id))
        return float(v) if v is not None else None

# === catalog_io.py ===
class CatalogIOMixin:
    def save(self, path: Union[str, Path]) -> Path:
        """Сохранить каталог в JSON (generate_template / update_template)."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return p

    def to_json(self, path: Union[str, Path]) -> Path:
        """Alias для save."""
        return self.save(path)



def _joint_table_or_triple(raw: Any, wavelength_nm: Optional[int] = None):
    """raw: число | {db/db_min/db_max} | {"1310": {...}, "1550": {...}}.

    Возвращает (db_min, db, db_max) с учётом wavelength_nm.
    """
    if raw is None:
        return None
    # per-wavelength table?
    if isinstance(raw, dict):
        keys = list(raw.keys())
        looks_wl = False
        for k in keys:
            ks = str(k)
            if ks.isdigit() or (isinstance(k, int)):
                looks_wl = True
                break
            # also accept nested without db keys at top
        if looks_wl and not any(k in raw for k in ("db", "db_min", "db_max")):
            if wavelength_nm is not None:
                picked = _pick_wl(raw, int(wavelength_nm), context="joint")
                if picked is not None:
                    return picked[0], picked[1], picked[2]
            # fallback: first available wavelength
            for k in sorted(keys, key=lambda x: str(x)):
                t = _as_db_triple(raw[k])
                if t:
                    return t
            return None
    return _as_db_triple(raw)

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


__all__ = ["AttenuationCatalog", "guess_ratio_key"]
