from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from crm.forms import ProfileUpdateForm


@login_required
def edit_profile(request):
    if request.method == "POST":
        form = ProfileUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile was updated.")
            return redirect("home")
    else:
        form = ProfileUpdateForm(instance=request.user)

    return render(
        request,
        "crm/user_form.html",
        {
            "form": form,
            "page_title": "Edit Profile",
            "submit_label": "Save profile",
            "form_description": "Update your own account details.",
        },
    )
