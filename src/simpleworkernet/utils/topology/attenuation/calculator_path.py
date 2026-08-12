# simpleworkernet/utils/topology/attenuation/calculator_path.py
"""Path report assembly for Attenuation."""
from __future__ import annotations
from typing import Any, List, Optional
from ..constants import (
    TYPE_CUSTOMER, TYPE_FIBER, TYPE_OLT, TYPE_SPLITTER,
    TYPE_SWITCH, TYPE_ONU, TYPE_RADIO,
)
from .models import AttenuationSegment, EndpointInfo, PathReport
from .calculator_segments import (
    _label_vertex, _obj_display_name, _olt_host, _cable_name, _attr,
    _SPLITTER_IN_SIDE, _SPLITTER_OUT_SIDE,
)
from .calculator_path_fiber import AttenuationPathFiberMixin


class AttenuationPathMixin(AttenuationPathFiberMixin):
    def _splitter_port_name(self, splitter_obj, port: int) -> Optional[str]:
        if splitter_obj is None or not port:
            return None
        for attr in ("ports", "port_list", "ifaces", "out_ports"):
            ports = (
                getattr(splitter_obj, attr, None)
                if not isinstance(splitter_obj, dict)
                else splitter_obj.get(attr)
            )
            if not ports:
                continue
            if isinstance(ports, dict):
                entry = ports.get(port) or ports.get(str(port))
                if isinstance(entry, dict):
                    return entry.get("name") or entry.get("title") or entry.get("label")
                if isinstance(entry, str):
                    return entry
            if isinstance(ports, list):
                for p in ports:
                    if not isinstance(p, dict):
                        continue
                    num = p.get("number") or p.get("port") or p.get("id")
                    try:
                        if int(num) == int(port):
                            return p.get("name") or p.get("title") or p.get("label")
                    except (TypeError, ValueError):
                        continue
        return None

    def _splitter_segments(
        self, splitter_vertex_attrs: dict, *, direction: str = "unknown", edge_side=None,
    ) -> List[AttenuationSegment]:
        splitter_vertex_attrs = self._ensure_api_obj(splitter_vertex_attrs)
        splitter_id = splitter_vertex_attrs.get("obj_id")
        side = int(splitter_vertex_attrs.get("side") or edge_side or 0)
        port = int(splitter_vertex_attrs.get("port") or 0)
        splitter_obj = splitter_vertex_attrs.get("api_obj")
        catalog_id = self._splitter_catalog_id(splitter_obj)
        pout = None
        if splitter_obj is not None:
            pout = (
                getattr(splitter_obj, "port_count_out", None)
                if not isinstance(splitter_obj, dict)
                else splitter_obj.get("port_count_out")
            )
        topology = None
        if splitter_obj is not None:
            if isinstance(splitter_obj, dict):
                topology = splitter_obj.get("topology_type") or splitter_obj.get("topology")
            else:
                topology = getattr(splitter_obj, "topology_type", None) or getattr(splitter_obj, "topology", None)
        if not topology:
            topology = splitter_vertex_attrs.get("splitter_type")
        name = splitter_vertex_attrs.get("obj_name")
        if not name and hasattr(self, "_resolve_splitter_name"):
            name = self._resolve_splitter_name(splitter_vertex_attrs)
        if not name:
            name = _obj_display_name(splitter_vertex_attrs)
        port_name = self._splitter_port_name(splitter_obj, port)
        if not port_name:
            port_name = splitter_vertex_attrs.get("port_name")
        ratio_key = None
        if name:
            from .catalog_helpers import guess_ratio_key
            ratio_key = guess_ratio_key(str(name))
        if hasattr(self.catalog, "splitter_port_db_triple"):
            db_min, db, db_max, source, cat_port_name = self.catalog.splitter_port_db_triple(
                splitter_id=splitter_id, catalog_id=catalog_id, catalog_name=name,
                ratio_key=ratio_key, topology_type=topology,
                port=port if port else None, port_name=port_name,
                port_count_out=pout or 0, wavelength_nm=self.wavelength, prefer_name=True,
            )
        else:
            result = self.catalog.splitter_port_db(
                splitter_id=splitter_id, catalog_id=catalog_id, catalog_name=name,
                ratio_key=ratio_key, topology_type=topology,
                port=port if port else None, port_name=port_name,
                port_count_out=pout or 0, wavelength_nm=self.wavelength,
                use_max=self.use_max, prefer_name=True,
            )
            db, source = result[0], result[1]
            cat_port_name = result[2] if len(result) > 2 else None
            db_min = db_max = db
        if cat_port_name:
            port_name = cat_port_name
        port_label = str(port) if port else "?"
        if port_name:
            port_label = f"{port}/{port_name}"
        name_label = name or f"id={splitter_id}"
        return [AttenuationSegment(
            kind="splitter", db=db, db_min=db_min, db_max=db_max,
            description=(
                f"splitter {name_label} port={port_label} "
                f"side={side} ({topology or '?'}) [{direction}] src={source}"
            ),
            obj_type=TYPE_SPLITTER, obj_id=str(splitter_id),
            obj_name=str(name) if name else None,
            port=port if port else None,
            port_name=str(port_name) if port_name else None,
            side=side, wavelength_nm=self.wavelength, source=source,
            meta={
                "catalog_id": catalog_id,
                "topology": topology,
                "direction": direction, "ratio_key": ratio_key,
                "in_side": _SPLITTER_IN_SIDE, "out_side": _SPLITTER_OUT_SIDE,
            },
        )]

    def _endpoint_from_vertex(self, vindex: int) -> EndpointInfo:
        va = self._ensure_api_obj(self._vertex_attrs(vindex))
        ot = str(va.get("obj_type") or "")
        oid = str(va.get("obj_id") or "")
        side = va.get("side")
        port = va.get("port")
        try:
            side_i = int(side) if side is not None else None
        except (TypeError, ValueError):
            side_i = None
        try:
            port_i = int(port) if port is not None else None
        except (TypeError, ValueError):
            port_i = None
        name = _obj_display_name(va)
        _dev = {TYPE_OLT, TYPE_SWITCH, TYPE_ONU, TYPE_RADIO}
        host = _olt_host(va) if ot in _dev else None
        port_name = va.get("port_name")
        obj = va.get("api_obj")
        if ot in _dev and port_i is not None:
            resolved = self._device_port_name(obj, port_i)
            if resolved:
                port_name = resolved
        elif port_name is None and obj is not None and port_i is not None:
            port_name = self._device_port_name(obj, port_i)
        commutation_index = None
        login = None
        if ot == TYPE_CUSTOMER:
            commutation_index = self._customer_commutation_index(va, port_i)
            login = self._customer_login(obj)
        meta = {}
        if ot == TYPE_FIBER:
            cn = _cable_name(va)
            if cn:
                meta["cable_name"] = cn
                if not name:
                    name = cn
            core = self._fiber_core_info(va)
            if core.get("port") is not None:
                port_i = int(core["port"])
            if core.get("port_name"):
                port_name = core["port_name"]
            if core.get("fiber_core_id") is not None:
                meta["fiber_core_id"] = core["fiber_core_id"]
            if core.get("fiber_number") is not None:
                meta["fiber_number"] = core["fiber_number"]
            if core.get("module_number") is not None:
                meta["module_number"] = core["module_number"]
            if core.get("fiber_color"):
                meta["fiber_color"] = core["fiber_color"]
            if core.get("module_color"):
                meta["module_color"] = core["module_color"]
            if core.get("mf_path"):
                meta["mf_path"] = core["mf_path"]
        node_id = va.get("node_id")
        try:
            node_id = int(node_id) if node_id is not None else None
        except (TypeError, ValueError):
            node_id = None
        return EndpointInfo(
            obj_type=ot, obj_id=oid,
            obj_name=str(name) if name else None,
            node_id=node_id,
            side=side_i, port=port_i,
            port_name=str(port_name) if port_name else None,
            host=str(host) if host else None,
            commutation_index=commutation_index,
            login=str(login) if login else None,
            label=_label_vertex(va), meta=meta,
        )

    def _device_port_name(self, obj: Any, port: int) -> Optional[str]:
        if obj is None:
            return None

        def _entry_name(entry) -> Optional[str]:
            if entry is None:
                return None
            if isinstance(entry, str):
                s = entry.strip()
                return s or None
            if isinstance(entry, dict):
                for key in ("ifName", "if_name", "name", "title", "label", "caption", "ifDescr"):
                    v = entry.get(key)
                    if v not in (None, ""):
                        return str(v).strip() or None
                return None
            for key in ("ifName", "if_name", "name", "title", "label", "caption", "ifDescr"):
                v = getattr(entry, key, None)
                if v not in (None, ""):
                    return str(v).strip() or None
            return None

        def _entry_nums(entry) -> list:
            nums = []
            if isinstance(entry, dict):
                keys = ("ifNumber", "if_number", "ifIndex", "if_index", "number", "port", "id", "index", "position")
                for k in keys:
                    v = entry.get(k)
                    if v is not None:
                        try:
                            nums.append(int(v))
                        except (TypeError, ValueError):
                            pass
            else:
                for k in ("ifNumber", "if_number", "ifIndex", "if_index", "number", "port", "id", "index", "position"):
                    v = getattr(entry, k, None)
                    if v is not None:
                        try:
                            nums.append(int(v))
                        except (TypeError, ValueError):
                            pass
            return nums

        for attr in ("ifaces", "interfaces", "ports", "port_list"):
            ports = getattr(obj, attr, None) if not isinstance(obj, dict) else obj.get(attr)
            if not ports:
                continue
            if isinstance(ports, dict):
                entry = ports.get(port) or ports.get(str(port))
                name = _entry_name(entry)
                if name:
                    return name
                for entry in ports.values():
                    if port in _entry_nums(entry):
                        name = _entry_name(entry)
                        if name:
                            return name
            if isinstance(ports, (list, tuple)):
                for p in ports:
                    if port in _entry_nums(p):
                        name = _entry_name(p)
                        if name:
                            return name
        return None

    def _customer_commutation_index(self, vattrs: dict, port: Optional[int]) -> Optional[int]:
        obj = vattrs.get("api_obj")
        if obj is None:
            return port
        for attr in ("commutation_index", "commutation", "comm_index", "index"):
            val = getattr(obj, attr, None) if not isinstance(obj, dict) else obj.get(attr)
            if val is not None:
                try:
                    return int(val)
                except (TypeError, ValueError):
                    pass
        meta = vattrs.get("meta") or {}
        if "commutation_index" in meta:
            try:
                return int(meta["commutation_index"])
            except (TypeError, ValueError):
                pass
        return port

    def _customer_login(self, obj: Any) -> Optional[str]:
        """Номер договора: Customer.login."""
        if obj is None:
            return None
        for key in ("login", "Login", "dognumber", "agreement_number", "contract"):
            val = getattr(obj, key, None) if not isinstance(obj, dict) else obj.get(key)
            if val is not None and val != "":
                return str(val).strip() or None
        return None

    def _dedupe_cross_adapters(
        self, segs: List[AttenuationSegment],
    ) -> List[AttenuationSegment]:
        """Оставить ровно один adapter на cross_id (первый по пути)."""
        seen: set = set()
        out: List[AttenuationSegment] = []
        for s in segs:
            if s.kind == "adapter" and s.obj_id:
                cid = str(s.obj_id)
                if cid in seen:
                    continue
                seen.add(cid)
            out.append(s)
        return out

    def _orient_vpath_for_cumulative(
        self, vpath: List[int], direction: str,
    ) -> List[int]:
        """Ориентировать путь по direction (upstream/downstream)."""
        if not vpath or len(vpath) < 2 or self.g is None:
            return list(vpath)
        d = (direction or "unknown").strip().lower()
        if d not in ("upstream", "downstream"):
            return list(vpath)

        device_types = {TYPE_OLT, TYPE_SWITCH, TYPE_ONU, TYPE_RADIO}
        try:
            t0 = self.g.vs[vpath[0]]["obj_type"]
            t1 = self.g.vs[vpath[-1]]["obj_type"]
        except Exception:
            return list(vpath)

        start_dev = t0 in device_types
        end_dev = t1 in device_types
        start_cust = t0 == TYPE_CUSTOMER
        end_cust = t1 == TYPE_CUSTOMER

        if d == "upstream":
            if start_cust and end_dev:
                return list(reversed(vpath))
            return list(vpath)
        if start_dev and end_cust:
            return list(reversed(vpath))
        return list(vpath)

    def _stamp_node_ids(self, segs, vpath) -> None:
        """Проставить node_id (сооружение связи) на сегменты по вершинам пути."""
        if self.g is None or not segs:
            return
        node_by_obj = {}
        for vi in vpath or []:
            try:
                va = self._vertex_attrs(int(vi))
            except Exception:
                continue
            ot, oid = va.get("obj_type"), va.get("obj_id")
            nid = va.get("node_id")
            if ot is None or oid is None or nid is None:
                continue
            try:
                node_by_obj[(str(ot), str(oid))] = int(nid)
            except (TypeError, ValueError):
                continue
        for s in segs:
            if s.node_id is not None:
                continue
            if s.obj_type is None or s.obj_id is None:
                continue
            s.node_id = node_by_obj.get((str(s.obj_type), str(s.obj_id)))

    def _report_from_vpath(
        self, vpath: List[int], *, direction: Optional[str] = None,
    ) -> PathReport:
        if direction is None:
            direction = self._direction_of_path(vpath)
        vpath = self._orient_vpath_for_cumulative(vpath, direction or "unknown")
        segs: List[AttenuationSegment] = []
        endpoints = {vpath[0], vpath[-1]} if len(vpath) >= 1 else set()
        cross_adapter_seen: set = set()
        for a, b in zip(vpath, vpath[1:]):
            segs.extend(self._edge_segments(
                a, b, direction=direction, path_endpoints=endpoints,
                cross_adapter_seen=cross_adapter_seen,
            ))
        segs = self._dedupe_cross_adapters(segs)
        self._stamp_node_ids(segs, vpath)
        total = sum(s.db for s in segs)
        total_min = sum((s.db_min if s.db_min is not None else s.db) for s in segs)
        total_max = sum((s.db_max if s.db_max is not None else s.db) for s in segs)
        warnings, missing = [], []
        for s in segs:
            if s.source == "estimated":
                warnings.append(f"estimated: {s.description}")
            if s.kind == "fiber" and s.length_m is None:
                missing.append(f"fiber length:{s.obj_id}")
        from_ep = self._endpoint_from_vertex(vpath[0])
        to_ep = self._endpoint_from_vertex(vpath[-1])
        device_ep = customer_ep = None
        for ep in (from_ep, to_ep):
            if ep.obj_type == TYPE_CUSTOMER and customer_ep is None:
                customer_ep = ep
        for prefer in (TYPE_OLT, TYPE_SWITCH, TYPE_ONU, TYPE_RADIO):
            for ep in (from_ep, to_ep):
                if ep.obj_type == prefer:
                    device_ep = ep
                    break
            if device_ep is not None:
                break
        return PathReport(
            total_db=total, total_db_min=total_min, total_db_max=total_max,
            wavelength_nm=self.wavelength, segments=segs,
            vertex_path=list(vpath), direction=direction or "",
            from_label=str(from_ep), to_label=str(to_ep),
            from_endpoint=from_ep, to_endpoint=to_ep,
            device_endpoint=device_ep, customer_endpoint=customer_ep,
            warnings=warnings, missing=missing,
        )
