# simpleworkernet/utils/topology/attenuation/report_io.py
"""Сохранение и загрузка PathReport (JSON)."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union

from .models import AttenuationSegment, PathReport


def default_reports_dir() -> Path:
    try:
        from ...config_manager import get_config_dir
        root = Path(get_config_dir())
    except Exception:
        root = Path.home() / ".config" / "simpleworkernet"
    d = root / "attenuation_reports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def report_filename(
    obj1_type: str,
    obj1_id: Union[int, str],
    obj2_type: str,
    obj2_id: Union[int, str],
    *,
    wavelength: Optional[int] = None,
    stamp: Optional[str] = None,
) -> str:
    wl = f"_wl{wavelength}" if wavelength is not None else ""
    ts = stamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe = lambda x: str(x).replace("/", "_").replace(":", "-")
    return (
        f"path_{safe(obj1_type)}_{safe(obj1_id)}"
        f"__{safe(obj2_type)}_{safe(obj2_id)}{wl}_{ts}.json"
    )


def path_report_to_dict(report: PathReport, *, extra: Optional[dict] = None) -> dict:
    d = report.to_dict()
    d["schema"] = "simpleworkernet.attenuation.PathReport/v1"
    d["computed_at"] = datetime.now(timezone.utc).isoformat()
    qm = getattr(report, "query_meta", None) or {}
    for k, v in qm.items():
        if k not in d and v is not None:
            d[k] = v
    if extra:
        d.update(extra)
    return d


def save_path_report(
    report: PathReport,
    path: Optional[Union[str, Path]] = None,
    *,
    obj1_type: Optional[str] = None,
    obj1_id: Any = None,
    obj2_type: Optional[str] = None,
    obj2_id: Any = None,
    wavelength: Optional[int] = None,
    extra: Optional[dict] = None,
) -> Path:
    """Сохранить PathReport в JSON. Возвращает путь."""
    if path is None:
        qm = getattr(report, "query_meta", None) or {}
        obj1_type = obj1_type or qm.get("obj1_type") or "obj1"
        obj1_id = obj1_id if obj1_id is not None else qm.get("obj1_id", "x")
        obj2_type = obj2_type or qm.get("obj2_type") or "obj2"
        obj2_id = obj2_id if obj2_id is not None else qm.get("obj2_id", "x")
        wavelength = wavelength if wavelength is not None else report.wavelength_nm
        path = default_reports_dir() / report_filename(
            str(obj1_type), obj1_id, str(obj2_type), obj2_id,
            wavelength=wavelength or report.wavelength_nm,
        )
    else:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

    extra = dict(extra or {})
    if obj1_type is not None:
        extra.setdefault("obj1_type", obj1_type)
    if obj1_id is not None:
        extra.setdefault("obj1_id", obj1_id)
    if obj2_type is not None:
        extra.setdefault("obj2_type", obj2_type)
    if obj2_id is not None:
        extra.setdefault("obj2_id", obj2_id)

    data = path_report_to_dict(report, extra=extra)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_path_report(path: Union[str, Path]) -> PathReport:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"PathReport не найден: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return PathReport.from_dict(data)
