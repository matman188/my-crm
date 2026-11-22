from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase
from django.urls import reverse

from crm.authz import ACCESS_LEVEL_USER, assign_access_level
from crm.models import Customer, ServiceOrder


class OrderListUpdateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.user = users.create_user(username="operator")
        assign_access_level(cls.user, ACCESS_LEVEL_USER)
        cls.worker = users.create_user(username="worker")
        cls.inactive = users.create_user(username="inactive", is_active=False)
        cls.customer = Customer.objects.create(
            first_name="Alex", email="alex@example.com"
        )

    def setUp(self):
        self.client.force_login(self.user)

    def make_order(self, status, **kwargs):
        return ServiceOrder.objects.create(
            customer=self.customer,
            status=status,
            currency="ZAR",
            notes="Keep these notes",
            **kwargs,
        )

    def post(self, order, **changes):
        return self.client.post(
            reverse("update_order_workflow", args=[order.pk]),
            {"revision": order.revision, **changes},
        )

    def test_updates_a_complete_order_and_returns_to_the_filtered_queue(self):
        order = self.make_order(ServiceOrder.Status.COMPLETE, assigned_to=self.user)
        destination = f"{reverse('orders')}?view=awaiting_collection&q=Alex"
        response = self.client.get(destination)
        self.assertContains(response, f"Collected for {order.reference}")
        self.assertContains(response, f"Payment status for {order.reference}")
        self.assertContains(response, f"Assigned to for {order.reference}")
        response = self.post(
            order,
            assigned_to=self.worker.pk,
            collected="true",
            payment_status="paid",
            next=destination,
            notes="Ignore these notes",
            status="cancelled",
        )
        self.assertRedirects(response, destination)
        order.refresh_from_db()
        self.assertEqual(order.revision, 2)
        self.assertEqual(order.assigned_to, self.worker)
        self.assertTrue(order.collected)
        self.assertEqual(order.payment_status, ServiceOrder.PaymentStatus.PAID)
        self.assertEqual(order.status, ServiceOrder.Status.COMPLETE)
        self.assertEqual(order.notes, "Keep these notes")
        self.assertNotContains(self.client.get(destination), order.reference)
        self.assertRedirects(self.post(order, collected="false"), reverse("orders"))
        order.refresh_from_db()
        self.assertFalse(order.collected)
        self.assertEqual(order.assigned_to, self.worker)
        self.assertEqual(order.payment_status, ServiceOrder.PaymentStatus.PAID)

    def test_in_progress_keeps_collection_locked_and_accepts_partial_updates(self):
        order = self.make_order(
            ServiceOrder.Status.IN_PROGRESS, assigned_to=self.worker
        )
        self.assertNotContains(
            self.client.get(reverse("orders")), f"Collected for {order.reference}"
        )
        self.assertRedirects(
            self.post(order, payment_status="paid", collected="true"),
            reverse("orders"),
        )
        order.refresh_from_db()
        self.assertFalse(order.collected)
        self.assertEqual(order.assigned_to, self.worker)
        self.assertEqual(order.payment_status, ServiceOrder.PaymentStatus.PAID)
        self.assertRedirects(self.post(order, assigned_to=""), reverse("orders"))
        order.refresh_from_db()
        self.assertIsNone(order.assigned_to)

    def test_locked_stages_and_invalid_selections_are_unchanged(self):
        for status in (ServiceOrder.Status.DRAFT, ServiceOrder.Status.CANCELLED):
            order = self.make_order(status)
            self.assertNotContains(
                self.client.get(reverse("orders")), f"Save changes to {order.reference}"
            )
            self.assertRedirects(
                self.post(order, assigned_to=self.worker.pk, payment_status="paid"),
                reverse("orders"),
            )
            order.refresh_from_db()
            self.assertEqual(order.revision, 1)
            self.assertIsNone(order.assigned_to)
        order = self.make_order(ServiceOrder.Status.COMPLETE, assigned_to=self.worker)
        for changes in (
            {"assigned_to": ""},
            {"assigned_to": self.inactive.pk},
            {"payment_status": "unknown"},
            {"payment_status": "refunded"},
            {"payment_status": "full_refund"},
            {"collected": "unknown"},
        ):
            self.assertRedirects(self.post(order, **changes), reverse("orders"))
            order.refresh_from_db()
            self.assertEqual(order.revision, 1)
            self.assertEqual(order.assigned_to, self.worker)

    def test_current_inactive_assignee_is_retained_and_stale_edit_is_rejected(self):
        order = self.make_order(ServiceOrder.Status.COMPLETE, assigned_to=self.inactive)
        self.assertContains(self.client.get(reverse("orders")), "inactive (Inactive)")
        self.assertRedirects(self.post(order, payment_status="paid"), reverse("orders"))
        self.assertRedirects(
            self.post(order, payment_status="unpaid"), reverse("orders")
        )
        order.refresh_from_db()
        self.assertEqual(order.payment_status, ServiceOrder.PaymentStatus.PAID)
        self.assertEqual(order.assigned_to, self.inactive)
        self.assertEqual(order.revision, 2)

    def test_requires_post_csrf_and_order_change_permission(self):
        order = self.make_order(ServiceOrder.Status.IN_PROGRESS)
        url = reverse("update_order_workflow", args=[order.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.user)
        self.assertEqual(
            protected.post(url, {"revision": 1, "payment_status": "paid"}).status_code,
            403,
        )
        self.worker.user_permissions.add(
            Permission.objects.get(codename="view_serviceorder")
        )
        self.client.force_login(self.worker)
        self.assertNotContains(
            self.client.get(reverse("orders")), "data-order-list-edit"
        )
        self.assertEqual(self.post(order, payment_status="paid").status_code, 403)
