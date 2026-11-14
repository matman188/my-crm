from datetime import date, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from crm.authz import ACCESS_LEVEL_USER, assign_access_level
from crm.models import (
    Customer,
    OrderItem,
    OrderServiceCharge,
    Product,
    Service,
    ServiceOrder,
    SystemSettings,
)


class DraftOrderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="operator")
        assign_access_level(cls.user, ACCESS_LEVEL_USER)
        cls.worker = get_user_model().objects.create_user(
            username="sewist", first_name="Jordan"
        )
        cls.customer = Customer.objects.create(
            first_name="Alex", last_name="Dancer", email="alex@example.com"
        )
        cls.product = Product.objects.create(name="Ballet shoes (pair)")
        cls.other_product = Product.objects.create(name="Dance bag")
        cls.service = Service.objects.create(name="Sew ribbons", price="12.35")
        cls.service.products.add(cls.product)
        cls.other_service = Service.objects.create(name="Repair handle", price="40.00")
        cls.other_service.products.add(cls.other_product)
        cls.global_service = Service.objects.create(name="Overnight", price="50.00")

    def setUp(self):
        self.client.force_login(self.user)

    def payload(self, *, customer=None):
        return {
            "customer_mode": "existing",
            "customer": str((customer or self.customer).pk),
            "assigned_to": "",
            "notes": "Call before collection",
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-0-product": str(self.product.pk),
            "items-0-due_date": "2026-11-20",
            "items-0-due_time": "",
            "items-0-notes": "Keep the original ribbons",
            "items-0-services-TOTAL_FORMS": "2",
            "items-0-services-INITIAL_FORMS": "0",
            "items-0-services-0-service": str(self.service.pk),
            "items-0-services-0-quantity": "2",
            "items-0-services-0-notes": "Left side",
            "items-0-services-1-service": str(self.service.pk),
            "items-0-services-1-quantity": "2",
            "items-0-services-1-notes": "Right side",
            "general-TOTAL_FORMS": "1",
            "general-INITIAL_FORMS": "0",
            "general-0-service": str(self.global_service.pk),
            "general-0-quantity": "1",
            "general-0-notes": "Prioritize this job",
        }

    def create_order(self, data=None):
        response = self.client.post(reverse("create_order"), data or self.payload())
        self.assertEqual(response.status_code, 302, getattr(response, "context", None))
        return ServiceOrder.objects.latest("pk")

    def edit_payload(self, order):
        data = self.payload()
        item = order.items.get()
        charges = list(item.charges.order_by("pk"))
        general = order.charges.get(item__isnull=True)
        data.update(
            {
                "revision": str(order.revision),
                "items-INITIAL_FORMS": "1",
                "items-0-id": str(item.pk),
                "items-0-services-INITIAL_FORMS": "2",
                "items-0-services-0-id": str(charges[0].pk),
                "items-0-services-1-id": str(charges[1].pk),
                "general-INITIAL_FORMS": "1",
                "general-0-id": str(general.pk),
            }
        )
        return data

    def test_authentication_and_permissions_are_required(self):
        stranger = get_user_model().objects.create_user(username="no_permissions")
        self.client.force_login(stranger)
        for name in ("orders", "create_order"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403)
        self.client.logout()
        self.assertRedirects(
            self.client.get(reverse("orders")), "/login/?next=/orders/"
        )

    def test_standard_crm_user_can_open_order_form_without_configuration_access(self):
        response = self.client.get(reverse("create_order"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Order notes")
        self.assertContains(response, 'role="combobox"')
        self.assertContains(response, "data-customer-dialog")
        self.assertContains(response, "Create New")
        self.assertContains(response, "Assignee")
        self.assertNotContains(response, 'name="items-0-quantity"')
        self.assertNotContains(response, 'name="items-0-description"')
        self.assertNotContains(response, "Times per product unit")
        self.assertNotContains(response, 'type="radio"')
        html = response.content.decode()
        self.assertLess(
            html.index("<h3>Extras</h3>"), html.index("<h3>Order details</h3>")
        )
        self.assertContains(response, "order-service-catalog")
        self.assertContains(response, 'name="items-0-services-0-service"')
        self.assertContains(response, 'name="items-__prefix__-services-0-service"')
        self.assertContains(
            response, 'name="items-__prefix__-services-__charge__-service"'
        )
        self.assertNotContains(response, "Configuration")

    def test_repeated_services_and_general_extras_have_correct_decimal_totals(self):
        data = self.payload()
        data.update(
            {
                "unit_price": "0.01",
                "total": "0.01",
                "currency": "USD",
                "status": "closed",
            }
        )
        order = self.create_order(data)
        self.assertEqual(order.status, ServiceOrder.Status.DRAFT)
        self.assertEqual(order.currency, "ZAR")
        self.assertEqual(order.created_by, self.user)
        self.assertIsNone(order.assigned_to)
        self.assertEqual(order.reference, f"SO-{order.pk:06d}")
        self.assertEqual(order.total, Decimal("99.40"))
        item = order.items.get()
        self.assertEqual(item.total, Decimal("49.40"))
        self.assertEqual(
            list(item.charges.values_list("notes", flat=True)),
            ["Left side", "Right side"],
        )
        self.assertEqual(item.due_date, date(2026, 11, 20))
        self.assertIsNone(item.due_time)
        response = self.client.get(reverse("edit_order", args=[order.pk]))
        self.assertContains(response, "Left side")
        self.assertContains(response, "Right side")
        self.assertContains(response, "Call before collection")

    def test_customer_can_be_created_inline_and_order_can_be_assigned(self):
        data = self.payload()
        data.update(
            {
                "customer_mode": "new",
                "customer": "",
                "customer-first_name": "New dancer",
                "customer-email": "new@example.com",
                "customer-primary_phone": "0123456789",
                "assigned_to": str(self.worker.pk),
                "items-0-due_time": "15:30",
            }
        )
        order = self.create_order(data)
        self.assertEqual(order.customer.first_name, "New dancer")
        self.assertEqual(order.customer.owner, self.user)
        self.assertEqual(order.assigned_to, self.worker)
        self.assertEqual(order.items.get().due_time, time(15, 30))

    def test_invalid_nested_form_does_not_create_customer_or_partial_order(self):
        data = self.payload()
        data.update(
            {
                "customer_mode": "new",
                "customer-first_name": "Do not save",
                "items-0-services-1-quantity": "0",
            }
        )
        response = self.client.post(reverse("create_order"), data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Customer.objects.filter(first_name="Do not save").exists())
        self.assertFalse(ServiceOrder.objects.exists())
        self.assertFalse(OrderItem.objects.exists())
        self.assertFalse(OrderServiceCharge.objects.exists())
        self.assertContains(response, "Right side")

    def test_new_customer_requires_customer_permission(self):
        restricted = get_user_model().objects.create_user(username="order_only")
        restricted.user_permissions.add(
            Permission.objects.get(codename="add_serviceorder")
        )
        self.client.force_login(restricted)
        data = self.payload()
        data.update({"customer_mode": "new", "customer-first_name": "Restricted"})
        response = self.client.post(reverse("create_order"), data)
        self.assertContains(response, "You do not have permission to create customers.")
        self.assertFalse(ServiceOrder.objects.exists())

    def test_product_specific_service_cannot_be_applied_to_wrong_product_or_whole_order(
        self,
    ):
        for key in ("items-0-services-0-service", "general-0-service"):
            data = self.payload()
            data[key] = str(self.other_service.pk)
            response = self.client.post(reverse("create_order"), data)
            self.assertEqual(response.status_code, 200)
            self.assertFalse(ServiceOrder.objects.exists())

    def test_global_service_is_available_on_an_item(self):
        data = self.payload()
        data["items-0-services-0-service"] = str(self.global_service.pk)
        order = self.create_order(data)
        self.assertEqual(order.total, Decimal("174.70"))

    def test_at_least_one_item_and_one_service_per_item_are_required(self):
        for prefix in ("items", "items-0-services"):
            data = self.payload()
            data[f"{prefix}-TOTAL_FORMS"] = "0"
            response = self.client.post(reverse("create_order"), data)
            self.assertEqual(response.status_code, 200)
            self.assertFalse(ServiceOrder.objects.exists())

    def test_invalid_or_missing_management_data_is_rejected_without_writes(self):
        for value in (None, "not-a-number", "100000"):
            data = self.payload()
            if value is None:
                del data["items-TOTAL_FORMS"]
            else:
                data["items-TOTAL_FORMS"] = value
            response = self.client.post(reverse("create_order"), data)
            self.assertEqual(response.status_code, 200)
            self.assertFalse(ServiceOrder.objects.exists())

    def test_edit_preserves_record_ids_prices_and_currency_and_can_remove_one_repeat(
        self,
    ):
        order = self.create_order()
        data = self.edit_payload(order)
        remaining_id = int(data["items-0-services-1-id"])
        self.service.price = Decimal("99.99")
        self.service.save()
        settings = SystemSettings.get_solo()
        settings.default_currency = "EUR"
        settings.save()
        data.update(
            {
                "items-0-services-0-DELETE": "on",
                "items-0-services-1-notes": "Updated right side",
                "items-0-due_time": "18:45",
                "assigned_to": str(self.worker.pk),
            }
        )
        response = self.client.post(reverse("edit_order", args=[order.pk]), data)
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.revision, 2)
        self.assertEqual(order.currency, "ZAR")
        self.assertEqual(order.total, Decimal("74.70"))
        charge = order.items.get().charges.get()
        self.assertEqual(charge.pk, remaining_id)
        self.assertEqual(charge.unit_price, Decimal("12.35"))
        self.assertEqual(charge.notes, "Updated right side")
        self.assertEqual(order.items.get().due_time, time(18, 45))
        self.assertEqual(order.assigned_to, self.worker)

    def test_stale_edit_does_not_overwrite_order_or_create_inline_customer(self):
        order = self.create_order()
        stale = self.edit_payload(order)
        current = dict(stale, notes="Saved by another operator")
        self.assertEqual(
            self.client.post(
                reverse("edit_order", args=[order.pk]), current
            ).status_code,
            302,
        )
        stale.update({"customer_mode": "new", "customer-first_name": "Stale customer"})
        response = self.client.post(reverse("edit_order", args=[order.pk]), stale)
        self.assertContains(response, "changed while you were editing")
        order.refresh_from_db()
        self.assertEqual(order.notes, "Saved by another operator")
        self.assertFalse(Customer.objects.filter(first_name="Stale customer").exists())

    def test_item_and_charge_ids_from_another_order_are_rejected(self):
        order = self.create_order()
        other = self.create_order()
        for field, forged_id in (
            ("items-0-id", other.items.get().pk),
            ("items-0-services-0-id", other.items.get().charges.first().pk),
            ("general-0-id", other.charges.get(item__isnull=True).pk),
        ):
            data = self.edit_payload(order)
            data[field] = str(forged_id)
            response = self.client.post(reverse("edit_order", args=[order.pk]), data)
            self.assertEqual(response.status_code, 200)
            order.refresh_from_db()
            other.refresh_from_db()
            self.assertEqual(order.revision, 1)
            self.assertEqual(other.revision, 1)
            self.assertEqual(OrderServiceCharge.objects.count(), 6)

    def test_duplicate_existing_charge_id_is_rejected(self):
        order = self.create_order()
        data = self.edit_payload(order)
        data["items-0-services-1-id"] = data["items-0-services-0-id"]
        response = self.client.post(reverse("edit_order", args=[order.pk]), data)
        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.revision, 1)

    def test_multiple_items_and_services_can_be_added_then_item_removed(self):
        order = self.create_order()
        data = self.edit_payload(order)
        data.update(
            {
                "items-TOTAL_FORMS": "2",
                "items-1-product": str(self.other_product.pk),
                "items-1-due_date": "2026-11-21",
                "items-1-due_time": "09:00",
                "items-1-services-TOTAL_FORMS": "1",
                "items-1-services-INITIAL_FORMS": "0",
                "items-1-services-0-service": str(self.other_service.pk),
                "items-1-services-0-quantity": "2",
            }
        )
        response = self.client.post(reverse("edit_order", args=[order.pk]), data)
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.items.count(), 2)
        self.assertEqual(order.total, Decimal("179.40"))
        bag = order.items.get(product=self.other_product)
        data.update(
            {
                "revision": str(order.revision),
                "items-INITIAL_FORMS": "2",
                "items-1-id": str(bag.pk),
                "items-1-DELETE": "on",
            }
        )
        response = self.client.post(reverse("edit_order", args=[order.pk]), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.charges.count(), 3)
        self.assertEqual(order.total, Decimal("99.40"))

    def test_changing_service_captures_new_price_and_time_can_be_cleared(self):
        data = self.payload()
        data["items-0-due_time"] = "14:15"
        order = self.create_order(data)
        data = self.edit_payload(order)
        data["items-0-services-0-service"] = str(self.global_service.pk)
        response = self.client.post(reverse("edit_order", args=[order.pk]), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(order.total, Decimal("174.70"))
        self.assertIsNone(order.items.get().due_time)

    def test_negative_catalog_price_is_rejected(self):
        self.service.price = Decimal("-5.00")
        self.service.save()
        response = self.client.post(reverse("create_order"), self.payload())
        self.assertContains(response, "negative price")
        self.assertFalse(ServiceOrder.objects.exists())

    def test_only_service_quantities_affect_total(self):
        data = self.payload()
        data.update({"items-0-quantity": "9999", "items-0-description": "Ignored"})
        order = self.create_order(data)
        self.assertEqual(order.total, Decimal("99.40"))
        self.assertFalse(hasattr(order.items.get(), "quantity"))

    def test_invalid_new_customer_reopens_modal_and_preserves_other_fields(self):
        data = self.payload()
        data.update(
            {
                "customer_mode": "new",
                "customer-first_name": "",
                "customer-email": "invalid",
            }
        )
        response = self.client.post(reverse("create_order"), data)
        self.assertContains(response, 'data-has-errors="true"')
        self.assertContains(response, 'value="invalid"')
        self.assertContains(response, "Left side")
        self.assertFalse(ServiceOrder.objects.exists())

    def test_customer_search_data_has_contact_details_and_selected_customer(self):
        order = self.create_order()
        response = self.client.get(reverse("edit_order", args=[order.pk]))
        customer = next(
            c
            for c in response.context["customer_catalog"]
            if c["id"] == self.customer.pk
        )
        self.assertEqual(customer["name"], "Alex Dancer")
        self.assertIn("alex@example.com", customer["label"])
        self.assertEqual(
            response.context["editor"].form["customer"].value(), self.customer.pk
        )

    def test_customer_product_and_service_used_on_orders_cannot_be_deleted(self):
        self.create_order()
        self.user.is_superuser = True
        self.user.save()
        for name, record in (
            ("delete_customer", self.customer),
            ("delete_product", self.product),
            ("delete_service", self.service),
        ):
            response = self.client.post(reverse(name, args=[record.pk]), follow=True)
            self.assertContains(
                response, "used on a service order and cannot be deleted"
            )
            self.assertTrue(type(record).objects.filter(pk=record.pk).exists())

    def test_orders_can_be_searched_by_reference_customer_and_assignee(self):
        data = self.payload()
        data["assigned_to"] = str(self.worker.pk)
        order = self.create_order(data)
        self.create_order(
            self.payload(customer=Customer.objects.create(first_name="Unrelated"))
        )
        for query in (order.reference, "alex@example.com", "Jordan"):
            response = self.client.get(reverse("orders"), {"q": query})
            self.assertEqual(response.context["page_obj"].paginator.count, 1)
            self.assertContains(response, order.reference)
            self.assertContains(response, "99.40")
        response = self.client.get(reverse("orders"), {"q": "no matching orders"})
        self.assertContains(response, "No orders match your search.")
