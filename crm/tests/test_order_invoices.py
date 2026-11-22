from datetime import date
from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse
from PIL import Image
from pypdf import PdfReader

from crm.authz import ACCESS_LEVEL_USER, assign_access_level
from crm.models import (
    Customer,
    Invoice,
    OrderItem,
    OrderServiceCharge,
    Product,
    Service,
    ServiceOrder,
    SystemSettings,
)
from crm.order_invoices import apply_invoice_action


class OrderInvoiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="operator")
        assign_access_level(cls.user, ACCESS_LEVEL_USER)
        cls.customer = Customer.objects.create(
            first_name="Alex",
            last_name="Dancer",
            email="alex@example.com",
            primary_phone="0123456789",
            notes="Private customer instruction",
        )
        cls.product = Product.objects.create(name="Ballet shoes")
        cls.service = Service.objects.create(name="Sew ribbons", price="99.00")
        cls.extra = Service.objects.create(name="Express", price="8.00")
        cls.order = ServiceOrder.objects.create(
            status=ServiceOrder.Status.IN_PROGRESS,
            customer=cls.customer,
            currency="ZAR",
            notes="Private order instruction",
        )
        cls.item = OrderItem.objects.create(
            order=cls.order,
            product=cls.product,
            due_date=date(2026, 11, 30),
            notes="Private item instruction",
        )
        cls.charge = OrderServiceCharge.objects.create(
            order=cls.order,
            item=cls.item,
            service=cls.service,
            quantity=2,
            unit_price="12.00",
            notes="Private service instruction",
        )
        cls.extra_charge = OrderServiceCharge.objects.create(
            order=cls.order,
            service=cls.extra,
            quantity=1,
            unit_price="8.00",
        )
        SystemSettings.get_solo()
        SystemSettings.objects.filter(pk=1).update(
            company_name="Studio Services",
            invoice_bank_details="Account 123456",
            invoice_note="Thank you for your order",
            default_currency="USD",
        )

    def setUp(self):
        self.client.force_login(self.user)
        self.edit_url = reverse("edit_order", args=[self.order.pk])

    def action_url(self, action):
        return reverse("order_invoice_action", args=[self.order.pk, action])

    def pdf_url(self, invoice):
        return reverse("order_invoice_pdf", args=[self.order.pk, invoice.pk])

    def issue(self):
        self.client.post(self.action_url("generate"), {"revision": self.order.revision})
        self.order.refresh_from_db()
        return self.order.invoices.get(status=Invoice.Status.ISSUED)

    @staticmethod
    def pdf_text(response):
        return "\n".join(
            page.extract_text() for page in PdfReader(BytesIO(response.content)).pages
        )

    def test_order_preview_and_idempotent_issuance_by_standard_user(self):
        self.assertContains(self.client.get(self.edit_url), "Generate invoice")
        preview = self.client.get(
            reverse("preview_order_invoice", args=[self.order.pk])
        )
        self.assertEqual(preview.status_code, 200)
        self.assertIn("Preview - not issued", self.pdf_text(preview))
        self.assertIn("Alex Dancer", self.pdf_text(preview))
        self.assertFalse(Invoice.objects.exists())
        self.assertEqual(self.client.get(self.action_url("generate")).status_code, 200)
        previous_revision = self.order.revision
        invoice = self.issue()
        self.assertRedirects(
            self.client.post(
                self.action_url("generate"), {"revision": previous_revision}
            ),
            self.edit_url,
        )
        self.assertEqual(Invoice.objects.count(), 1)
        self.assertEqual(invoice.issued_by, self.user)
        self.assertContains(self.client.get(self.edit_url), invoice.number)
        response = self.client.get(self.pdf_url(invoice))
        text = self.pdf_text(response)
        for value in (
            invoice.number,
            self.order.reference,
            "Alex Dancer",
            "Express",
            "Sew ribbons",
            "32.00",
            "TOTAL ZAR",
            "Account 123456",
            "Thank you for your order",
        ):
            self.assertIn(value, text)
        for value in ("PREVIEW", "Private", "99.00", "TOTAL USD"):
            self.assertNotIn(value, text)
        self.assertIn("inline", response["Content-Disposition"])
        download = self.client.get(self.pdf_url(invoice), {"download": "1"})
        self.assertIn(
            f'attachment; filename="{invoice.number}.pdf"',
            download["Content-Disposition"],
        )
        self.assertEqual(self.pdf_text(download), text)
        self.assertIn("no-store", download["Cache-Control"])

    def test_snapshot_uses_original_names_prices_settings_date_and_logo(self):
        with TemporaryDirectory() as media, self.settings(MEDIA_ROOT=media):
            settings = SystemSettings.get_solo()
            image = BytesIO()
            Image.new("RGB", (12, 12), "blue").save(image, "PNG")
            settings.invoice_logo.save("before.png", ContentFile(image.getvalue()))
            original_logo = settings.invoice_logo.name
            invoice = self.issue()
            original_pdf = self.pdf_text(self.client.get(self.pdf_url(invoice)))
            settings.invoice_logo.save("after.png", ContentFile(image.getvalue()))
            SystemSettings.objects.filter(pk=1).update(
                company_name="Different business",
                invoice_prefix="NEW",
                invoice_bank_details="Different bank",
                business_timezone="UTC",
            )
            Customer.objects.filter(pk=self.customer.pk).update(
                first_name="Changed customer"
            )
            Service.objects.filter(pk=self.service.pk).update(name="Changed service")
            Product.objects.filter(pk=self.product.pk).update(name="Changed product")
            self.charge.quantity = 4
            self.charge.save(update_fields=["quantity"])
            invoice.refresh_from_db()
            self.assertEqual(invoice.logo.name, original_logo)
            self.assertEqual(
                self.pdf_text(self.client.get(self.pdf_url(invoice))), original_pdf
            )

    def test_revision_edits_order_then_replaces_old_invoice_once(self):
        invoice = self.issue()
        order_page = self.client.get(self.edit_url)
        self.assertNotContains(order_page, 'value="return_to_draft"')
        self.assertNotContains(order_page, 'value="cancel"')
        for action in ("return_to_draft", "cancel"):
            response = self.client.post(
                self.edit_url,
                {
                    "action": action,
                    "revision": self.order.revision,
                    "payment_status": "unpaid",
                },
            )
            self.assertContains(response, "This action is not available")
        self.client.post(
            self.action_url("revise"),
            {
                "invoice": invoice.pk,
                "revision": self.order.revision,
                "reason": "Customer requested an extra service",
                "not_shared": "on",
            },
        )
        self.order.refresh_from_db()
        invoice.refresh_from_db()
        self.assertEqual(self.order.status, ServiceOrder.Status.DRAFT)
        self.assertEqual(invoice.status, Invoice.Status.ISSUED)
        self.assertNotContains(self.client.get(self.edit_url), "Delete draft")
        delete = self.client.post(
            reverse("delete_order", args=[self.order.pk]),
            {"revision": self.order.revision},
        )
        self.assertEqual(delete.status_code, 403)
        response = self.client.post(
            self.edit_url,
            {
                "action": "submit",
                "revision": self.order.revision,
                "customer_mode": "existing",
                "customer": self.customer.pk,
                "items-TOTAL_FORMS": 1,
                "items-INITIAL_FORMS": 1,
                "items-0-id": self.item.pk,
                "items-0-product": self.product.pk,
                "items-0-due_date": "2026-11-30",
                "items-0-services-TOTAL_FORMS": 1,
                "items-0-services-INITIAL_FORMS": 1,
                "items-0-services-0-id": self.charge.pk,
                "items-0-services-0-service": self.service.pk,
                "items-0-services-0-quantity": 3,
                "general-TOTAL_FORMS": 1,
                "general-INITIAL_FORMS": 1,
                "general-0-id": self.extra_charge.pk,
                "general-0-service": self.extra.pk,
                "general-0-quantity": 1,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertContains(self.client.get(self.edit_url), "Replace invoice")
        self.assertEqual(self.client.get(self.action_url("replace")).status_code, 200)
        payload = {
            "invoice": invoice.pk,
            "revision": self.order.revision,
            "not_shared": "on",
        }
        self.assertRedirects(
            self.client.post(self.action_url("replace"), payload), self.edit_url
        )
        self.assertRedirects(
            self.client.post(self.action_url("replace"), payload), self.edit_url
        )
        invoice.refresh_from_db()
        replacement = invoice.replacement
        self.assertEqual(self.order.invoices.count(), 2)
        self.assertEqual(invoice.status, Invoice.Status.SUPERSEDED)
        self.assertEqual(invoice.closure_reason, "Customer requested an extra service")
        self.assertEqual(invoice.closed_by, self.user)
        self.assertNotEqual(invoice.number, replacement.number)
        self.assertIn("32.00", self.pdf_text(self.client.get(self.pdf_url(invoice))))
        self.assertIn(
            "44.00", self.pdf_text(self.client.get(self.pdf_url(replacement)))
        )

    def test_failed_replacement_rolls_back_and_failed_render_can_retry(self):
        invoice = self.issue()
        self.order.invoice_revision_reason = "Correct billing details"
        self.order.save(update_fields=["invoice_revision_reason"])
        with patch(
            "crm.order_invoices.Invoice.objects.create", side_effect=IntegrityError
        ):
            with self.assertRaises(IntegrityError):
                apply_invoice_action(
                    self.order.pk,
                    "replace",
                    user=self.user,
                    revision=self.order.revision,
                    invoice_id=invoice.pk,
                    reason="",
                )
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.ISSUED)
        self.assertEqual(self.order.invoices.count(), 1)
        with patch(
            "crm.views.invoices.render_invoice",
            side_effect=ValueError("PDF temporarily unavailable"),
        ):
            self.assertContains(
                self.client.get(self.pdf_url(invoice)),
                "PDF temporarily unavailable",
                status_code=422,
            )
        self.assertIn(
            invoice.number, self.pdf_text(self.client.get(self.pdf_url(invoice)))
        )

    def test_void_requires_reason_unshared_confirmation_and_unpaid_invoice(self):
        invoice = self.issue()
        payload = {
            "invoice": invoice.pk,
            "revision": self.order.revision,
            "reason": "Order cancelled",
        }
        response = self.client.post(self.action_url("void"), payload)
        self.assertFormError(
            response.context["form"], "not_shared", "This field is required."
        )
        payload["not_shared"] = "on"
        ServiceOrder.objects.filter(pk=self.order.pk).update(
            payment_status=ServiceOrder.PaymentStatus.PAID
        )
        self.assertNotContains(self.client.get(self.edit_url), "Void invoice")
        self.assertRedirects(
            self.client.post(self.action_url("void"), payload), self.edit_url
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.ISSUED)
        ServiceOrder.objects.filter(pk=self.order.pk).update(
            payment_status=ServiceOrder.PaymentStatus.UNPAID
        )
        self.assertRedirects(
            self.client.post(self.action_url("void"), payload), self.edit_url
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.VOID)
        self.assertEqual(invoice.closure_reason, "Order cancelled")
        self.assertContains(self.client.get(self.edit_url), 'value="cancel"')
        self.assertEqual(self.client.get(self.pdf_url(invoice)).status_code, 200)

    def test_stage_permissions_stale_revision_and_csrf_are_enforced(self):
        for status in (ServiceOrder.Status.DRAFT, ServiceOrder.Status.CANCELLED):
            ServiceOrder.objects.filter(pk=self.order.pk).update(status=status)
            self.assertNotContains(self.client.get(self.edit_url), "Generate invoice")
            self.assertRedirects(
                self.client.post(
                    self.action_url("generate"), {"revision": self.order.revision}
                ),
                self.edit_url,
            )
        ServiceOrder.objects.filter(pk=self.order.pk).update(
            status=ServiceOrder.Status.COMPLETE
        )
        self.assertContains(self.client.get(self.edit_url), "Generate invoice")
        self.client.post(
            self.action_url("generate"), {"revision": self.order.revision + 1}
        )
        self.assertFalse(Invoice.objects.exists())
        protected_client = Client(enforce_csrf_checks=True)
        protected_client.force_login(self.user)
        self.assertEqual(
            protected_client.post(
                self.action_url("generate"), {"revision": self.order.revision}
            ).status_code,
            403,
        )
        invoice = self.issue()
        stranger = get_user_model().objects.create_user(username="stranger")
        self.client.force_login(stranger)
        self.assertEqual(self.client.get(self.pdf_url(invoice)).status_code, 403)
        self.assertEqual(self.client.get(self.action_url("generate")).status_code, 403)
