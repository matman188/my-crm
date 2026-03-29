def has_permission(user, permission):
    return user.is_superuser or user.has_perm(permission)
