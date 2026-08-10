"""
Менеджер конфигурации для SimpleWorkerNet
Синглтон для текущего процесса, использует имя текущего приложения
"""
import os
import sys
import json
from pathlib import Path
from typing import Optional, Dict, Any, Union, Literal, List
from dataclasses import dataclass, field, asdict

from ..utils.app_name import get_app_name


# Типы для конфигурации
CacheEvictStrategy = Literal['lru', 'lfu', 'fifo']


def get_app_config_dir(app_name: str) -> Path:
    """Возвращает директорию конфигурации для приложения"""
    if sys.platform == 'win32':
        base = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming'))
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support'
    else:
        base = Path.home() / '.config'
    return base / 'simpleworkernet' / app_name


def get_app_cache_dir(app_name: str) -> Path:
    """Возвращает директорию кэша для приложения"""
    if sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Caches'
    else:
        base = Path.home() / '.cache'
    return base / 'simpleworkernet' / app_name


def get_app_logs_dir(app_name: str) -> Path:
    """Возвращает директорию логов для приложения (legacy, для cleanup старых файлов)."""
    if sys.platform == 'win32':
        base = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming'))
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Logs'
    else:
        base = Path.home() / '.local' / 'share'
    return base / 'simpleworkernet' / app_name / 'logs'


@dataclass
class CacheConfig:
    """Конфигурация кэша для SmartDataCache"""
    enabled: bool = True
    max_size: int = 200000
    evict_strategy: CacheEvictStrategy = 'lru'
    evict_threshold: float = 0.95
    evict_percent: float = 0.25
    auto_save: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            'enabled': self.enabled,
            'max_size': self.max_size,
            'evict_strategy': self.evict_strategy,
            'evict_threshold': self.evict_threshold,
            'evict_percent': self.evict_percent,
            'auto_save': self.auto_save,
        }


def _default_preload_types() -> List[str]:
    return ["node", "device", "splitter", "cross", "cwdm", "fiber"]


@dataclass
class WorkerNetConfig:
    """Конфигурация для текущего приложения.

    Настройки topology/attenuation — плоские поля здесь же
    (доступ через ConfigManager), без отдельных классов.
    """

    cache: CacheConfig = field(default_factory=CacheConfig)
    default_timeout: int = 30
    max_retries: int = 3
    user_agent: str = "SimpleWorkerNet/1.0"
    smartdata_max_depth: int = 100

    bulk_timeout: int = 120
    customer_list_timeout: int = 300
    preload_on_init: bool = True
    preload_types: List[str] = field(default_factory=_default_preload_types)
    preload_customers: bool = False
    preload_workers: int = 6

    attenuation_json_dir: Optional[str] = None
    attenuation_json_filename: str = "attenuation_{host}.json"
    attenuation_default_wavelength: int = 1550
    attenuation_use_max_default: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkerNetConfig":
        valid_keys = set(cls.__annotations__.keys())
        filtered: Dict[str, Any] = {}
        topo = data.get("topology") if isinstance(data.get("topology"), dict) else {}
        att = data.get("attenuation") if isinstance(data.get("attenuation"), dict) else {}
        legacy_map = {
            "bulk_timeout": topo.get("bulk_timeout"),
            "customer_list_timeout": topo.get("customer_list_timeout"),
            "preload_on_init": topo.get("preload_on_init"),
            "preload_types": topo.get("preload_types"),
            "preload_customers": topo.get("preload_customers"),
            "preload_workers": topo.get("preload_workers"),
            "attenuation_json_dir": att.get("json_dir"),
            "attenuation_json_filename": att.get("json_filename"),
            "attenuation_default_wavelength": att.get("default_wavelength"),
            "attenuation_use_max_default": att.get("use_max_default"),
        }
        for k, v in legacy_map.items():
            if v is not None and k not in data:
                data = {**data, k: v}
        for k, v in data.items():
            if k not in valid_keys:
                continue
            if k == "cache" and isinstance(v, dict):
                filtered[k] = CacheConfig(**{
                    kk: vv for kk, vv in v.items()
                    if kk in CacheConfig.__annotations__
                })
            else:
                filtered[k] = v
        return cls(**filtered)
