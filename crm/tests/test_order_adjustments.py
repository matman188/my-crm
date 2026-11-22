from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from crm.authz import ACCESS_LEVEL_USER, assign_access_level
from crm.models import (
    Customer,
    Invoice,
    OrderComplaint,
    OrderItem,
    OrderRefund,
    OrderRefundAmountChange,
    OrderServiceCharge,
    Product,
    Service,
    ServiceOrder,
    SystemSettings,
)


class OrderAdjustmentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="operator")
        assign_access_level(cls.user, ACCESS_LEVEL_USER)
        cls.customer = Customer.objects.create(
            first_name="Alex", email="alex@example.com"
        )
        cls.order = ServiceOrder.objects.create(
            customer=cls.customer,
            currency="ZAR",
            status=ServiceOrder.Status.COMPLETE,
            payment_status=ServiceOrder.PaymentStatus.PAID,
            assigned_to=cls.user,
            collected=True,
            notes="General order notes",
        )
        product = Product.objects.create(name="Ballet shoe")
        item = OrderItem.objects.create(
            order=cls.order, product=product, due_date=timezone.localdate()
        )
        service = Service.objects.create(name="Sew ribbons", price="100.00")
        cls.charge = OrderServiceCharge.objects.create(
            order=cls.order, item=item, service=service, quantity=1, unit_price="100.00"
        )
        OrderServiceCharge.objects.create(
            order=cls.order, item=item, service=service, quantity=4, unit_price="100.00"
        )

    def setUp(self):
        self.client.force_login(self.user)
        self.edit_url = self.url("edit_order")
        self.complaint_url = self.url("edit_order_complaint")
        self.refund_url = self.url("record_order_refund")

    def url(self, name):
        return reverse(name, args=[self.order.pk])

    def refund_payload(self, **changes):
        return {
            "revision": self.order.revision,
            "amount_received": "500.00",
            "amount": "50.00",
            "refunded_on": (timezone.localdate() - timedelta(days=1)).isoformat(),
            "reason": "Half of the service charge",
            "affected_service": self.charge.pk,
            **changes,
        }

    def test_free_redo_can_be_logged_and_found_in_orders(self):
        detail = self.client.get(self.edit_url)
        self.assertContains(detail, 'name="complaint-logged"')
        self.assertContains(detail, "Optional complaint details")
        self.assertRedirects(
            self.client.get(self.complaint_url),
            f"{self.edit_url}#order-complaint-heading",
        )
        payload = {
            "revision": self.order.revision,
            "assigned_to": self.user.pk,
            "payment_status": "paid",
            "collected": "on",
            "complaint-revision": self.order.revision,
            "complaint-logged": "on",
            "complaint-details": "Ribbon came loose",
            "complaint-outcome": "redo",
            "complaint-affected_service": self.charge.pk,
        }
        self.assertRedirects(self.client.post(self.edit_url, payload), self.edit_url)
        self.order.refresh_from_db()
        self.assertEqual(self.order.complaint.affected_service, self.charge)
        self.assertIn(
            "Item 1 · Ballet shoe · Sew ribbons",
            self.order.complaint.service_description,
        )
        self.assertEqual(self.order.notes, "General order notes")
        self.assertTrue(self.order.collected)
        self.assertEqual(self.order.payment_status, ServiceOrder.PaymentStatus.PAID)
        self.assertFalse(Invoice.objects.exists())
        self.assertFalse(OrderRefund.objects.exists())
        detail = self.client.get(self.edit_url)
        self.assertContains(detail, "Ribbon came loose")
        self.assertContains(detail, "Free redo")
        for value in ("yes", "redo"):
            self.assertContains(
                self.client.get(reverse("orders"), {"complaint": value}),
                self.order.reference,
            )
        self.assertNotContains(
            self.client.get(reverse("orders"), {"complaint": "no"}),
            self.order.reference,
        )
        payload.update(
            revision=self.order.revision, **{"complaint-revision": self.order.revision}
        )
        del payload["complaint-logged"]
        self.assertRedirects(self.client.post(self.edit_url, payload), self.edit_url)
        self.assertContains(
            self.client.get(reverse("orders"), {"complaint": "no"}),
            self.order.reference,
        )
        self.assertFalse(OrderComplaint.objects.get(order=self.order).logged)

    def test_first_refund_prefills_payment_and_accepts_amount_without_optional_details(
        self,
    ):
        response = self.client.get(self.edit_url)
        self.assertContains(response, 'form="order-refund-form"')
        self.assertContains(response, "Optional refund details")
        self.assertEqual(
            response.context["refund_form"]["amount_received"].value(),
            Decimal("500.00"),
        )
        self.assertRedirects(
            self.client.post(
                self.refund_url,
                {
                    "revision": self.order.revision,
                    "amount_received": "500.00",
                    "amount": "50.00",
                },
            ),
            self.edit_url,
        )
        refund = OrderRefund.objects.get(order=self.order)
        self.assertEqual(refund.reason, "")
        self.assertIsNone(refund.affected_service)
        self.assertEqual(
            refund.refunded_on,
            timezone.localdate(timezone=SystemSettings.get_solo().business_zone),
        )

    def test_partial_then_full_refund_keeps_charges_and_issued_invoice(self):
        issue_url = reverse("order_invoice_action", args=[self.order.pk, "generate"])
        self.assertRedirects(
            self.client.post(issue_url, {"revision": self.order.revision}),
            self.edit_url,
        )
        self.order.refresh_from_db()
        invoice = self.order.invoices.get()
        snapshot = invoice.snapshot
        payload = self.refund_payload()
        self.assertRedirects(self.client.post(self.refund_url, payload), self.edit_url)
        self.order.refresh_from_db()
        self.assertEqual(
            self.order.payment_status, ServiceOrder.PaymentStatus.PARTIALLY_REFUNDED
        )
        self.assertEqual(self.order.refund_amount_received, Decimal("500.00"))
        self.assertEqual(self.order.total_refunded, Decimal("50.00"))
        self.assertEqual(self.order.refunds.get().recorded_by, self.user)
        response = self.client.get(self.edit_url)
        self.assertContains(response, "Partially refunded")
        self.assertContains(response, "ZAR 450.00")
        self.assertContains(response, "Half of the service charge")
        self.assertNotContains(response, 'name="amount_received"')
        regular_edit = self.client.post(
            reverse("update_order_workflow", args=[self.order.pk]),
            {
                "revision": self.order.revision,
                "payment_status": "unpaid",
            },
        )
        self.assertRedirects(regular_edit, reverse("orders"))
        self.order.refresh_from_db()
        self.assertEqual(
            self.order.payment_status, ServiceOrder.PaymentStatus.PARTIALLY_REFUNDED
        )
        response = self.client.post(self.refund_url, payload)
        self.assertContains(response, "This order changed")
        self.assertEqual(self.order.refunds.count(), 1)
        response = self.client.post(
            self.refund_url, self.refund_payload(amount="450.01")
        )
        self.assertContains(response, "exceeds the remaining amount")
        self.assertContains(response, 'class="order-refund-entry" open')
        self.assertEqual(self.order.refunds.count(), 1)
        self.assertRedirects(
            self.client.post(
                self.refund_url, {"revision": self.order.revision, "amount": "450.00"}
            ),
            self.edit_url,
        )
        self.order.refresh_from_db()
        invoice.refresh_from_db()
        self.assertEqual(
            self.order.payment_status, ServiceOrder.PaymentStatus.FULLY_REFUNDED
        )
        self.assertEqual(self.order.total_refunded, Decimal("500.00"))
        self.assertEqual(self.order.total, Decimal("500.00"))
        self.assertEqual(self.order.status, ServiceOrder.Status.COMPLETE)
        self.assertTrue(self.order.collected)
        self.assertEqual(invoice.snapshot, snapshot)
        self.assertEqual(invoice.status, Invoice.Status.ISSUED)
        self.assertContains(
            self.client.get(reverse("orders"), {"payment_status": "full_refund"}),
            self.order.reference,
        )

    def test_refund_validation_and_permissions(self):
        other = ServiceOrder.objects.create(customer=self.customer, currency="ZAR")
        foreign_charge = OrderServiceCharge.objects.create(
            order=other, service=self.charge.service, quantity=1, unit_price="100.00"
        )
        for bad in (
            {"amount_received": ""},
            {"amount": "0"},
            {"amount": "-0.01"},
            {"affected_service": foreign_charge.pk},
            {"refunded_on": (timezone.localdate() + timedelta(days=2)).isoformat()},
        ):
            response = self.client.post(self.refund_url, self.refund_payload(**bad))
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["refund_form"].errors)
            self.assertFalse(OrderRefund.objects.exists())
        ServiceOrder.objects.filter(pk=self.order.pk).update(
            payment_status=ServiceOrder.PaymentStatus.UNPAID
        )
        self.assertRedirects(
            self.client.post(self.refund_url, self.refund_payload()), self.edit_url
        )
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.user)
        self.assertEqual(
            protected.post(self.refund_url, self.refund_payload()).status_code, 403
        )
        reader = get_user_model().objects.create_user(username="reader")
        reader.user_permissions.add(
            Permission.objects.get(codename="view_serviceorder")
        )
        self.client.force_login(reader)
        self.assertEqual(self.client.get(self.complaint_url).status_code, 403)
        self.assertEqual(
            self.client.post(self.refund_url, self.refund_payload()).status_code, 403
        )

    def test_correcting_a_refund_updates_totals_and_preserves_the_original_amount_in_history(
        self,
    ):
        self.assertRedirects(
            self.client.post(self.refund_url, self.refund_payload()), self.edit_url
        )
        self.order.refresh_from_db()
        self.assertRedirects(
            self.client.post(
                self.refund_url, {"revision": self.order.revision, "amount": "450.00"}
            ),
            self.edit_url,
        )
        self.order.refresh_from_db()
        self.assertEqual(
            self.order.payment_status, ServiceOrder.PaymentStatus.FULLY_REFUNDED
        )
        refund = self.order.refunds.get(amount="50.00")
        correction_url = reverse(
            "edit_order_refund_amount", args=[self.order.pk, refund.pk]
        )
        self.assertContains(self.client.get(self.edit_url), "Edit amount")
        page = self.client.get(correction_url)
        self.assertContains(page, "Save amount")
        self.assertContains(page, "Maximum corrected amount <strong>ZAR 50.00</strong>")
        self.assertEqual(
            page.context["refund_form"]["amount"].value(), Decimal("50.00")
        )

        editor = get_user_model().objects.create_user(username="editor")
        assign_access_level(editor, ACCESS_LEVEL_USER)
        self.client.force_login(editor)
        payload = {"revision": self.order.revision, "amount": "40.00"}
        self.assertRedirects(
            self.client.post(correction_url, payload),
            f"{self.edit_url}#order-refunds-heading",
        )
        self.order.refresh_from_db()
        refund.refresh_from_db()
        self.assertEqual(refund.amount, Decimal("40.00"))
        self.assertEqual(refund.reason, "Half of the service charge")
        self.assertEqual(refund.affected_service, self.charge)
        self.assertEqual(refund.recorded_by, self.user)
        self.assertEqual(self.order.total_refunded, Decimal("490.00"))
        self.assertEqual(
            self.order.payment_status, ServiceOrder.PaymentStatus.PARTIALLY_REFUNDED
        )
        audit = refund.amount_changes.get()
        self.assertEqual(audit.previous_amount, Decimal("50.00"))
        self.assertEqual(audit.new_amount, Decimal("40.00"))
        self.assertEqual(audit.changed_by, editor)
        page = self.client.get(self.edit_url)
        self.assertContains(page, "ZAR 50.00 → ZAR 40.00")
        self.assertContains(page, "ZAR 10.00")
        self.assertContains(
            self.client.post(correction_url, payload), "This order changed"
        )
        self.assertEqual(OrderRefundAmountChange.objects.count(), 1)
        self.assertRedirects(
            self.client.post(
                correction_url,
                {
                    "revision": self.order.revision,
                    "amount": "40.00",
                },
            ),
            f"{self.edit_url}#order-refunds-heading",
        )
        self.assertEqual(OrderRefundAmountChange.objects.count(), 1)

    def test_refund_amount_correction_validates_limits_order_ownership_and_permissions(
        self,
    ):
        self.assertRedirects(
            self.client.post(self.refund_url, self.refund_payload()), self.edit_url
        )
        self.order.refresh_from_db()
        refund = self.order.refunds.get()
        correction_url = reverse(
            "edit_order_refund_amount", args=[self.order.pk, refund.pk]
        )
        data = {"revision": self.order.revision, "amount": "500.01"}
        self.assertContains(
            self.client.post(correction_url, data), "exceed the amount received"
        )
        self.assertEqual(
            self.client.post(correction_url, {**data, "amount": "0"}).status_code, 200
        )
        other_order = ServiceOrder.objects.create(
            customer=self.customer, currency="ZAR"
        )
        foreign_url = reverse(
            "edit_order_refund_amount", args=[other_order.pk, refund.pk]
        )
        self.assertEqual(self.client.post(foreign_url, data).status_code, 404)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.user)
        self.assertEqual(protected.post(correction_url, data).status_code, 403)
        reader = get_user_model().objects.create_user(username="reader")
        reader.user_permissions.add(
            Permission.objects.get(codename="view_serviceorder")
        )
        self.client.force_login(reader)
        self.assertEqual(self.client.post(correction_url, data).status_code, 403)
        refund.refresh_from_db()
        self.assertEqual(refund.amount, Decimal("50.00"))
        self.assertFalse(OrderRefundAmountChange.objects.exists())

    def test_legacy_refund_keeps_status_until_amount_recorded_and_protects_history(
        self,
    ):
        self.order.payment_status = ServiceOrder.PaymentStatus.REFUNDED
        self.order.status = ServiceOrder.Status.CANCELLED
        self.order.save(update_fields=["payment_status", "status"])
        self.assertContains(self.client.get(self.edit_url), "Refund amount unrecorded")
        self.assertRedirects(
            self.client.post(self.refund_url, self.refund_payload()), self.edit_url
        )
        self.order.refresh_from_db()
        self.assertEqual(
            self.order.payment_status, ServiceOrder.PaymentStatus.PARTIALLY_REFUNDED
        )
        self.assertEqual(self.order.status, ServiceOrder.Status.CANCELLED)
        self.order.status = ServiceOrder.Status.DRAFT
        self.order.save(update_fields=["status"])
        self.assertNotContains(self.client.get(self.edit_url), "Delete draft")
        response = self.client.post(
            self.url("delete_order"), {"revision": self.order.revision}
        )
        self.assertEqual(response.status_code, 403)
        self.charge.delete()
        record = self.order.refunds.get()
        self.assertIsNone(record.affected_service)
        self.assertIn("Ballet shoe · Sew ribbons", record.service_description)
