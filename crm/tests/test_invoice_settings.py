from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image
from pypdf import PdfReader

from crm.forms.settings import InvoiceSettingsForm
from crm.models import (
    Customer,
    OrderItem,
    OrderServiceCharge,
    Product,
    Service,
    ServiceOrder,
    SystemSettings,
)
from crm.tests.helpers import create_admin_user


def image_upload(format="PNG", size=(300, 120)):
    buffer = BytesIO()
    Image.new("RGB", size, "#2f6f86").save(buffer, format)
    return SimpleUploadedFile(
        "business-logo.jpg" if format == "JPEG" else "business-logo.png",
        buffer.getvalue(),
        f"image/{format.lower()}",
    )


class InvoiceSettingsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = create_admin_user()
        cls.operator = get_user_model().objects.create_user(username="invoice-operator")

    def setUp(self):
        self.client.force_login(self.admin)
        self.settings = SystemSettings.get_solo()
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        override = override_settings(MEDIA_ROOT=self.media.name)
        override.enable()
        self.addCleanup(override.disable)

    def payload(self, **changes):
        data = {
            name: getattr(self.settings, name)
            for name in InvoiceSettingsForm.Meta.fields
            if name != "invoice_logo"
        }
        data.update(
            section="invoicing",
            company_name="Example Services",
            invoice_prefix="INV",
        )
        data.update(changes)
        return data

    def preview(self, **changes):
        return self.client.post(reverse("preview_invoice"), self.payload(**changes))

    def test_tabs_and_grouped_fields_are_available_to_admin(self):
        response = self.client.get(reverse("system_settings"), {"tab": "invoicing"})
        for text in (
            "General",
            "Invoicing",
            "Business details",
            "Payment details",
            "Invoice appearance and wording",
            "Save settings",
            "Preview sample invoice",
            "Multi-page invoice",
        ):
            self.assertContains(response, text)
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertNotContains(response, "Load demo data")
        self.assertNotIn("default_currency", response.context["form"].fields)
        self.assertNotIn("business_timezone", response.context["form"].fields)
        self.assertNotIn("invoice_payment_terms_days", response.context["form"].fields)
        self.assertNotContains(response, "Payment terms")

    def test_save_invoice_settings_and_reuse_business_name(self):
        response = self.client.post(
            reverse("system_settings"),
            self.payload(
                invoice_address="Example Street",
                invoice_bank_details="Bank: Example Bank",
                invoice_note="Thank you",
                invoice_accent="#243e59",
                invoice_prefix=" abc ",
            ),
        )
        self.assertRedirects(response, reverse("system_settings") + "?tab=invoicing")
        self.settings.refresh_from_db()
        self.assertEqual(self.settings.company_name, "Example Services")
        self.assertEqual(self.settings.invoice_prefix, "ABC")
        self.assertEqual(self.settings.invoice_bank_details, "Bank: Example Bank")
        self.assertEqual(self.settings.invoice_accent, "#243e59")
        self.assertContains(self.client.get(reverse("home")), "Example Services")

    def test_general_save_preserves_invoice_fields_and_stale_invoice_save_preserves_general_fields(
        self,
    ):
        self.settings.invoice_bank_details = "Keep banking details"
        self.settings.save()
        stale = SystemSettings.objects.get(pk=self.settings.pk)
        form = InvoiceSettingsForm(self.payload(), instance=stale)
        self.assertTrue(form.is_valid(), form.errors)
        SystemSettings.objects.filter(pk=self.settings.pk).update(
            default_currency="USD", business_timezone="Europe/London"
        )
        form.save()
        self.settings.refresh_from_db()
        self.assertEqual(self.settings.default_currency, "USD")
        self.assertEqual(self.settings.business_timezone, "Europe/London")
        self.client.post(
            reverse("system_settings"),
            {
                "company_name": "New name",
                "default_currency": "EUR",
                "business_timezone": "UTC",
            },
        )
        self.settings.refresh_from_db()
        self.assertEqual(self.settings.invoice_bank_details, "Keep banking details")

    def test_preview_uses_unsaved_inputs_without_persisting_settings_or_business_records(
        self,
    ):
        before = SystemSettings.objects.values().get()
        models = (
            Customer,
            Product,
            Service,
            ServiceOrder,
            OrderItem,
            OrderServiceCharge,
        )
        counts = [model.objects.count() for model in models]
        response = self.preview(
            invoice_note="Unsaved customer-facing wording",
            invoice_bank_details="Unsaved banking details",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("inline", response["Content-Disposition"])
        reader = PdfReader(BytesIO(response.content))
        text = "\n".join(page.extract_text() for page in reader.pages)
        self.assertIn("Example Services", text)
        self.assertIn("Unsaved customer-facing wording", text)
        self.assertIn("Unsaved banking details", text)
        self.assertIn("PREVIEW", text)
        self.assertIn("Sample Customer", text)
        self.assertEqual(SystemSettings.objects.values().get(), before)
        self.assertEqual([model.objects.count() for model in models], counts)
        self.assertFalse(list(Path(self.media.name).rglob("*")))

    def test_short_pdf_and_optional_blank_sections(self):
        response = self.preview()
        reader = PdfReader(BytesIO(response.content))
        self.assertEqual(len(reader.pages), 1)
        page = reader.pages[0]
        self.assertAlmostEqual(float(page.mediabox.width), 595.276, places=2)
        text = page.extract_text()
        for value in (
            "INV-PREVIEW",
            "SO-SAMPLE",
            "245.00",
            "TOTAL ZAR",
            "Page 1",
            "Sample only - not issued",
        ):
            self.assertIn(value, text)
        for value in (
            "BANKING DETAILS",
            "INVOICE NOTE",
            "TERMS AND DISCLAIMER",
            "Tax number:",
        ):
            self.assertNotIn(value, text)

    def test_long_sample_has_repeat_headers_and_page_numbers(self):
        response = self.preview(
            sample="long",
            invoice_bank_details="Bank sample",
            invoice_terms="Sample disclaimer",
        )
        self.assertEqual(response.status_code, 200)
        reader = PdfReader(BytesIO(response.content))
        self.assertGreater(len(reader.pages), 1)
        for index, page in enumerate(reader.pages, 1):
            text = page.extract_text()
            self.assertIn(f"Page {index}", text)
            self.assertIn("PREVIEW", text)
            self.assertIn("SERVICE / DESCRIPTION", text)
        self.assertIn("TOTAL ZAR", reader.pages[-1].extract_text())

    def test_issue_date_uses_business_timezone_without_payment_terms(self):
        self.settings.business_timezone = "Africa/Johannesburg"
        self.settings.save()
        with patch(
            "crm.invoice_pdf.timezone.now",
            return_value=datetime(2026, 11, 15, 23, 30, tzinfo=timezone.utc),
        ):
            response = self.preview(invoice_payment_terms_days="14")
        text = PdfReader(BytesIO(response.content)).pages[0].extract_text()
        self.assertIn("16 Nov 2026", text)
        self.assertNotIn("Payment due", text)
        self.assertNotIn("Payment terms", text)
        self.assertNotIn("Due on receipt", text)

    def test_currency_comes_from_general_settings_and_internal_notes_are_not_used(self):
        self.settings.default_currency = "USD"
        self.settings.save()
        response = self.preview(
            default_currency="EUR",
            notes="DO NOT DISCLOSE",
            **{
                "customer-notes": "SECRET CUSTOMER NOTE",
                "items-0-notes": "SECRET ITEM NOTE",
            },
        )
        text = PdfReader(BytesIO(response.content)).pages[0].extract_text()
        self.assertIn("TOTAL USD", text)
        self.assertNotIn("EUR", text)
        self.assertNotIn("SECRET", text)
        self.assertNotIn("DO NOT DISCLOSE", text)

    def test_logo_preview_does_not_store_file_and_save_normalizes_jpeg_to_png(self):
        response = self.preview(invoice_logo=image_upload("JPEG"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(list(Path(self.media.name).rglob("*")))
        response = self.client.post(
            reverse("system_settings"), self.payload(invoice_logo=image_upload("JPEG"))
        )
        self.assertEqual(response.status_code, 302)
        self.settings.refresh_from_db()
        self.assertTrue(self.settings.invoice_logo.name.endswith(".png"))
        page = self.client.get(reverse("system_settings"), {"tab": "invoicing"})
        self.assertContains(page, 'href="/system-settings/invoice-logo/"')
        self.assertNotContains(page, 'href="/media/')
        with self.settings.invoice_logo.open("rb") as file:
            self.assertTrue(file.read().startswith(b"\x89PNG"))
        self.assertEqual(self.preview().status_code, 200)
        saved = self.client.get(reverse("invoice_logo"))
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved["Content-Type"], "image/png")
        saved.close()

    def test_remove_logo_from_preview_or_saved_settings(self):
        self.client.post(
            reverse("system_settings"), self.payload(invoice_logo=image_upload())
        )
        self.settings.refresh_from_db()
        name = self.settings.invoice_logo.name
        response = self.preview(**{"invoice_logo-clear": "on"})
        self.assertEqual(response.status_code, 200)
        self.settings.refresh_from_db()
        self.assertEqual(self.settings.invoice_logo.name, name)
        self.client.post(
            reverse("system_settings"), self.payload(**{"invoice_logo-clear": "on"})
        )
        self.settings.refresh_from_db()
        self.assertFalse(self.settings.invoice_logo)
        self.assertEqual(self.client.get(reverse("invoice_logo")).status_code, 404)

    def test_invalid_logo_types_sizes_and_dimensions_are_rejected(self):
        for file in (
            SimpleUploadedFile("logo.svg", b"<svg></svg>", "image/svg+xml"),
            SimpleUploadedFile("logo.png", b"x" * (2 * 1024 * 1024 + 1), "image/png"),
            image_upload(size=(4097, 1)),
        ):
            with self.subTest(name=file.name, size=file.size):
                response = self.preview(invoice_logo=file)
                self.assertEqual(response.status_code, 400)
                self.assertIn("invoice_logo", response.json()["errors"])
        self.assertFalse(list(Path(self.media.name).rglob("*")))

    def test_prefix_terms_accent_email_address_validation_and_unknown_sample(self):
        for field, value in (
            ("company_name", ""),
            ("invoice_prefix", "../BAD"),
            ("invoice_accent", "javascript:bad"),
            ("invoice_email", "not-an-email"),
            ("invoice_address", "Line\n" * 9),
        ):
            with self.subTest(field=field, value=value):
                response = self.preview(**{field: value})
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json()["errors"])
        self.assertEqual(self.preview(sample="unknown").status_code, 400)

    def test_plain_text_escaping_unicode_and_long_terms_render(self):
        response = self.preview(
            company_name="Café & Co <Example>",
            invoice_note="<b>Literal markup</b> & notes",
            invoice_terms="Long wording with references. " * 130,
        )
        self.assertEqual(response.status_code, 200)
        text = "\n".join(
            page.extract_text() for page in PdfReader(BytesIO(response.content)).pages
        )
        self.assertIn("Café & Co <Example>", text)
        self.assertIn("<b>Literal markup</b>", text)
        self.assertIn("Long wording", text)

    def test_preview_is_post_only_permission_checked_and_csrf_protected(self):
        self.assertEqual(self.client.get(reverse("preview_invoice")).status_code, 405)
        secured = Client(enforce_csrf_checks=True)
        secured.force_login(self.admin)
        self.assertEqual(
            secured.post(reverse("preview_invoice"), self.payload()).status_code, 403
        )
        self.client.force_login(self.operator)
        self.assertEqual(
            self.client.get(
                reverse("system_settings"), {"tab": "invoicing"}
            ).status_code,
            403,
        )
        self.assertEqual(self.preview().status_code, 403)
        self.assertEqual(self.client.get(reverse("invoice_logo")).status_code, 403)
        self.client.logout()
        self.assertEqual(self.preview().status_code, 302)

    def test_invalid_save_retains_invoicing_tab_and_does_not_change_settings(self):
        before = SystemSettings.objects.values().get()
        response = self.client.post(
            reverse("system_settings"), self.payload(invoice_prefix="../bad")
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["settings_tab"], "invoicing")
        self.assertTrue(response.context["form"].errors)
        self.assertEqual(SystemSettings.objects.values().get(), before)
