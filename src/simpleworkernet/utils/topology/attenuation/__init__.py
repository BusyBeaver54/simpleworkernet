# simpleworkernet/utils/topology/attenuation/__init__.py
"""
Расчёт оптических затуханий по CGraph (по запросу).

    cat = generate_template(client, ("PLC", "FBT"))
    # → config_dir/attenuation_<host>.json
    cat = update_template(client, ("PLC", "FBT"))
    cat = load_attenuation_catalog(client)
    att = Attenuation(cgraph, catalog=cat, wavelength=1550)
"""

from .catalog import AttenuationCatalog, guess_ratio_key
from .models import AttenuationSegment, PathReport
from .calculator import Attenuation
from .template import (
    attenuation_json_path,
    client_file_key,
    generate_template,
    load_attenuation_catalog,
    update_template,
)

__all__ = [
    "Attenuation",
    "AttenuationCatalog",
    "AttenuationSegment",
    "PathReport",
    "guess_ratio_key",
    "attenuation_json_path",
    "client_file_key",
    "generate_template",
    "load_attenuation_catalog",
    "update_template",
]
