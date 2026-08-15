# Установка

## Базовый пакет

```bash
pip install simpleworkernet
```

Или из GitHub (актуальный `main`):

```bash
pip install git+https://github.com/busy4beaver/simpleworkernet.git
```

Требуется **Python 3.12+**. Единственная обязательная зависимость: `requests`.

После установки доступны:

- импорт `import simpleworkernet` / `from simpleworkernet import WorkerNetClient, …`
- CLI: `cleanup-simpleworkernet`

## Опциональные зависимости

| Пакет | Зачем | Без него |
|-------|-------|----------|
| `python-igraph` | CGraph / FNGraph / Topology | Импорт топологии упадёт при использовании графов |
| `pyproj` | `projection="utm"` у GeoPoint | UTM недоступен (`HAS_PYPROJ=False`) |
| `Wand` (+ ImageMagick) | SVG → PNG | Другие бэкенды (Cairo / Inkscape / WeasyPrint) или ошибка конвертации |

Рекомендуемый способ для топологии (через extras, как в README):

```bash
pip install "simpleworkernet[topology]"
```

Либо вручную:

```bash
pip install python-igraph pyproj Wand
```

## Разработка

```bash
git clone https://github.com/busy4beaver/simpleworkernet.git
cd simpleworkernet
pip install -e .
pip install -r requirements-dev.txt   # pytest и пр.
pytest tests/ -m "not integration" -v
```

Документация в репозитории: [docs/](https://github.com/busy4beaver/simpleworkernet/tree/main/docs).
