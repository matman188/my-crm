from django.utils import timezone

from crm.models import SystemSettings


def business_timezone(get_response):
    def middleware(request):
        request.crm_settings = SystemSettings.get_solo()
        with timezone.override(request.crm_settings.business_zone):
            return get_response(request)

    return middleware
