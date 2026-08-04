# Графика

```python
from simpleworkernet import save_svg, load_svg, svg_to_png

save_svg(svg_string, "scheme.svg")
data = load_svg("scheme.svg")
svg_to_png("scheme.svg", "scheme.png", width=1200)
```

Бэкенды (первый доступный): Wand → Cairo → Inkscape → WeasyPrint.

Для Wand: `pip install Wand` (нужен ImageMagick).
