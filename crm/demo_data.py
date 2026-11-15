from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction

from crm.authz import (
    ACCESS_LEVEL_ADMIN,
    ACCESS_LEVEL_SYSTEM_ADMIN,
    ACCESS_LEVEL_USER,
    assign_access_level,
)
from crm.models import Customer, Product, ProductCategory, Service

DEMO_PASSWORD = "DemoPass123!"

DEMO_CATEGORIES = (
    {
        "name": "Demo Standard Items",
        "previous_name": "Demo Infrastructure",
        "description": "Everyday items used to demonstrate a general service workflow.",
    },
    {
        "name": "Demo Special Items",
        "previous_name": "Demo Productivity",
        "description": "Items that may need a specialist or customised service.",
    },
    {
        "name": "Demo Item Sets",
        "previous_name": "Demo Security",
        "description": "Sets of items that can be handled together on an order.",
    },
)

DEMO_PRODUCTS = (
    {
        "name": "Demo Standard Item",
        "previous_name": "Demo Edge Router X1",
        "category": "Demo Standard Items",
        "description": "A general-purpose item for a typical customer request.",
    },
    {
        "name": "Demo Small Item",
        "previous_name": "Demo Managed Switch 24",
        "category": "Demo Standard Items",
        "description": "A smaller item that can receive one or more services.",
    },
    {
        "name": "Demo Large Item",
        "previous_name": "Demo Wi-Fi Access Point Pro",
        "category": "Demo Standard Items",
        "description": "A larger item used to demonstrate a separate order line.",
    },
    {
        "name": "Demo Accessory",
        "previous_name": "Demo Backup Appliance Mini",
        "category": "Demo Standard Items",
        "description": "An accessory that can be assessed or serviced separately.",
    },
    {
        "name": "Demo Premium Item",
        "previous_name": "Demo Cloud Desk Suite",
        "category": "Demo Special Items",
        "description": "An item that may require additional care or customisation.",
    },
    {
        "name": "Demo Custom Item",
        "previous_name": "Demo Team Mail Plus",
        "category": "Demo Special Items",
        "description": "An item with customer-specific instructions.",
    },
    {
        "name": "Demo Replacement Part",
        "previous_name": "Demo CRM Insights Add-on",
        "category": "Demo Special Items",
        "description": "A part that can be adjusted or prepared as part of a service.",
    },
    {
        "name": "Demo Small Set",
        "previous_name": "Demo Endpoint Shield",
        "category": "Demo Item Sets",
        "description": "A small set of related customer items.",
    },
    {
        "name": "Demo Standard Set",
        "previous_name": "Demo Secure Gateway",
        "category": "Demo Item Sets",
        "description": "A set of related items handled as one catalog entry.",
    },
    {
        "name": "Demo Large Set",
        "previous_name": "Demo Identity Vault",
        "category": "Demo Item Sets",
        "description": "A larger set for demonstrating an order with several services.",
    },
)

DEMO_SERVICES = (
    {
        "name": "Demo Basic Service",
        "previous_name": "Demo Installation and Setup",
        "description": "A standard service for everyday items.",
        "price": Decimal("75.00"),
        "products": (
            "Demo Standard Item",
            "Demo Small Item",
            "Demo Large Item",
        ),
    },
    {
        "name": "Demo Detailed Service",
        "previous_name": "Demo Network Health Check",
        "description": "Additional work for items that need more time and attention.",
        "price": Decimal("150.00"),
        "products": (
            "Demo Standard Item",
            "Demo Small Item",
            "Demo Standard Set",
        ),
    },
    {
        "name": "Demo Customisation",
        "previous_name": "Demo Migration Workshop",
        "description": "Changes made to suit the customer's instructions.",
        "price": Decimal("100.00"),
        "products": (
            "Demo Premium Item",
            "Demo Custom Item",
            "Demo Replacement Part",
        ),
    },
    {
        "name": "Demo Assessment",
        "previous_name": "Demo Managed Backup Review",
        "description": "Inspect an item and record the work required.",
        "price": Decimal("50.00"),
        "products": ("Demo Accessory",),
    },
    {
        "name": "Demo Express Service",
        "previous_name": "Demo Endpoint Rollout",
        "description": "An optional priority service for any item or the whole order.",
        "price": Decimal("80.00"),
        "products": (),
    },
    {
        "name": "Demo Delivery",
        "previous_name": "Demo Security Audit",
        "description": "An optional delivery charge that can be added to any order.",
        "price": Decimal("40.00"),
        "products": (),
    },
)

DEMO_USERS = (
    {
        "username": "demo.sysadmin",
        "email": "demo.sysadmin@example.com",
        "first_name": "Jordan",
        "last_name": "Naidoo",
        "access_level": ACCESS_LEVEL_SYSTEM_ADMIN,
    },
    {
        "username": "demo.admin.sales",
        "email": "demo.admin.sales@example.com",
        "first_name": "Ayanda",
        "last_name": "Maseko",
        "access_level": ACCESS_LEVEL_ADMIN,
    },
    {
        "username": "demo.admin.ops",
        "email": "demo.admin.ops@example.com",
        "first_name": "Priya",
        "last_name": "Pillay",
        "access_level": ACCESS_LEVEL_ADMIN,
    },
    {
        "username": "demo.agent.lindi",
        "email": "demo.agent.lindi@example.com",
        "first_name": "Lindi",
        "last_name": "Mokoena",
        "access_level": ACCESS_LEVEL_USER,
    },
    {
        "username": "demo.agent.sam",
        "email": "demo.agent.sam@example.com",
        "first_name": "Sam",
        "last_name": "Daniels",
        "access_level": ACCESS_LEVEL_USER,
    },
)

DEMO_CUSTOMERS = (
    {
        "first_name": "Avery",
        "last_name": "Mokoena",
        "email": "avery.mokoena@demo-customers.example.com",
        "primary_phone": "+27 11 555 0101",
        "secondary_phone": "",
        "company": "",
        "notes": "Prefers email updates.",
        "owner": "demo.admin.sales",
    },
    {
        "first_name": "Naledi",
        "last_name": "Dlamini",
        "email": "naledi.dlamini@demo-customers.example.com",
        "primary_phone": "+27 11 555 0102",
        "secondary_phone": "",
        "company": "Demo Trading Co.",
        "notes": "Contact by phone before collection.",
        "owner": "demo.admin.ops",
    },
    {
        "first_name": "Chris",
        "last_name": "Peters",
        "email": "chris.peters@demo-customers.example.com",
        "primary_phone": "+27 11 555 0103",
        "secondary_phone": "",
        "company": "",
        "notes": "Requested an estimate before work starts.",
        "owner": "demo.agent.lindi",
    },
    {
        "first_name": "Tumi",
        "last_name": "Khumalo",
        "email": "tumi.khumalo@demo-customers.example.com",
        "primary_phone": "+27 11 555 0104",
        "secondary_phone": "",
        "company": "",
        "notes": "Prefers afternoon collection.",
        "owner": "demo.agent.sam",
    },
    {
        "first_name": "Rhea",
        "last_name": "Govender",
        "email": "rhea.govender@demo-customers.example.com",
        "primary_phone": "+27 11 555 0105",
        "secondary_phone": "",
        "company": "Demo Supplies",
        "notes": "Send the invoice by email.",
        "owner": "demo.admin.sales",
    },
    {
        "first_name": "Imran",
        "last_name": "Jacobs",
        "email": "imran.jacobs@demo-customers.example.com",
        "primary_phone": "+27 11 555 0106",
        "secondary_phone": "",
        "company": "Demo Workshop",
        "notes": "Check availability before scheduling.",
        "owner": "demo.admin.ops",
    },
    {
        "first_name": "Lebo",
        "last_name": "Sithole",
        "email": "lebo.sithole@demo-customers.example.com",
        "primary_phone": "+27 11 555 0107",
        "secondary_phone": "",
        "company": "Demo Studio",
        "notes": "Returning customer.",
        "owner": "demo.agent.lindi",
    },
    {
        "first_name": "Megan",
        "last_name": "Botha",
        "email": "megan.botha@demo-customers.example.com",
        "primary_phone": "+27 11 555 0108",
        "secondary_phone": "",
        "company": "",
        "notes": "Confirm the deadline before starting.",
        "owner": "demo.agent.sam",
    },
    {
        "first_name": "Sipho",
        "last_name": "Nkosi",
        "email": "sipho.nkosi@demo-customers.example.com",
        "primary_phone": "+27 11 555 0109",
        "secondary_phone": "",
        "company": "Demo Services",
        "notes": "Requires an itemised invoice.",
        "owner": "demo.admin.sales",
    },
    {
        "first_name": "Paula",
        "last_name": "Fernandes",
        "email": "paula.fernandes@demo-customers.example.com",
        "primary_phone": "+27 11 555 0110",
        "secondary_phone": "",
        "company": "Demo Partners",
        "notes": "Contact when the order is ready.",
        "owner": "demo.sysadmin",
    },
)

DEMO_USERNAMES = tuple(user["username"] for user in DEMO_USERS)


def _refresh_demo_catalog_entry(model, data, defaults):
    # Reuse original demo records so orders retain their product/service links.
    if not model.objects.filter(name=data["name"]).exists():
        previous = model.objects.filter(name=data["previous_name"]).first()
        if previous:
            previous.name = data["name"]
            previous.save(update_fields=["name"])
    record, _ = model.objects.update_or_create(name=data["name"], defaults=defaults)
    return record


@transaction.atomic
def load_demo_data():
    category_map = {}
    for category_data in DEMO_CATEGORIES:
        category = _refresh_demo_catalog_entry(
            ProductCategory,
            category_data,
            defaults={
                "description": category_data["description"],
            },
        )
        category_map[category.name] = category

    product_map = {}
    for product_data in DEMO_PRODUCTS:
        product = _refresh_demo_catalog_entry(
            Product,
            product_data,
            defaults={
                "category": category_map[product_data["category"]],
                "description": product_data["description"],
            },
        )
        product_map[product.name] = product

    for service_data in DEMO_SERVICES:
        service = _refresh_demo_catalog_entry(
            Service,
            service_data,
            defaults={
                "description": service_data["description"],
                "price": service_data["price"],
            },
        )
        service.products.set(
            [product_map[product_name] for product_name in service_data["products"]]
        )

    user_map = {}
    user_model = get_user_model()
    for user_data in DEMO_USERS:
        user, _ = user_model.objects.update_or_create(
            username=user_data["username"],
            defaults={
                "email": user_data["email"],
                "first_name": user_data["first_name"],
                "last_name": user_data["last_name"],
                "is_active": True,
            },
        )
        user.set_password(DEMO_PASSWORD)
        user.save(update_fields=["password"])
        assign_access_level(user, user_data["access_level"])
        user_map[user.username] = user

    for customer_data in DEMO_CUSTOMERS:
        Customer.objects.update_or_create(
            email=customer_data["email"],
            defaults={
                "first_name": customer_data["first_name"],
                "last_name": customer_data["last_name"],
                "primary_phone": customer_data["primary_phone"],
                "secondary_phone": customer_data["secondary_phone"],
                "company": customer_data["company"],
                "notes": customer_data["notes"],
                "owner": user_map[customer_data["owner"]],
            },
        )

    return {
        "categories": len(DEMO_CATEGORIES),
        "products": len(DEMO_PRODUCTS),
        "services": len(DEMO_SERVICES),
        "customers": len(DEMO_CUSTOMERS),
        "users": len(DEMO_USERS),
    }
