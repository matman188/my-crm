from django.urls import path
from crm.views.catalog import set_catalog_archive
from crm.views.users import set_user_active
from crm.views.orders import update_order_workflow
from crm.views.order_adjustments import (
    edit_order_complaint,
    edit_order_refund_amount,
    record_order_refund,
)
from crm.views.invoices import (
    invoice_logo,
    order_invoice_action,
    order_invoice_pdf,
    preview_invoice,
    preview_order_invoice,
)

from crm.views import (
    archive_customer,
    restore_customer,
    change_user_password,
    create_customer,
    create_order,
    create_product,
    create_product_category,
    create_service,
    create_user,
    customers,
    delete_customer,
    delete_order,
    delete_product,
    delete_product_category,
    delete_service,
    delete_user,
    edit_customer,
    edit_order,
    edit_product,
    edit_product_category,
    edit_profile,
    edit_service,
    edit_user,
    home,
    orders,
    save_order_customer,
    product_categories,
    products,
    services,
    system_settings,
    users,
)

urlpatterns = [
    path(
        "products/<int:object_id>/archive/",
        set_catalog_archive,
        {"kind": "product", "archived": True},
        name="archive_product",
    ),
    path(
        "products/<int:object_id>/restore/",
        set_catalog_archive,
        {"kind": "product", "archived": False},
        name="restore_product",
    ),
    path(
        "services/<int:object_id>/archive/",
        set_catalog_archive,
        {"kind": "service", "archived": True},
        name="archive_service",
    ),
    path(
        "services/<int:object_id>/restore/",
        set_catalog_archive,
        {"kind": "service", "archived": False},
        name="restore_service",
    ),
    path(
        "users/<int:user_id>/deactivate/",
        set_user_active,
        {"active": False},
        name="deactivate_user",
    ),
    path(
        "users/<int:user_id>/reactivate/",
        set_user_active,
        {"active": True},
        name="reactivate_user",
    ),
    path("", home, name="home"),
    path("orders/", orders, name="orders"),
    path("orders/create/", create_order, name="create_order"),
    path("orders/<int:order_id>/edit/", edit_order, name="edit_order"),
    path(
        "orders/<int:order_id>/complaint/",
        edit_order_complaint,
        name="edit_order_complaint",
    ),
    path(
        "orders/<int:order_id>/refund/", record_order_refund, name="record_order_refund"
    ),
    path(
        "orders/<int:order_id>/refund/<int:refund_id>/edit/",
        edit_order_refund_amount,
        name="edit_order_refund_amount",
    ),
    path(
        "orders/<int:order_id>/workflow/",
        update_order_workflow,
        name="update_order_workflow",
    ),
    path("orders/<int:order_id>/delete/", delete_order, name="delete_order"),
    path(
        "orders/<int:order_id>/invoice/preview/",
        preview_order_invoice,
        name="preview_order_invoice",
    ),
    path(
        "orders/<int:order_id>/invoices/<int:invoice_id>/pdf/",
        order_invoice_pdf,
        name="order_invoice_pdf",
    ),
    path(
        "orders/<int:order_id>/invoice/<slug:action>/",
        order_invoice_action,
        name="order_invoice_action",
    ),
    path(
        "orders/customers/<int:customer_id>/save/",
        save_order_customer,
        name="save_new_order_customer",
    ),
    path(
        "orders/<int:order_id>/customers/<int:customer_id>/save/",
        save_order_customer,
        name="save_order_customer",
    ),
    path("customers/", customers, name="customers"),
    path(
        "customers/<int:customer_id>/archive/",
        archive_customer,
        name="archive_customer",
    ),
    path(
        "customers/<int:customer_id>/restore/",
        restore_customer,
        name="restore_customer",
    ),
    path("customers/create/", create_customer, name="create_customer"),
    path("customers/<int:customer_id>/edit/", edit_customer, name="edit_customer"),
    path(
        "customers/<int:customer_id>/delete/", delete_customer, name="delete_customer"
    ),
    path("product-categories/", product_categories, name="product_categories"),
    path(
        "product-categories/create/",
        create_product_category,
        name="create_product_category",
    ),
    path(
        "product-categories/<int:category_id>/edit/",
        edit_product_category,
        name="edit_product_category",
    ),
    path(
        "product-categories/<int:category_id>/delete/",
        delete_product_category,
        name="delete_product_category",
    ),
    path("products/", products, name="products"),
    path("products/create/", create_product, name="create_product"),
    path("products/<int:product_id>/edit/", edit_product, name="edit_product"),
    path("products/<int:product_id>/delete/", delete_product, name="delete_product"),
    path("services/", services, name="services"),
    path("services/create/", create_service, name="create_service"),
    path("services/<int:service_id>/edit/", edit_service, name="edit_service"),
    path("services/<int:service_id>/delete/", delete_service, name="delete_service"),
    path("profile/", edit_profile, name="edit_profile"),
    path("system-settings/", system_settings, name="system_settings"),
    path("system-settings/invoice-preview/", preview_invoice, name="preview_invoice"),
    path("system-settings/invoice-logo/", invoice_logo, name="invoice_logo"),
    path("users/", users, name="users"),
    path("users/create/", create_user, name="create_user"),
    path("users/<int:user_id>/edit/", edit_user, name="edit_user"),
    path(
        "users/<int:user_id>/change-password/",
        change_user_password,
        name="change_user_password",
    ),
    path("users/<int:user_id>/delete/", delete_user, name="delete_user"),
]
