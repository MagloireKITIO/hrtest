""" horilla/config.py  Horilla app configurations """
import importlib
import logging
from django.apps import apps
from django.conf import settings
from django.contrib.auth.context_processors import PermWrapper

from horilla.horilla_apps import SIDEBARS

logger = logging.getLogger(__name__)

def get_apps_in_base_dir():
    logger.info(f"SIDEBARS content: {SIDEBARS}")
    return SIDEBARS

def import_method(accessibility):
    try:
        module_path, method_name = accessibility.rsplit(".", 1)
        module = importlib.import_module(module_path)
        accessibility_method = getattr(module, method_name)
        return accessibility_method
    except Exception as e:
        logger.error(f"Import error: {str(e)}")
        return None

ALL_MENUS = {}

def sidebar(request):
    if not request.session.session_key:
        request.session.create()
        
    base_dir_apps = get_apps_in_base_dir()
    request.MENUS = []
    MENUS = request.MENUS

    if not request.user.is_anonymous:
        for app in base_dir_apps:
            try:
                if apps.is_installed(app):
                    sidebar = importlib.import_module(f"{app}.sidebar")
                    
                    if sidebar:
                        accessibility = None
                        if getattr(sidebar, "ACCESSIBILITY", None):
                            accessibility = import_method(sidebar.ACCESSIBILITY)

                        if not accessibility or accessibility(
                            request,
                            getattr(sidebar, 'MENU', ''),
                            PermWrapper(request.user),
                        ):
                            menu_data = {
                                "menu": getattr(sidebar, 'MENU', ''),
                                "app": app,
                                "img_src": getattr(sidebar, 'IMG_SRC', ''),
                                "submenu": []
                            }
                            
                            for submenu in getattr(sidebar, 'SUBMENUS', []):
                                try:
                                    submenu_accessibility = None
                                    if submenu.get("accessibility"):
                                        submenu_accessibility = import_method(submenu["accessibility"])

                                    redirect = submenu["redirect"].split("?")[0]
                                    submenu["redirect"] = redirect

                                    if not submenu_accessibility or submenu_accessibility(
                                        request,
                                        submenu,
                                        PermWrapper(request.user),
                                    ):
                                        menu_data["submenu"].append(submenu)
                                except Exception as e:
                                    logger.error(f"Submenu error: {str(e)}")
                                    continue
                                    
                            MENUS.append(menu_data)
            except Exception as e:
                logger.error(f"Error processing app {app}: {str(e)}")
                continue

    ALL_MENUS[request.session.session_key] = MENUS
    return MENUS

def get_MENUS(request):
    if not request.session.session_key:
        request.session.create()
    ALL_MENUS[request.session.session_key] = []
    sidebar(request)
    return {"sidebar": ALL_MENUS.get(request.session.session_key, [])}