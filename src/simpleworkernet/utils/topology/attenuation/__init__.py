# simpleworkernet/utils/topology/attenuation/__init__.py
"""
Расчёт оптических затуханий по CGraph (по запросу).

    cat = generate_template(client, ("PLC", "FBT"))
    cat = load_attenuation_catalog(client)
    att = Attenuation(catalog=cat, client=client, cache=cache)
    r = att.calculate(
        "fiber", 13259, "fiber", 13235,
        obj1_side=2, obj1_port=1, obj2_side=2, obj2_port=1,
        wavelength=1490,
    )
    path = r.save()                 # ~/.config/simpleworkernet/attenuation_reports/...
    r2 = PathReport.load(path)
"""

from .catalog import AttenuationCatalog, guess_ratio_key
from .models import AttenuationSegment, PathReport
from .calculator import Attenuation, AttenuationError
from .template import (
    attenuation_json_path,
    client_file_key,
    generate_template,
    load_attenuation_catalog,
    update_template,
)
from .report_io import (
    save_path_report,
    load_path_report,
    default_reports_dir,
    report_filename,
)
from .calculator_pairs import pair_plan, validate_pair_inputs, PairPlan

__all__ = [
    "Attenuation",
    "AttenuationError",
    "AttenuationCatalog",
    "AttenuationSegment",
    "PathReport",
    "PairPlan",
    "pair_plan",
    "validate_pair_inputs",
    "guess_ratio_key",
    "attenuation_json_path",
    "client_file_key",
    "generate_template",
    "load_attenuation_catalog",
    "update_template",
    "save_path_report",
    "load_path_report",
    "default_reports_dir",
    "report_filename",
]
