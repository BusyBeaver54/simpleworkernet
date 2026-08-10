# simpleworkernet/utils/topology/errors.py
"""Ошибки построения топологии."""


class TopologyBuildError(Exception):
    """Невозможно построить граф по заданным правилам (в т.ч. linear)."""
