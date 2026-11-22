from collections import defaultdict
from datetime import date

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from crm.invoice_pdf import invoice_business_details
from crm.models import Invoice, ServiceOrder, SystemSettings


INVOICE_STAGES = (ServiceOrder.Status.IN_PROGRESS, ServiceOrder.Status.COMPLETE)
INVOICE_ACTION_LABELS = {
    "generate": "Generate invoice",
    "revise": "Correct invoice",
    "replace": "Issue corrected invoice",
    "void": "Void invoice",
}


class InvoiceConflict(Exception):
    pass


def available_invoice_actions(order, active):
    submitted = order.status in INVOICE_STAGES
    if not active:
        return ("generate",) if submitted else ()
    if order.payment_status != ServiceOrder.PaymentStatus.UNPAID:
        return ()
    if order.invoice_revision_reason:
        return ("replace", "void") if submitted else ("void",)
    return ("revise", "void") if submitted else ()


def order_invoice_snapshot(order, settings, issued_at):
    customer = order.customer
    charges = defaultdict(list)
    for charge in order.charges.select_related("service"):
        charges[charge.item_id].append(
            {
                "description": charge.service.name,
                "quantity": charge.quantity,
                "unit_price": str(charge.unit_price),
            }
        )
    groups = []
    for index, item in enumerate(order.items.select_related("product"), 1):
        if not charges[item.pk]:
            raise InvoiceConflict(
                "Save at least one service on each item before invoicing."
            )
        groups.append(
            {
                "label": f"ITEM {index:02d} - {item.product.name}",
                "lines": charges[item.pk],
            }
        )
    if not groups:
        raise InvoiceConflict("Save at least one order item before invoicing.")
    if charges[None]:
        groups.append({"label": "ORDER-WIDE EXTRAS", "lines": charges[None]})
    customer_name = f"{customer.first_name} {customer.last_name}".strip()
    return {
        "business": invoice_business_details(settings),
        "issue_date": timezone.localdate(issued_at, settings.business_zone).isoformat(),
        "currency": order.currency,
        "order_reference": order.reference,
        "bill_to": [
            value
            for value in (
                customer_name,
                customer.company,
                customer.email,
                customer.primary_phone,
            )
            if value
        ],
        "groups": groups,
    }


@transaction.atomic
def apply_invoice_action(order_id, action, *, user, revision, invoice_id, reason):
    # Acquire the same row write lock used for order saves before reading its
    # state. This also serializes invoice requests on SQLite.
    if not ServiceOrder.objects.filter(pk=order_id).update(revision=F("revision")):
        raise ServiceOrder.DoesNotExist
    order = ServiceOrder.objects.select_related("customer").get(pk=order_id)
    active = order.invoices.filter(status=Invoice.Status.ISSUED).first()
    if active and (
        (action == "generate" and not order.invoice_revision_reason and not invoice_id)
        or (action == "replace" and invoice_id and active.replaces_id == invoice_id)
    ):
        return active
    if order.revision != revision or (active.pk if active else None) != invoice_id:
        raise InvoiceConflict(
            "The order or invoice changed. Review the order and try again."
        )
    if action not in available_invoice_actions(order, active):
        raise InvoiceConflict(
            "This invoice action is unavailable for the current order or payment status."
        )

    now = timezone.now()
    if action == "revise":
        order.invoice_revision_reason = reason
        order.status = ServiceOrder.Status.DRAFT
        result = active
    elif action == "void":
        close_invoice(active, Invoice.Status.VOID, user, now, reason)
        order.invoice_revision_reason = ""
        result = active
    else:
        settings = SystemSettings.get_solo()
        snapshot = order_invoice_snapshot(order, settings, now)
        if active:
            close_invoice(
                active,
                Invoice.Status.SUPERSEDED,
                user,
                now,
                order.invoice_revision_reason,
            )
        # The primary key supplies the global sequence. The other segments use
        # the prefix and company-local date captured when the invoice is issued.
        result = Invoice.objects.create(
            order=order,
            issued_by=user,
            issued_at=now,
            number_prefix=settings.invoice_prefix,
            number_date=date.fromisoformat(snapshot["issue_date"]),
            snapshot=snapshot,
            logo=settings.invoice_logo.name or "",
            replaces=active,
        )
        order.invoice_revision_reason = ""

    order.revision += 1
    order.save(
        update_fields=["revision", "status", "invoice_revision_reason", "updated_at"]
    )
    return result


def close_invoice(invoice, status, user, closed_at, reason):
    invoice.status = status
    invoice.closed_by = user
    invoice.closed_at = closed_at
    invoice.closure_reason = reason
    invoice.save(update_fields=["status", "closed_by", "closed_at", "closure_reason"])
