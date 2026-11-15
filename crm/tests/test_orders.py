import re
from datetime import date, time
from decimal import Decimal
from html.parser import HTMLParser
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase
from django.urls import reverse

from crm.authz import ACCESS_LEVEL_USER, assign_access_level
from crm.forms.customers import CustomerForm
from crm.forms.orders import OrderConflict, OrderEditor
from crm.models import (
    Customer,
    OrderItem,
    OrderServiceCharge,
    Product,
    Service,
    ServiceOrder,
    SystemSettings,
)


class ServiceOrderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="operator")
        assign_access_level(cls.user, ACCESS_LEVEL_USER)
        cls.worker = get_user_model().objects.create_user(
            username="sewist", first_name="Jordan"
        )
        cls.customer = Customer.objects.create(
            first_name="Alex",
            last_name="Dancer",
            email="alex@example.com",
            primary_phone="0123456789",
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
            "payment_status": ServiceOrder.PaymentStatus.UNPAID,
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
        data = (data or self.payload()).copy()
        # Prepare persisted-stage fixtures; transitions themselves are tested via actions.
        fixture_status = data.pop("status", None)
        response = self.client.post(reverse("create_order"), data)
        self.assertEqual(response.status_code, 302, getattr(response, "context", None))
        order = ServiceOrder.objects.latest("pk")
        if fixture_status is not None:
            order.status = fixture_status
            order.assigned_to_id = data.get("assigned_to") or None
            order.payment_status = data.get("payment_status", "unpaid")
            order.collected = bool(data.get("collected"))
            order.save(
                update_fields=["status", "assigned_to", "payment_status", "collected"]
            )
        return order

    def edit_payload(self, order):
        data = self.payload()
        item = order.items.get()
        charges = list(item.charges.order_by("pk"))
        general = order.charges.get(item__isnull=True)
        data.update(
            {
                "revision": str(order.revision),
                "payment_status": order.payment_status,
                "assigned_to": str(order.assigned_to_id or ""),
                "items-INITIAL_FORMS": "1",
                "items-0-id": str(item.pk),
                "items-0-services-INITIAL_FORMS": "2",
                "items-0-services-0-id": str(charges[0].pk),
                "items-0-services-1-id": str(charges[1].pk),
                "general-INITIAL_FORMS": "1",
                "general-0-id": str(general.pk),
            }
        )
        if order.collected:
            data["collected"] = "on"
        return data

    def workflow_payload(self, order, **changes):
        data = {
            "revision": str(order.revision),
            "assigned_to": str(order.assigned_to_id or ""),
            "payment_status": order.payment_status,
        }
        if order.collected:
            data["collected"] = "on"
        data.update(changes)
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
        self.assertContains(response, "Assigned To")
        self.assertNotContains(response, 'name="items-0-quantity"')
        self.assertNotContains(response, 'name="items-0-description"')
        self.assertNotContains(response, "Times per product unit")
        self.assertNotContains(response, 'type="radio"')
        self.assertNotContains(response, 'name="status"')
        self.assertContains(response, 'aria-label="Order summary"')
        self.assertNotContains(response, "order-status-banner")
        self.assertContains(response, "data-order-total", count=2)
        self.assertContains(response, "ZAR 0.00", count=2)
        self.assertContains(response, 'name="action" value="submit"')
        html = response.content.decode()
        self.assertLess(
            html.index("<h3>Order Details</h3>"), html.index("<h3>Customer</h3>")
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
            }
        )
        order = self.create_order(data)
        self.assertEqual(order.status, ServiceOrder.Status.DRAFT)
        self.assertEqual(order.payment_status, ServiceOrder.PaymentStatus.UNPAID)
        self.assertFalse(order.collected)
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

    def test_customer_can_be_created_inline_while_draft_assignment_is_locked(self):
        data = self.payload()
        data.update(
            {
                "customer_mode": "new",
                "customer": "",
                "customer-first_name": "New dancer",
                "customer-last_name": "Smith",
                "customer-email": "new@example.com",
                "customer-primary_phone": "0123456789",
                "assigned_to": str(self.worker.pk),
                "items-0-due_time": "15:30",
            }
        )
        order = self.create_order(data)
        self.assertEqual(order.customer.first_name, "New dancer")
        self.assertEqual(order.customer.owner, self.user)
        self.assertIsNone(order.assigned_to)
        self.assertEqual(order.items.get().due_time, time(15, 30))

    def test_invalid_nested_form_does_not_create_customer_or_partial_order(self):
        data = self.payload()
        data.update(
            {
                "customer_mode": "new",
                "customer-first_name": "Do not save",
                "customer-last_name": "Smith",
                "customer-email": "invalid-order@example.com",
                "customer-primary_phone": "0123456789",
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
        self.assertIsNone(order.assigned_to)

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
        stale.update(
            {
                "customer_mode": "new",
                "customer-first_name": "Stale customer",
                "customer-last_name": "Smith",
                "customer-email": "stale@example.com",
                "customer-primary_phone": "0123456789",
            }
        )
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

    def new_customer_payload(self):
        return dict(
            self.payload(),
            **{
                "customer_mode": "new",
                "customer": "",
                "customer-first_name": "New",
                "customer-last_name": "Customer",
                "customer-email": "new-contact@example.com",
                "customer-primary_phone": "0123456789",
                "customer-notes": "Special customer instructions",
            },
        )

    def test_customer_modal_requires_and_marks_all_four_contact_fields(self):
        response = self.client.get(reverse("create_order"))
        self.assertContains(response, 'class="required-marker"', count=4)
        for name in ("first_name", "last_name", "email", "primary_phone"):
            with self.subTest(name=name):
                self.assertTrue(
                    response.context["editor"].customer_form.fields[name].required
                )
                data = self.new_customer_payload()
                data[f"customer-{name}"] = ""
                invalid = self.client.post(reverse("create_order"), data)
                self.assertIn(name, invalid.context["editor"].customer_form.errors)
                self.assertContains(invalid, 'data-has-errors="true"')
                self.assertFalse(ServiceOrder.objects.exists())
                self.assertEqual(Customer.objects.count(), 1)

    def test_inline_duplicate_email_reopens_modal_without_partial_order_writes(self):
        data = self.new_customer_payload()
        data["customer-email"] = " ALEX@EXAMPLE.COM "
        response = self.client.post(reverse("create_order"), data)
        self.assertContains(response, CustomerForm.duplicate_email_message)
        self.assertIn("email", response.context["editor"].customer_form.errors)
        self.assertContains(response, 'data-has-errors="true"')
        self.assertContains(response, "Left side")
        self.assertFalse(ServiceOrder.objects.exists())
        self.assertFalse(OrderItem.objects.exists())
        self.assertEqual(Customer.objects.count(), 1)

    def test_inline_duplicate_race_rolls_back_order_revision_and_returns_modal_error(
        self,
    ):
        order = self.create_order()
        data = self.edit_payload(order)
        data.update(
            {
                key: value
                for key, value in self.new_customer_payload().items()
                if key.startswith("customer")
            }
        )
        data["customer-email"] = "alex@example.com"
        with patch.object(
            CustomerForm, "_email_in_use", side_effect=[False, True]
        ), patch.object(Customer, "validate_constraints"):
            response = self.client.post(reverse("edit_order", args=[order.pk]), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, CustomerForm.duplicate_email_message)
        self.assertContains(response, 'data-has-errors="true"')
        order.refresh_from_db()
        self.assertEqual(order.revision, 1)
        self.assertEqual(order.customer, self.customer)
        self.assertEqual(order.charges.count(), 3)
        self.assertEqual(Customer.objects.count(), 1)

    def test_orders_show_current_customer_notes_in_every_stage_as_read_only_text(self):
        self.customer.notes = "Use the side entrance.\n<strong>VIP</strong>"
        self.customer.save(update_fields=["notes"])
        for status in ServiceOrder.Status.values:
            with self.subTest(status=status):
                order = self.create_order(
                    dict(self.payload(), status=status, assigned_to=str(self.worker.pk))
                )
                response = self.client.get(reverse("edit_order", args=[order.pk]))
                self.assertEqual(
                    response.context["customer_notes"], self.customer.notes
                )
                self.assertContains(response, "Customer Notes")
                self.assertContains(
                    response, "Use the side entrance.\n&lt;strong&gt;VIP&lt;/strong&gt;"
                )
                self.assertNotContains(response, "<strong>VIP</strong>")
                customer = next(
                    c
                    for c in response.context["customer_catalog"]
                    if c["id"] == self.customer.pk
                )
                self.assertEqual(customer["notes"], self.customer.notes)
                self.assertEqual(customer["email"], self.customer.email)
        self.customer.notes = "Updated customer instructions"
        self.customer.save(update_fields=["notes"])
        response = self.client.get(reverse("edit_order", args=[order.pk]))
        self.assertContains(response, "Updated customer instructions")

    def test_new_customer_notes_remain_separate_from_order_notes(self):
        order = self.create_order(self.new_customer_payload())
        response = self.client.get(reverse("edit_order", args=[order.pk]))
        self.assertEqual(
            response.context["customer_notes"], "Special customer instructions"
        )
        self.assertEqual(order.customer.notes, "Special customer instructions")
        self.assertEqual(order.notes, "Call before collection")

    def test_customer_notes_match_the_selected_customer_on_invalid_and_locked_orders(
        self,
    ):
        other = Customer.objects.create(
            first_name="Other",
            last_name="Person",
            email="other@example.com",
            primary_phone="0123456789",
            notes="Other customer notes",
        )
        order = self.create_order()
        data = self.edit_payload(order)
        data.update({"customer": str(other.pk), "items-0-due_date": "invalid"})
        response = self.client.post(reverse("edit_order", args=[order.pk]), data)
        self.assertEqual(response.context["customer_notes"], other.notes)
        order.status = "in_progress"
        order.save(update_fields=["status"])
        self.customer.notes = "Original customer notes"
        self.customer.save(update_fields=["notes"])
        response = self.client.post(
            reverse("edit_order", args=[order.pk]),
            dict(
                self.workflow_payload(order), customer=str(other.pk), action="invalid"
            ),
        )
        self.assertEqual(response.context["customer_notes"], self.customer.notes)

    def customer_edit_payload(self, order=None):
        data = self.edit_payload(order) if order else self.payload()
        data.update(
            {
                "customer_mode": "edit",
                "customer": str(self.customer.pk),
                "customer-first_name": "Updated",
                "customer-last_name": "Customer",
                "customer-email": " ALEX@EXAMPLE.COM ",
                "customer-primary_phone": "0987654321",
                "customer-secondary_phone": "0123400000",
                "customer-company": "Updated business",
                "customer-notes": "New shared customer instructions",
            }
        )
        return data

    def test_draft_customer_edit_updates_the_same_record_with_unsaved_order_changes(
        self,
    ):
        order = self.create_order()
        self.customer.owner = self.worker
        self.customer.save(update_fields=["owner"])
        charge_ids = list(order.charges.values_list("pk", flat=True))
        data = self.customer_edit_payload(order)
        data["items-0-due_time"] = "17:30"
        data["customer-owner"] = str(self.user.pk)
        self.assertEqual(
            self.client.post(reverse("edit_order", args=[order.pk]), data).status_code,
            302,
        )
        self.customer.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(order.customer_id, self.customer.pk)
        self.assertEqual(self.customer.first_name, "Updated")
        self.assertEqual(self.customer.last_name, "Customer")
        self.assertEqual(self.customer.email, "alex@example.com")
        self.assertEqual(self.customer.primary_phone, "0987654321")
        self.assertEqual(self.customer.secondary_phone, "0123400000")
        self.assertEqual(self.customer.company, "Updated business")
        self.assertEqual(self.customer.notes, "New shared customer instructions")
        self.assertEqual(self.customer.owner, self.worker)
        self.assertEqual(order.notes, "Call before collection")
        self.assertEqual(order.items.get().due_time, time(17, 30))
        self.assertEqual(list(order.charges.values_list("pk", flat=True)), charge_ids)
        self.assertEqual(order.total, Decimal("99.40"))

    def test_selected_customer_can_be_edited_while_creating_an_order(self):
        order = self.create_order(self.customer_edit_payload())
        self.customer.refresh_from_db()
        self.assertEqual(order.customer_id, self.customer.pk)
        self.assertEqual(self.customer.first_name, "Updated")
        self.assertEqual(Customer.objects.count(), 1)

    def test_inline_customer_edit_validation_keeps_customer_and_order_unchanged(self):
        other = Customer.objects.create(
            first_name="Other",
            last_name="Person",
            email="other@example.com",
            primary_phone="0123456789",
        )
        order = self.create_order()
        for field, value in (
            ("last_name", ""),
            ("email", "OTHER@example.com"),
            ("primary_phone", ""),
        ):
            with self.subTest(field=field):
                data = self.customer_edit_payload(order)
                data[f"customer-{field}"] = value
                response = self.client.post(
                    reverse("edit_order", args=[order.pk]), data
                )
                self.assertEqual(response.status_code, 200)
                editor = response.context["editor"]
                self.assertTrue(editor.editing_customer)
                self.assertEqual(editor.customer_form.instance.pk, self.customer.pk)
                self.assertIn(field, editor.customer_form.errors)
                self.assertContains(response, 'data-has-errors="true"')
                self.assertContains(response, "Save customer")
                self.assertContains(response, 'value="Updated"')
                self.assertEqual(
                    response.context["customer_notes"],
                    "New shared customer instructions",
                )
                self.customer.refresh_from_db()
                order.refresh_from_db()
                self.assertEqual(self.customer.first_name, "Alex")
                self.assertEqual(order.revision, 1)
                self.assertEqual(Customer.objects.count(), 2)
        self.assertTrue(Customer.objects.filter(pk=other.pk).exists())

    def test_stale_order_cannot_save_customer_edits(self):
        order = self.create_order()
        data = self.customer_edit_payload(order)
        ServiceOrder.objects.filter(pk=order.pk).update(revision=2)
        response = self.client.post(reverse("edit_order", args=[order.pk]), data)
        self.assertContains(response, "changed while you were editing")
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.first_name, "Alex")
        self.assertEqual(self.customer.notes, "")

    def test_edit_customer_requires_change_customer_permission(self):
        order = self.create_order()
        restricted = get_user_model().objects.create_user(username="order_editor_only")
        restricted.user_permissions.add(
            Permission.objects.get(codename="change_serviceorder")
        )
        self.client.force_login(restricted)
        response = self.client.get(reverse("edit_order", args=[order.pk]))
        self.assertNotContains(response, "data-edit-customer")
        response = self.client.post(
            reverse("edit_order", args=[order.pk]), self.customer_edit_payload(order)
        )
        self.assertContains(response, "You do not have permission to edit customers.")
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.first_name, "Alex")

    def test_customer_edit_controls_and_forged_edits_stay_locked_after_draft(self):
        for status in ("in_progress", "complete", "cancelled"):
            with self.subTest(status=status):
                order = self.create_order(
                    dict(self.payload(), status=status, assigned_to=str(self.worker.pk))
                )
                response = self.client.get(reverse("edit_order", args=[order.pk]))
                self.assertNotContains(response, "data-edit-customer")
                self.assertEqual(
                    self.client.post(
                        reverse("edit_order", args=[order.pk]),
                        self.customer_edit_payload(order),
                    ).status_code,
                    302,
                )
                self.customer.refresh_from_db()
                self.assertEqual(self.customer.first_name, "Alex")
                self.assertEqual(self.customer.notes, "")
        order = self.create_order()
        response = self.client.get(reverse("edit_order", args=[order.pk]))
        self.assertContains(response, "data-edit-customer")
        catalog_customer = next(
            c
            for c in response.context["customer_catalog"]
            if c["id"] == self.customer.pk
        )
        self.assertEqual(catalog_customer["details"]["first_name"], "Alex")
        self.assertEqual(catalog_customer["details"]["primary_phone"], "0123456789")

    def test_edit_customer_rejects_missing_or_invalid_selected_customer(self):
        for customer in ("", "999999", "invalid"):
            data = self.customer_edit_payload()
            data["customer"] = customer
            response = self.client.post(reverse("create_order"), data)
            self.assertEqual(response.status_code, 200)
            self.assertIn("customer", response.context["editor"].form.errors)
            self.assertEqual(Customer.objects.count(), 1)
            self.assertFalse(ServiceOrder.objects.exists())

    def test_inline_customer_edit_duplicate_race_rolls_back_order_and_customer(self):
        other = Customer.objects.create(
            first_name="Other",
            last_name="Person",
            email="other@example.com",
            primary_phone="0123456789",
        )
        order = self.create_order()
        data = self.customer_edit_payload(order)
        data["customer-email"] = other.email
        with patch.object(
            CustomerForm, "_email_in_use", side_effect=[False, True]
        ), patch.object(Customer, "validate_constraints"):
            response = self.client.post(reverse("edit_order", args=[order.pk]), data)
        self.assertContains(response, CustomerForm.duplicate_email_message)
        self.assertContains(response, 'data-has-errors="true"')
        order.refresh_from_db()
        self.customer.refresh_from_db()
        self.assertEqual(order.revision, 1)
        self.assertEqual(self.customer.first_name, "Alex")
        self.assertEqual(self.customer.email, "alex@example.com")

    def customer_save_url(self, order=None, customer=None):
        kwargs = {"customer_id": (customer or self.customer).pk}
        if order:
            kwargs["order_id"] = order.pk
        return reverse(
            "save_order_customer" if order else "save_new_order_customer", kwargs=kwargs
        )

    def test_customer_modal_save_changes_only_customer_and_keeps_order_revision(self):
        self.customer.owner = self.worker
        self.customer.save(update_fields=["owner"])
        order = self.create_order()
        before = ServiceOrder.objects.values().get(pk=order.pk)
        items_before = list(order.items.values())
        charges_before = list(order.charges.values())
        data = self.customer_edit_payload(order)
        data.update(
            {
                "notes": "Do not save order notes",
                "items-0-due_time": "18:45",
                "customer-owner": str(self.user.pk),
            }
        )
        response = self.client.post(self.customer_save_url(order), data)
        self.assertEqual(response.status_code, 200)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.first_name, "Updated")
        self.assertEqual(self.customer.email, "alex@example.com")
        self.assertEqual(self.customer.notes, "New shared customer instructions")
        self.assertEqual(self.customer.owner, self.worker)
        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(ServiceOrder.objects.values().get(pk=order.pk), before)
        self.assertEqual(list(order.items.values()), items_before)
        self.assertEqual(list(order.charges.values()), charges_before)
        result = response.json()["customer"]
        self.assertEqual(result["id"], self.customer.pk)
        self.assertEqual(result["details"]["first_name"], "Updated")
        self.assertEqual(result["notes"], self.customer.notes)
        self.assertIn("Updated Customer", result["label"])
        self.assertEqual(result["save_url"], self.customer_save_url(order))
        # The unsaved order can still be saved using its original revision.
        ordinary_order_save = self.edit_payload(order)
        ordinary_order_save["notes"] = "Now save order notes"
        self.assertEqual(
            self.client.post(
                reverse("edit_order", args=[order.pk]), ordinary_order_save
            ).status_code,
            302,
        )
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.notes, "New shared customer instructions")

    def test_customer_modal_save_works_before_an_order_is_created(self):
        response = self.client.post(
            self.customer_save_url(), self.customer_edit_payload()
        )
        self.assertEqual(response.status_code, 200)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.first_name, "Updated")
        self.assertFalse(ServiceOrder.objects.exists())
        self.assertEqual(
            response.json()["customer"]["save_url"], self.customer_save_url()
        )

    def test_customer_modal_can_save_pending_customer_selection_without_changing_order(
        self,
    ):
        order = self.create_order()
        other = Customer.objects.create(
            first_name="Other",
            last_name="Person",
            email="other@example.com",
            primary_phone="0123456789",
        )
        data = self.customer_edit_payload(order)
        data["customer-email"] = other.email
        response = self.client.post(self.customer_save_url(order, other), data)
        self.assertEqual(response.status_code, 200)
        other.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(other.first_name, "Updated")
        self.assertEqual(order.customer_id, self.customer.pk)

    def test_customer_modal_save_returns_field_errors_without_changes(self):
        order = self.create_order()
        Customer.objects.create(
            first_name="Other",
            last_name="Person",
            email="other@example.com",
            primary_phone="0123456789",
        )
        for field, value in (
            ("last_name", ""),
            ("primary_phone", ""),
            ("email", "OTHER@example.com"),
        ):
            with self.subTest(field=field):
                data = self.customer_edit_payload(order)
                data[f"customer-{field}"] = value
                response = self.client.post(self.customer_save_url(order), data)
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json()["errors"])
                self.customer.refresh_from_db()
                order.refresh_from_db()
                self.assertEqual(self.customer.first_name, "Alex")
                self.assertEqual(order.revision, 1)

    def test_customer_modal_save_obeys_stage_and_stale_order_locks(self):
        order = self.create_order()
        data = self.customer_edit_payload(order)
        ServiceOrder.objects.filter(pk=order.pk).update(revision=2)
        response = self.client.post(self.customer_save_url(order), data)
        self.assertEqual(response.status_code, 409)
        for status in ("in_progress", "complete", "cancelled"):
            ServiceOrder.objects.filter(pk=order.pk).update(status=status, revision=1)
            response = self.client.post(self.customer_save_url(order), data)
            self.assertEqual(response.status_code, 403)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.first_name, "Alex")

    def test_customer_modal_save_requires_customer_and_order_permissions(self):
        order = self.create_order()
        for permissions in (
            ("change_customer",),
            ("change_serviceorder", "add_serviceorder"),
        ):
            user = get_user_model().objects.create_user(
                username="modal_" + permissions[0]
            )
            user.user_permissions.add(
                *Permission.objects.filter(codename__in=permissions)
            )
            self.client.force_login(user)
            for url in (self.customer_save_url(order), self.customer_save_url()):
                self.assertEqual(
                    self.client.post(
                        url, self.customer_edit_payload(order)
                    ).status_code,
                    403,
                )
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.first_name, "Alex")

    def test_customer_modal_save_requires_post_revision_and_valid_customer(self):
        order = self.create_order()
        self.assertEqual(
            self.client.get(self.customer_save_url(order)).status_code, 405
        )
        for revision in ("", "invalid", "0", "9999999999999999999999999999999999"):
            data = self.customer_edit_payload(order)
            data["revision"] = revision
            self.assertEqual(
                self.client.post(self.customer_save_url(order), data).status_code, 400
            )
        self.assertEqual(
            self.client.post(
                reverse("save_new_order_customer", args=[999999]),
                self.customer_edit_payload(),
            ).status_code,
            404,
        )

    def test_customer_modal_save_requires_csrf(self):
        order = self.create_order()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        client.get(reverse("edit_order", args=[order.pk]))
        data = self.customer_edit_payload(order)
        self.assertEqual(
            client.post(self.customer_save_url(order), data).status_code, 403
        )
        response = client.post(
            self.customer_save_url(order),
            data,
            HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value,
        )
        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.revision, 1)

    def test_customer_modal_save_duplicate_race_returns_error_and_preserves_order(self):
        order = self.create_order()
        other = Customer.objects.create(
            first_name="Other",
            last_name="Person",
            email="other@example.com",
            primary_phone="0123456789",
        )
        data = self.customer_edit_payload(order)
        data["customer-email"] = other.email
        with patch.object(
            CustomerForm, "_email_in_use", side_effect=[False, True]
        ), patch.object(Customer, "validate_constraints"):
            response = self.client.post(self.customer_save_url(order), data)
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json()["errors"])
        order.refresh_from_db()
        self.customer.refresh_from_db()
        self.assertEqual(order.revision, 1)
        self.assertEqual(self.customer.email, "alex@example.com")

    def test_archived_customer_cannot_be_selected_for_new_orders(self):
        Customer.objects.filter(pk=self.customer.pk).update(is_archived=True)
        response = self.client.get(reverse("create_order"))
        self.assertNotIn(
            self.customer.pk, {c["id"] for c in response.context["customer_catalog"]}
        )
        response = self.client.post(reverse("create_order"), self.payload())
        self.assertIn("customer", response.context["editor"].form.errors)
        self.assertFalse(ServiceOrder.objects.exists())

    def test_existing_orders_keep_archived_customers_and_save_in_all_stages(self):
        orders = [
            self.create_order(
                dict(self.payload(), status=status, assigned_to=str(self.worker.pk))
            )
            for status in ServiceOrder.Status.values
        ]
        Customer.objects.filter(pk=self.customer.pk).update(is_archived=True)
        for order in orders:
            response = self.client.get(reverse("edit_order", args=[order.pk]))
            customer = next(
                c
                for c in response.context["customer_catalog"]
                if c["id"] == self.customer.pk
            )
            self.assertTrue(customer["is_archived"])
            self.assertIn("(Archived)", customer["label"])
            self.assertEqual(
                self.client.post(
                    reverse("edit_order", args=[order.pk]), self.edit_payload(order)
                ).status_code,
                302,
            )
            order.refresh_from_db()
            self.assertEqual(order.customer_id, self.customer.pk)
            self.assertEqual(order.total, Decimal("99.40"))

    def test_draft_cannot_switch_to_a_different_archived_customer(self):
        order = self.create_order()
        archived = Customer.objects.create(
            first_name="Archived",
            last_name="Customer",
            email="archived@example.com",
            primary_phone="0123456789",
            is_archived=True,
        )
        data = self.edit_payload(order)
        data["customer"] = str(archived.pk)
        response = self.client.post(reverse("edit_order", args=[order.pk]), data)
        self.assertIn("customer", response.context["editor"].form.errors)
        order.refresh_from_db()
        self.assertEqual(order.customer_id, self.customer.pk)

    def test_customer_archived_after_validation_cannot_receive_a_new_order(self):
        editor = OrderEditor(user=self.user, data=self.payload())
        self.assertTrue(editor.is_valid(), editor.form.errors)
        Customer.objects.filter(pk=self.customer.pk).update(is_archived=True)
        with self.assertRaisesMessage(OrderConflict, "archived or removed"):
            editor.save()
        self.assertFalse(ServiceOrder.objects.exists())

    def test_inline_contact_edits_do_not_undo_concurrent_archiving(self):
        order = self.create_order()
        editor = OrderEditor(
            user=self.user, instance=order, data=self.customer_edit_payload(order)
        )
        self.assertTrue(editor.is_valid(), editor.form.errors)
        Customer.objects.filter(pk=self.customer.pk).update(is_archived=True)
        editor.save()
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.is_archived)
        self.assertEqual(self.customer.notes, "New shared customer instructions")

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
        data["status"] = "in_progress"
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

    def test_all_four_statuses_remain_editable_and_preserve_services(self):
        order = self.create_order()
        charge_ids = list(order.charges.values_list("pk", flat=True))
        for action, status in [
            ("submit", "in_progress"),
            ("complete", "complete"),
            ("reopen", "in_progress"),
            ("return_to_draft", "draft"),
            ("submit", "in_progress"),
            ("cancel", "cancelled"),
            ("restore_to_draft", "draft"),
        ]:
            with self.subTest(status=status):
                data = self.edit_payload(order)
                data["action"] = action
                data["assigned_to"] = str(self.worker.pk)
                response = self.client.post(
                    reverse("edit_order", args=[order.pk]), data
                )
                self.assertRedirects(response, reverse("edit_order", args=[order.pk]))
                order.refresh_from_db()
                self.assertEqual(order.status, status)
                self.assertEqual(order.total, Decimal("99.40"))
                self.assertEqual(
                    list(order.charges.values_list("pk", flat=True)), charge_ids
                )
                self.assertEqual(
                    order.payment_status, ServiceOrder.PaymentStatus.UNPAID
                )
                self.assertFalse(order.collected)

    def test_collection_and_payment_can_change_independently_on_complete_order(self):
        data = self.payload()
        data["status"] = ServiceOrder.Status.COMPLETE
        data["assigned_to"] = str(self.worker.pk)
        order = self.create_order(data)
        for paid, collected in [
            ("paid", False),
            ("paid", True),
            ("unpaid", True),
            ("unpaid", False),
        ]:
            with self.subTest(paid=paid, collected=collected):
                data = self.edit_payload(order)
                data["payment_status"] = paid
                if collected:
                    data["collected"] = "on"
                else:
                    data.pop("collected", None)
                self.assertEqual(
                    self.client.post(
                        reverse("edit_order", args=[order.pk]), data
                    ).status_code,
                    302,
                )
                order.refresh_from_db()
                self.assertEqual(order.status, ServiceOrder.Status.COMPLETE)
                self.assertEqual(order.payment_status, paid)
                self.assertEqual(order.collected, collected)

    def test_status_changes_preserve_paid_and_collected_flags(self):
        data = self.payload()
        data.update(
            {
                "payment_status": "paid",
                "collected": "on",
                "assigned_to": str(self.worker.pk),
            }
        )
        order = self.create_order(dict(data, status="complete"))
        for action, status in [
            ("reopen", "in_progress"),
            ("cancel", "cancelled"),
            ("restore_to_draft", "draft"),
            ("submit", "in_progress"),
            ("complete", "complete"),
        ]:
            data = self.edit_payload(order)
            data["action"] = action
            self.assertEqual(
                self.client.post(
                    reverse("edit_order", args=[order.pk]), data
                ).status_code,
                302,
            )
            order.refresh_from_db()
            self.assertTrue(order.collected)
            self.assertEqual(order.payment_status, ServiceOrder.PaymentStatus.PAID)
            self.assertEqual(order.status, status)

    def test_refunded_can_be_saved_without_changing_order_work_or_charges(self):
        for status in ("in_progress", "complete"):
            with self.subTest(status=status):
                order = self.create_order(
                    dict(
                        self.payload(),
                        status=status,
                        assigned_to=str(self.worker.pk),
                        payment_status="paid",
                        collected="on",
                    )
                )
                charges = list(order.charges.values())
                data = self.workflow_payload(order, payment_status="refunded")
                self.assertEqual(
                    self.client.post(
                        reverse("edit_order", args=[order.pk]), data
                    ).status_code,
                    302,
                )
                order.refresh_from_db()
                self.assertEqual(
                    order.payment_status, ServiceOrder.PaymentStatus.REFUNDED
                )
                self.assertEqual(order.status, status)
                self.assertTrue(order.collected)
                self.assertEqual(order.assigned_to, self.worker)
                self.assertEqual(order.notes, "Call before collection")
                self.assertEqual(order.currency, "ZAR")
                self.assertEqual(order.total, Decimal("99.40"))
                self.assertEqual(list(order.charges.values()), charges)
                response = self.client.get(reverse("edit_order", args=[order.pk]))
                self.assertContains(
                    response,
                    '<option value="refunded" selected>Refunded</option>',
                    html=True,
                )

    def test_refunded_orders_have_a_list_badge_and_can_be_filtered(self):
        refunded = self.create_order(
            dict(
                self.payload(),
                status="complete",
                payment_status="refunded",
                assigned_to=str(self.worker.pk),
            )
        )
        cancelled = self.create_order(
            dict(self.payload(), status="cancelled", payment_status="refunded")
        )
        self.create_order(
            dict(self.payload(), status="in_progress", payment_status="paid")
        )
        self.create_order()
        response = self.client.get(reverse("orders"), {"payment_status": "refunded"})
        self.assertEqual(
            {order.pk for order in response.context["page_obj"]},
            {refunded.pk, cancelled.pk},
        )
        self.assertContains(
            response,
            'class="role-badge order-payment-refunded">Refunded</span>',
            count=2,
        )
        self.assertContains(
            response, '<option value="refunded" selected>Refunded</option>', html=True
        )
        response = self.client.get(
            reverse("orders"), {"payment_status": "refunded", "status": "complete"}
        )
        self.assertEqual(
            {order.pk for order in response.context["page_obj"]}, {refunded.pk}
        )

    def test_refunded_status_obeys_draft_and_cancelled_field_locks(self):
        for status in ("draft", "cancelled"):
            for payment_status in ServiceOrder.PaymentStatus.values:
                with self.subTest(status=status, payment_status=payment_status):
                    order = self.create_order(
                        dict(
                            self.payload(), status=status, payment_status=payment_status
                        )
                    )
                    data = self.edit_payload(order)
                    data["payment_status"] = (
                        "unpaid" if payment_status == "refunded" else "refunded"
                    )
                    self.assertEqual(
                        self.client.post(
                            reverse("edit_order", args=[order.pk]), data
                        ).status_code,
                        302,
                    )
                    order.refresh_from_db()
                    self.assertEqual(order.payment_status, payment_status)
                    self.assertEqual(order.status, status)

    def test_invalid_order_and_payment_statuses_are_rejected(self):
        for field, value in [
            ("status", "closed"),
            ("status", "completed"),
        ]:
            data = self.payload()
            data[field] = value
            response = self.client.post(reverse("create_order"), data)
            self.assertEqual(response.status_code, 200)
            self.assertIn(
                field if field == "payment_status" else "__all__",
                response.context["editor"].form.errors,
            )
            self.assertFalse(ServiceOrder.objects.exists())

    def test_workflow_changes_require_order_change_permission(self):
        order = self.create_order()
        data = self.edit_payload(order)
        data.update({"action": "complete", "payment_status": "paid", "collected": "on"})
        reader = get_user_model().objects.create_user(username="order_reader")
        reader.user_permissions.add(
            Permission.objects.get(codename="view_serviceorder")
        )
        self.client.force_login(reader)
        response = self.client.post(reverse("edit_order", args=[order.pk]), data)
        self.assertEqual(response.status_code, 403)
        order.refresh_from_db()
        self.assertEqual(order.status, ServiceOrder.Status.DRAFT)
        self.assertEqual(order.payment_status, ServiceOrder.PaymentStatus.UNPAID)
        self.assertFalse(order.collected)

    def test_stale_edit_cannot_overwrite_new_workflow_values(self):
        order = self.create_order()
        stale = self.edit_payload(order)
        current = self.edit_payload(order)
        current.update(
            {"action": "submit", "payment_status": "paid", "collected": "on"}
        )
        self.assertEqual(
            self.client.post(
                reverse("edit_order", args=[order.pk]), current
            ).status_code,
            302,
        )
        stale["action"] = "complete"
        stale["assigned_to"] = str(self.worker.pk)
        response = self.client.post(reverse("edit_order", args=[order.pk]), stale)
        self.assertContains(response, "changed while you were editing")
        order.refresh_from_db()
        self.assertEqual(order.status, ServiceOrder.Status.IN_PROGRESS)
        self.assertEqual(order.payment_status, ServiceOrder.PaymentStatus.UNPAID)
        self.assertFalse(order.collected)
        self.assertEqual(order.revision, 2)

    def test_workflow_filters_can_be_used_separately_or_together(self):
        first = self.create_order(
            dict(self.payload(), status="complete", assigned_to=str(self.worker.pk))
        )
        second = self.create_order(
            dict(
                self.payload(),
                status="complete",
                payment_status="paid",
                collected="on",
                assigned_to=str(self.worker.pk),
            )
        )
        third = self.create_order(dict(self.payload(), status="in_progress"))
        cases = [
            ({"status": "complete"}, {first.pk, second.pk}),
            ({"payment_status": "unpaid"}, {first.pk, third.pk}),
            ({"collected": "no"}, {first.pk, third.pk}),
            ({"collected": "yes"}, {second.pk}),
            (
                {"status": "complete", "payment_status": "unpaid", "collected": "no"},
                {first.pk},
            ),
            (
                {
                    "q": self.customer.email,
                    "payment_status": "paid",
                    "collected": "yes",
                },
                {second.pk},
            ),
            ({"status": "cancelled"}, set()),
        ]
        for filters, expected in cases:
            with self.subTest(filters=filters):
                response = self.client.get(reverse("orders"), filters)
                self.assertEqual(
                    {order.pk for order in response.context["page_obj"]}, expected
                )
        response = self.client.get(reverse("orders"))
        self.assertContains(response, "In Progress")
        self.assertContains(response, "Payment status")
        self.assertContains(response, "Collected")

    def test_invalid_list_filters_show_errors_instead_of_unfiltered_records(self):
        self.create_order()
        for filters in [
            {"status": "closed"},
            {"payment_status": "partial"},
            {"collected": "maybe"},
        ]:
            response = self.client.get(reverse("orders"), filters)
            self.assertTrue(response.context["filter_form"].errors)
            self.assertEqual(response.context["page_obj"].paginator.count, 0)

    def test_pagination_retains_all_workflow_filters(self):
        ServiceOrder.objects.bulk_create(
            [
                ServiceOrder(
                    customer=self.customer,
                    currency="ZAR",
                    status="complete",
                    collected=True,
                )
                for _ in range(26)
            ]
        )
        filters = {
            "status": "complete",
            "payment_status": "unpaid",
            "collected": "yes",
            "q": "Alex",
        }
        response = self.client.get(reverse("orders"), filters)
        self.assertEqual(response.context["page_obj"].paginator.count, 26)
        for query_part in [
            "status=complete",
            "payment_status=unpaid",
            "collected=yes",
            "q=Alex",
            "page=2",
        ]:
            self.assertContains(response, query_part)
        response = self.client.get(reverse("orders"), dict(filters, page=2))
        self.assertEqual(response.context["page_obj"].number, 2)
        self.assertEqual(len(response.context["page_obj"]), 1)

    def test_submit_draft_saves_changes_and_locks_order(self):
        order = self.create_order()
        data = self.edit_payload(order)
        data.update(
            {
                "action": "submit",
                "notes": "Instructions before submission",
                "items-0-services-0-quantity": "3",
                "items-0-due_time": "16:30",
            }
        )
        self.assertRedirects(
            self.client.post(reverse("edit_order", args=[order.pk]), data),
            reverse("edit_order", args=[order.pk]),
        )
        order.refresh_from_db()
        self.assertEqual(order.status, ServiceOrder.Status.IN_PROGRESS)
        self.assertIsNone(order.assigned_to)
        self.assertEqual(order.notes, "Instructions before submission")
        self.assertEqual(order.items.get().due_time, time(16, 30))
        self.assertEqual(order.total, Decimal("111.75"))
        response = self.client.get(reverse("edit_order", args=[order.pk]))
        self.assertTrue(response.context["editor"].locked)
        self.assertContains(response, 'data-order-locked="true"')
        self.assertFalse(response.context["editor"].form.fields["notes"].disabled)
        self.assertFalse(response.context["editor"].form.fields["assigned_to"].disabled)
        self.assertNotContains(response, 'name="action" value="submit"')

    def test_draft_submission_does_not_accept_assignment(self):
        data = dict(self.payload(), action="submit", assigned_to=str(self.worker.pk))
        order = self.create_order(data)
        self.assertEqual(order.status, ServiceOrder.Status.IN_PROGRESS)
        self.assertIsNone(order.assigned_to)

    def test_invalid_draft_cannot_be_submitted(self):
        order = self.create_order()
        data = self.edit_payload(order)
        data.update(
            {
                "action": "submit",
                "notes": "Do not save",
                "items-0-due_date": "",
            }
        )
        response = self.client.post(reverse("edit_order", args=[order.pk]), data)
        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, ServiceOrder.Status.DRAFT)
        self.assertEqual(order.revision, 1)
        self.assertEqual(order.notes, "Call before collection")

    def test_completion_requires_assignment_and_accepts_it_in_same_save(self):
        order = self.create_order(dict(self.payload(), status="in_progress"))
        data = self.workflow_payload(order, action="complete")
        response = self.client.post(reverse("edit_order", args=[order.pk]), data)
        self.assertContains(
            response, "Assign a user before marking the order Complete."
        )
        order.refresh_from_db()
        self.assertEqual(order.status, ServiceOrder.Status.IN_PROGRESS)
        self.assertEqual(order.revision, 1)
        data["assigned_to"] = str(self.worker.pk)
        self.assertEqual(
            self.client.post(reverse("edit_order", args=[order.pk]), data).status_code,
            302,
        )
        order.refresh_from_db()
        self.assertEqual(order.status, ServiceOrder.Status.COMPLETE)
        self.assertEqual(order.assigned_to, self.worker)
        self.assertEqual(order.total, Decimal("99.40"))

    def test_completed_order_cannot_clear_its_assigned_user(self):
        order = self.create_order(
            dict(self.payload(), status="complete", assigned_to=str(self.worker.pk))
        )
        data = self.workflow_payload(order, assigned_to="")
        response = self.client.post(reverse("edit_order", args=[order.pk]), data)
        self.assertContains(
            response, "Assign a user before marking the order Complete."
        )
        order.refresh_from_db()
        self.assertEqual(order.assigned_to, self.worker)
        self.assertEqual(order.revision, 1)

    def test_complete_and_cancelled_orders_preserve_their_locked_details(self):
        for status in [
            ServiceOrder.Status.COMPLETE,
            ServiceOrder.Status.CANCELLED,
        ]:
            with self.subTest(status=status):
                order = self.create_order(
                    dict(self.payload(), status=status, assigned_to=str(self.worker.pk))
                )
                original_item = order.items.get()
                original_charges = list(
                    order.charges.values_list("pk", "quantity", "unit_price", "notes")
                )
                data = self.edit_payload(order)
                data.update(
                    {
                        "customer_mode": "new",
                        "customer-first_name": "Forged customer",
                        "notes": "Updated order notes",
                        "items-0-DELETE": "on",
                        "items-0-notes": "Forged item notes",
                        "items-0-due_date": "2027-01-01",
                        "items-0-due_time": "18:45",
                        "items-0-services-0-quantity": "999",
                        "general-0-notes": "Forged service note",
                        "payment_status": "paid",
                        "collected": "on",
                    }
                )
                self.assertEqual(
                    self.client.post(
                        reverse("edit_order", args=[order.pk]), data
                    ).status_code,
                    302,
                )
                order.refresh_from_db()
                original_item.refresh_from_db()
                self.assertEqual(order.customer, self.customer)
                self.assertFalse(
                    Customer.objects.filter(first_name="Forged customer").exists()
                )
                self.assertEqual(
                    order.notes,
                    (
                        "Updated order notes"
                        if status == "cancelled"
                        else "Call before collection"
                    ),
                )
                self.assertEqual(original_item.notes, "Keep the original ribbons")
                self.assertEqual(original_item.due_date, date(2026, 11, 20))
                self.assertIsNone(original_item.due_time)
                self.assertEqual(
                    list(
                        order.charges.values_list(
                            "pk", "quantity", "unit_price", "notes"
                        )
                    ),
                    original_charges,
                )
                self.assertEqual(
                    order.payment_status,
                    (
                        ServiceOrder.PaymentStatus.PAID
                        if status == "complete"
                        else ServiceOrder.PaymentStatus.UNPAID
                    ),
                )
                self.assertEqual(
                    order.collected, status == ServiceOrder.Status.COMPLETE
                )

    def test_return_to_draft_unlocks_details_on_the_next_request(self):
        order = self.create_order(dict(self.payload(), status="in_progress"))
        data = self.workflow_payload(
            order, action="return_to_draft", notes="Updated during unlock"
        )
        self.assertEqual(
            self.client.post(reverse("edit_order", args=[order.pk]), data).status_code,
            302,
        )
        order.refresh_from_db()
        self.assertEqual(order.status, ServiceOrder.Status.DRAFT)
        self.assertEqual(order.notes, "Updated during unlock")
        response = self.client.get(reverse("edit_order", args=[order.pk]))
        self.assertFalse(response.context["editor"].locked)
        self.assertFalse(response.context["editor"].form.fields["notes"].disabled)
        self.assertContains(response, 'name="action" value="submit"')
        data = self.edit_payload(order)
        data.update(
            {"notes": "Edited after reopening", "items-0-services-0-quantity": "3"}
        )
        self.assertEqual(
            self.client.post(reverse("edit_order", args=[order.pk]), data).status_code,
            302,
        )
        order.refresh_from_db()
        self.assertEqual(order.notes, "Edited after reopening")
        self.assertEqual(order.total, Decimal("111.75"))

    def test_stale_draft_cannot_overwrite_a_submitted_order(self):
        order = self.create_order()
        stale = self.edit_payload(order)
        submitted = self.edit_payload(order)
        submitted["action"] = "submit"
        self.assertEqual(
            self.client.post(
                reverse("edit_order", args=[order.pk]), submitted
            ).status_code,
            302,
        )
        stale["notes"] = "Outdated edits"
        response = self.client.post(reverse("edit_order", args=[order.pk]), stale)
        self.assertContains(response, "changed while you were editing")
        order.refresh_from_db()
        self.assertEqual(order.status, ServiceOrder.Status.IN_PROGRESS)
        self.assertEqual(order.notes, "Call before collection")
        self.assertEqual(order.revision, 2)

    def test_locked_order_keeps_captured_services_after_catalog_links_change(self):
        order = self.create_order(dict(self.payload(), status="in_progress"))
        self.service.products.set([self.other_product])
        response = self.client.get(reverse("edit_order", args=[order.pk]))
        charge_form = response.context["editor"].items.forms[0].services.forms[0]
        self.assertTrue(
            charge_form.fields["service"].queryset.filter(pk=self.service.pk).exists()
        )
        data = self.workflow_payload(order, payment_status="paid")
        self.assertEqual(
            self.client.post(reverse("edit_order", args=[order.pk]), data).status_code,
            302,
        )
        order.refresh_from_db()
        self.assertEqual(order.total, Decimal("99.40"))
        self.assertEqual(order.notes, "Call before collection")

    def test_in_progress_deadlines_and_all_internal_notes_can_change_without_repricing(
        self,
    ):
        order = self.create_order(dict(self.payload(), status="in_progress"))
        before = list(
            order.charges.values_list("pk", "service_id", "quantity", "unit_price")
        )
        self.service.price = Decimal("999.00")
        self.service.save(update_fields=["price"])
        self.service.products.set([self.other_product])
        data = self.edit_payload(order)
        data.update(
            {
                "notes": "Customer requested a later collection",
                "items-0-due_date": "2026-12-02",
                "items-0-due_time": "17:15",
                "items-0-notes": "New item instructions",
                "items-0-services-0-notes": "Updated first occurrence",
                "items-0-services-1-notes": "Updated second occurrence",
                "general-0-notes": "Updated extra instructions",
                "customer": "999999",
                "customer_mode": "new",
                "customer-first_name": "Not a new customer",
                "items-0-product": str(self.other_product.pk),
                "items-0-DELETE": "on",
                "items-0-services-0-service": str(self.other_service.pk),
                "items-0-services-0-quantity": "999",
                "items-0-services-0-unit_price": "0.01",
                "items-0-services-0-DELETE": "on",
                "general-0-quantity": "999",
                "general-0-DELETE": "on",
                "items-TOTAL_FORMS": "0",
                "general-TOTAL_FORMS": "0",
            }
        )
        self.assertEqual(
            self.client.post(reverse("edit_order", args=[order.pk]), data).status_code,
            302,
        )
        order.refresh_from_db()
        item = order.items.get()
        self.assertEqual(order.status, "in_progress")
        self.assertEqual(order.customer, self.customer)
        self.assertFalse(
            Customer.objects.filter(first_name="Not a new customer").exists()
        )
        self.assertEqual(order.notes, "Customer requested a later collection")
        self.assertEqual(item.product, self.product)
        self.assertEqual(item.due_date, date(2026, 12, 2))
        self.assertEqual(item.due_time, time(17, 15))
        self.assertEqual(item.notes, "New item instructions")
        self.assertEqual(
            list(
                order.charges.values_list("pk", "service_id", "quantity", "unit_price")
            ),
            before,
        )
        self.assertEqual(
            list(item.charges.values_list("notes", flat=True)),
            ["Updated first occurrence", "Updated second occurrence"],
        )
        self.assertEqual(
            order.charges.get(item__isnull=True).notes, "Updated extra instructions"
        )
        self.assertEqual(order.total, Decimal("99.40"))

    def test_in_progress_optional_time_and_notes_can_be_cleared(self):
        order = self.create_order(
            dict(self.payload(), status="in_progress", **{"items-0-due_time": "09:00"})
        )
        data = self.workflow_payload(order)
        data.update(
            {
                "notes": "",
                "items-0-due_time": "",
                "items-0-notes": "",
                "items-0-services-0-notes": "",
                "general-0-notes": "",
            }
        )
        self.assertEqual(
            self.client.post(reverse("edit_order", args=[order.pk]), data).status_code,
            302,
        )
        order.refresh_from_db()
        self.assertEqual(order.notes, "")
        item = order.items.get()
        self.assertIsNone(item.due_time)
        self.assertEqual(item.due_date, date(2026, 11, 20))
        self.assertEqual(item.notes, "")
        self.assertEqual(
            list(item.charges.values_list("notes", flat=True)), ["", "Right side"]
        )
        self.assertEqual(order.charges.get(item__isnull=True).notes, "")

    def test_invalid_in_progress_deadline_prevents_all_changes_and_completion(self):
        order = self.create_order(dict(self.payload(), status="in_progress"))
        for changes, field in [
            ({"items-0-due_date": ""}, "due_date"),
            ({"items-0-due_date": "bad-date"}, "due_date"),
            ({"items-0-due_time": "25:75"}, "due_time"),
        ]:
            with self.subTest(changes=changes):
                data = self.workflow_payload(
                    order,
                    action="complete",
                    assigned_to=str(self.worker.pk),
                    payment_status="paid",
                    notes="Do not save this",
                )
                data.update(changes)
                data["general-0-notes"] = "Do not save this either"
                response = self.client.post(
                    reverse("edit_order", args=[order.pk]), data
                )
                self.assertEqual(response.status_code, 200)
                editor = response.context["editor"]
                self.assertIn(field, editor.items.forms[0].detail_form.errors)
                self.assertContains(response, "Check the fields below")
                order.refresh_from_db()
                self.assertEqual(order.status, "in_progress")
                self.assertEqual(order.revision, 1)
                self.assertIsNone(order.assigned_to)
                self.assertEqual(order.payment_status, "unpaid")
                self.assertEqual(order.notes, "Call before collection")
                self.assertEqual(
                    order.charges.get(item__isnull=True).notes, "Prioritize this job"
                )

    def test_in_progress_details_save_with_completion_then_lock_until_reopened(self):
        order = self.create_order(dict(self.payload(), status="in_progress"))
        data = self.workflow_payload(
            order,
            action="complete",
            assigned_to=str(self.worker.pk),
            notes="Final work instructions",
        )
        data.update(
            {"items-0-due_date": "2026-12-03", "items-0-notes": "Final item note"}
        )
        self.assertEqual(
            self.client.post(reverse("edit_order", args=[order.pk]), data).status_code,
            302,
        )
        order.refresh_from_db()
        self.assertEqual(order.status, "complete")
        self.assertEqual(order.notes, "Final work instructions")
        data = self.workflow_payload(
            order, action="reopen", notes="Ignored until reopened"
        )
        data["items-0-due_date"] = "2027-01-01"
        self.assertEqual(
            self.client.post(reverse("edit_order", args=[order.pk]), data).status_code,
            302,
        )
        order.refresh_from_db()
        self.assertEqual(order.status, "in_progress")
        self.assertEqual(order.notes, "Final work instructions")
        self.assertEqual(order.items.get().due_date, date(2026, 12, 3))

    def test_stale_in_progress_details_cannot_overwrite_newer_edits(self):
        order = self.create_order(dict(self.payload(), status="in_progress"))
        stale = self.edit_payload(order)
        current = self.edit_payload(order)
        current.update(
            {
                "notes": "Latest notes",
                "items-0-due_date": "2026-12-04",
                "general-0-notes": "Latest extra note",
            }
        )
        self.assertEqual(
            self.client.post(
                reverse("edit_order", args=[order.pk]), current
            ).status_code,
            302,
        )
        response = self.client.post(reverse("edit_order", args=[order.pk]), stale)
        self.assertContains(response, "changed while you were editing")
        order.refresh_from_db()
        self.assertEqual(order.notes, "Latest notes")
        self.assertEqual(order.items.get().due_date, date(2026, 12, 4))
        self.assertEqual(
            order.charges.get(item__isnull=True).notes, "Latest extra note"
        )
        self.assertEqual(order.revision, 2)

    def test_in_progress_detail_posts_cannot_add_or_edit_other_orders_rows(self):
        order = self.create_order(dict(self.payload(), status="in_progress"))
        other = self.create_order(dict(self.payload(), status="in_progress"))
        data = self.workflow_payload(order)
        data.update(
            {
                "items-TOTAL_FORMS": "2",
                "items-0-id": str(other.items.get().pk),
                "items-0-notes": "This order only",
                "items-1-product": str(self.other_product.pk),
                "items-1-due_date": "2026-12-01",
                "items-1-notes": "Do not add",
                "items-0-services-TOTAL_FORMS": "3",
                "items-0-services-0-id": str(
                    other.charges.filter(item__isnull=False).first().pk
                ),
                "items-0-services-0-notes": "This service only",
                "items-0-services-2-service": str(self.service.pk),
                "items-0-services-2-quantity": "10",
                "general-TOTAL_FORMS": "2",
                "general-1-service": str(self.global_service.pk),
                "general-1-quantity": "10",
            }
        )
        self.assertEqual(
            self.client.post(reverse("edit_order", args=[order.pk]), data).status_code,
            302,
        )
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.charges.count(), 3)
        self.assertEqual(order.items.get().notes, "This order only")
        self.assertEqual(
            order.charges.filter(item__isnull=False).first().notes, "This service only"
        )
        self.assertEqual(other.items.get().notes, "Keep the original ribbons")
        self.assertEqual(
            other.charges.filter(item__isnull=False).first().notes, "Left side"
        )

    def test_in_progress_form_unlocks_only_deadlines_and_notes(self):
        class ControlParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.fieldsets = []
                self.disabled = {}

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == "fieldset":
                    self.fieldsets.append("disabled" in attrs)
                if tag in ("input", "select", "textarea") and "name" in attrs:
                    self.disabled[attrs["name"]] = "disabled" in attrs or any(
                        self.fieldsets
                    )

            def handle_endtag(self, tag):
                if tag == "fieldset":
                    self.fieldsets.pop()

        order = self.create_order(dict(self.payload(), status="in_progress"))
        response = self.client.get(reverse("edit_order", args=[order.pk]))
        editor = response.context["editor"]
        self.assertTrue(editor.details_editable)
        self.assertTrue(editor.form.fields["customer"].disabled)
        self.assertFalse(editor.form.fields["notes"].disabled)
        item = editor.items.forms[0]
        self.assertTrue(item.fields["product"].disabled)
        for field in ("due_date", "due_time", "notes"):
            self.assertFalse(item.detail_form.fields[field].disabled)
        charge = item.services.forms[0]
        self.assertTrue(charge.fields["service"].disabled)
        self.assertTrue(charge.fields["quantity"].disabled)
        self.assertFalse(charge.detail_form.fields["notes"].disabled)
        self.assertFalse(editor.general.forms[0].detail_form.fields["notes"].disabled)
        self.assertContains(response, "data-add-item disabled")
        self.assertContains(response, "data-remove-item disabled")
        self.assertContains(response, "data-add-charge disabled")
        self.assertContains(response, "data-remove-charge disabled")
        # Each editable control is rendered once, outside disabled fieldsets.
        for name in (
            "items-0-due_date",
            "items-0-due_time",
            "items-0-notes",
            "items-0-services-0-notes",
            "general-0-notes",
        ):
            self.assertContains(response, f'name="{name}"', count=1)
        controls = ControlParser()
        controls.feed(response.content.decode())
        for name in (
            "notes",
            "items-0-due_date",
            "items-0-due_time",
            "items-0-notes",
            "items-0-services-0-notes",
            "general-0-notes",
        ):
            self.assertFalse(controls.disabled[name], name)
        for name in (
            "items-0-product",
            "items-0-services-0-service",
            "items-0-services-0-quantity",
            "general-0-service",
            "general-0-quantity",
        ):
            self.assertTrue(controls.disabled[name], name)

    def test_invalid_submit_transition_is_rejected(self):
        data = dict(self.payload(), action="closed")
        response = self.client.post(reverse("create_order"), data)
        self.assertEqual(response.status_code, 200)
        self.assertIn("__all__", response.context["editor"].form.errors)
        self.assertFalse(ServiceOrder.objects.exists())

    def test_only_the_current_stage_action_buttons_are_displayed(self):
        expected = {
            "draft": {"save", "submit", "delete_draft"},
            "in_progress": {"save", "complete", "cancel", "return_to_draft"},
            "complete": {"save", "reopen"},
            "cancelled": {"save", "restore_to_draft"},
        }
        for status, actions in expected.items():
            with self.subTest(status=status):
                order = self.create_order(
                    dict(self.payload(), status=status, assigned_to=str(self.worker.pk))
                )
                response = self.client.get(reverse("edit_order", args=[order.pk]))
                html = response.content.decode()
                self.assertContains(response, "data-order-confirmation", count=1)
                self.assertContains(
                    response, 'aria-describedby="order-confirm-message"'
                )
                self.assertContains(response, "crm/js/order-confirmation.js")
                self.assertEqual(
                    set(re.findall(r'name="action" value="([^"]+)"', html)), actions
                )
                for button in re.findall(r'<button[^>]*name="action"[^>]*>', html):
                    if 'value="save"' in button:
                        self.assertNotIn("data-confirm", button)
                    else:
                        self.assertIn('data-confirm="Are you sure you wish to ', button)
                self.assertNotContains(response, "order-status-banner")
                self.assertContains(
                    response, f"order-status-badge order-state order-state-{status}"
                )
                self.assertContains(response, "ZAR 99.40", count=2)
                self.assertNotContains(response, 'name="status"')
                self.assertNotContains(response, 'type="radio"')

    def test_actions_from_other_stages_are_rejected_without_changes(self):
        invalid = {
            "draft": [
                "cancel",
                "complete",
                "reopen",
                "return_to_draft",
                "restore_to_draft",
            ],
            "in_progress": ["submit", "reopen", "restore_to_draft"],
            "complete": [
                "submit",
                "complete",
                "cancel",
                "return_to_draft",
                "restore_to_draft",
            ],
            "cancelled": ["submit", "complete", "cancel", "reopen", "return_to_draft"],
        }
        for status, actions in invalid.items():
            order = self.create_order(
                dict(
                    self.payload(),
                    status=status,
                    assigned_to=str(self.worker.pk),
                    payment_status="paid",
                    collected="on",
                )
            )
            for action in actions:
                with self.subTest(status=status, action=action):
                    data = self.edit_payload(order)
                    data.update({"action": action, "payment_status": "unpaid"})
                    data.pop("collected", None)
                    response = self.client.post(
                        reverse("edit_order", args=[order.pk]), data
                    )
                    self.assertContains(
                        response,
                        "This action is not available for the current order status.",
                    )
                    order.refresh_from_db()
                    self.assertEqual(order.status, status)
                    self.assertEqual(order.revision, 1)
                    self.assertEqual(
                        order.payment_status, ServiceOrder.PaymentStatus.PAID
                    )
                    self.assertTrue(order.collected)
                    self.assertEqual(order.total, Decimal("99.40"))

    def test_direct_status_values_cannot_bypass_the_action_buttons(self):
        for source, target in [
            ("draft", "in_progress"),
            ("in_progress", "complete"),
            ("complete", "draft"),
            ("cancelled", "in_progress"),
        ]:
            order = self.create_order(
                dict(self.payload(), status=source, assigned_to=str(self.worker.pk))
            )
            data = self.edit_payload(order)
            data.update({"status": target, "action": "save"})
            response = self.client.post(reverse("edit_order", args=[order.pk]), data)
            self.assertContains(
                response, "Use the order action buttons to change the status."
            )
            order.refresh_from_db()
            self.assertEqual(order.status, source)
            self.assertEqual(order.revision, 1)

    def test_old_transition_parameter_is_rejected(self):
        order = self.create_order()
        data = self.edit_payload(order)
        data["transition"] = "in_progress"
        response = self.client.post(reverse("edit_order", args=[order.pk]), data)
        self.assertContains(
            response, "Use the order action buttons to change the status."
        )
        order.refresh_from_db()
        self.assertEqual(order.status, ServiceOrder.Status.DRAFT)
        self.assertEqual(order.revision, 1)

    def test_duplicate_submit_does_not_repeat_the_transition(self):
        order = self.create_order()
        data = self.edit_payload(order)
        data["action"] = "submit"
        self.assertEqual(
            self.client.post(reverse("edit_order", args=[order.pk]), data).status_code,
            302,
        )
        response = self.client.post(reverse("edit_order", args=[order.pk]), data)
        self.assertContains(
            response, "This action is not available for the current order status."
        )
        order.refresh_from_db()
        self.assertEqual(order.status, ServiceOrder.Status.IN_PROGRESS)
        self.assertEqual(order.revision, 2)
        self.assertEqual(order.charges.count(), 3)

    def test_workflow_fields_have_stage_specific_ui_locks(self):
        for status in ServiceOrder.Status.values:
            order = self.create_order(
                dict(self.payload(), status=status, assigned_to=str(self.worker.pk))
            )
            response = self.client.get(reverse("edit_order", args=[order.pk]))
            fields = response.context["editor"].form.fields
            self.assertEqual(
                fields["assigned_to"].disabled, status in ("draft", "cancelled")
            )
            self.assertEqual(
                fields["payment_status"].disabled, status in ("draft", "cancelled")
            )
            self.assertEqual(fields["collected"].disabled, status != "complete")
            self.assertEqual(fields["notes"].disabled, status == "complete")
            assign_button = re.search(
                r"<button[^>]*data-assign-to-me[^>]*>", response.content.decode()
            ).group()
            self.assertEqual(
                " disabled" in assign_button, status in ("draft", "cancelled")
            )

    def test_draft_workflow_edits_are_ignored_on_save_and_submit(self):
        for action in ["save", "submit"]:
            order = self.create_order()
            data = self.edit_payload(order)
            data.update(
                {
                    "action": action,
                    "assigned_to": str(self.worker.pk),
                    "payment_status": "paid",
                    "collected": "on",
                    "notes": "Editable draft notes",
                }
            )
            self.assertEqual(
                self.client.post(
                    reverse("edit_order", args=[order.pk]), data
                ).status_code,
                302,
            )
            order.refresh_from_db()
            self.assertIsNone(order.assigned_to)
            self.assertEqual(order.payment_status, ServiceOrder.PaymentStatus.UNPAID)
            self.assertFalse(order.collected)
            self.assertEqual(order.notes, "Editable draft notes")
            self.assertEqual(
                order.status, "draft" if action == "save" else "in_progress"
            )

    def test_cancelled_order_form_only_allows_order_notes(self):
        order = self.create_order(dict(self.payload(), status="cancelled"))
        response = self.client.get(reverse("edit_order", args=[order.pk]))
        editor = response.context["editor"]
        for name in (
            "customer",
            "customer_mode",
            "assigned_to",
            "payment_status",
            "collected",
        ):
            self.assertTrue(editor.form.fields[name].disabled, name)
        self.assertFalse(editor.form.fields["notes"].disabled)
        self.assertFalse(editor.details_editable)
        for item_form in editor.items:
            self.assertTrue(all(field.disabled for field in item_form.fields.values()))
            for charge_form in item_form.services:
                self.assertTrue(
                    all(field.disabled for field in charge_form.fields.values())
                )
        for charge_form in editor.general:
            self.assertTrue(
                all(field.disabled for field in charge_form.fields.values())
            )
        self.assertContains(response, "Save notes", count=2)
        self.assertContains(response, "Only Order Notes can be updated.")
        self.assertContains(
            response, "Add a cancellation reason or other internal notes."
        )
        self.assertContains(response, 'name="action" value="restore_to_draft"', count=2)

    def test_cancelled_notes_save_and_restore_ignore_all_other_field_changes(self):
        for action in ("save", "restore_to_draft"):
            with self.subTest(action=action):
                order = self.create_order(
                    dict(
                        self.payload(),
                        status="cancelled",
                        assigned_to=str(self.worker.pk),
                        payment_status="paid",
                        collected="on",
                    )
                )
                original_item = dict(order.items.values().get())
                original_charges = list(order.charges.values())
                data = self.edit_payload(order)
                data.update(
                    {
                        "action": action,
                        "notes": "Cancelled at the customer's request",
                        "customer_mode": "new",
                        "customer": "999999",
                        "customer-first_name": "Do not create",
                        "assigned_to": str(self.user.pk),
                        "payment_status": "unpaid",
                        "items-0-product": str(self.other_product.pk),
                        "items-0-due_date": "2027-01-01",
                        "items-0-due_time": "15:45",
                        "items-0-notes": "Do not change item notes",
                        "items-0-DELETE": "on",
                        "items-0-services-0-service": str(self.other_service.pk),
                        "items-0-services-0-quantity": "999",
                        "items-0-services-0-unit_price": "0.01",
                        "items-0-services-0-notes": "Do not change service notes",
                        "general-0-notes": "Do not change extra notes",
                        "general-0-DELETE": "on",
                        "items-TOTAL_FORMS": "0",
                    }
                )
                data.pop("collected")
                response = self.client.post(
                    reverse("edit_order", args=[order.pk]), data
                )
                self.assertEqual(response.status_code, 302)
                order.refresh_from_db()
                self.assertEqual(order.notes, "Cancelled at the customer's request")
                self.assertEqual(
                    order.status, "cancelled" if action == "save" else "draft"
                )
                self.assertEqual(order.assigned_to, self.worker)
                self.assertEqual(order.payment_status, "paid")
                self.assertTrue(order.collected)
                self.assertEqual(order.customer, self.customer)
                self.assertFalse(
                    Customer.objects.filter(first_name="Do not create").exists()
                )
                self.assertEqual(dict(order.items.values().get()), original_item)
                self.assertEqual(list(order.charges.values()), original_charges)
                self.assertEqual(order.total, Decimal("99.40"))

    def test_cancelled_order_preserves_omitted_notes_and_allows_clearing(self):
        order = self.create_order(dict(self.payload(), status="cancelled"))
        for changes, expected in [({}, "Call before collection"), ({"notes": ""}, "")]:
            data = self.workflow_payload(order, **changes)
            self.assertEqual(
                self.client.post(
                    reverse("edit_order", args=[order.pk]), data
                ).status_code,
                302,
            )
            order.refresh_from_db()
            self.assertEqual(order.notes, expected)
            self.assertEqual(order.status, "cancelled")

    def test_stale_cancelled_order_notes_cannot_overwrite_a_newer_reason(self):
        order = self.create_order(dict(self.payload(), status="cancelled"))
        stale = self.workflow_payload(order, notes="Outdated reason")
        current = self.workflow_payload(order, notes="Latest cancellation reason")
        self.assertEqual(
            self.client.post(
                reverse("edit_order", args=[order.pk]), current
            ).status_code,
            302,
        )
        response = self.client.post(reverse("edit_order", args=[order.pk]), stale)
        self.assertContains(response, "changed while you were editing")
        order.refresh_from_db()
        self.assertEqual(order.notes, "Latest cancellation reason")
        self.assertEqual(order.revision, 2)
        self.assertEqual(order.status, "cancelled")

    def test_collection_changes_outside_complete_are_ignored(self):
        for status in ["draft", "in_progress", "cancelled"]:
            for collected in [False, True]:
                order = self.create_order(
                    dict(
                        self.payload(),
                        status=status,
                        collected="on" if collected else "",
                    )
                )
                data = self.edit_payload(order)
                if collected:
                    data.pop("collected", None)
                else:
                    data["collected"] = "on"
                self.assertEqual(
                    self.client.post(
                        reverse("edit_order", args=[order.pk]), data
                    ).status_code,
                    302,
                )
                order.refresh_from_db()
                self.assertEqual(order.collected, collected)

    def test_submit_assign_complete_then_collect(self):
        order = self.create_order()
        data = self.edit_payload(order)
        data.update(
            {
                "action": "submit",
                "assigned_to": str(self.user.pk),
                "payment_status": "paid",
                "collected": "on",
            }
        )
        self.assertEqual(
            self.client.post(reverse("edit_order", args=[order.pk]), data).status_code,
            302,
        )
        order.refresh_from_db()
        self.assertIsNone(order.assigned_to)
        self.assertFalse(order.collected)
        data = self.workflow_payload(
            order, assigned_to=str(self.user.pk), payment_status="paid", collected="on"
        )
        self.assertEqual(
            self.client.post(reverse("edit_order", args=[order.pk]), data).status_code,
            302,
        )
        order.refresh_from_db()
        self.assertEqual(order.assigned_to, self.user)
        self.assertEqual(order.payment_status, "paid")
        self.assertFalse(order.collected)
        data = self.workflow_payload(order, action="complete", collected="on")
        self.assertEqual(
            self.client.post(reverse("edit_order", args=[order.pk]), data).status_code,
            302,
        )
        order.refresh_from_db()
        self.assertEqual(order.status, "complete")
        self.assertFalse(order.collected)
        data = self.workflow_payload(order, collected="on")
        self.assertEqual(
            self.client.post(reverse("edit_order", args=[order.pk]), data).status_code,
            302,
        )
        order.refresh_from_db()
        self.assertTrue(order.collected)
        self.assertEqual(order.total, Decimal("99.40"))

    def test_invalid_payment_status_is_rejected_after_submission(self):
        order = self.create_order(dict(self.payload(), status="in_progress"))
        response = self.client.post(
            reverse("edit_order", args=[order.pk]),
            self.workflow_payload(order, payment_status="partial"),
        )
        self.assertIn("payment_status", response.context["editor"].form.errors)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, "unpaid")
        self.assertEqual(order.revision, 1)

    def test_delete_draft_removes_only_order_items_and_charges(self):
        order = self.create_order()
        other = self.create_order()
        item_id = order.items.get().pk
        charge_ids = list(order.charges.values_list("pk", flat=True))
        response = self.client.post(
            reverse("delete_order", args=[order.pk]), {"revision": order.revision}
        )
        self.assertRedirects(response, reverse("orders"))
        self.assertFalse(ServiceOrder.objects.filter(pk=order.pk).exists())
        self.assertFalse(OrderItem.objects.filter(pk=item_id).exists())
        self.assertFalse(OrderServiceCharge.objects.filter(pk__in=charge_ids).exists())
        self.assertTrue(ServiceOrder.objects.filter(pk=other.pk).exists())
        self.assertTrue(Customer.objects.filter(pk=self.customer.pk).exists())
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())
        self.assertTrue(Service.objects.filter(pk=self.service.pk).exists())

    def test_non_draft_orders_cannot_be_deleted(self):
        for status in ["in_progress", "complete", "cancelled"]:
            order = self.create_order(
                dict(self.payload(), status=status, assigned_to=str(self.worker.pk))
            )
            response = self.client.post(
                reverse("delete_order", args=[order.pk]), {"revision": order.revision}
            )
            self.assertEqual(response.status_code, 403)
            order.refresh_from_db()
            self.assertEqual(order.status, status)
            self.assertEqual(order.revision, 1)
            self.assertEqual(order.charges.count(), 3)

    def test_deleting_drafts_requires_delete_permission(self):
        order = self.create_order()
        editor = get_user_model().objects.create_user(username="editor_without_delete")
        editor.user_permissions.add(
            Permission.objects.get(codename="change_serviceorder")
        )
        self.client.force_login(editor)
        response = self.client.post(
            reverse("delete_order", args=[order.pk]), {"revision": order.revision}
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(ServiceOrder.objects.filter(pk=order.pk).exists())

    def test_draft_deletion_requires_post_and_a_valid_revision(self):
        order = self.create_order()
        url = reverse("delete_order", args=[order.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        for data in [{}, {"revision": "invalid"}, {"revision": "0"}]:
            self.assertEqual(self.client.post(url, data).status_code, 400)
            self.assertTrue(ServiceOrder.objects.filter(pk=order.pk).exists())

    def test_stale_draft_deletion_preserves_newer_changes(self):
        order = self.create_order()
        stale = self.edit_payload(order)
        current = self.edit_payload(order)
        current["notes"] = "Newer notes"
        self.assertEqual(
            self.client.post(
                reverse("edit_order", args=[order.pk]), current
            ).status_code,
            302,
        )
        response = self.client.post(reverse("edit_order", args=[order.pk]), stale)
        delete_form = re.search(
            r'<form id="delete-draft-form".*?</form>', response.content.decode(), re.S
        ).group()
        self.assertIn('name="revision" value="1"', delete_form)
        response = self.client.post(
            reverse("delete_order", args=[order.pk]), {"revision": 1}, follow=True
        )
        self.assertContains(response, "The draft changed. Review it before deleting.")
        order.refresh_from_db()
        self.assertEqual(order.notes, "Newer notes")
        self.assertEqual(order.revision, 2)

    def test_stale_delete_cannot_remove_a_submitted_order(self):
        order = self.create_order()
        data = self.edit_payload(order)
        data["action"] = "submit"
        self.assertEqual(
            self.client.post(reverse("edit_order", args=[order.pk]), data).status_code,
            302,
        )
        response = self.client.post(
            reverse("delete_order", args=[order.pk]), {"revision": 1}
        )
        self.assertEqual(response.status_code, 403)
        order.refresh_from_db()
        self.assertEqual(order.status, "in_progress")
        self.assertEqual(order.revision, 2)

    def test_delete_draft_requires_csrf_token(self):
        order = self.create_order()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        client.get(reverse("edit_order", args=[order.pk]))
        url = reverse("delete_order", args=[order.pk])
        self.assertEqual(
            client.post(url, {"revision": order.revision}).status_code, 403
        )
        self.assertTrue(ServiceOrder.objects.filter(pk=order.pk).exists())
        response = client.post(
            url,
            {
                "revision": order.revision,
                "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ServiceOrder.objects.filter(pk=order.pk).exists())

    def test_new_drafts_show_discard_and_saved_drafts_show_delete(self):
        response = self.client.get(reverse("create_order"))
        self.assertContains(response, "Discard", count=2)
        self.assertContains(
            response,
            'data-confirm="Are you sure you wish to discard this unsaved order?"',
            count=2,
        )
        self.assertNotContains(response, "Delete draft")
        self.assertNotContains(response, 'name="action" value="cancel"')
        order = self.create_order()
        response = self.client.get(reverse("edit_order", args=[order.pk]))
        self.assertContains(response, "Delete draft", count=2)
        self.assertContains(response, 'form="delete-draft-form"', count=2)
        self.assertNotContains(response, 'name="action" value="cancel"')
        order.status = "in_progress"
        order.save(update_fields=["status"])
        response = self.client.get(reverse("edit_order", args=[order.pk]))
        self.assertNotContains(response, "Delete draft")
        self.assertContains(response, 'name="action" value="cancel"', count=2)

    def test_save_without_a_transition_preserves_each_current_status(self):
        for status in ServiceOrder.Status.values:
            order = self.create_order(
                dict(self.payload(), status=status, assigned_to=str(self.worker.pk))
            )
            for action in [None, "save"]:
                data = self.edit_payload(order)
                data["payment_status"] = "paid"
                if action:
                    data["action"] = action
                self.assertEqual(
                    self.client.post(
                        reverse("edit_order", args=[order.pk]), data
                    ).status_code,
                    302,
                )
                order.refresh_from_db()
                self.assertEqual(order.status, status)
                self.assertEqual(
                    order.payment_status,
                    (
                        ServiceOrder.PaymentStatus.UNPAID
                        if status
                        in (ServiceOrder.Status.DRAFT, ServiceOrder.Status.CANCELLED)
                        else ServiceOrder.PaymentStatus.PAID
                    ),
                )
