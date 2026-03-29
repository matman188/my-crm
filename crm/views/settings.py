from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render

from crm.forms import SystemSettingsForm
from crm.models import SystemSettings

from .common import has_permission


@login_required
def system_settings(request):
    if not has_permission(request.user, "crm.change_systemsettings"):
        return HttpResponseForbidden("Only admin users can manage system settings.")

    settings = SystemSettings.get_solo()

    if request.method == "POST":
        form = SystemSettingsForm(request.POST, instance=settings)
        if form.is_valid():
            messages.success(
                request,
                "System settings were updated.",
            )
            form.save()
            return redirect("system_settings")
    else:
        form = SystemSettingsForm(instance=settings)

    return render(
        request,
        "crm/system_settings.html",
        {
            "form": form,
        },
    )
