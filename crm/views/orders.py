from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Prefetch, Q
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from crm.forms.orders import (
    DeleteDraftForm,
    OrderConflict,
    OrderEditor,
    OrderFilterForm,
)
from crm.models import OrderItem, OrderServiceCharge, Service, ServiceOrder


@login_required
@permission_required("crm.view_serviceorder", raise_exception=True)
def orders(request):
    filters = OrderFilterForm(request.GET)
    valid_filters = filters.is_valid()
    query = filters.cleaned_data.get("q", "")
    queryset = ServiceOrder.objects.select_related(
        "customer", "assigned_to"
    ).prefetch_related(
        Prefetch("items", queryset=OrderItem.objects.select_related("product")),
        Prefetch("charges", queryset=OrderServiceCharge.objects.select_related("item")),
    )
    if not valid_filters:
        queryset = queryset.none()
    else:
        if filters.cleaned_data["status"]:
            queryset = queryset.filter(status=filters.cleaned_data["status"])
        if filters.cleaned_data["payment_status"]:
            queryset = queryset.filter(
                payment_status=filters.cleaned_data["payment_status"]
            )
        if filters.cleaned_data["collected"]:
            queryset = queryset.filter(
                collected=filters.cleaned_data["collected"] == "yes"
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
    pagination_query = request.GET.copy()
    pagination_query.pop("page", None)
    return render(
        request,
        "crm/orders.html",
        {
            "page_obj": Paginator(queryset, 25).get_page(request.GET.get("page")),
            "search_query": query,
            "filter_form": filters,
            "filter_query": pagination_query.urlencode(),
            "has_filters": any(pagination_query.values()),
        },
    )


def _order_form(request, instance=None):
    editor = OrderEditor(
        user=request.user,
        instance=instance,
        data=request.POST if request.method == "POST" else None,
    )
    if request.method == "POST" and editor.is_valid():
        try:
            order = editor.save()
        except OrderConflict as error:
            editor.form.add_error(None, str(error))
        else:
            messages.success(request, f"Order {order.reference} was saved.")
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
                f"Order {instance.reference}" if instance else "Create service order"
            ),
        },
    )


@login_required
@permission_required("crm.add_serviceorder", raise_exception=True)
def create_order(request):
    return _order_form(request)


@login_required
@permission_required("crm.change_serviceorder", raise_exception=True)
def edit_order(request, order_id):
    return _order_form(request, get_object_or_404(ServiceOrder, pk=order_id))


@login_required
@permission_required("crm.delete_serviceorder", raise_exception=True)
@require_POST
def delete_order(request, order_id):
    form = DeleteDraftForm(request.POST)
    if not form.is_valid():
        return HttpResponseBadRequest("Reload the draft before deleting it.")
    with transaction.atomic():
        # Claim this exact draft revision before deleting its dependent rows.
        # The write also protects against a concurrent submission on SQLite.
        claimed = ServiceOrder.objects.filter(
            pk=order_id,
            status=ServiceOrder.Status.DRAFT,
            revision=form.cleaned_data["revision"],
        ).update(revision=F("revision") + 1)
        order = get_object_or_404(ServiceOrder, pk=order_id)
        if order.status != ServiceOrder.Status.DRAFT:
            return HttpResponseForbidden("Only draft orders can be deleted.")
        if not claimed:
            messages.error(request, "The draft changed. Review it before deleting.")
            return redirect("edit_order", order_id=order.pk)
        reference = order.reference
        order.delete()
    messages.success(request, f"Draft {reference} was deleted.")
    return redirect("orders")
