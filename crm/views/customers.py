from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.db.models.deletion import ProtectedError
from django.db.models.functions import Lower
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from crm.forms import CustomerForm
from crm.models import Customer, ServiceOrder


@login_required
def customers(request):
    search_query = request.GET.get("q", "").strip()
    existing_customers = Customer.objects.annotate(order_count=Count("orders"))
    customer_status = request.GET.get("status", "active")
    if customer_status not in ("active", "archived", "all"):
        customer_status = "active"
    if customer_status != "all":
        existing_customers = existing_customers.filter(
            is_archived=customer_status == "archived"
        )

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
            "customer_status": customer_status,
        },
    )


@login_required
def create_customer(request):
    if request.method == "POST":
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.owner = request.user
            try:
                with transaction.atomic():
                    customer.save()
            except IntegrityError:
                if not form.add_duplicate_email_error():
                    raise
            else:
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
    customer_delete_name = str(customer)
    customer_order_counts = customer.orders.aggregate(
        total_orders=Count("pk"),
        open_orders=Count(
            "pk",
            filter=Q(
                status__in=(ServiceOrder.Status.DRAFT, ServiceOrder.Status.IN_PROGRESS)
            ),
        ),
    )

    if request.method == "POST":
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            try:
                with transaction.atomic():
                    form.save()
            except IntegrityError:
                if not form.add_duplicate_email_error():
                    raise
            else:
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
            "customer_delete_name": customer_delete_name,
            "customer_order_counts": customer_order_counts,
            "submit_label": "Save changes",
            "form_description": "Update the customer details below.",
        },
    )


@login_required
def delete_customer(request, customer_id):
    if request.method != "POST":
        return HttpResponseForbidden(
            "Customers can only be deleted with a POST request."
        )

    customer = get_object_or_404(Customer, pk=customer_id)
    customer_name = str(customer)
    try:
        customer.delete()
    except ProtectedError:
        messages.error(
            request, "This customer is used on a service order and cannot be deleted."
        )
        return redirect("customers")
    messages.success(request, f"Customer '{customer_name}' was deleted.")
    return redirect("customers")


@login_required
@permission_required("crm.change_customer", raise_exception=True)
@require_POST
def archive_customer(request, customer_id):
    customer = get_object_or_404(Customer, pk=customer_id)
    Customer.objects.filter(pk=customer.pk).update(
        is_archived=True, updated_at=timezone.now()
    )
    messages.success(request, f"Customer '{customer}' was archived.")
    return redirect("edit_customer", customer_id=customer.pk)


@login_required
@permission_required("crm.change_customer", raise_exception=True)
@require_POST
def restore_customer(request, customer_id):
    customer = get_object_or_404(Customer, pk=customer_id)
    Customer.objects.filter(pk=customer.pk).update(
        is_archived=False, updated_at=timezone.now()
    )
    messages.success(request, f"Customer '{customer}' was restored.")
    return redirect("edit_customer", customer_id=customer.pk)
