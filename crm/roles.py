from django.apps import apps
from django.contrib.auth.management import create_permissions
from django.contrib.auth.models import Group, Permission
from django.db import DEFAULT_DB_ALIAS


ACCESS_LEVEL_USER = "user"
ACCESS_LEVEL_ADMIN = "admin"
ACCESS_LEVEL_SYSTEM_ADMIN = "system_admin"

CRM_USER_GROUP = "CRM User"
CRM_ADMIN_GROUP = "CRM Admin"
SYSTEM_ADMIN_GROUP = "System Admin"

ROLE_GROUP_NAMES = (
    CRM_USER_GROUP,
    CRM_ADMIN_GROUP,
    SYSTEM_ADMIN_GROUP,
)

ACCESS_LEVEL_GROUPS = {
    ACCESS_LEVEL_USER: CRM_USER_GROUP,
    ACCESS_LEVEL_ADMIN: CRM_ADMIN_GROUP,
    ACCESS_LEVEL_SYSTEM_ADMIN: SYSTEM_ADMIN_GROUP,
}

GROUP_PERMISSION_MAP = {
    CRM_USER_GROUP: {
        "crm": {
            "view_customer",
            "add_customer",
            "change_customer",
            "delete_customer",
        },
    },
    CRM_ADMIN_GROUP: {
        "crm": {
            "view_customer",
            "add_customer",
            "change_customer",
            "delete_customer",
            "view_productcategory",
            "add_productcategory",
            "change_productcategory",
            "delete_productcategory",
            "view_product",
            "add_product",
            "change_product",
            "delete_product",
            "view_service",
            "add_service",
            "change_service",
            "delete_service",
            "view_systemsettings",
            "change_systemsettings",
        },
        "auth": {
            "view_user",
            "add_user",
            "change_user",
            "delete_user",
        },
    },
    SYSTEM_ADMIN_GROUP: {
        "crm": {
            "view_customer",
            "add_customer",
            "change_customer",
            "delete_customer",
            "view_productcategory",
            "add_productcategory",
            "change_productcategory",
            "delete_productcategory",
            "view_product",
            "add_product",
            "change_product",
            "delete_product",
            "view_service",
            "add_service",
            "change_service",
            "delete_service",
            "view_systemsettings",
            "change_systemsettings",
        },
        "auth": {
            "view_user",
            "add_user",
            "change_user",
            "delete_user",
        },
    },
}


def ensure_crm_groups(using=DEFAULT_DB_ALIAS):
    for app_label in ("auth", "crm"):
        create_permissions(apps.get_app_config(app_label), verbosity=0, using=using)

    groups = {}
    for group_name, permission_map in GROUP_PERMISSION_MAP.items():
        group, _ = Group.objects.using(using).get_or_create(name=group_name)
        permission_ids = list(
            Permission.objects.using(using)
            .filter(
                content_type__app_label__in=permission_map.keys(),
                codename__in={
                    codename
                    for codenames in permission_map.values()
                    for codename in codenames
                },
            )
            .values_list("id", flat=True)
        )
        group.permissions.set(permission_ids)
        groups[group_name] = group
    return groups


def assign_access_level(user, access_level):
    if access_level not in ACCESS_LEVEL_GROUPS:
        raise ValueError(f"Unsupported access level: {access_level}")
    if not user.pk:
        raise ValueError("User must be saved before assigning an access level.")

    groups = ensure_crm_groups()
    desired_group = groups[ACCESS_LEVEL_GROUPS[access_level]]

    managed_groups = user.groups.filter(name__in=ROLE_GROUP_NAMES)
    if managed_groups.exists():
        user.groups.remove(*managed_groups)
    user.groups.add(desired_group)

    desired_is_staff = user.is_superuser or access_level == ACCESS_LEVEL_SYSTEM_ADMIN
    if user.is_staff != desired_is_staff:
        user.is_staff = desired_is_staff
        user.save(update_fields=["is_staff"])
