from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_http_methods

from crm.forms.order_adjustments import (
    OrderComplaintForm,
    OrderRefundAmountForm,
    OrderRefundForm,
)
from crm.models import (
    OrderComplaint,
    OrderRefund,
    OrderRefundAmountChange,
    ServiceOrder,
)

from .common import record_url
from .orders import order_form_response


@login_required
@permission_required(
    ("crm.view_serviceorder", "crm.change_serviceorder"), raise_exception=True
)
@require_http_methods(["GET", "POST"])
def edit_order_complaint(request, order_id):
    order = get_object_or_404(ServiceOrder, pk=order_id)
    order_url = record_url(request, "edit_order", order_id=order.pk)
    if request.method == "GET":
        return redirect(f"{order_url}#order-complaint-heading")
    complaint = getattr(order, "complaint", None) or OrderComplaint(order=order)
    form = OrderComplaintForm(request.POST, order=order, instance=complaint)
    if form.is_valid():
        with transaction.atomic():
            if lock_order(order, form):
                if complaint.pk or form.cleaned_data["logged"]:
                    form.save()
                    order.revision += 1
                    order.save(update_fields=("revision", "updated_at"))
                    messages.success(request, "Complaint details saved.")
                return redirect(order_url)
    for error in form.errors.values():
        messages.error(request, " ".join(error))
    return redirect(f"{order_url}#order-complaint-heading")


@login_required
@permission_required(
    ("crm.view_serviceorder", "crm.change_serviceorder"), raise_exception=True
)
@require_http_methods(["GET", "POST"])
def record_order_refund(request, order_id):
    order = get_object_or_404(ServiceOrder, pk=order_id)
    order_url = record_url(request, "edit_order", order_id=order.pk)
    if not order.can_record_refund:
        messages.error(
            request,
            "Record refunds against an order with a payment and a refundable balance.",
        )
        return redirect(order_url)
    if request.method == "GET":
        return redirect(f"{order_url}#order-refunds-heading")
    refund = OrderRefund(order=order, recorded_by=request.user)
    form = OrderRefundForm(request.POST, order=order, instance=refund)
    if form.is_valid():
        with transaction.atomic():
            if lock_order(order, form):
                received = (
                    order.refund_amount_received or form.cleaned_data["amount_received"]
                )
                refunded = order.total_refunded + form.cleaned_data["amount"]
                if refunded > received:
                    form.add_error(
                        "amount",
                        "The refund exceeds the remaining amount received from the customer.",
                    )
                else:
                    form.save()
                    save_refund_payment_status(order, received, refunded)
                    messages.success(request, "Refund recorded.")
                    return redirect(order_url)
    return order_form_response(request, order, refund_form=form)


@login_required
@permission_required(
    ("crm.view_serviceorder", "crm.change_serviceorder"), raise_exception=True
)
@require_http_methods(["GET", "POST"])
def edit_order_refund_amount(request, order_id, refund_id):
    refund = get_object_or_404(
        OrderRefund.objects.select_related("order__complaint"),
        pk=refund_id,
        order_id=order_id,
    )
    order = refund.order
    order_url = record_url(request, "edit_order", order_id=order.pk)
    received = order.refund_amount_received
    if received is None:
        messages.error(
            request,
            "The original payment must be recorded before editing a refund amount.",
        )
        return redirect(order_url)

    form = OrderRefundAmountForm(
        request.POST if request.method == "POST" else None, order=order, refund=refund
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            if lock_order(order, form):
                amount = form.cleaned_data["amount"]
                if amount == refund.amount:
                    return redirect(f"{order_url}#order-refunds-heading")
                revised_total = order.total_refunded - refund.amount + amount
                if revised_total > received:
                    form.add_error(
                        "amount",
                        "The corrected total would exceed the amount received from the customer.",
                    )
                else:
                    OrderRefundAmountChange.objects.create(
                        refund=refund,
                        previous_amount=refund.amount,
                        new_amount=amount,
                        changed_by=request.user,
                    )
                    refund.amount = amount
                    refund.save(update_fields=("amount",))
                    save_refund_payment_status(order, received, revised_total)
                    messages.success(request, "Refund amount corrected.")
                    return redirect(f"{order_url}#order-refunds-heading")
    return order_form_response(request, order, refund_form=form, editing_refund=refund)


def save_refund_payment_status(order, received, refunded):
    order.refund_amount_received = received
    order.payment_status = (
        ServiceOrder.PaymentStatus.FULLY_REFUNDED
        if refunded == received
        else ServiceOrder.PaymentStatus.PARTIALLY_REFUNDED
    )
    order.revision += 1
    order.save(
        update_fields=(
            "refund_amount_received",
            "payment_status",
            "revision",
            "updated_at",
        )
    )


def lock_order(order, form):
    revision = form.cleaned_data["revision"]
    if revision == order.revision and ServiceOrder.objects.filter(
        pk=order.pk, revision=revision
    ).update(revision=F("revision")):
        return True
    form.add_error(
        None,
        "This order changed. Reopen the order and review the latest details before saving again.",
    )
    return False
