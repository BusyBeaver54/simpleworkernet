# Графика (SVG / PNG)

Модуль `simpleworkernet.utils.graphics` — загрузка, проверка, сохранение SVG
схем WorkerNet и конвертация в PNG.

```python
from simpleworkernet.utils.graphics import (
    SVGHandler, ImageHandler,
    save_svg, load_svg, is_svg, svg_to_png,
)
# или из пакета утилит:
from simpleworkernet.utils import SVGHandler, load_svg, svg_to_png
```

Опциональные зависимости для PNG (ставится то, что есть в системе):

| Бэкенд | Пакет / бинарь | Примечание |
|--------|----------------|------------|
| Wand | `Wand` + ImageMagick | приоритетный |
| Cairo | `cairosvg` | |
| Inkscape | бинарь `inkscape` в PATH | |
| WeasyPrint | `weasyprint` | |
| Matplotlib | `matplotlib` | fallback |

`SVGHandler.to_png` перебирает доступные бэкенды по очереди, пока один не сработает.

---

## SVGHandler

Основной класс для работы с SVG.

```python
# из bytes / str / файла
svg = SVGHandler(data)           # data: bytes | str | Path
svg = load_svg("/tmp/scheme.svg")
svg = SVGHandler().load(raw_bytes, validate=True)

print(svg.is_svg, svg.width, svg.height, svg.size)
print(svg.has_cyrillic)
print(svg.metadata)              # viewBox, размеры, …
print(svg.extract_texts())       # текстовые узлы
print(svg.extract_node_ids())    # id узлов схемы, если есть в SVG
```

### Сохранение

```python
svg.save("/tmp/out.svg", mkdir=True)
svg.save_auto(prefix="scheme", directory="~/.cache/simpleworkernet/svg")
# → уникальное имя scheme_YYYYMMDD_HHMMSS.svg
```

### PNG

```python
svg.to_png("/tmp/out.png")                 # авто-выбор бэкенда
svg.to_png("/tmp/out.png", backend="wand") # wand | cairo | inkscape | weasyprint | matplotlib
svg.to_png_wand("/tmp/out.png", dpi=150)
svg.to_png_cairo("/tmp/out.png")
# …
```

Вспомогательные представления:

```python
svg.to_bytes()
svg.to_str()
svg.to_base64()
svg.to_html(width=800, height=600)
svg.display()   # Jupyter / IPython
```

Перед конвертацией можно подготовить шрифты для кириллицы:

```python
prepared = svg.prepare_for_conversion(font_family="Arial")
```

---

## Функции верхнего уровня

```python
save_svg(data, path, force=False) -> Path
load_svg(path, validate=True, strict=False) -> SVGHandler
is_svg(data) -> bool
svg_to_png(data, output_path, backend=None, **kwargs) -> Path
# data: bytes | str | Path | SVGHandler
```

---

## ImageHandler

Обёртка над растром (PNG/JPEG/…), определяется по сигнатуре файла.

```python
img = ImageHandler(path_or_bytes)
print(img.format)   # "png", "jpeg", …
img.save("/tmp/copy.png")
```

---

## Типичный сценарий со схемой WorkerNet

```python
from simpleworkernet import WorkerNetClient
from simpleworkernet.utils.graphics import SVGHandler, svg_to_png

client = WorkerNetClient(...)
# получить SVG схемы узла / коммутации через API Node 
raw = client.Node.get_scheme(...)   # bytes

svg = SVGHandler(raw)
svg.save_auto(prefix=f"node_{node_id}")
svg.to_png(f"/tmp/node_{node_id}.png", dpi=150)
```

Подробнее о клиенте: [client-and-smartdata.md](client-and-smartdata.md).
