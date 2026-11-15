from crm.authz import can_manage_configuration, get_access_level_label
from crm.models import SystemSettings
from crm.views.common import return_url


def system_settings(request):
    settings = SystemSettings.get_solo()
    return {
        "system_settings": settings,
        "company_name": settings.company_name,
        "default_currency": settings.default_currency,
        "return_to": return_url(request),
        "can_manage_configuration": can_manage_configuration(request.user),
        "user_access_level": get_access_level_label(request.user),
    }
