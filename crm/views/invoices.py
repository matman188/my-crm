from copy import copy

from django.contrib.auth.decorators import login_required, permission_required
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.views.decorators.http import require_GET, require_POST
from reportlab.platypus.doctemplate import LayoutError

from crm.forms.settings import InvoiceSettingsForm
from crm.invoice_pdf import build_sample_invoice
from crm.models import SystemSettings


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
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = 'inline; filename="sample-invoice.pdf"'
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


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
