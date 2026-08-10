# **SimpleWorkerNet**

Python-клиент для REST API [WorkerNet](https://workernet.ru) с типизацией ответов, SmartData и графовой топологией сети.

[![Tag](https://img.shields.io/github/v/tag/busy4beaver/simpleworkernet?color=00c2e8)](https://pypi.org/project/simpleworkernet/)
[![Supported Python versions](https://img.shields.io/badge/python-3.12%2B-blue?logo=python&logoColor=FFE873)](https://www.python.org/downloads/)
[![PyPI - Version](https://img.shields.io/pypi/v/simpleworkernet)](https://pypi.org/project/simpleworkernet/)
[![Downloads](https://static.pepy.tech/badge/simpleworkernet)](https://pepy.tech/project/simpleworkernet)

---

## Возможности

| Модуль | Описание |
|--------|----------|
| **Клиент** | REST, сессии, retry, типизированные ответы |
| **SmartData** | Динамические модели по схемам полей API |
| **Топология** | `NetworkTopology`, CGraph + FNGraph, единый `port`, linear-режим, `get_linear`, simple paths |
| **Attenuation** | `calculate()` по запросу, JSON-каталог, PathReport / MultiPathReport |
| **Графика** | SVG → PNG (Wand / Cairo / Inkscape / WeasyPrint) |

---

## Установка

```bash
pip install simpleworkernet
# топология и затухания:
pip install "simpleworkernet[topology]"   # python-igraph
```

---

## Быстрый старт

```python
from simpleworkernet import WorkerNetClient

client = WorkerNetClient("my.workernet.ru", api_key="...")
nodes = client.Node.get_list()
```

Топология и затухания — см. документацию ниже.

---

## Документация

| Документ | Содержание |
|----------|------------|
| [Топология](docs/topology.md) | NetworkTopology, CGraph, FNGraph, port, linear, get_linear |
| [Затухания](docs/attenuation.md) | Каталог JSON, calculate, PathReport, MultiPathReport |
| [Графика](docs/graphics.md) | SVG / PNG |

---

## Лицензия

MIT
