# simpleworkernet/utils/topology/topology_build_params.py
"""Общие kwargs построения Topology/CGraph."""

# Документация параметров build_from_*:
#
# port: int — один порт
# ports: list[int] | str — список или "1-8,10,12-15"
# port_ranges: list[tuple[int,int]] — [(1,8),(10,12)]
# side: 1|2 — для cross/splitter/fiber
# linear: bool — линейный CGraph
# linear_on_fail: "raise" | "continue"
# included_fibers / excluded_fibers / excluded_nodes — фильтры (без изменений)

BUILD_KW = (
    "port", "ports", "port_ranges", "side",
    "included_fibers", "excluded_fibers", "excluded_nodes",
    "linear", "linear_on_fail",
)
