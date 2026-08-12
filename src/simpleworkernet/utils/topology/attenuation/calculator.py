# simpleworkernet/utils/topology/attenuation/calculator.py
"""Attenuation — calculate() between objects or over entire CGraph."""
from __future__ import annotations
from typing import Any, List, Optional, Sequence, Tuple, Union
from ..keys import Interface
from ..constants import (
    TYPE_CUSTOMER, TYPE_OLT, TYPE_ONU, TYPE_RADIO, TYPE_SWITCH,
    TERMINAL_TYPES,
)
from .catalog import AttenuationCatalog
from .models import PathReport
from .multipath import MultiPathReport
from .calculator_segments import AttenuationSegmentsMixin, _label_vertex
from .calculator_path import AttenuationPathMixin
from .calculator_edge import AttenuationEdgeMixin
from .calculator_build import AttenuationBuildMixin
from .calculator_fn import AttenuationFNMixin
from .calculator_fiber import AttenuationFiberMixin
from .calculator_paths import AttenuationPathsMixin
from .errors import AttenuationError

VertexRef = Union[int, Interface, Tuple[str, Union[int, str], int, int], str]

_SINK_TYPES = frozenset({TYPE_OLT, TYPE_SWITCH, TYPE_ONU, TYPE_RADIO})
_SOURCE_TYPES = frozenset({TYPE_CUSTOMER}) | _SINK_TYPES


def _is_network_topology(obj: Any) -> bool:
    if obj is None:
        return False
    cgraphs = getattr(obj, "cgraphs", None)
    return isinstance(cgraphs, list) and hasattr(obj, "client")


def _is_cgraph_like(obj: Any) -> bool:
    if obj is None:
        return False
    return hasattr(obj, "vs") and (
        hasattr(obj, "vcount") or hasattr(obj, "get_eid") or hasattr(obj, "es")
    )


class Attenuation(
    AttenuationBuildMixin,
    AttenuationFNMixin,
    AttenuationFiberMixin,
    AttenuationSegmentsMixin,
    AttenuationEdgeMixin,
    AttenuationPathMixin,
    AttenuationPathsMixin,
):
    def __init__(
        self,
        graph: Any = None,
        *,
        catalog: Optional[AttenuationCatalog] = None,
        wavelength: int = 1550,
        cache: Any = None,
        client: Any = None,
        # устаревшие алиасы (graph предпочтителен)
        cgraph: Any = None,
        topology: Any = None,
    ) -> None:
        """graph — CGraph или NetworkTopology (единственный входной граф).

        cgraph=/topology= оставлены как алиасы graph= для совместимости.
        """
        self.topology: Any = None
        self.cgraphs: List[Any] = []
        self.g: Any = None

        self.wavelength = int(wavelength)
        # min/max/avg считаются всегда; use_max больше не используется
        self.use_max = False

        src = graph if graph is not None else (topology if topology is not None else cgraph)
        self._bind_graphs(cgraph=None if _is_network_topology(src) else src, topology=src if _is_network_topology(src) else None)

        if client is not None:
            self.client = client
        elif self.topology is not None:
            self.client = getattr(self.topology, "client", None)
        elif self.g is not None:
            self.client = getattr(self.g, "client", None)
        elif self.cgraphs:
            self.client = getattr(self.cgraphs[0], "client", None)
        else:
            self.client = None

        if cache is not None:
            self.cache = cache
        elif self.topology is not None:
            self.cache = getattr(self.topology, "cache", None)
        elif self.g is not None:
            self.cache = getattr(self.g, "cache", None)
        elif self.cgraphs:
            self.cache = getattr(self.cgraphs[0], "cache", None)
        else:
            self.cache = None

        if catalog is not None:
            self.catalog = catalog
        else:
            loaded = None
            if self.client is not None:
                try:
                    from .template import load_attenuation_catalog
                    loaded = load_attenuation_catalog(self.client)
                except Exception:
                    loaded = None
            self.catalog = loaded or AttenuationCatalog.with_defaults()

    def _bind_graphs(self, *, cgraph: Any = None, topology: Any = None) -> None:
        self.topology = None
        self.cgraphs = []
        self.g = None

        src = topology if topology is not None else cgraph
        if src is None:
            return

        if topology is not None and cgraph is not None and topology is not cgraph:
            src = topology

        if _is_network_topology(src):
            self.topology = src
            self.cgraphs = [cg for cg in (src.cgraphs or []) if cg is not None]
            if len(self.cgraphs) == 1:
                self.g = self.cgraphs[0]
            return

        if isinstance(src, (list, tuple)):
            self.cgraphs = [cg for cg in src if cg is not None]
            if len(self.cgraphs) == 1:
                self.g = self.cgraphs[0]
            return

        if _is_cgraph_like(src):
            self.cgraphs = [src]
            self.g = src
            return

        self.cgraphs = [src]
        self.g = src
