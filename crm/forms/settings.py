from django import forms
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from io import BytesIO
from uuid import uuid4

from django.core.files.uploadedfile import SimpleUploadedFile, UploadedFile
from PIL import Image, ImageOps

from crm.models import SystemSettings


class SettingsDetailsForm(forms.ModelForm):
    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            instance.save(update_fields=self.Meta.fields if instance.pk else None)
            self.save_m2m()
        return instance


class SystemSettingsForm(SettingsDetailsForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.is_bound and "business_timezone" not in self.data:
            self.data = self.data.copy()
            self.data["business_timezone"] = (
                self.instance.business_timezone or "Africa/Johannesburg"
            )

    business_timezone = forms.CharField(
        initial="Africa/Johannesburg",
        help_text="Used for displayed timestamps and work deadlines. Examples include Africa/Johannesburg, Europe/London, and America/New_York.",
    )

    def clean_business_timezone(self):
        value = self.cleaned_data["business_timezone"]
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise forms.ValidationError(
                "Enter a valid timezone, for example Africa/Johannesburg."
            )
        return value

    class Meta:
        model = SystemSettings
        fields = ("company_name", "default_currency", "business_timezone")
        labels = {
            "company_name": "Company Name",
            "default_currency": "Default Currency",
        }


class InvoiceLogoField(forms.ImageField):
    def clean(self, data, initial=None):
        if isinstance(data, UploadedFile) and data.size > 2 * 1024 * 1024:
            raise forms.ValidationError("Choose a PNG or JPEG logo smaller than 2 MB.")
        value = super().clean(data, initial)
        if not isinstance(value, UploadedFile):
            return value
        try:
            value.seek(0)
            with Image.open(value) as image:
                if image.format not in ("PNG", "JPEG"):
                    raise forms.ValidationError("Choose a PNG or JPEG logo.")
                if image.width > 4096 or image.height > 4096:
                    raise forms.ValidationError(
                        "The logo must be at most 4096 pixels on each side."
                    )
                image = ImageOps.exif_transpose(image)
                image.thumbnail((1600, 1600))
                image = image.convert(
                    "RGBA"
                    if "A" in image.getbands() or "transparency" in image.info
                    else "RGB"
                )
                output = BytesIO()
                image.save(output, format="PNG")
        except (OSError, ValueError, Image.DecompressionBombError):
            raise forms.ValidationError(
                "The logo could not be read. Choose a valid PNG or JPEG."
            )
        if output.tell() > 2 * 1024 * 1024:
            raise forms.ValidationError(
                "The logo is too detailed. Choose a smaller image."
            )
        return SimpleUploadedFile(
            f"{uuid4().hex}.png", output.getvalue(), content_type="image/png"
        )


class InvoiceLogoInput(forms.ClearableFileInput):
    template_name = "crm/widgets/invoice_logo.html"


class InvoiceSettingsForm(SettingsDetailsForm):
    invoice_logo = InvoiceLogoField(
        required=False,
        label="Logo",
        help_text="PNG or JPEG, up to 2 MB and 4096 pixels per side.",
        widget=InvoiceLogoInput(attrs={"accept": "image/png,image/jpeg"}),
    )
    invoice_prefix = forms.RegexField(
        regex=r"^[A-Z0-9][A-Z0-9-]{0,11}$",
        max_length=12,
        initial="INV",
        label="Sample preview prefix",
        help_text="Issued invoices use INV followed by the date and daily sequence, for example INV2026112201.",
    )

    def clean_invoice_prefix(self):
        return self.cleaned_data["invoice_prefix"].rstrip("-")

    def clean_invoice_address(self):
        value = self.cleaned_data["invoice_address"]
        if len(value.splitlines()) > 8:
            raise forms.ValidationError("Use no more than 8 address lines.")
        return value

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.is_bound and "invoice_prefix" in self.data:
            self.data = self.data.copy()
            self.data["invoice_prefix"] = self.data["invoice_prefix"].strip().upper()
        self.sections = [
            (
                "Business details",
                [
                    self[name]
                    for name in (
                        "company_name",
                        "invoice_logo",
                        "invoice_address",
                        "invoice_email",
                        "invoice_phone",
                        "invoice_registration_number",
                        "invoice_tax_number",
                    )
                ],
            ),
            (
                "Payment details",
                [
                    self[name]
                    for name in (
                        "invoice_bank_details",
                        "invoice_payment_instructions",
                    )
                ],
            ),
            (
                "Invoice appearance and wording",
                [
                    self[name]
                    for name in (
                        "invoice_prefix",
                        "invoice_accent",
                        "invoice_terms",
                        "invoice_note",
                    )
                ],
            ),
        ]

    class Meta:
        model = SystemSettings
        fields = (
            "company_name",
            "invoice_logo",
            "invoice_address",
            "invoice_email",
            "invoice_phone",
            "invoice_registration_number",
            "invoice_tax_number",
            "invoice_bank_details",
            "invoice_payment_instructions",
            "invoice_prefix",
            "invoice_accent",
            "invoice_terms",
            "invoice_note",
        )
        labels = {
            "company_name": "Business name",
            "invoice_address": "Address",
            "invoice_email": "Email",
            "invoice_phone": "Phone",
            "invoice_registration_number": "Registration number",
            "invoice_tax_number": "Tax number",
            "invoice_bank_details": "Banking details",
            "invoice_payment_instructions": "Payment instructions",
            "invoice_accent": "Accent colour",
            "invoice_terms": "Terms and disclaimer",
            "invoice_note": "Default Invoice Note",
        }
        widgets = {
            name: forms.Textarea(attrs={"rows": 3})
            for name in (
                "invoice_address",
                "invoice_bank_details",
                "invoice_payment_instructions",
                "invoice_terms",
                "invoice_note",
            )
        }
        help_texts = {
            "company_name": "Shared with the business name shown elsewhere in the CRM.",
            "invoice_bank_details": "Enter the bank, account holder, account number, branch code and any other details on separate lines.",
            "invoice_tax_number": "Optional identifier only. Tax calculations are not configured in this step.",
            "invoice_note": "Customer-facing text. Internal customer, order and service notes are excluded.",
        }


class SystemSettingsAdminForm(InvoiceSettingsForm, SystemSettingsForm):
    class Meta(InvoiceSettingsForm.Meta):
        fields = (
            *InvoiceSettingsForm.Meta.fields,
            "default_currency",
            "business_timezone",
        )
