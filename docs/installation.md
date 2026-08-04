# Установка

## Базовый пакет

```bash
pip install simpleworkernet
```

Или из GitHub:

```bash
pip install git+https://github.com/busy4beaver/simpleworkernet.git
```

Требуется **Python 3.12+**.

## Опциональные зависимости

| Пакет | Зачем |
|-------|-------|
| `python-igraph` | графовая топология (CGraph / FNGraph) |
| `pyproj` | проекция UTM |
| `Wand` (ImageMagick) | SVG → PNG (один из бэкендов) |

```bash
pip install python-igraph
pip install pyproj
pip install Wand
```

## Разработка

```bash
git clone https://github.com/busy4beaver/simpleworkernet.git
cd simpleworkernet
pip install -e ".[dev]"   # или: pip install -r requirements-dev.txt
pytest tests/ -m "not integration" -v
```
