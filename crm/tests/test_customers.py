from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse
from unittest.mock import patch

from crm.forms.customers import CustomerForm
from crm.models import Customer, ServiceOrder


class CustomerViewTests(TestCase):
    def test_customers_page_requires_login(self):
        response = self.client.get(reverse("customers"))

        self.assertRedirects(response, "/login/?next=/customers/")

    def test_customers_page_shows_sorted_customer_list(self):
        user = get_user_model().objects.create_user(
            username="agent",
            password="testpass123",
        )
        Customer.objects.create(
            first_name="Charlie", email="charlie@example.com", owner=user
        )
        Customer.objects.create(
            first_name="alice", email="alice@example.com", owner=user
        )
        Customer.objects.create(
            first_name="Bravo", email="bravo@example.com", owner=user
        )
        self.client.force_login(user)

        response = self.client.get(reverse("customers"))
        content = response.content.decode()

        self.assertLess(content.index("alice"), content.index("Bravo"))
        self.assertLess(content.index("Bravo"), content.index("Charlie"))

    def test_customers_page_can_search_customer(self):
        user = get_user_model().objects.create_user(
            username="agent",
            password="testpass123",
        )
        Customer.objects.create(
            first_name="Jane", email="jane@example.com", company="Acme", owner=user
        )
        Customer.objects.create(
            first_name="John", email="john@example.com", company="Globex", owner=user
        )
        self.client.force_login(user)

        response = self.client.get(reverse("customers"), {"q": "acme"})

        self.assertContains(response, "Jane")
        self.assertNotContains(response, "John")

    def test_logged_in_user_can_create_customer(self):
        user = get_user_model().objects.create_user(
            username="agent",
            password="testpass123",
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("create_customer"),
            {
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "jane@example.com",
                "primary_phone": "1234567890",
                "secondary_phone": "0987654321",
                "company": "Acme",
                "notes": "Important client",
            },
            follow=True,
        )

        self.assertRedirects(response, reverse("customers"))
        customer = Customer.objects.get(first_name="Jane", last_name="Doe")
        self.assertEqual(customer.owner, user)
        self.assertEqual(customer.company, "Acme")
        self.assertEqual(customer.primary_phone, "1234567890")
        self.assertEqual(customer.secondary_phone, "0987654321")

    def test_logged_in_user_can_edit_customer(self):
        user = get_user_model().objects.create_user(
            username="agent",
            password="testpass123",
        )
        customer = Customer.objects.create(
            first_name="Jane", last_name="Doe", owner=user
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("edit_customer", args=[customer.id]),
            {
                "first_name": "Janet",
                "last_name": "Doe",
                "email": "janet@example.com",
                "primary_phone": "5550001",
                "secondary_phone": "5550002",
                "company": "Acme",
                "notes": "Updated notes",
            },
            follow=True,
        )

        self.assertRedirects(response, reverse("customers"))
        customer.refresh_from_db()
        self.assertEqual(customer.first_name, "Janet")
        self.assertEqual(customer.email, "janet@example.com")
        self.assertEqual(customer.primary_phone, "5550001")
        self.assertEqual(customer.secondary_phone, "5550002")

    def test_logged_in_user_can_delete_customer(self):
        user = get_user_model().objects.create_user(
            username="agent",
            password="testpass123",
        )
        customer = Customer.objects.create(first_name="Jane", owner=user)
        self.client.force_login(user)

        response = self.client.post(
            reverse("delete_customer", args=[customer.id]), follow=True
        )

        self.assertRedirects(response, reverse("customers"))
        self.assertFalse(Customer.objects.filter(id=customer.id).exists())


class CustomerOrderSummaryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="customer_orders")
        cls.user.user_permissions.add(
            Permission.objects.get(codename="view_serviceorder")
        )
        cls.customer = Customer.objects.create(
            first_name="Alex",
            last_name="Smith",
            email="alex@example.com",
            primary_phone="0123456789",
        )
        cls.other = Customer.objects.create(
            first_name="Alex",
            last_name="Smith",
            email="other@example.com",
            primary_phone="0123456789",
        )
        cls.empty = Customer.objects.create(
            first_name="No",
            last_name="Orders",
            email="empty@example.com",
            primary_phone="0123456789",
        )
        for status in ServiceOrder.Status.values:
            ServiceOrder.objects.create(
                customer=cls.customer, currency="ZAR", status=status
            )
        ServiceOrder.objects.create(customer=cls.other, currency="ZAR")

    def setUp(self):
        self.client.force_login(self.user)

    def test_customer_list_has_exact_order_counts_and_no_owner_column(self):
        response = self.client.get(reverse("customers"))
        customers = {
            customer.pk: customer for customer in response.context["existing_customers"]
        }
        self.assertEqual(customers[self.customer.pk].order_count, 4)
        self.assertEqual(customers[self.other.pk].order_count, 1)
        self.assertEqual(customers[self.empty.pk].order_count, 0)
        self.assertContains(response, "<th>Orders</th>", html=True)
        self.assertNotContains(response, "<th>Owner</th>", html=True)
        self.assertContains(
            response, f'{reverse("orders")}?customer={self.customer.pk}'
        )
        searched = self.client.get(reverse("customers"), {"q": "empty@example.com"})
        self.assertEqual(searched.context["existing_customers"].get().order_count, 0)

    def test_customer_form_shows_all_and_open_counts_and_view_orders(self):
        response = self.client.get(reverse("edit_customer", args=[self.customer.pk]))
        self.assertEqual(
            response.context["customer_order_counts"],
            {"total_orders": 4, "open_orders": 2},
        )
        self.assertContains(response, "<dt>Total Orders</dt><dd>4</dd>", html=True)
        self.assertContains(response, "<dt>Open Orders</dt><dd>2</dd>", html=True)
        self.assertContains(
            response,
            f'href="{reverse("orders")}?customer={self.customer.pk}">View Orders</a>',
        )
        response = self.client.get(reverse("edit_customer", args=[self.empty.pk]))
        self.assertEqual(
            response.context["customer_order_counts"],
            {"total_orders": 0, "open_orders": 0},
        )
        self.assertNotContains(
            self.client.get(reverse("create_customer")), "View Orders"
        )

    def test_view_orders_uses_customer_identity_and_composes_with_other_filters(self):
        response = self.client.get(reverse("orders"), {"customer": self.customer.pk})
        self.assertEqual(response.context["page_obj"].paginator.count, 4)
        self.assertEqual(
            {order.customer_id for order in response.context["page_obj"]},
            {self.customer.pk},
        )
        response = self.client.get(
            reverse("orders"),
            {
                "customer": self.customer.pk,
                "status": "in_progress",
                "payment_status": "unpaid",
            },
        )
        self.assertEqual(response.context["page_obj"].paginator.count, 1)
        self.assertEqual(
            response.context["page_obj"].object_list[0].customer_id, self.customer.pk
        )

    def test_customer_filter_is_retained_when_filtering_and_paging(self):
        ServiceOrder.objects.bulk_create(
            [ServiceOrder(customer=self.customer, currency="ZAR") for _ in range(26)]
        )
        response = self.client.get(
            reverse("orders"), {"customer": self.customer.pk, "status": "draft"}
        )
        self.assertEqual(response.context["page_obj"].paginator.count, 27)
        self.assertContains(
            response, f"customer={self.customer.pk}&amp;status=draft&amp;page=2"
        )
        response = self.client.get(
            reverse("orders"),
            {"customer": self.customer.pk, "status": "draft", "page": 2},
        )
        self.assertEqual(len(response.context["page_obj"]), 2)
        self.assertEqual(
            {order.customer_id for order in response.context["page_obj"]},
            {self.customer.pk},
        )
        self.assertEqual(
            str(response.context["filter_form"]["customer"].value()),
            str(self.customer.pk),
        )

    def test_invalid_customer_filter_does_not_expose_all_orders(self):
        for value in ("missing", "999999999999999999999999", "-1"):
            response = self.client.get(reverse("orders"), {"customer": value})
            self.assertIn("customer", response.context["filter_form"].errors)
            self.assertEqual(response.context["page_obj"].paginator.count, 0)

    def test_view_orders_link_follows_order_view_permission(self):
        self.user.user_permissions.clear()
        response = self.client.get(reverse("edit_customer", args=[self.customer.pk]))
        self.assertNotContains(response, "View Orders")
        self.assertEqual(response.context["customer_order_counts"]["total_orders"], 4)


class CustomerValidationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="customer_operator")
        cls.customer = Customer.objects.create(
            first_name="Alex",
            last_name="Smith",
            email="Existing@Example.com",
            primary_phone="0123456789",
            notes="Keep customer instructions",
        )

    def setUp(self):
        self.client.force_login(self.user)

    def payload(self, **changes):
        data = {
            "first_name": "Jordan",
            "last_name": "Taylor",
            "email": "new@example.com",
            "primary_phone": "0987654321",
            "notes": "New customer notes",
        }
        data.update(changes)
        return data

    def test_required_contact_fields_are_validated_on_create_and_edit(self):
        for url in (
            reverse("create_customer"),
            reverse("edit_customer", args=[self.customer.pk]),
        ):
            for field in ("first_name", "last_name", "email", "primary_phone"):
                with self.subTest(url=url, field=field):
                    response = self.client.post(url, self.payload(**{field: "   "}))
                    self.assertEqual(response.status_code, 200)
                    self.assertIn(field, response.context["form"].errors)
                    self.assertEqual(Customer.objects.count(), 1)
                    self.customer.refresh_from_db()
                    self.assertEqual(self.customer.first_name, "Alex")

    def test_customer_form_shows_small_delete_with_a_separate_confirmation_form(self):
        response = self.client.get(reverse("edit_customer", args=[self.customer.pk]))
        self.assertContains(
            response,
            'class="button danger customer-delete-button" type="button" data-delete-customer',
        )
        self.assertContains(response, "data-customer-delete-dialog", count=1)
        self.assertContains(response, "Are you sure you wish to delete Alex Smith?")
        self.assertContains(
            response,
            f'<form method="post" action="{reverse("delete_customer", args=[self.customer.pk])}">',
        )
        self.assertContains(response, "data-cancel-customer-delete autofocus")
        self.assertContains(response, "crm/js/customer-delete.js")
        created = self.client.get(reverse("create_customer"))
        self.assertNotContains(created, "data-delete-customer")
        self.assertNotContains(created, "data-customer-delete-dialog")

    def test_invalid_customer_form_still_confirms_the_persisted_customer_name(self):
        response = self.client.post(
            reverse("edit_customer", args=[self.customer.pk]),
            self.payload(last_name=""),
        )
        self.assertContains(response, "Are you sure you wish to delete Alex Smith?")
        self.assertContains(response, "data-delete-customer")
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.first_name, "Alex")

    def test_customer_form_delete_requires_csrf_and_uses_only_the_delete_request(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        client.get(reverse("edit_customer", args=[self.customer.pk]))
        url = reverse("delete_customer", args=[self.customer.pk])
        self.assertEqual(client.get(url).status_code, 403)
        self.assertEqual(client.post(url).status_code, 403)
        self.assertTrue(Customer.objects.filter(pk=self.customer.pk).exists())
        response = client.post(
            url, {"csrfmiddlewaretoken": client.cookies["csrftoken"].value}
        )
        self.assertRedirects(response, reverse("customers"))
        self.assertFalse(Customer.objects.filter(pk=self.customer.pk).exists())

    def test_required_markers_and_browser_validation_are_present(self):
        for url in (
            reverse("create_customer"),
            reverse("edit_customer", args=[self.customer.pk]),
        ):
            response = self.client.get(url)
            self.assertContains(response, 'class="required-marker"', count=4)
            form = response.context["form"]
            for name in ("first_name", "last_name", "email", "primary_phone"):
                self.assertTrue(form.fields[name].required)
                self.assertIn("required", str(form[name]))
            for name in ("secondary_phone", "company", "notes"):
                self.assertFalse(form.fields[name].required)

    def test_duplicate_email_is_rejected_case_insensitively_on_create_and_edit(self):
        other = Customer.objects.create(**self.payload())
        for url in (
            reverse("create_customer"),
            reverse("edit_customer", args=[other.pk]),
        ):
            for email in (
                "Existing@Example.com",
                "EXISTING@example.COM",
                " existing@example.com ",
            ):
                with self.subTest(url=url, email=email):
                    response = self.client.post(url, self.payload(email=email))
                    self.assertContains(response, CustomerForm.duplicate_email_message)
                    self.assertIn("email", response.context["form"].errors)
                    self.assertEqual(Customer.objects.count(), 2)
                    other.refresh_from_db()
                    self.assertEqual(other.email, "new@example.com")

    def test_customer_can_keep_own_email_and_new_email_is_normalized(self):
        response = self.client.post(
            reverse("edit_customer", args=[self.customer.pk]),
            self.payload(email=" EXISTING@Example.com "),
        )
        self.assertEqual(response.status_code, 302)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.email, "existing@example.com")
        self.assertEqual(self.customer.first_name, "Jordan")

    def test_database_constraint_rejects_case_and_whitespace_duplicates(self):
        for email in ("EXISTING@example.com", " existing@example.com "):
            with self.subTest(email=email), self.assertRaises(
                IntegrityError
            ), transaction.atomic():
                Customer.objects.create(**self.payload(email=email))
        self.assertEqual(Customer.objects.count(), 1)

    def test_duplicate_save_race_returns_an_email_error_on_create_and_edit(self):
        other = Customer.objects.create(**self.payload())
        for url in (
            reverse("create_customer"),
            reverse("edit_customer", args=[other.pk]),
        ):
            # Simulate a conflicting insert after the validation queries passed.
            with self.subTest(url=url), patch.object(
                CustomerForm, "_email_in_use", side_effect=[False, True]
            ), patch.object(Customer, "validate_constraints"):
                response = self.client.post(
                    url, self.payload(email="existing@example.com")
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn("email", response.context["form"].errors)
                self.assertContains(response, CustomerForm.duplicate_email_message)
                other.refresh_from_db()
                self.assertEqual(other.email, "new@example.com")
                self.assertEqual(Customer.objects.count(), 2)


class CustomerArchivingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="archive_operator")
        cls.user.user_permissions.add(
            *Permission.objects.filter(
                codename__in=("change_customer", "view_serviceorder")
            )
        )
        cls.customer = Customer.objects.create(
            first_name="Alex",
            last_name="Smith",
            email="archive@example.com",
            primary_phone="0123456789",
            notes="Keep all instructions",
            owner=cls.user,
        )
        cls.other = Customer.objects.create(
            first_name="Other",
            last_name="Customer",
            email="active@example.com",
            primary_phone="0123456789",
        )
        for status in ServiceOrder.Status.values:
            ServiceOrder.objects.create(
                customer=cls.customer, status=status, currency="ZAR"
            )

    def setUp(self):
        self.client.force_login(self.user)

    def test_archiving_keeps_customer_details_orders_and_counts(self):
        before = Customer.objects.values().get(pk=self.customer.pk)
        orders = list(self.customer.orders.values())
        response = self.client.post(
            reverse("archive_customer", args=[self.customer.pk])
        )
        self.assertRedirects(
            response, reverse("edit_customer", args=[self.customer.pk])
        )
        self.customer.refresh_from_db()
        after = Customer.objects.values().get(pk=self.customer.pk)
        self.assertTrue(after.pop("is_archived"))
        before.pop("is_archived")
        before.pop("updated_at")
        after.pop("updated_at")
        self.assertEqual(after, before)
        self.assertEqual(list(self.customer.orders.values()), orders)
        response = self.client.get(reverse("edit_customer", args=[self.customer.pk]))
        self.assertEqual(
            response.context["customer_order_counts"],
            {"total_orders": 4, "open_orders": 2},
        )
        self.assertContains(response, "Restore customer")
        self.assertContains(response, "data-customer-status-dialog")
        self.assertNotContains(response, "data-delete-customer")
        self.assertContains(response, "View Orders")

    def test_directory_filters_active_archived_and_all_with_search(self):
        Customer.objects.filter(pk=self.customer.pk).update(is_archived=True)
        for filters, expected in (
            ({}, {self.other.pk}),
            ({"status": "archived"}, {self.customer.pk}),
            ({"status": "all"}, {self.customer.pk, self.other.pk}),
            ({"status": "archived", "q": "archive@example.com"}, {self.customer.pk}),
        ):
            response = self.client.get(reverse("customers"), filters)
            self.assertEqual(
                {c.pk for c in response.context["existing_customers"]}, expected
            )
        response = self.client.get(reverse("customers"), {"status": "archived"})
        self.assertContains(response, "Archived")
        self.assertEqual(response.context["existing_customers"].get().order_count, 4)

    def test_restore_makes_the_same_customer_active_again(self):
        Customer.objects.filter(pk=self.customer.pk).update(is_archived=True)
        response = self.client.post(
            reverse("restore_customer", args=[self.customer.pk])
        )
        self.assertRedirects(
            response, reverse("edit_customer", args=[self.customer.pk])
        )
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.is_archived)
        self.assertEqual(self.customer.notes, "Keep all instructions")
        response = self.client.get(reverse("customers"))
        self.assertIn(
            self.customer.pk, {c.pk for c in response.context["existing_customers"]}
        )

    def test_archive_and_restore_require_post_permission_and_csrf(self):
        for name in ("archive_customer", "restore_customer"):
            url = reverse(name, args=[self.customer.pk])
            self.assertEqual(self.client.get(url).status_code, 405)
            csrf_client = Client(enforce_csrf_checks=True)
            csrf_client.force_login(self.user)
            csrf_client.get(reverse("edit_customer", args=[self.customer.pk]))
            self.assertEqual(csrf_client.post(url).status_code, 403)
            self.assertEqual(
                csrf_client.post(
                    url, {"csrfmiddlewaretoken": csrf_client.cookies["csrftoken"].value}
                ).status_code,
                302,
            )
        restricted = get_user_model().objects.create_user(username="archive_reader")
        self.client.force_login(restricted)
        for name in ("archive_customer", "restore_customer"):
            self.assertEqual(
                self.client.post(reverse(name, args=[self.customer.pk])).status_code,
                403,
            )
        self.assertNotContains(
            self.client.get(reverse("edit_customer", args=[self.customer.pk])),
            "data-customer-status-action",
        )

    def test_contact_save_cannot_undo_an_archive_done_after_validation(self):
        data = {name: getattr(self.customer, name) for name in CustomerForm.Meta.fields}
        data["notes"] = "Updated contact notes"
        form = CustomerForm(data, instance=self.customer)
        self.assertTrue(form.is_valid(), form.errors)
        Customer.objects.filter(pk=self.customer.pk).update(is_archived=True)
        form.save()
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.is_archived)
        self.assertEqual(self.customer.notes, "Updated contact notes")
        self.assertTrue(
            CustomerForm(
                dict(data, is_archived=False), instance=self.customer
            ).is_valid()
        )

    def test_archived_email_remains_unique_and_linked_customer_cannot_be_deleted(self):
        Customer.objects.filter(pk=self.customer.pk).update(is_archived=True)
        data = {name: getattr(self.customer, name) for name in CustomerForm.Meta.fields}
        form = CustomerForm(dict(data, email=" ARCHIVE@EXAMPLE.COM "))
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)
        response = self.client.post(
            reverse("delete_customer", args=[self.customer.pk]), follow=True
        )
        self.assertContains(response, "cannot be deleted")
        self.assertTrue(
            Customer.objects.filter(pk=self.customer.pk, is_archived=True).exists()
        )

    def test_archived_customer_order_history_can_still_be_filtered(self):
        Customer.objects.filter(pk=self.customer.pk).update(is_archived=True)
        response = self.client.get(reverse("orders"), {"customer": self.customer.pk})
        self.assertEqual(response.context["page_obj"].paginator.count, 4)
        self.assertEqual(
            {o.customer_id for o in response.context["page_obj"]}, {self.customer.pk}
        )
