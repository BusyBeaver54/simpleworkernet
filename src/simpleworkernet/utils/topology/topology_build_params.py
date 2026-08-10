# simpleworkernet/utils/topology/topology_build_params.py
"""Параметры построения Topology/CGraph.

port — единый параметр портов::

    port=5
    port=(1, 8)                 # диапазон 1..8
    port=[1, 2, (5, 8), 10]     # смешанный список
    port=[5]                    # список из одного
    port="1-8,10,12-15"         # строка
    port=None                   # все порты

side: 1|2 — для cross/splitter/fiber
linear: bool
linear_on_fail: "raise" | "continue"
included_fibers / excluded_fibers / excluded_nodes — фильтры
"""

BUILD_KW = (
    "port", "side",
    "included_fibers", "excluded_fibers", "excluded_nodes",
    "linear", "linear_on_fail",
)
