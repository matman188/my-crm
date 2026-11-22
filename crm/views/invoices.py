from copy import copy

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import content_disposition_header
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from reportlab.platypus.doctemplate import LayoutError

from crm.forms.settings import InvoiceSettingsForm
from crm.invoice_pdf import build_sample_invoice, render_invoice
from crm.models import Invoice, ServiceOrder, SystemSettings
from crm.order_invoices import (
    INVOICE_ACTION_LABELS,
    INVOICE_STAGES,
    InvoiceConflict,
    apply_invoice_action,
    available_invoice_actions,
    order_invoice_snapshot,
)

from .common import record_url


def pdf_response(content, filename, *, download=False):
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = content_disposition_header(download, filename)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
@permission_required("crm.change_systemsettings", raise_exception=True)
@require_POST
def preview_invoice(request):
    sample = request.POST.get("sample", "short")
    if sample not in ("short", "long"):
        return JsonResponse(
            {"message": "Choose a short or multi-page sample."}, status=400
        )
    form = InvoiceSettingsForm(
        request.POST, request.FILES, instance=copy(SystemSettings.get_solo())
    )
    if not form.is_valid():
        return JsonResponse({"errors": form.errors.get_json_data()}, status=400)
    try:
        content = build_sample_invoice(
            form.instance, logo=form.cleaned_data["invoice_logo"], long=sample == "long"
        )
    except (ValueError, LayoutError) as exc:
        message = (
            str(exc)
            if isinstance(exc, ValueError)
            else "This content does not fit the sample layout. Shorten long address lines and try again."
        )
        return JsonResponse({"message": message}, status=400)
    return pdf_response(content, "sample-invoice.pdf")


@login_required
@permission_required("crm.change_systemsettings", raise_exception=True)
@require_GET
def invoice_logo(request):
    logo = SystemSettings.get_solo().invoice_logo
    if not logo:
        raise Http404("No invoice logo has been saved.")
    try:
        response = FileResponse(logo.open("rb"), content_type="image/png")
    except OSError:
        raise Http404("The invoice logo is unavailable.")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


class InvoiceActionForm(forms.Form):
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    invoice = forms.IntegerField(min_value=1, required=False, widget=forms.HiddenInput)
    reason = forms.CharField(max_length=500, widget=forms.Textarea(attrs={"rows": 3}))
    not_shared = forms.BooleanField(
        label="I confirm this invoice has not been shared with the customer."
    )

    def __init__(self, *args, action, **kwargs):
        super().__init__(*args, **kwargs)
        if action not in ("revise", "void"):
            del self.fields["reason"]
        if action == "generate":
            del self.fields["not_shared"]


@login_required
@permission_required("crm.view_serviceorder", raise_exception=True)
@require_http_methods(["GET", "POST"])
def order_invoice_action(request, order_id, action):
    if action not in INVOICE_ACTION_LABELS:
        raise Http404
    if action in ("revise", "void") and not request.user.has_perm(
        "crm.change_serviceorder"
    ):
        raise PermissionDenied
    order = get_object_or_404(ServiceOrder, pk=order_id)
    active = order.invoices.filter(status=Invoice.Status.ISSUED).first()
    order_url = record_url(request, "edit_order", order_id=order.pk)
    if request.method == "GET" and action not in available_invoice_actions(
        order, active
    ):
        messages.error(
            request,
            "This invoice action is unavailable for the current order or payment status.",
        )
        return redirect(order_url)
    form = InvoiceActionForm(
        request.POST if request.method == "POST" else None,
        action=action,
        initial={"revision": order.revision, "invoice": active.pk if active else None},
    )
    if request.method == "POST" and form.is_valid():
        try:
            invoice = apply_invoice_action(
                order.pk,
                action,
                user=request.user,
                revision=form.cleaned_data["revision"],
                invoice_id=form.cleaned_data["invoice"],
                reason=form.cleaned_data.get("reason", ""),
            )
        except ServiceOrder.DoesNotExist as exc:
            raise Http404 from exc
        except InvoiceConflict as exc:
            messages.error(request, str(exc))
        else:
            message = {
                "generate": f"Invoice {invoice.number} is ready to preview or download.",
                "revise": f"Edit and submit the order to issue a correction for invoice {invoice.number}.",
                "replace": f"Corrected invoice {invoice.number} is ready to preview or download.",
                "void": f"Invoice {invoice.number} was voided.",
            }[action]
            messages.success(request, message)
        return redirect(order_url)
    return render(
        request,
        "crm/order_invoice_action.html",
        {
            "order": order,
            "active_invoice": active,
            "order_url": order_url,
            "form": form,
            "invoice_action": action,
            "page_title": INVOICE_ACTION_LABELS[action],
        },
    )


@login_required
@permission_required("crm.view_serviceorder", raise_exception=True)
@require_GET
def preview_order_invoice(request, order_id):
    order = get_object_or_404(
        ServiceOrder.objects.select_related("customer"), pk=order_id
    )
    if order.status not in (ServiceOrder.Status.DRAFT, *INVOICE_STAGES):
        raise Http404
    settings = SystemSettings.get_solo()
    try:
        snapshot = order_invoice_snapshot(order, settings, timezone.now())
        content = render_invoice(snapshot, logo=settings.invoice_logo)
    except (InvoiceConflict, ValueError, LayoutError) as exc:
        return invoice_pdf_error(exc)
    return pdf_response(content, f"{order.reference}-invoice-preview.pdf")


@login_required
@permission_required("crm.view_serviceorder", raise_exception=True)
@require_GET
def order_invoice_pdf(request, order_id, invoice_id):
    invoice = get_object_or_404(Invoice, order_id=order_id, pk=invoice_id)
    try:
        content = render_invoice(
            invoice.snapshot,
            logo=invoice.logo,
            number=invoice.number,
            template_version=invoice.template_version,
        )
    except (ValueError, LayoutError) as exc:
        return invoice_pdf_error(exc)
    return pdf_response(
        content, f"{invoice.number}.pdf", download=request.GET.get("download") == "1"
    )


def invoice_pdf_error(error):
    response = HttpResponse(
        "Could not render the PDF. Review the order and invoice settings, then try again."
        if isinstance(error, LayoutError)
        else str(error),
        status=422,
        content_type="text/plain; charset=utf-8",
    )
    response["Cache-Control"] = "private, no-store"
    return response
