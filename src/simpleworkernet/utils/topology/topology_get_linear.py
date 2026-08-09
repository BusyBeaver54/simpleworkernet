# simpleworkernet/utils/topology/topology_get_linear.py
"""get_linear + NetworkTopology (подключается из topology/__init__)."""
from __future__ import annotations
from typing import Optional, Union
from .errors import TopologyBuildError
from .linear_extract import extract_linear_cgraph, extract_linear_fngraph

def get_linear(
    self,
    start_type: str,
    start_id: Union[int, str],
    end_type: Optional[str] = None,
    end_id: Optional[Union[int, str]] = None,
    *,
    port=None,
    side: Optional[int] = None,
    source: str = "cgraph",
    cgraph_index: int = 0,
    start_node_id: Optional[int] = None,
    end_node_id: Optional[int] = None,
):
    """Линейный подграф из уже построенного CGraph или FNGraph."""
    cls = type(self)
    new_topo = cls(self.client, cache=self.cache)
    if source == "fngraph":
        if self.fngraph is None:
            raise TopologyBuildError("FNGraph не построен")
        sn = start_node_id
        if sn is None and start_type in ("node", "facility"):
            sn = int(start_id)
        if sn is None:
            raise TopologyBuildError("для source=fngraph укажите start_node_id")
        en = end_node_id
        if en is None and end_id is not None:
            try:
                en = int(end_id)
            except (TypeError, ValueError):
                en = None
        new_topo._set_fngraph(extract_linear_fngraph(self.fngraph, sn, en))
        return new_topo
    if not self.cgraphs:
        raise TopologyBuildError("Нет CGraph. Сначала build_from_*")
    if cgraph_index < 0 or cgraph_index >= len(self.cgraphs):
        raise TopologyBuildError(f"cgraph_index={cgraph_index} вне диапазона")
    linear_cg = extract_linear_cgraph(
        self.cgraphs[cgraph_index],
        start_type, start_id, end_type, end_id,
        port=port, side=side,
    )
    new_topo._add_cgraph(linear_cg)
    fn = new_topo._build_fngraph_from_cgraph(linear_cg)
    if fn is not None:
        new_topo._set_fngraph(fn)
    return new_topo

def topology_from_commutation(
    self, last_object_type, last_object_id, port=None, side=None,
    first_object_type=None, first_object_id=None,
):
    """Устарело → get_linear."""
    return self.get_linear(
        start_type=last_object_type, start_id=last_object_id,
        end_type=first_object_type, end_id=first_object_id,
        port=port, side=side,
    )

def apply_network_topology_api(TopologyCls):
    TopologyCls.get_linear = get_linear
    TopologyCls.topology_from_commutation = topology_from_commutation
    TopologyCls.__name__ = "NetworkTopology"
    TopologyCls.__qualname__ = "NetworkTopology"
    return TopologyCls
