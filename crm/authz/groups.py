from django.apps import apps
from django.contrib.auth.management import create_permissions
from django.contrib.auth.models import Group, Permission
from django.db import DEFAULT_DB_ALIAS

from .constants import (
    ACCESS_LEVEL_GROUPS,
    ACCESS_LEVEL_SYSTEM_ADMIN,
    GROUP_PERMISSION_MAP,
    MANAGED_ROLE_GROUP_NAMES,
)


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

    managed_groups = user.groups.filter(name__in=MANAGED_ROLE_GROUP_NAMES)
    if managed_groups.exists():
        user.groups.remove(*managed_groups)
    user.groups.add(desired_group)

    desired_is_staff = user.is_superuser or access_level == ACCESS_LEVEL_SYSTEM_ADMIN
    if user.is_staff != desired_is_staff:
        user.is_staff = desired_is_staff
        user.save(update_fields=["is_staff"])
