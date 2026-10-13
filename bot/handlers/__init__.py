from .common import setup_common_router
from .catalog import setup_catalog_router
from .cart import setup_cart_router
from .checkout import setup_checkout_router
from .orders import setup_orders_router
from .admin import setup_admin_router
from .channel import setup_channel_router

__all__ = [
    "setup_common_router",
    "setup_catalog_router",
    "setup_cart_router",
    "setup_checkout_router",
    "setup_orders_router",
    "setup_admin_router",
    "setup_channel_router"
]
