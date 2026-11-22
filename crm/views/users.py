from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.db.models.functions import Lower
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render

from crm.authz import can_manage_user_record, get_access_level_label
from crm.forms import (
    SystemUserCreationForm,
    SystemUserPasswordChangeForm,
    SystemUserUpdateForm,
)

from .common import has_permission, list_page, return_to_list
from django.views.decorators.http import require_POST


def has_work_history(user):
    return (
        user.assigned_orders.exists()
        or user.created_orders.exists()
        or user.issued_invoices.exists()
        or user.closed_invoices.exists()
    )


@login_required
def users(request):
    if not has_permission(request.user, "auth.view_user"):
        return HttpResponseForbidden("Only admin users can manage system users.")

    search_query = request.GET.get("q", "").strip()
    existing_users = get_user_model().objects.all().order_by(Lower("username"), "id")

    if search_query:
        existing_users = existing_users.filter(
            Q(username__icontains=search_query)
            | Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(email__icontains=search_query)
        )

    page_context = list_page(request, existing_users, "existing_users")
    for user in page_context["existing_users"]:
        user.has_work_history = has_work_history(user)
        user.access_level_label = get_access_level_label(user)
        user.can_be_managed_by_current_user = can_manage_user_record(request.user, user)
    return render(
        request,
        "crm/users.html",
        {
            **page_context,
            "search_query": search_query,
        },
    )


@login_required
def create_user(request):
    if not has_permission(request.user, "auth.add_user"):
        return HttpResponseForbidden("Only admin users can create system users.")

    if request.method == "POST":
        form = SystemUserCreationForm(request.POST, current_user=request.user)
        if form.is_valid():
            created_user = form.save()
            messages.success(request, f"User '{created_user.username}' was created.")
            return return_to_list(request, "users")
    else:
        form = SystemUserCreationForm(current_user=request.user)

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
    if not has_permission(request.user, "auth.change_user"):
        return HttpResponseForbidden("Only admin users can manage system users.")

    user_to_edit = get_object_or_404(get_user_model(), pk=user_id)
    if not can_manage_user_record(request.user, user_to_edit):
        return HttpResponseForbidden("You cannot manage this user.")

    if request.method == "POST":
        form = SystemUserUpdateForm(
            request.POST, instance=user_to_edit, current_user=request.user
        )
        if form.is_valid():
            form.save()
            messages.success(request, f"User '{user_to_edit.username}' was updated.")
            return return_to_list(request, "users")
    else:
        form = SystemUserUpdateForm(instance=user_to_edit, current_user=request.user)

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
    if not has_permission(request.user, "auth.change_user"):
        return HttpResponseForbidden("Only admin users can manage system users.")

    user_to_update = get_object_or_404(get_user_model(), pk=user_id)
    if not can_manage_user_record(request.user, user_to_update):
        return HttpResponseForbidden("You cannot manage this user.")

    if request.method == "POST":
        form = SystemUserPasswordChangeForm(user_to_update, request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request, f"Password updated for '{user_to_update.username}'."
            )
            return return_to_list(request, "users")
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
    if not has_permission(request.user, "auth.delete_user"):
        return HttpResponseForbidden("Only admin users can manage system users.")

    if request.method != "POST":
        return HttpResponseForbidden("Users can only be deleted with a POST request.")

    user_to_delete = get_object_or_404(get_user_model(), pk=user_id)
    if not can_manage_user_record(request.user, user_to_delete):
        return HttpResponseForbidden("You cannot manage this user.")
    username = user_to_delete.username

    if user_to_delete.is_superuser:
        messages.error(request, "Superusers cannot be deleted from this screen.")
        return return_to_list(request, "users")

    if user_to_delete.pk == request.user.pk or has_work_history(user_to_delete):
        messages.error(
            request,
            "This user has order or invoice history or is your account. Deactivate staff to retain their history.",
        )
        return return_to_list(request, "users")

    try:
        user_to_delete.delete()
    except ProtectedError:
        messages.error(
            request,
            "This user has order or invoice history. Deactivate the account to retain it.",
        )
        return return_to_list(request, "users")
    messages.success(request, f"User '{username}' was deleted.")
    return return_to_list(request, "users")


@login_required
@require_POST
def set_user_active(request, user_id, active):
    if not has_permission(request.user, "auth.change_user"):
        return HttpResponseForbidden("You cannot manage system users.")
    person = get_object_or_404(get_user_model(), pk=user_id)
    if (
        not can_manage_user_record(request.user, person)
        or person.is_superuser
        or person.pk == request.user.pk
    ):
        return HttpResponseForbidden(
            "You cannot deactivate or reactivate this account."
        )
    get_user_model().objects.filter(pk=person.pk).update(is_active=active)
    messages.success(
        request,
        f"User '{person.username}' was {'reactivated' if active else 'deactivated'}.",
    )
    return return_to_list(request, "users")
