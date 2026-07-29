# simpleworkernet/utils/topology/attenuation/calculator.py
"""Attenuation — расчёт затуханий по CGraph по запросу."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from ..constants import (
    DEVICE_TYPES,
    TYPE_CROSS,
    TYPE_CUSTOMER,
    TYPE_FIBER,
    TYPE_OLT,
    TYPE_SPLITTER,
    TYPE_SWITCH,
)
from ..keys import Interface, ObjKey
from .catalog import AttenuationCatalog
from .length import resolve_fiber_length_m
from .models import AttenuationSegment, PathReport

VertexRef = Union[int, Interface, Tuple[str, Union[int, str], int, int], str]


def _label_vertex(vattrs: dict) -> str:
    return (
        f"{vattrs.get('obj_type')}:{vattrs.get('obj_id')}"
        f" s{vattrs.get('side')}p{vattrs.get('port')}"
    )


class Attenuation:
    """
    Калькулятор затуханий для уже построенного CGraph.

    Не вызывается при build — только по явному запросу.

        att = Attenuation(cgraph, wavelength=1550)
        r = att.olt_to_customer(68168)
        r = att.between("olt", 1, port=2, to_type="customer", to_id=68168)
        r = att.olt_to_splitter_out(splitter_id=10, port=3)
        r = att.to_node_first_hop(node_id=23779)
    """

    def __init__(
        self,
        cgraph: Any,
        *,
        catalog: Optional[AttenuationCatalog] = None,
        wavelength: int = 1550,
        cache: Any = None,
        client: Any = None,
    ) -> None:
        self.g = cgraph
        self.catalog = catalog or AttenuationCatalog.with_defaults()
        self.wavelength = int(wavelength)
        self.cache = cache if cache is not None else getattr(cgraph, "cache", None)
        self.client = client if client is not None else getattr(cgraph, "client", None)

    # ------------------------------------------------------------------
    # vertex resolution
    # ------------------------------------------------------------------

    def _vertex_attrs(self, idx: int) -> dict:
        v = self.g.vs[idx]
        return {k: v[k] for k in v.attributes()}

    def find_vertices(
        self,
        obj_type: Optional[str] = None,
        obj_id: Optional[Union[int, str]] = None,
        *,
        side: Optional[int] = None,
        port: Optional[int] = None,
        node_id: Optional[int] = None,
    ) -> List[int]:
        found: List[int] = []
        for v in self.g.vs:
            if obj_type is not None and v["obj_type"] != obj_type:
                continue
            if obj_id is not None and str(v["obj_id"]) != str(obj_id):
                continue
            if side is not None and int(v["side"]) != int(side):
                continue
            if port is not None and int(v["port"]) != int(port):
                continue
            if node_id is not None and v["node_id"] != node_id:
                continue
            found.append(v.index)
        return found

    def find_vertex(
        self,
        obj_type: Optional[str] = None,
        obj_id: Optional[Union[int, str]] = None,
        **kwargs: Any,
    ) -> Optional[int]:
        hits = self.find_vertices(obj_type, obj_id, **kwargs)
        return hits[0] if hits else None

    def resolve_vertex(self, ref: VertexRef) -> Optional[int]:
        if isinstance(ref, int):
            return ref if 0 <= ref < self.g.vcount() else None
        if isinstance(ref, Interface):
            return self.find_vertex(
                ref.obj.obj_type, ref.obj.id, side=ref.side, port=ref.port
            )
        if isinstance(ref, tuple) and len(ref) >= 2:
            obj_type, obj_id = ref[0], ref[1]
            side = ref[2] if len(ref) > 2 else None
            port = ref[3] if len(ref) > 3 else None
            return self.find_vertex(obj_type, obj_id, side=side, port=port)
        if isinstance(ref, str) and ":" in ref:
            # "olt:123" or "fiber:5:1:2"
            parts = ref.split(":")
            obj_type = parts[0]
            obj_id = parts[1]
            side = int(parts[2]) if len(parts) > 2 else None
            port = int(parts[3]) if len(parts) > 3 else None
            return self.find_vertex(obj_type, obj_id, side=side, port=port)
        return None

    def find_olts(self) -> List[int]:
        return self.find_vertices(TYPE_OLT)

    def find_customers(self) -> List[int]:
        return self.find_vertices(TYPE_CUSTOMER)

    def primary_olt(self) -> Optional[int]:
        olts = self.find_olts()
        return olts[0] if olts else None

    # ------------------------------------------------------------------
    # path finding
    # ------------------------------------------------------------------

    def shortest_path(
        self, source: int, target: int
    ) -> List[int]:
        try:
            path = self.g.get_shortest_paths(source, to=target, output="vpath")
            if path and path[0]:
                return list(path[0])
        except Exception:
            pass
        return []

    def _direction_of_path(self, vpath: Sequence[int]) -> str:
        if not vpath:
            return "unknown"
        types = [self.g.vs[i]["obj_type"] for i in vpath]
        if TYPE_OLT in types and TYPE_CUSTOMER in types:
            if types.index(TYPE_OLT) < types.index(TYPE_CUSTOMER):
                return "downstream"
            return "upstream"
        if TYPE_OLT in types:
            return "downstream" if types[0] == TYPE_OLT else "upstream"
        if TYPE_CUSTOMER in types:
            return "upstream" if types[0] == TYPE_CUSTOMER else "downstream"
        return "unknown"

    # ------------------------------------------------------------------
    # segment contribution
    # ------------------------------------------------------------------

    def _fiber_length(
        self, fiber_id: Union[int, str], fiber_obj: Any
    ) -> Tuple[Optional[float], str]:
        # кэш длин
        if self.cache is not None and hasattr(self.cache, "get_fiber_length_m"):
            cached = self.cache.get_fiber_length_m(fiber_id)
            if cached is not None:
                return cached

        geo_api = None
        if (
            self.client is not None
            and self.cache is not None
            and hasattr(self.cache, "get_geo_length")
        ):
            geo_api = self.cache.get_geo_length(self.client, int(fiber_id))

        length_m, source = resolve_fiber_length_m(
            fiber_obj,
            slack_k=self.catalog.geo_slack_k(),
            geo_length_api=geo_api,
        )
        if self.cache is not None and hasattr(self.cache, "set_fiber_length_m"):
            self.cache.set_fiber_length_m(fiber_id, length_m, source)
        return length_m, source

    def _splitter_catalog_id(self, splitter_obj: Any) -> Optional[int]:
        if splitter_obj is None:
            return None
        inv_id = getattr(splitter_obj, "inventory_id", None)
        if inv_id is None or self.cache is None or self.client is None:
            return None
        if hasattr(self.cache, "get_inventory"):
            inv = self.cache.get_inventory(self.client, inv_id)
            if inv is not None:
                return getattr(inv, "catalog_id", None)
        return None

    def _segment_on_edge(
        self,
        u: int,
        v: int,
        direction: str,
    ) -> List[AttenuationSegment]:
        """Вклады на ребре u→v (с учётом направления для сплиттера)."""
        segs: List[AttenuationSegment] = []
        ua, va = self._vertex_attrs(u), self._vertex_attrs(v)

        # найти ребро
        eid = None
        try:
            eid = self.g.get_eid(u, v, directed=False, error=False)
        except Exception:
            eid = -1
        edge_attrs: dict = {}
        if eid is not None and eid >= 0:
            e = self.g.es[eid]
            edge_attrs = {k: e[k] for k in e.attributes()}

        connect_id = int(edge_attrs.get("connect_id") or 0)
        is_internal = bool(edge_attrs.get("is_internal", False))

        forced_edge = (
            self.catalog.forced_edge_db(connect_id) if connect_id else None
        )
        if forced_edge is not None:
            segs.append(
                AttenuationSegment(
                    kind="force",
                    db=forced_edge,
                    description=f"force edge connect_id={connect_id}",
                    source="force",
                    meta={"connect_id": connect_id},
                )
            )
            return segs

        # --- fiber span (оба конца — fiber одного кабеля, разные side) ---
        if (
            ua.get("obj_type") == TYPE_FIBER
            and va.get("obj_type") == TYPE_FIBER
            and str(ua.get("obj_id")) == str(va.get("obj_id"))
            and int(ua.get("side", 0)) != int(va.get("side", 0))
        ):
            segs.extend(self._fiber_segments(ua))
            return segs

        # --- internal splitter: in↔out ---
        if is_internal and (
            ua.get("obj_type") == TYPE_SPLITTER
            or va.get("obj_type") == TYPE_SPLITTER
        ):
            segs.extend(self._splitter_segments(ua, va, direction))
            return segs

        # --- cross adapter on external hop touching cross ---
        for attrs in (ua, va):
            if attrs.get("obj_type") == TYPE_CROSS:
                db = self.catalog.adapter_db()
                segs.append(
                    AttenuationSegment(
                        kind="adapter",
                        db=db,
                        description=(
                            f"adapter cross:{attrs.get('obj_id')} "
                            f"port={attrs.get('port')}"
                        ),
                        obj_type=TYPE_CROSS,
                        obj_id=str(attrs.get("obj_id")),
                        port=attrs.get("port"),
                        side=attrs.get("side"),
                        wavelength_nm=self.wavelength,
                        source="default",
                    )
                )

        # connector-like external joint (не internal, не fiber-span)
        if not is_internal and not segs:
            # стык коннектор/сварка — мягкий default, если не fiber
            if TYPE_FIBER in (ua.get("obj_type"), va.get("obj_type")):
                db = self.catalog.splice_db()
                segs.append(
                    AttenuationSegment(
                        kind="splice",
                        db=db,
                        description="splice/connector joint",
                        source="default",
                        wavelength_nm=self.wavelength,
                        meta={"connect_id": connect_id},
                    )
                )
            else:
                db = self.catalog.connector_db()
                segs.append(
                    AttenuationSegment(
                        kind="connector",
                        db=db,
                        description="connector joint",
                        source="default",
                        wavelength_nm=self.wavelength,
                        meta={"connect_id": connect_id},
                    )
                )

        return segs

    def _fiber_segments(self, fiber_vertex_attrs: dict) -> List[AttenuationSegment]:
        fiber_id = fiber_vertex_attrs.get("obj_id")
        fiber_obj = fiber_vertex_attrs.get("api_obj")
        if fiber_obj is None and self.cache is not None and self.client is not None:
            fiber_obj = self.cache.get_fiber(self.client, int(fiber_id))

        length_m, length_source = self._fiber_length(fiber_id, fiber_obj)

        forced = self.catalog.forced_fiber_db_per_km(fiber_id)
        cabletype_id = getattr(fiber_obj, "cablecode", None) or getattr(
            fiber_obj, "cabletype_id", None
        )
        # cablecode в get_list — часто id типа кабеля; иначе cable_line_type_id
        if cabletype_id is None and fiber_obj is not None:
            cabletype_id = getattr(fiber_obj, "cable_line_type_id", None)

        if forced is not None:
            alpha = forced
            source = "force"
        else:
            alpha = self.catalog.cable_db_per_km(cabletype_id, self.wavelength)
            source = "profile" if cabletype_id is not None else "default"

        if length_m is None:
            return [
                AttenuationSegment(
                    kind="fiber",
                    db=0.0,
                    description=f"fiber:{fiber_id} length unknown",
                    obj_type=TYPE_FIBER,
                    obj_id=str(fiber_id),
                    length_m=None,
                    length_source=length_source,
                    wavelength_nm=self.wavelength,
                    source=source,
                    meta={"db_per_km": alpha, "cabletype_id": cabletype_id},
                )
            ]

        db = alpha * (length_m / 1000.0)
        return [
            AttenuationSegment(
                kind="fiber",
                db=db,
                description=(
                    f"fiber:{fiber_id} L={length_m:.1f}m "
                    f"α={alpha:.3f} dB/km ({length_source})"
                ),
                obj_type=TYPE_FIBER,
                obj_id=str(fiber_id),
                length_m=length_m,
                length_source=length_source,
                wavelength_nm=self.wavelength,
                source=source,
                meta={"db_per_km": alpha, "cabletype_id": cabletype_id},
            )
        ]

    def _splitter_segments(
        self, ua: dict, va: dict, direction: str
    ) -> List[AttenuationSegment]:
        """
        Затухание сплиттера одинаково в обе стороны для данного порта:
        downstream OLT→client и upstream client→OLT через тот же out-port.
        Берём out-port (side с port_count логикой: port вершины).
        """
        # выберем вершину-«выход» — та, у которой port относится к out
        # эвристика: у 1xN side1=in, side2=out (как в builders); port на out
        sp_attrs = ua if ua.get("obj_type") == TYPE_SPLITTER else va
        other = va if sp_attrs is ua else ua

        # порт вклада — порт исходящей стороны (не in)
        out_attrs = sp_attrs
        if other.get("obj_type") == TYPE_SPLITTER:
            # оба splitter? не должно
            out_attrs = other

        # если идём через internal, обе вершины — один splitter, разные side/port
        if (
            ua.get("obj_type") == TYPE_SPLITTER
            and va.get("obj_type") == TYPE_SPLITTER
            and str(ua.get("obj_id")) == str(va.get("obj_id"))
        ):
            # берём вершину с большим side как out (типично side=2 out)
            out_attrs = ua if int(ua.get("side", 1)) >= int(va.get("side", 1)) else va
            if int(ua.get("side", 1)) == int(va.get("side", 1)):
                out_attrs = ua if int(ua.get("port", 0)) >= int(va.get("port", 0)) else va

        splitter_id = out_attrs.get("obj_id")
        port = int(out_attrs.get("port") or 0)
        splitter_obj = out_attrs.get("api_obj")
        if splitter_obj is None and self.cache is not None and self.client is not None:
            splitter_obj = self.cache.get_splitter(self.client, int(splitter_id))

        catalog_id = self._splitter_catalog_id(splitter_obj)
        pin = getattr(splitter_obj, "port_count_in", 0) or 0
        pout = getattr(splitter_obj, "port_count_out", 0) or 0
        topology = out_attrs.get("splitter_type") or (
            f"{pin}x{pout}" if pin and pout else None
        )

        db, source = self.catalog.splitter_port_db(
            splitter_id=splitter_id,
            catalog_id=catalog_id,
            ratio_key=None,
            topology_type=topology,
            port=port,
            port_count_out=pout,
            wavelength_nm=self.wavelength,
        )

        return [
            AttenuationSegment(
                kind="splitter",
                db=db,
                description=(
                    f"splitter:{splitter_id} port={port} "
                    f"({topology or '?'}) [{direction}]"
                ),
                obj_type=TYPE_SPLITTER,
                obj_id=str(splitter_id),
                port=port,
                side=out_attrs.get("side"),
                wavelength_nm=self.wavelength,
                source=source,
                meta={
                    "catalog_id": catalog_id,
                    "topology": topology,
                    "direction": direction,
                },
            )
        ]

    # ------------------------------------------------------------------
    # core path calculation
    # ------------------------------------------------------------------

    def path(
        self,
        source: VertexRef,
        target: VertexRef,
        *,
        direction: Optional[str] = None,
    ) -> PathReport:
        s = self.resolve_vertex(source)
        t = self.resolve_vertex(target)
        report = PathReport(wavelength_nm=self.wavelength)

        if s is None or t is None:
            report.warnings.append(
                f"vertex not found: source={source!r} target={target!r}"
            )
            return report

        vpath = self.shortest_path(s, t)
        if not vpath:
            report.warnings.append(f"no path between {s} and {t}")
            report.from_label = _label_vertex(self._vertex_attrs(s))
            report.to_label = _label_vertex(self._vertex_attrs(t))
            return report

        report.vertex_path = vpath
        report.from_label = _label_vertex(self._vertex_attrs(vpath[0]))
        report.to_label = _label_vertex(self._vertex_attrs(vpath[-1]))
        report.direction = direction or self._direction_of_path(vpath)

        for a, b in zip(vpath, vpath[1:]):
            report.segments.extend(
                self._segment_on_edge(a, b, report.direction)
            )

        report.total_db = sum(seg.db for seg in report.segments)
        for seg in report.segments:
            if seg.kind == "fiber" and seg.length_m is None:
                report.missing.append(f"length fiber:{seg.obj_id}")
            if seg.source == "estimated":
                report.missing.append(
                    f"splitter profile {seg.obj_id} port={seg.port}"
                )
        return report

    def path_db(self, source: VertexRef, target: VertexRef, **kw: Any) -> float:
        return self.path(source, target, **kw).total_db

    # ------------------------------------------------------------------
    # convenience queries
    # ------------------------------------------------------------------

    def between(
        self,
        from_type: str,
        from_id: Union[int, str],
        *,
        to_type: str,
        to_id: Union[int, str],
        from_port: Optional[int] = None,
        from_side: Optional[int] = None,
        to_port: Optional[int] = None,
        to_side: Optional[int] = None,
    ) -> PathReport:
        s = self.find_vertex(
            from_type, from_id, port=from_port, side=from_side
        )
        t = self.find_vertex(to_type, to_id, port=to_port, side=to_side)
        if s is None or t is None:
            r = PathReport(wavelength_nm=self.wavelength)
            r.warnings.append("between: endpoint not in graph")
            return r
        return self.path(s, t)

    def olt_to_customer(
        self,
        customer_id: Union[int, str],
        *,
        olt_id: Optional[Union[int, str]] = None,
        olt_port: Optional[int] = None,
    ) -> PathReport:
        olt = (
            self.find_vertex(TYPE_OLT, olt_id, port=olt_port)
            if olt_id is not None
            else self.primary_olt()
        )
        cust = self.find_vertex(TYPE_CUSTOMER, customer_id)
        if olt is None or cust is None:
            r = PathReport(wavelength_nm=self.wavelength)
            r.warnings.append("olt_to_customer: OLT or customer not in graph")
            return r
        return self.path(olt, cust, direction="downstream")

    def customer_to_olt(
        self,
        customer_id: Union[int, str],
        *,
        olt_id: Optional[Union[int, str]] = None,
    ) -> PathReport:
        r = self.olt_to_customer(customer_id, olt_id=olt_id)
        # симметрия сплиттера: те же dB; направление помечаем upstream
        r.direction = "upstream"
        r.from_label, r.to_label = r.to_label, r.from_label
        r.vertex_path = list(reversed(r.vertex_path))
        r.segments = list(reversed(r.segments))
        return r

    def olt_to_splitter_out(
        self,
        splitter_id: Union[int, str],
        port: int,
        *,
        olt_id: Optional[Union[int, str]] = None,
        side: int = 2,
    ) -> PathReport:
        olt = (
            self.find_vertex(TYPE_OLT, olt_id)
            if olt_id is not None
            else self.primary_olt()
        )
        sp = self.find_vertex(TYPE_SPLITTER, splitter_id, port=port, side=side)
        if sp is None:
            # любая сторона с этим port
            sp = self.find_vertex(TYPE_SPLITTER, splitter_id, port=port)
        if olt is None or sp is None:
            r = PathReport(wavelength_nm=self.wavelength)
            r.warnings.append("olt_to_splitter_out: endpoint missing")
            return r
        return self.path(olt, sp, direction="downstream")

    def olt_to_splitter_in(
        self,
        splitter_id: Union[int, str],
        *,
        olt_id: Optional[Union[int, str]] = None,
        side: int = 1,
        port: int = 1,
    ) -> PathReport:
        olt = (
            self.find_vertex(TYPE_OLT, olt_id)
            if olt_id is not None
            else self.primary_olt()
        )
        sp = self.find_vertex(TYPE_SPLITTER, splitter_id, side=side, port=port)
        if sp is None:
            hits = self.find_vertices(TYPE_SPLITTER, splitter_id, side=side)
            sp = hits[0] if hits else None
        if olt is None or sp is None:
            r = PathReport(wavelength_nm=self.wavelength)
            r.warnings.append("olt_to_splitter_in: endpoint missing")
            return r
        return self.path(olt, sp, direction="downstream")

    def olt_to_cross(
        self,
        cross_id: Union[int, str],
        *,
        port: Optional[int] = None,
        side: Optional[int] = None,
        olt_id: Optional[Union[int, str]] = None,
    ) -> PathReport:
        olt = (
            self.find_vertex(TYPE_OLT, olt_id)
            if olt_id is not None
            else self.primary_olt()
        )
        cr = self.find_vertex(TYPE_CROSS, cross_id, port=port, side=side)
        if cr is None:
            hits = self.find_vertices(TYPE_CROSS, cross_id)
            cr = hits[0] if hits else None
        if olt is None or cr is None:
            r = PathReport(wavelength_nm=self.wavelength)
            r.warnings.append("olt_to_cross: endpoint missing")
            return r
        return self.path(olt, cr, direction="downstream")

    def cross_to_customer(
        self,
        cross_id: Union[int, str],
        customer_id: Union[int, str],
        *,
        port: Optional[int] = None,
        side: Optional[int] = None,
    ) -> PathReport:
        return self.between(
            TYPE_CROSS,
            cross_id,
            to_type=TYPE_CUSTOMER,
            to_id=customer_id,
            from_port=port,
            from_side=side,
        )

    def first_in_node(
        self,
        node_id: int,
        *,
        from_ref: Optional[VertexRef] = None,
        prefer_types: Optional[Sequence[str]] = None,
    ) -> PathReport:
        """
        Путь от from_ref (или OLT) до первого интерфейса в сооружении node_id.
        """
        start = self.resolve_vertex(from_ref) if from_ref is not None else self.primary_olt()
        if start is None:
            r = PathReport(wavelength_nm=self.wavelength)
            r.warnings.append("first_in_node: no start vertex")
            return r

        candidates = self.find_vertices(node_id=node_id)
        if prefer_types:
            preferred = [
                i
                for i in candidates
                if self.g.vs[i]["obj_type"] in prefer_types
            ]
            if preferred:
                candidates = preferred

        best: Optional[PathReport] = None
        best_len = 10**9
        for c in candidates:
            if c == start:
                continue
            vpath = self.shortest_path(start, c)
            if vpath and len(vpath) < best_len:
                best_len = len(vpath)
                best = self.path(start, c)
        if best is None:
            r = PathReport(wavelength_nm=self.wavelength)
            r.warnings.append(f"first_in_node: no vertex in node {node_id}")
            return r
        return best

    def from_cross_to_node(
        self,
        cross_id: Union[int, str],
        node_id: int,
        *,
        port: Optional[int] = None,
        side: Optional[int] = None,
    ) -> PathReport:
        """От кросса до первой коммутации в указанном сооружении."""
        cr = self.find_vertex(TYPE_CROSS, cross_id, port=port, side=side)
        if cr is None:
            hits = self.find_vertices(TYPE_CROSS, cross_id)
            cr = hits[0] if hits else None
        if cr is None:
            r = PathReport(wavelength_nm=self.wavelength)
            r.warnings.append("from_cross_to_node: cross not in graph")
            return r
        return self.first_in_node(node_id, from_ref=cr)

    def budget_summary(
        self,
        customer_ids: Optional[Iterable[Union[int, str]]] = None,
        *,
        olt_id: Optional[Union[int, str]] = None,
    ) -> List[PathReport]:
        """Затухание OLT→каждый абонент (или все в графе)."""
        if customer_ids is None:
            customer_ids = [
                self.g.vs[i]["obj_id"] for i in self.find_customers()
            ]
        return [
            self.olt_to_customer(cid, olt_id=olt_id) for cid in customer_ids
        ]

    def worst_customer(
        self, *,
        olt_id: Optional[Union[int, str]] = None,
    ) -> Optional[PathReport]:
        reports = self.budget_summary(olt_id=olt_id)
        reports = [r for r in reports if not r.warnings or r.segments]
        if not reports:
            return None
        return max(reports, key=lambda r: r.total_db)

    def describe_interface(self, ref: VertexRef) -> dict:
        idx = self.resolve_vertex(ref)
        if idx is None:
            return {}
        a = self._vertex_attrs(idx)
        return {
            "index": idx,
            "obj_type": a.get("obj_type"),
            "obj_id": a.get("obj_id"),
            "side": a.get("side"),
            "port": a.get("port"),
            "node_id": a.get("node_id"),
            "splitter_type": a.get("splitter_type"),
            "name": a.get("name"),
        }
