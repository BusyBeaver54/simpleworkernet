# simpleworkernet/utils/topology/attenuation/__init__.py
"""
Расчёт оптических затуханий по CGraph (по запросу).

Константы типов — из topology.constants (не дублировать локально):

    from simpleworkernet.utils.topology import TYPE_FIBER, TYPE_OLT, ...
    # или
    from simpleworkernet.utils.topology.constants import TYPE_FIBER
"""

from ..constants import (
    TYPE_CUSTOMER,
    TYPE_FIBER,
    TYPE_SPLITTER,
    TYPE_CROSS,
    TYPE_CWDM,
    TYPE_SWITCH,
    TYPE_OLT,
    TYPE_ONU,
    TYPE_RADIO,
    DEVICE_TYPES,
    SIDE_TYPES,
    TERMINAL_TYPES,
    ALL_OBJECT_TYPES,
)
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
    # shared type constants
    "TYPE_CUSTOMER",
    "TYPE_FIBER",
    "TYPE_SPLITTER",
    "TYPE_CROSS",
    "TYPE_CWDM",
    "TYPE_SWITCH",
    "TYPE_OLT",
    "TYPE_ONU",
    "TYPE_RADIO",
    "DEVICE_TYPES",
    "SIDE_TYPES",
    "TERMINAL_TYPES",
    "ALL_OBJECT_TYPES",
    # attenuation API
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
