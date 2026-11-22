from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Exists, F, OuterRef, Prefetch, Q, Value
from django.db.models.functions import Concat
from django.forms import IntegerField
from django.http import HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from crm.forms.customers import CustomerForm
from crm.forms.orders import (
    CustomerChoiceField,
    DeleteDraftForm,
    OrderConflict,
    OrderEditor,
    OrderFilterForm,
)
from crm.models import (
    Customer,
    Invoice,
    OrderItem,
    OrderServiceCharge,
    Service,
    ServiceOrder,
)
from crm.order_invoices import available_invoice_actions
from crm.order_queries import (
    WORK_VIEWS,
    deadline_order,
    with_deadlines,
    work_condition,
    work_counts,
)
from .common import record_url, return_to_list


def _customer_entry(customer, order_id=None):
    url_name = "save_order_customer" if order_id else "save_new_order_customer"
    kwargs = {"customer_id": customer.pk}
    if order_id:
        kwargs["order_id"] = order_id
    return {
        "id": customer.pk,
        "name": str(customer),
        "label": CustomerChoiceField.label_from_instance(customer),
        "notes": customer.notes,
        "email": customer.email,
        "is_archived": customer.is_archived,
        "details": {name: getattr(customer, name) for name in CustomerForm.Meta.fields},
        "save_url": reverse(url_name, kwargs=kwargs),
    }


@login_required
@permission_required("crm.view_serviceorder", raise_exception=True)
def orders(request):
    filter_data = request.GET.copy()
    if filter_data.get("view") == "unpaid" and not filter_data.get("payment_status"):
        filter_data["payment_status"] = "unpaid"
    filters = OrderFilterForm(filter_data)
    valid_filters = filters.is_valid()
    query = filters.cleaned_data.get("q", "")
    queryset = with_deadlines(
        ServiceOrder.objects.select_related("customer", "assigned_to").prefetch_related(
            Prefetch("items", queryset=OrderItem.objects.select_related("product")),
            Prefetch(
                "charges", queryset=OrderServiceCharge.objects.select_related("item")
            ),
        )
    )
    if not valid_filters:
        queryset = queryset.none()
    else:
        if filters.cleaned_data["customer"]:
            queryset = queryset.filter(customer=filters.cleaned_data["customer"])
    if query:
        queryset = queryset.alias(
            customer_full_name=Concat(
                "customer__first_name", Value(" "), "customer__last_name"
            )
        )
        conditions = (
            Q(customer__first_name__icontains=query)
            | Q(customer__last_name__icontains=query)
            | Q(customer_full_name__icontains=query)
            | Q(customer__company__icontains=query)
            | Q(customer__email__icontains=query)
            | Q(customer__primary_phone__icontains=query)
            | Q(customer__secondary_phone__icontains=query)
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
    counts = work_counts(queryset, request.user)
    selected_view = filters.cleaned_data.get("view") or "all"
    queryset = queryset.filter(work_condition(selected_view, request.user))
    if valid_filters:
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
    sort = filters.cleaned_data.get("sort") or "newest"
    queryset = (
        deadline_order(queryset)
        if sort == "deadline"
        else (
            queryset.order_by("created_at", "pk")
            if sort == "oldest"
            else queryset.order_by("-created_at", "-pk")
        )
    )
    quick_views = []
    for key, label in WORK_VIEWS:
        if key == "unpaid":
            continue
        params = request.GET.copy()
        for field in ("page", "status", "collected", "payment_status"):
            params.pop(field, None)
        params["view"] = key
        if key in ("due_today", "overdue", "unassigned"):
            params["sort"] = "deadline"
        quick_views.append(
            {
                "label": label,
                "count": counts[key],
                "url": "?" + params.urlencode(),
                "active": selected_view == key,
            }
        )
    pagination_query = request.GET.copy()
    pagination_query.pop("page", None)
    return render(
        request,
        "crm/orders.html",
        {
            "page_obj": Paginator(queryset, 25).get_page(request.GET.get("page")),
            "search_query": query,
            "filter_form": filters,
            "customer_filter": filters.cleaned_data.get("customer"),
            "filter_query": pagination_query.urlencode(),
            "has_filters": any(pagination_query.values()),
            "quick_views": quick_views,
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
        except IntegrityError:
            if (
                not (editor.new_customer or editor.editing_customer)
                or not editor.customer_form.add_duplicate_email_error()
            ):
                raise
        else:
            action = {
                "submit": "submitted",
                "complete": "marked Complete",
                "cancel": "cancelled",
                "reopen": "reopened",
                "return_to_draft": "returned to Draft",
                "restore_to_draft": "restored to Draft",
            }.get(editor.form.action, "saved")
            messages.success(request, f"Order {order.reference} was {action}.")
            return redirect(record_url(request, "edit_order", order_id=order.pk))
    catalog = [
        {
            "id": service.pk,
            "name": service.name,
            "price": str(service.price),
            "is_archived": service.is_archived,
            "products": [product.pk for product in service.products.all()],
        }
        for service in Service.objects.prefetch_related("products").order_by(
            "name", "pk"
        )
    ]
    customer_catalog = [
        _customer_entry(customer, editor.instance.pk)
        for customer in editor.form.fields["customer"].queryset
    ]
    selected_customer = next(
        (
            customer
            for customer in customer_catalog
            if str(customer["id"]) == str(editor.form["customer"].value())
        ),
        None,
    )
    customer_notes = (
        editor.customer_form["notes"].value()
        if editor.new_customer or editor.editing_customer
        else selected_customer["notes"] if selected_customer else ""
    )
    return render(
        request,
        "crm/order_form.html",
        {
            "editor": editor,
            "order": editor.instance,
            "service_catalog": catalog,
            "customer_catalog": customer_catalog,
            "customer_notes": customer_notes,
            "invoice_actions": available_invoice_actions(
                editor.instance, editor.active_invoice
            ),
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
@permission_required("crm.change_customer", raise_exception=True)
@require_POST
def save_order_customer(request, customer_id, order_id=None):
    permission = "crm.change_serviceorder" if order_id else "crm.add_serviceorder"
    if not request.user.has_perm(permission):
        raise PermissionDenied
    revision = None
    if order_id:
        try:
            revision = IntegerField(min_value=1, max_value=2147483647).clean(
                request.POST.get("revision")
            )
        except ValidationError:
            return JsonResponse(
                {"message": "Reload the order before editing its customer."}, status=400
            )
    customer = get_object_or_404(Customer, pk=customer_id)
    form = CustomerForm(request.POST, instance=customer, prefix="customer")
    if form.is_valid():
        try:
            with transaction.atomic():
                if order_id:
                    # Lock the saved draft for this transaction without changing
                    # its revision, details, or update timestamp.
                    claimed = ServiceOrder.objects.filter(
                        pk=order_id, status=ServiceOrder.Status.DRAFT, revision=revision
                    ).update(revision=F("revision"))
                    if not claimed:
                        order = get_object_or_404(ServiceOrder, pk=order_id)
                        if order.status != ServiceOrder.Status.DRAFT:
                            return JsonResponse(
                                {
                                    "message": "Customer editing is only available in Draft."
                                },
                                status=403,
                            )
                        return JsonResponse(
                            {
                                "message": "This order changed. Reload it before editing the customer."
                            },
                            status=409,
                        )
                customer = form.save()
        except IntegrityError:
            if not form.add_duplicate_email_error():
                raise
        else:
            return JsonResponse({"customer": _customer_entry(customer, order_id)})
    return JsonResponse({"errors": form.errors.get_json_data()}, status=400)


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
        claimed = (
            ServiceOrder.objects.filter(
                pk=order_id,
                status=ServiceOrder.Status.DRAFT,
                revision=form.cleaned_data["revision"],
            )
            .filter(~Exists(Invoice.objects.filter(order_id=OuterRef("pk"))))
            .update(revision=F("revision") + 1)
        )
        order = get_object_or_404(ServiceOrder, pk=order_id)
        if order.status != ServiceOrder.Status.DRAFT:
            return HttpResponseForbidden("Only draft orders can be deleted.")
        if not claimed and order.invoices.exists():
            return HttpResponseForbidden(
                "Orders with invoice history cannot be deleted."
            )
        if not claimed:
            messages.error(request, "The draft changed. Review it before deleting.")
            return redirect(record_url(request, "edit_order", order_id=order.pk))
        reference = order.reference
        order.delete()
    messages.success(request, f"Draft {reference} was deleted.")
    return return_to_list(request, "orders")
