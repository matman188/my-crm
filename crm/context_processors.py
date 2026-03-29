from crm.authz import can_manage_configuration, get_access_level_label
from crm.models import SystemSettings


def system_settings(request):
    settings = SystemSettings.get_solo()
    return {
        "system_settings": settings,
        "company_name": settings.company_name,
        "default_currency": settings.default_currency,
        "can_manage_configuration": can_manage_configuration(request.user),
        "user_access_level": get_access_level_label(request.user),
    }
