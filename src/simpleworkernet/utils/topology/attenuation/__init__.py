# simpleworkernet/utils/topology/attenuation/__init__.py
"""
Расчёт оптических затуханий по CGraph (по запросу, не при build).

    from simpleworkernet.utils.topology.attenuation import (
        Attenuation, AttenuationCatalog, load_attenuation_catalog,
        generate_template, update_template,
    )

    cat = generate_template(client)          # → config_dir/attenuation.json
    cat = update_template(client)            # дописать новые из БД
    cat = load_attenuation_catalog()         # загрузить для расчёта
    att = Attenuation(cgraph, catalog=cat, wavelength=1550)
"""

from .catalog import AttenuationCatalog, guess_ratio_key
from .models import AttenuationSegment, PathReport
from .calculator import Attenuation
from .template import (
    attenuation_json_path,
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
    "generate_template",
    "load_attenuation_catalog",
    "update_template",
]
