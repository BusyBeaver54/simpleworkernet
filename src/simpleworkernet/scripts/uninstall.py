# simpleworkernet/scripts/uninstall.py
"""
Скрипт для полной очистки SimpleWorkerNet
"""
import os
# Устанавливаем переменную окружения до любых импортов simpleworkernet
os.environ['SIMPLEWORKERNET_CLEANUP'] = '1'

import sys
import shutil
import time
import stat
import json
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Set, Any, Literal
import argparse

CleanupMode = Literal['all', 'logs', 'cache', 'config']


def get_simpleworkernet_root_dirs() -> Dict[str, Path]:
    """Возвращает корневые директории SimpleWorkerNet для разных ОС."""
    dirs = {}
    if sys.platform == 'win32':
        app_data = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming'))
        local_app_data = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
        dirs['config_root'] = app_data / 'simpleworkernet'
        dirs['cache_root'] = local_app_data / 'simpleworkernet'
        dirs['logs_root'] = app_data / 'simpleworkernet'
    elif sys.platform == 'darwin':
        dirs['config_root'] = Path.home() / 'Library' / 'Application Support' / 'simpleworkernet'
        dirs['cache_root'] = Path.home() / 'Library' / 'Caches' / 'simpleworkernet'
        dirs['logs_root'] = Path.home() / 'Library' / 'Logs' / 'simpleworkernet'
    else:
        # Linux: match get_app_logs_dir -> ~/.local/share/simpleworkernet/<app>/logs
        dirs['config_root'] = Path.home() / '.config' / 'simpleworkernet'
        dirs['cache_root'] = Path.home() / '.cache' / 'simpleworkernet'
        dirs['logs_root'] = Path.home() / '.local' / 'share' / 'simpleworkernet'
    return dirs
