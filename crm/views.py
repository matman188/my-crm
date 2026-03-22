from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from crm.forms import (
    SystemUserCreationForm,
    SystemUserPasswordChangeForm,
    SystemUserUpdateForm,
)


@login_required
def home(request):
    return render(request, "crm/home.html")


@login_required
def customers(request):
    return render(request, "crm/customers.html")


@login_required
def users(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden("Only superusers can create system users.")

    existing_users = get_user_model().objects.order_by("username")
    return render(request, "crm/users.html", {"existing_users": existing_users})


@login_required
def create_user(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden("Only superusers can create system users.")

    if request.method == "POST":
        form = SystemUserCreationForm(request.POST)
        if form.is_valid():
            created_user = form.save()
            messages.success(request, f"User '{created_user.username}' was created.")
            return redirect("users")
    else:
        form = SystemUserCreationForm()

    return render(
        request,
        "crm/user_form.html",
        {
            "form": form,
            "page_title": "Create User",
            "submit_label": "Create user",
        },
    )


@login_required
def edit_user(request, user_id):
    if not request.user.is_superuser:
        return HttpResponseForbidden("Only superusers can manage system users.")

    user_to_edit = get_object_or_404(get_user_model(), pk=user_id)

    if request.method == "POST":
        form = SystemUserUpdateForm(request.POST, instance=user_to_edit)
        if form.is_valid():
            form.save()
            messages.success(request, f"User '{user_to_edit.username}' was updated.")
            return redirect("users")
    else:
        form = SystemUserUpdateForm(instance=user_to_edit)

    return render(
        request,
        "crm/user_form.html",
        {
            "form": form,
            "page_title": f"Edit User: {user_to_edit.username}",
            "submit_label": "Save changes",
            "form_description": "Update the user's profile details below.",
        },
    )


@login_required
def change_user_password(request, user_id):
    if not request.user.is_superuser:
        return HttpResponseForbidden("Only superusers can manage system users.")

    user_to_update = get_object_or_404(get_user_model(), pk=user_id)

    if request.method == "POST":
        form = SystemUserPasswordChangeForm(user_to_update, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f"Password updated for '{user_to_update.username}'.")
            return redirect("users")
    else:
        form = SystemUserPasswordChangeForm(user_to_update)

    return render(
        request,
        "crm/user_form.html",
        {
            "form": form,
            "page_title": f"Change Password: {user_to_update.username}",
            "submit_label": "Update password",
            "form_description": "Set a new password for this user.",
        },
    )


@login_required
def delete_user(request, user_id):
    if not request.user.is_superuser:
        return HttpResponseForbidden("Only superusers can manage system users.")

    if request.method != "POST":
        return HttpResponseForbidden("Users can only be deleted with a POST request.")

    user_to_delete = get_object_or_404(get_user_model(), pk=user_id)
    username = user_to_delete.username

    if user_to_delete.is_superuser:
        messages.error(request, "Superusers cannot be deleted from this screen.")
        return redirect("users")

    user_to_delete.delete()
    messages.success(request, f"User '{username}' was deleted.")
    return redirect("users")
