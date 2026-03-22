from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.db.models.functions import Lower
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from crm.forms import (
    CustomerForm,
    ProfileUpdateForm,
    SystemUserCreationForm,
    SystemUserPasswordChangeForm,
    SystemUserUpdateForm,
)
from crm.models import Customer


@login_required
def home(request):
    return render(request, "crm/home.html")


@login_required
def customers(request):
    search_query = request.GET.get("q", "").strip()
    existing_customers = Customer.objects.select_related("owner").all()

    if search_query:
        existing_customers = existing_customers.filter(
            Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(company__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(primary_phone__icontains=search_query)
            | Q(secondary_phone__icontains=search_query)
        )

    existing_customers = existing_customers.order_by(
        Lower("first_name"),
        Lower("last_name"),
        "id",
    )
    return render(
        request,
        "crm/customers.html",
        {
            "existing_customers": existing_customers,
            "search_query": search_query,
        },
    )


@login_required
def create_customer(request):
    if request.method == "POST":
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.owner = request.user
            customer.save()
            messages.success(request, f"Customer '{customer}' was created.")
            return redirect("customers")
    else:
        form = CustomerForm()

    return render(
        request,
        "crm/customer_form.html",
        {
            "form": form,
            "page_title": "Create Customer",
            "submit_label": "Create customer",
            "form_description": "Add a new customer record to the CRM.",
        },
    )


@login_required
def edit_customer(request, customer_id):
    customer = get_object_or_404(Customer, pk=customer_id)

    if request.method == "POST":
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            messages.success(request, f"Customer '{customer}' was updated.")
            return redirect("customers")
    else:
        form = CustomerForm(instance=customer)

    return render(
        request,
        "crm/customer_form.html",
        {
            "form": form,
            "page_title": f"Edit Customer: {customer}",
            "submit_label": "Save changes",
            "form_description": "Update the customer details below.",
        },
    )


@login_required
def delete_customer(request, customer_id):
    if request.method != "POST":
        return HttpResponseForbidden("Customers can only be deleted with a POST request.")

    customer = get_object_or_404(Customer, pk=customer_id)
    customer_name = str(customer)
    customer.delete()
    messages.success(request, f"Customer '{customer_name}' was deleted.")
    return redirect("customers")


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


@login_required
def users(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden("Only superusers can create system users.")

    search_query = request.GET.get("q", "").strip()
    existing_users = get_user_model().objects.all()

    if search_query:
        existing_users = existing_users.filter(
            Q(username__icontains=search_query)
            | Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(email__icontains=search_query)
        )

    existing_users = existing_users.order_by(Lower("username"), "id")
    return render(
        request,
        "crm/users.html",
        {
            "existing_users": existing_users,
            "search_query": search_query,
        },
    )


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
