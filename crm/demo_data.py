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
        "name": "Demo Infrastructure",
        "description": "Core networking and resilience products used in the sample account set.",
    },
    {
        "name": "Demo Productivity",
        "description": "Collaboration and workflow tools included in the demo catalog.",
    },
    {
        "name": "Demo Security",
        "description": "Security-focused software and services for the sample environment.",
    },
)

DEMO_PRODUCTS = (
    {
        "name": "Demo Edge Router X1",
        "category": "Demo Infrastructure",
        "description": "Branch-ready router with VPN and traffic shaping support.",
    },
    {
        "name": "Demo Managed Switch 24",
        "category": "Demo Infrastructure",
        "description": "24-port managed switch for growing office networks.",
    },
    {
        "name": "Demo Wi-Fi Access Point Pro",
        "category": "Demo Infrastructure",
        "description": "Ceiling-mounted wireless access point for dense office coverage.",
    },
    {
        "name": "Demo Backup Appliance Mini",
        "category": "Demo Infrastructure",
        "description": "Compact backup appliance for daily endpoint and server snapshots.",
    },
    {
        "name": "Demo Cloud Desk Suite",
        "category": "Demo Productivity",
        "description": "Shared document, chat, and planning workspace for distributed teams.",
    },
    {
        "name": "Demo Team Mail Plus",
        "category": "Demo Productivity",
        "description": "Business email and calendar package for small teams.",
    },
    {
        "name": "Demo CRM Insights Add-on",
        "category": "Demo Productivity",
        "description": "Reporting extension that surfaces deal and service trends.",
    },
    {
        "name": "Demo Endpoint Shield",
        "category": "Demo Security",
        "description": "Endpoint protection package with device health monitoring.",
    },
    {
        "name": "Demo Secure Gateway",
        "category": "Demo Security",
        "description": "Secure web gateway for traffic inspection and policy control.",
    },
    {
        "name": "Demo Identity Vault",
        "category": "Demo Security",
        "description": "Identity and password management service for internal teams.",
    },
)

DEMO_SERVICES = (
    {
        "name": "Demo Installation and Setup",
        "description": "Deployment and initial configuration for onsite hardware rollouts.",
        "price": Decimal("4500.00"),
        "products": (
            "Demo Edge Router X1",
            "Demo Managed Switch 24",
            "Demo Wi-Fi Access Point Pro",
        ),
    },
    {
        "name": "Demo Network Health Check",
        "description": "Quarterly network review with performance and risk recommendations.",
        "price": Decimal("2200.00"),
        "products": (
            "Demo Edge Router X1",
            "Demo Managed Switch 24",
            "Demo Secure Gateway",
        ),
    },
    {
        "name": "Demo Migration Workshop",
        "description": "Planning and enablement session for cloud productivity deployments.",
        "price": Decimal("3200.00"),
        "products": (
            "Demo Cloud Desk Suite",
            "Demo Team Mail Plus",
            "Demo CRM Insights Add-on",
        ),
    },
    {
        "name": "Demo Managed Backup Review",
        "description": "Backup validation and retention tuning for the demo appliance stack.",
        "price": Decimal("1800.00"),
        "products": ("Demo Backup Appliance Mini",),
    },
    {
        "name": "Demo Endpoint Rollout",
        "description": "Device onboarding and policy setup for endpoint protection.",
        "price": Decimal("2750.00"),
        "products": (
            "Demo Endpoint Shield",
            "Demo Identity Vault",
        ),
    },
    {
        "name": "Demo Security Audit",
        "description": "Configuration review across security products with remediation guidance.",
        "price": Decimal("3900.00"),
        "products": (
            "Demo Secure Gateway",
            "Demo Endpoint Shield",
            "Demo Identity Vault",
        ),
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
        "company": "Mokoena Retail Group",
        "notes": "Interested in a full branch connectivity refresh.",
        "owner": "demo.admin.sales",
    },
    {
        "first_name": "Naledi",
        "last_name": "Dlamini",
        "email": "naledi.dlamini@demo-customers.example.com",
        "primary_phone": "+27 11 555 0102",
        "secondary_phone": "",
        "company": "Dlamini Logistics",
        "notes": "Needs better warehouse Wi-Fi coverage and reporting.",
        "owner": "demo.admin.ops",
    },
    {
        "first_name": "Chris",
        "last_name": "Peters",
        "email": "chris.peters@demo-customers.example.com",
        "primary_phone": "+27 11 555 0103",
        "secondary_phone": "",
        "company": "Peters & Co Architects",
        "notes": "Evaluating shared productivity tools for hybrid staff.",
        "owner": "demo.agent.lindi",
    },
    {
        "first_name": "Tumi",
        "last_name": "Khumalo",
        "email": "tumi.khumalo@demo-customers.example.com",
        "primary_phone": "+27 11 555 0104",
        "secondary_phone": "",
        "company": "Khumalo Legal Advisory",
        "notes": "Requested an identity and endpoint security proposal.",
        "owner": "demo.agent.sam",
    },
    {
        "first_name": "Rhea",
        "last_name": "Govender",
        "email": "rhea.govender@demo-customers.example.com",
        "primary_phone": "+27 11 555 0105",
        "secondary_phone": "",
        "company": "Govender Foods",
        "notes": "Looking to centralize backups across two locations.",
        "owner": "demo.admin.sales",
    },
    {
        "first_name": "Imran",
        "last_name": "Jacobs",
        "email": "imran.jacobs@demo-customers.example.com",
        "primary_phone": "+27 11 555 0106",
        "secondary_phone": "",
        "company": "Jacobs Engineering",
        "notes": "Needs a phased network health-check engagement.",
        "owner": "demo.admin.ops",
    },
    {
        "first_name": "Lebo",
        "last_name": "Sithole",
        "email": "lebo.sithole@demo-customers.example.com",
        "primary_phone": "+27 11 555 0107",
        "secondary_phone": "",
        "company": "Sithole Clinics",
        "notes": "Interested in secure mail and collaboration tools.",
        "owner": "demo.agent.lindi",
    },
    {
        "first_name": "Megan",
        "last_name": "Botha",
        "email": "megan.botha@demo-customers.example.com",
        "primary_phone": "+27 11 555 0108",
        "secondary_phone": "",
        "company": "Botha Property Partners",
        "notes": "Requested a quick-start bundle for new branch openings.",
        "owner": "demo.agent.sam",
    },
    {
        "first_name": "Sipho",
        "last_name": "Nkosi",
        "email": "sipho.nkosi@demo-customers.example.com",
        "primary_phone": "+27 11 555 0109",
        "secondary_phone": "",
        "company": "Nkosi Field Services",
        "notes": "Wants secure remote access and better device visibility.",
        "owner": "demo.admin.sales",
    },
    {
        "first_name": "Paula",
        "last_name": "Fernandes",
        "email": "paula.fernandes@demo-customers.example.com",
        "primary_phone": "+27 11 555 0110",
        "secondary_phone": "",
        "company": "Fernandes Consulting",
        "notes": "Asked for a bundled proposal that includes onboarding services.",
        "owner": "demo.sysadmin",
    },
)

DEMO_USERNAMES = tuple(user["username"] for user in DEMO_USERS)


@transaction.atomic
def load_demo_data():
    category_map = {}
    for category_data in DEMO_CATEGORIES:
        category, _ = ProductCategory.objects.update_or_create(
            name=category_data["name"],
            defaults={
                "description": category_data["description"],
            },
        )
        category_map[category.name] = category

    product_map = {}
    for product_data in DEMO_PRODUCTS:
        product, _ = Product.objects.update_or_create(
            name=product_data["name"],
            defaults={
                "category": category_map[product_data["category"]],
                "description": product_data["description"],
            },
        )
        product_map[product.name] = product

    for service_data in DEMO_SERVICES:
        service, _ = Service.objects.update_or_create(
            name=service_data["name"],
            defaults={
                "description": service_data["description"],
                "price": service_data["price"],
            },
        )
        service.products.set([product_map[product_name] for product_name in service_data["products"]])

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
