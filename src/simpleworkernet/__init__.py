# simpleworkernet/__init__.py
"""
SimpleWorkerNet - Python клиент для API WorkerNet
"""

import sys
import os
import atexit

from .__version__ import __version__, __author__, __email__, __license__

_IN_CLEANUP = os.environ.get('SIMPLEWORKERNET_CLEANUP') == '1'

is_cli = any(arg.endswith(('cleanup-simpleworkernet', 'simpleworkernet-cli'))
             for arg in sys.argv) or '--help' in sys.argv or '--version' in sys.argv

if is_cli:
    from .scripts.uninstall import cleanup_with_confirmation, list_applications
    from .core.logger import log
    from .core.config import config_manager

    log.suppress_output(True)
    log.configure(**config_manager.get_log_config())

    __all__ = [
        '__version__', '__author__', '__email__', '__license__',
        'cleanup_with_confirmation', 'list_applications',
    ]
else:
    from .core.constants import DEBUG, INFO, WARNING, ERROR, CRITICAL
    from .utils.app_name import get_app_name
    from .core.config import config_manager
    from .core.logger import log
    log.configure(**config_manager.get_log_config())

    from .core.client import WorkerNetClient
    from .core.cache import cache
    from .core.exceptions import (
        WorkerNetError, WorkerNetConfigError, WorkerNetConnectionError,
        WorkerNetAPIError, WorkerNetCacheError, WorkerNetValidationError,
        WorkerNetSmartDataError, GraphicsError, SVGValidationError
    )

    from .models.base import BaseModel, BaseCategory, smart_model, CollapsedField
    from .models.primitives import (
        vStr, vFlag, GeoPoint, GeoPointArray, vPhoneNumber, vINN, vKPP, vSNILS, vOGRN,
        vMoney, vPercent, vPeriod, additional_field, additional_data, HAS_PYPROJ,
    )
    from .models.operators import Operator, Where
    from .smartdata import SmartData
    from .smartdata.metadata import MetaData, PathSegment, SegmentType
    from .utils.decorators import api_method, logged_method, timer
    from .utils.graphics import save_svg, load_svg, svg_to_png
    from .utils.topology import Topology, CGraph, FNGraph
    from .scripts.uninstall import cleanup_with_confirmation, cleanup

    if not _IN_CLEANUP:
        if config_manager.cache_enabled:
            if not cache.load():
                log.info("Создание нового кэша...")
                from .models.categories.additional_data import Additional_data
                from .models.categories.address import Address
                from .models.categories.advertising import Advertising
                from .models.categories.billing import Billing
                from .models.categories.cable_route import Cable_route
                from .models.categories.call import Call
                from .models.categories.commutation import Commutation
                from .models.categories.cross import Cross
                from .models.categories.customer import Customer
                from .models.categories.cwdm import Cwdm
                from .models.categories.device import Device
                from .models.categories.employee import Employee
                from .models.categories.fiber import Fiber
                from .models.categories.gps import Gps
                from .models.categories.inventory import Inventory
                from .models.categories.key import Key
                from .models.categories.map import Map
                from .models.categories.module import Module
                from .models.categories.node import Node
                from .models.categories.notepad import Notepad
                from .models.categories.owner import Owner
                from .models.categories.service import Service
                from .models.categories.setting import Setting
                from .models.categories.sms import Sms
                from .models.categories.splitter import Splitter
                from .models.categories.system import System
                from .models.categories.tariff import Tariff
                from .models.categories.task import Task
                from .models.categories.trader import Trader
                from .models.categories.vehicle import Vehicle
                from .models.categories.vlan import Vlan

                models = [
                    Additional_data.Get_list, Additional_data.Get_value,
                    Address.Get_locality_type, Address.Get_alias, Address.Get,
                    Address.Get_province, Address.Get_district, Address.Get_city,
                    Address.Get_area, Address.Get_street, Address.Get_building_structure,
                    Address.Get_house, Address.Get_level,
                    Advertising.Get, Billing.Get,
                    Cable_route.Get_route, Cable_route.GetDuct,
                    Call.Get, Commutation.Get_data, Cross.Get_list,
                    Customer.Abon_hist, Customer.Get_customer_group, Customer.Get_data,
                    Customer.Get_data.Agreement, Customer.Get_data.Traffic,
                    Customer.Get_data.Phone, Customer.Get_data.Address,
                    Customer.Get_data.Tariff, Customer.Get_data.Service,
                    Customer.Get_data.Ip_mac, Customer.Get_data.Billing,
                    Customer.Get_data.Additional_data, Customer.Get_data.Mark,
                    Customer.Get_data.Tag, Customer.Get_data.Email, Customer.Msg,
                    Cwdm.Get, Device.Get_connected_ont_information, Device.Get_data,
                    Device.Get_data.Ifaces, Device.Get_current_ont_data,
                    Device.Get_iface_info, Device.Get_iface_info.Iface,
                    Device.Get_iface_info.Iface.Raw, Device.Get_iface_mac,
                    Device.Get_mac_list, Device.Get_ont_data, Device.Get_pon_level_history,
                    Employee.Get_data, Employee.Get_data.Division, Employee.Get_division,
                    Employee.Get_division.Staff, Employee.Get_division.Staff.Employee,
                    Employee.Get_division_list, Employee.Get_history, Employee.Get_history_type,
                    Employee.Get_timesheet_data,
                    Fiber.Catalog_cables_get, Fiber.Catalog_types_get, Fiber.Get_fiber,
                    Fiber.Get_list, Fiber.Get_list.Properties, Fiber.Get_list.Fibers,
                    Fiber.Get_list.Fibers.Color, Fiber.Map_color_get,
                    Gps.Get_info, Gps.Get_list, Gps.Get_route,
                    Inventory.Get_inventory, Inventory.Get_inventory_amount,
                    Inventory.Get_inventory_catalog, Inventory.Get_inventory_section_catalog,
                    Inventory.Get_inventory_storage, Inventory.Get_operation,
                    Key.Get_list, Map.Check_entry_point_in_polygon, Map.Get, Map.Get.Center,
                    Map.Get_poly,
                    Module.Get_api_information, Module.Get_city_list, Module.Get_connect_list,
                    Module.Get_device_list, Module.Get_device_model, Module.Get_house_list,
                    Module.Get_services_list, Module.Get_street_list,
                    Module.Get_system_information, Module.Get_system_information.Erp,
                    Module.Get_tariff_list, Module.Get_tariff_list.Speed,
                    Module.Get_user_additional_data_type_list, Module.Get_user_history,
                    Module.Get_user_list, Module.Get_user_list.Agreement,
                    Module.Get_user_list.Traffic, Module.Get_user_list.Phone,
                    Module.Get_user_list.Address, Module.Get_user_list.Tariff,
                    Module.Get_user_list.Service, Module.Get_user_list.Ip_mac,
                    Module.Get_user_list.Billing, Module.Get_user_list.Additional_data,
                    Module.Get_user_list.Mark, Module.Get_user_list.Tag,
                    Module.Get_user_list.Email, Module.Get_user_messages,
                    Module.Get_user_state_list, Module.Get_user_tags,
                    Node.Get, Node.Get_icon_list, Node.Get_id_by_coord,
                    Node.Get_redevelopment_scheme, Node.Get_type_list,
                    Node.Get_type_list.Employee_profile_rights,
                    Notepad.Get_chapter, Notepad.Get_chapter.Item, Notepad.Get_note,
                    Owner.Get, Owner.Get.Agreement, Owner.Get.Object, Owner.Get.Object.Building,
                    Service.Get, Setting.Mark_show, Sms.Status, Splitter.Get,
                    System.Get_system_info, Tariff.Get, Tariff.Get_group,
                    Task.Get_allow_staff, Task.Get_catalog_type, Task.Get_catalog_type.Timescale,
                    Task.Get_catalog_type.Access, Task.Get_catalog_type_group,
                    Task.Get_catalog_state, Task.Get_comment, Task.Get_list,
                    Task.Get_typical_comments, Task.Show, Task.Show.Date, Task.Show.State,
                    Task.Show.Address, Task.Show.Comments, Task.Show.Additional_data,
                    Task.Show.Staff, Task.Show.History, Task.Show.Task_status_history,
                    Trader.Get, Vehicle.Get, Vehicle.Get.Gps_activity, Vlan.Get_list,
                ]
                if models:
                    SmartData.preload_from_models(*models, recursive=True)

        def _save_cache():
            try:
                cache.ensure_saved()
            except Exception as e:
                log.error(f"Ошибка при сохранении кэша: {e}")

        atexit.register(_save_cache)

        app_name = get_app_name(with_hash=False)
        log.info("=" * 60)
        log.info(f"SimpleWorkerNet v{__version__} - '{app_name}'")
        log.info("=" * 60)

    __all__ = [
        '__version__', '__author__', '__email__', '__license__',
        'WorkerNetClient',
        'WorkerNetError', 'WorkerNetConfigError', 'WorkerNetConnectionError',
        'WorkerNetAPIError', 'WorkerNetCacheError', 'WorkerNetValidationError',
        'WorkerNetSmartDataError', 'GraphicsError', 'SVGValidationError',
        'config_manager', 'log', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL',
        'get_app_name', 'cleanup_with_confirmation', 'cleanup',
        'SmartData', 'cache',
        'MetaData', 'PathSegment', 'SegmentType',
        'BaseCategory', 'BaseModel', 'smart_model', 'CollapsedField',
        'vStr', 'vFlag', 'GeoPoint', 'GeoPointArray', 'HAS_PYPROJ',
        'vPhoneNumber', 'vINN', 'vKPP', 'vSNILS', 'vOGRN',
        'vMoney', 'vPercent', 'vPeriod',
        'Operator', 'Where',
        'api_method', 'logged_method', 'timer',
        'additional_field', 'additional_data',
        'save_svg', 'load_svg', 'svg_to_png',
        'CGraph', 'FNGraph', 'Topology',
    ]
