from django.contrib.auth import get_user_model

from crm.authz import ACCESS_LEVEL_ADMIN, ACCESS_LEVEL_SYSTEM_ADMIN, assign_access_level


def create_admin_user(username="admin_agent", system_admin=False):
    user = get_user_model().objects.create_user(
        username=username,
        password="testpass123",
    )
    assign_access_level(
        user,
        ACCESS_LEVEL_SYSTEM_ADMIN if system_admin else ACCESS_LEVEL_ADMIN,
    )
    return user
