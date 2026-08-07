# simpleworkernet/utils/topology/attenuation/__init__.py
"""
Расчёт оптических затуханий по CGraph (по запросу).

    cat = generate_template(client, ("PLC", "FBT"))
    cat = load_attenuation_catalog(client)
    att = Attenuation(catalog=cat, client=client, cache=cache)
    r = att.calculate("olt", 1, "customer", 100, wavelength=1490)
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

__all__ = [
    "Attenuation",
    "AttenuationError",
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
