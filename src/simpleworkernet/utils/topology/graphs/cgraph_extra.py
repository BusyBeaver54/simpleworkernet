# simpleworkernet/utils/topology/graphs/cgraph_extra.py
"""Доп. методы CGraph (linear check)."""


def cgraph_is_linear(self) -> bool:
    """Путь: связен и все степени ≤ 2."""
    n = self.vcount()
    if n <= 1:
        return True
    try:
        if not self.is_connected():
            return False
    except Exception:
        pass
    try:
        degrees = self.degree()
    except Exception:
        degrees = [self._g.degree(i) for i in range(n)]
    return all(d <= 2 for d in degrees)
