from .catalog import (
    create_product,
    create_product_category,
    create_service,
    delete_product,
    delete_product_category,
    delete_service,
    edit_product,
    edit_product_category,
    edit_service,
    product_categories,
    products,
    services,
)
from .customers import (
    archive_customer,
    create_customer,
    customers,
    delete_customer,
    edit_customer,
    restore_customer,
)
from .home import home
from .orders import create_order, delete_order, edit_order, orders, save_order_customer
from .profile import edit_profile
from .settings import system_settings
from .users import change_user_password, create_user, delete_user, edit_user, users

__all__ = [
    "archive_customer",
    "restore_customer",
    "change_user_password",
    "create_customer",
    "create_order",
    "create_product",
    "create_product_category",
    "create_service",
    "create_user",
    "customers",
    "delete_customer",
    "delete_order",
    "delete_product",
    "delete_product_category",
    "delete_service",
    "delete_user",
    "edit_customer",
    "edit_order",
    "edit_product",
    "edit_product_category",
    "edit_profile",
    "edit_service",
    "edit_user",
    "home",
    "orders",
    "save_order_customer",
    "product_categories",
    "products",
    "services",
    "system_settings",
    "users",
]
