# DataCache — auto-expanded from compressed parts (see _cache_src.part*)
from __future__ import annotations
import base64
import zlib
from pathlib import Path

_parts_dir = Path(__file__).resolve().parent
_chunks = []
for _i in range(20):
    _p = _parts_dir / f"_cache_src.part{_i}"
    if not _p.exists():
        break
    _chunks.append(_p.read_text(encoding="ascii"))
if not _chunks:
    raise ImportError("DataCache source parts missing: _cache_src.part*")
_src = zlib.decompress(base64.b64decode("".join(_chunks))).decode("utf-8")
_g = globals()
_g["__package__"] = __package__ or "simpleworkernet.utils.topology"
_g["__name__"] = __name__
_g["__file__"] = __file__
exec(compile(_src, __file__, "exec"), _g)
