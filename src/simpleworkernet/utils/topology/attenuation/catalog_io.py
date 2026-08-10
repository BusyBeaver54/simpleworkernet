# simpleworkernet/utils/topology/attenuation/catalog_io.py
"""Сохранение/загрузка AttenuationCatalog."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Union


class CatalogIOMixin:
    def save(self, path: Union[str, Path]) -> Path:
        """Сохранить каталог в JSON (generate_template / update_template)."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return p

    def to_json(self, path: Union[str, Path]) -> Path:
        """Alias для save."""
        return self.save(path)
