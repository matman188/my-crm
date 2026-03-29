ACCESS_LEVEL_USER = "user"
ACCESS_LEVEL_ADMIN = "admin"
ACCESS_LEVEL_SYSTEM_ADMIN = "system_admin"

CRM_USER_GROUP = "CRM User"
CRM_ADMIN_GROUP = "CRM Admin"
SYSTEM_ADMIN_GROUP = "System Admin"

MANAGED_ROLE_GROUP_NAMES = (
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
