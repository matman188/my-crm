from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.db.models.functions import Lower
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from crm.forms import CustomerForm
from crm.models import Customer


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
