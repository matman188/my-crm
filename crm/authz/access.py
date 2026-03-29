from .constants import (
    ACCESS_LEVEL_ADMIN,
    ACCESS_LEVEL_SYSTEM_ADMIN,
    ACCESS_LEVEL_USER,
    CRM_ADMIN_GROUP,
    SYSTEM_ADMIN_GROUP,
)


def can_manage_configuration(user):
    return get_access_level(user) in {ACCESS_LEVEL_ADMIN, ACCESS_LEVEL_SYSTEM_ADMIN}


def get_access_level(user):
    if not getattr(user, "is_authenticated", False):
        return ACCESS_LEVEL_USER

    if user.is_superuser or user.is_staff or user.groups.filter(name=SYSTEM_ADMIN_GROUP).exists():
        return ACCESS_LEVEL_SYSTEM_ADMIN

    if user.groups.filter(name=CRM_ADMIN_GROUP).exists():
        return ACCESS_LEVEL_ADMIN

    return ACCESS_LEVEL_USER


def get_access_level_label(user):
    access_level = get_access_level(user)
    if access_level == ACCESS_LEVEL_SYSTEM_ADMIN:
        return "System Admin"
    if access_level == ACCESS_LEVEL_ADMIN:
        return "Admin"
    return "User"


def can_manage_user_record(current_user, target_user):
    if not getattr(current_user, "is_authenticated", False):
        return False

    if not current_user.has_perm("auth.change_user") and not current_user.is_superuser:
        return False

    if current_user.is_superuser:
        return True

    if target_user.is_superuser:
        return False

    if (
        get_access_level(target_user) == ACCESS_LEVEL_SYSTEM_ADMIN
        and get_access_level(current_user) != ACCESS_LEVEL_SYSTEM_ADMIN
    ):
        return False

    return True
