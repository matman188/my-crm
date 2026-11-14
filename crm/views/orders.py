from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Prefetch, Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from crm.forms.orders import DraftConflict, DraftOrderEditor
from crm.models import OrderItem, OrderServiceCharge, Service, ServiceOrder


@login_required
@permission_required("crm.view_serviceorder", raise_exception=True)
def orders(request):
    query = request.GET.get("q", "").strip()
    queryset = ServiceOrder.objects.select_related(
        "customer", "assigned_to"
    ).prefetch_related(
        Prefetch("items", queryset=OrderItem.objects.select_related("product")),
        Prefetch("charges", queryset=OrderServiceCharge.objects.select_related("item")),
    )
    if query:
        conditions = (
            Q(customer__first_name__icontains=query)
            | Q(customer__last_name__icontains=query)
            | Q(customer__company__icontains=query)
            | Q(customer__email__icontains=query)
            | Q(assigned_to__username__icontains=query)
            | Q(assigned_to__first_name__icontains=query)
            | Q(assigned_to__last_name__icontains=query)
            | Q(notes__icontains=query)
        )
        reference_number = query.upper().removeprefix("SO-")
        if (
            reference_number.isascii()
            and reference_number.isdigit()
            and len(reference_number) <= 18
        ):
            conditions |= Q(pk=int(reference_number))
        queryset = queryset.filter(conditions)
    return render(
        request,
        "crm/orders.html",
        {
            "page_obj": Paginator(queryset, 25).get_page(request.GET.get("page")),
            "search_query": query,
        },
    )


def _edit_draft(request, instance=None):
    if instance and instance.status != ServiceOrder.Status.DRAFT:
        return HttpResponseForbidden("Only draft orders can be edited here.")
    editor = DraftOrderEditor(
        user=request.user,
        instance=instance,
        data=request.POST if request.method == "POST" else None,
    )
    if request.method == "POST" and editor.is_valid():
        try:
            order = editor.save()
        except DraftConflict as error:
            editor.form.add_error(None, str(error))
        else:
            messages.success(request, f"Draft {order.reference} was saved.")
            return redirect("edit_order", order_id=order.pk)
    catalog = [
        {
            "id": service.pk,
            "name": service.name,
            "price": str(service.price),
            "products": [product.pk for product in service.products.all()],
        }
        for service in Service.objects.prefetch_related("products").order_by(
            "name", "pk"
        )
    ]
    return render(
        request,
        "crm/order_form.html",
        {
            "editor": editor,
            "order": editor.instance,
            "service_catalog": catalog,
            "customer_catalog": [
                {
                    "id": customer.pk,
                    "name": str(customer),
                    "label": editor.form.fields["customer"].label_from_instance(
                        customer
                    ),
                }
                for customer in editor.form.fields["customer"].queryset
            ],
            "page_title": (
                f"Edit {instance.reference}" if instance else "Create service order"
            ),
        },
    )


@login_required
@permission_required("crm.add_serviceorder", raise_exception=True)
def create_order(request):
    return _edit_draft(request)


@login_required
@permission_required("crm.change_serviceorder", raise_exception=True)
def edit_order(request, order_id):
    return _edit_draft(request, get_object_or_404(ServiceOrder, pk=order_id))
