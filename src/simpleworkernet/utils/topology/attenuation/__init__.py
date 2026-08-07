# simpleworkernet/utils/topology/attenuation/__init__.py
"""
Расчёт оптических затуханий по CGraph (по запросу, не при build).

    from simpleworkernet.utils.topology.attenuation import Attenuation, AttenuationCatalog

    cat = AttenuationCatalog.with_defaults()
    att = Attenuation(cgraph, catalog=cat, wavelength=1550)
    report = att.olt_to_customer(customer_id)
    print(report.total_db, report.to_table())
"""

from .catalog import AttenuationCatalog, guess_ratio_key
from .models import AttenuationSegment, PathReport
from .calculator import Attenuation

__all__ = [
    "Attenuation",
    "AttenuationCatalog",
    "AttenuationSegment",
    "PathReport",
    "guess_ratio_key",
]
