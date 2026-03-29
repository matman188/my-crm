from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render

from crm.demo_data import DEMO_PASSWORD, load_demo_data
from crm.forms import SystemSettingsForm
from crm.models import SystemSettings

from .common import has_permission


@login_required
def system_settings(request):
    if not has_permission(request.user, "crm.change_systemsettings"):
        return HttpResponseForbidden("Only admin users can manage system settings.")

    settings = SystemSettings.get_solo()

    if request.method == "POST":
        if request.POST.get("action") == "load_demo_data":
            counts = load_demo_data()
            messages.success(
                request,
                "Demo data refreshed: "
                f"{counts['categories']} categories, "
                f"{counts['products']} products, "
                f"{counts['services']} services, "
                f"{counts['customers']} customers, and "
                f"{counts['users']} users. "
                f"Demo user password: {DEMO_PASSWORD}",
            )
            return redirect("system_settings")
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
