# Графика

Утилиты SVG/PNG в `simpleworkernet.utils.graphics`.

```python
from simpleworkernet import save_svg, load_svg, svg_to_png

save_svg(svg_string, "scheme.svg")
data = load_svg("scheme.svg")          # str или bytes содержимого
svg_to_png("scheme.svg", "scheme.png", width=1200)
```

## Бэкенды SVG → PNG

Пробуются по порядку, используется первый доступный:

1. **Wand** (ImageMagick) — `pip install Wand`
2. **Cairo**
3. **Inkscape** (CLI)
4. **WeasyPrint**

При отсутствии всех бэкендов — ошибка конвертации (`GraphicsError` / связанное исключение).

Параметр `width` задаёт целевую ширину растра; высота масштабируется пропорционально (зависит от бэкенда).
