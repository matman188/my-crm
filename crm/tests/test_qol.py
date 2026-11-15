from datetime import date, datetime, time, timezone
import json
from pathlib import Path
import shutil
import subprocess
import unittest

from django.contrib.auth import get_user_model
from django.db.models.deletion import ProtectedError
from django.test import RequestFactory, TestCase
from django.urls import reverse

from crm.forms.catalog import ProductForm, ServiceForm
from crm.forms.orders import OrderConflict, OrderEditor
from crm.forms.settings import SystemSettingsForm
from crm.models import (
    Customer,
    OrderItem,
    Product,
    ProductCategory,
    Service,
    ServiceOrder,
    SystemSettings,
)
from crm.order_queries import (
    deadline_order,
    with_deadlines,
    work_condition,
    work_counts,
)
from crm.views.common import return_url
from . import test_orders


class QualityOfLifeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Reuse the real order payload helpers without inheriting all order tests.
        test_orders.ServiceOrderTests.setUpTestData.__func__(cls)
        cls.admin = get_user_model().objects.create_superuser(username="qol-admin")

    payload = test_orders.ServiceOrderTests.payload
    edit_payload = test_orders.ServiceOrderTests.edit_payload
    create_order = test_orders.ServiceOrderTests.create_order

    def setUp(self):
        self.client.force_login(self.user)

    def make_order(
        self, *, status="draft", due_date=date(2026, 11, 15), due_time=None, **kwargs
    ):
        order = ServiceOrder.objects.create(
            customer=self.customer, currency="ZAR", status=status, **kwargs
        )
        OrderItem.objects.create(
            order=order, product=self.product, due_date=due_date, due_time=due_time
        )
        return order

    def test_deadlines_use_business_timezone_and_optional_time(self):
        now = datetime(2026, 11, 15, 22, 30, tzinfo=timezone.utc)  # 16 Nov 00:30 local
        past = self.make_order(due_date=date(2026, 11, 15))
        date_only = self.make_order(due_date=date(2026, 11, 16))
        before = self.make_order(due_date=date(2026, 11, 16), due_time=time(0, 29))
        exact = self.make_order(due_date=date(2026, 11, 16), due_time=time(0, 30))
        closed = self.make_order(status="complete", due_date=date(2026, 11, 15))
        records = {o.pk: o for o in with_deadlines(ServiceOrder.objects.all(), now=now)}
        self.assertTrue(records[past.pk].is_overdue)
        self.assertTrue(records[before.pk].is_overdue)
        self.assertFalse(records[exact.pk].is_overdue)
        self.assertFalse(records[date_only.pk].is_overdue)
        self.assertTrue(records[date_only.pk].is_due_today)
        self.assertFalse(records[closed.pk].is_overdue)
        settings = SystemSettings.get_solo()
        settings.business_timezone = "UTC"
        settings.save()
        self.assertFalse(
            with_deadlines(ServiceOrder.objects.all(), now=now)
            .get(pk=past.pk)
            .is_overdue
        )

    def test_work_queues_have_distinct_business_rules(self):
        draft = self.make_order()
        progress = self.make_order(status="in_progress", assigned_to=self.user)
        complete = self.make_order(status="complete")
        collected = self.make_order(
            status="complete", collected=True, payment_status="paid"
        )
        cancelled = self.make_order(status="cancelled")
        refunded = self.make_order(status="complete", payment_status="refunded")
        qs = with_deadlines(ServiceOrder.objects.all())
        self.assertEqual(
            set(
                qs.filter(work_condition("unpaid", self.user)).values_list(
                    "pk", flat=True
                )
            ),
            {progress.pk, complete.pk},
        )
        self.assertEqual(
            set(
                qs.filter(work_condition("awaiting_collection", self.user)).values_list(
                    "pk", flat=True
                )
            ),
            {complete.pk, refunded.pk},
        )
        self.assertEqual(
            list(qs.filter(work_condition("unassigned", self.user))),
            [qs.get(pk=draft.pk)],
        )
        self.assertEqual(work_counts(qs, self.user)["mine"], 1)
        self.assertEqual(work_counts(qs, self.user)["all"], 6)
        self.assertNotEqual(collected.pk, cancelled.pk)

    def test_deadline_sort_is_stable_and_prioritises_open_work(self):
        closed = self.make_order(status="complete", due_date=date(2020, 1, 1))
        later = self.make_order(due_time=None)
        earlier = self.make_order(due_time=time(10))
        first = self.make_order(due_date=date(2026, 11, 14))
        self.assertEqual(
            list(
                deadline_order(with_deadlines(ServiceOrder.objects.all())).values_list(
                    "pk", flat=True
                )
            ),
            [first.pk, earlier.pk, later.pk, closed.pk],
        )

    def test_open_orders_view_includes_only_draft_and_in_progress(self):
        draft = self.make_order(status="draft")
        progress = self.make_order(status="in_progress", assigned_to=self.user)
        self.make_order(status="complete", payment_status="unpaid")
        self.make_order(status="cancelled")
        before = list(ServiceOrder.objects.values())
        response = self.client.get(reverse("orders"), {"view": "open"})
        self.assertEqual(
            {order.pk for order in response.context["page_obj"]},
            {draft.pk, progress.pk},
        )
        queue = next(
            view
            for view in response.context["quick_views"]
            if view["label"] == "Open Orders"
        )
        self.assertTrue(queue["active"])
        self.assertEqual(queue["count"], 2)
        self.assertContains(response, "Open Orders")
        home = self.client.get(reverse("home"))
        self.assertEqual(
            next(
                card["count"]
                for card in home.context["work_cards"]
                if card["key"] == "open"
            ),
            2,
        )
        self.assertEqual(list(ServiceOrder.objects.values()), before)

    def test_open_orders_preserves_search_customer_scope_and_pagination(self):
        other = Customer.objects.create(
            first_name="Alex",
            last_name="Other",
            email="open-other@example.com",
            primary_phone="0123",
        )
        ServiceOrder.objects.bulk_create(
            [
                ServiceOrder(
                    customer=self.customer,
                    currency="ZAR",
                    status="draft" if index % 2 else "in_progress",
                )
                for index in range(26)
            ]
        )
        ServiceOrder.objects.create(customer=other, currency="ZAR", status="draft")
        self.make_order(status="complete")
        filters = {
            "view": "open",
            "q": "Alex",
            "customer": self.customer.pk,
            "sort": "oldest",
        }
        response = self.client.get(reverse("orders"), filters)
        self.assertEqual(response.context["page_obj"].paginator.count, 26)
        for value in (
            "view=open",
            "q=Alex",
            f"customer={self.customer.pk}",
            "sort=oldest",
            "page=2",
        ):
            self.assertContains(response, value)
        response = self.client.get(reverse("orders"), dict(filters, page=2))
        self.assertEqual(len(response.context["page_obj"]), 1)
        self.assertIn(response.context["page_obj"][0].status, ("draft", "in_progress"))
        queue = next(
            view
            for view in response.context["quick_views"]
            if view["label"] == "Open Orders"
        )
        self.assertEqual(queue["count"], 26)

    def test_queue_counts_dashboard_and_filters_match(self):
        self.make_order(status="in_progress", assigned_to=self.user)
        self.make_order(status="complete", assigned_to=self.worker)
        response = self.client.get(
            reverse("orders"), {"view": "mine", "q": "Alex", "sort": "deadline"}
        )
        self.assertEqual(response.context["page_obj"].paginator.count, 1)
        self.assertEqual(
            next(
                v["count"]
                for v in response.context["quick_views"]
                if v["label"] == "My Orders"
            ),
            1,
        )
        self.assertContains(response, "Awaiting Collection")
        home = self.client.get(reverse("home"))
        self.assertEqual(
            next(v["count"] for v in home.context["work_cards"] if v["key"] == "mine"),
            1,
        )
        self.client.force_login(
            get_user_model().objects.create_user(username="no-order-access")
        )
        self.assertNotContains(
            self.client.get(reverse("home")), 'class="dashboard-card"'
        )

    def test_invalid_queue_and_sort_are_validation_errors_not_server_errors(self):
        response = self.client.get(
            reverse("orders"), {"view": "invented", "sort": "invented"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["filter_form"].errors)

    def test_order_filters_use_search_and_no_redundant_unpaid_shortcut(self):
        self.make_order(status="in_progress", payment_status="unpaid")
        self.make_order(status="in_progress", payment_status="paid")
        response = self.client.get(reverse("orders"), {"payment_status": "unpaid"})
        self.assertEqual(response.context["page_obj"].paginator.count, 1)
        self.assertNotIn(
            "Unpaid", [view["label"] for view in response.context["quick_views"]]
        )
        self.assertIn(
            "Open Orders", [view["label"] for view in response.context["quick_views"]]
        )
        self.assertContains(response, "data-list-filters")
        self.assertContains(response, 'type="submit">Search</button>')
        self.assertNotContains(response, 'type="submit">Filter</button>')
        self.assertEqual(
            response.context["filter_form"]["payment_status"].value(), "unpaid"
        )
        legacy = self.client.get(reverse("orders"), {"view": "unpaid"})
        self.assertEqual(
            legacy.context["filter_form"]["payment_status"].value(), "unpaid"
        )
        self.assertEqual(legacy.context["page_obj"].paginator.count, 1)

    def test_archived_catalogue_is_excluded_from_new_order_but_existing_prices_survive(
        self,
    ):
        order = self.create_order()
        Product.objects.filter(pk=self.product.pk).update(is_archived=True)
        Service.objects.filter(pk__in=[self.service.pk, self.global_service.pk]).update(
            is_archived=True, price="999.00"
        )
        self.assertFalse(OrderEditor(user=self.user, data=self.payload()).is_valid())
        editor = OrderEditor(
            user=self.user, instance=order, data=self.edit_payload(order)
        )
        self.assertTrue(editor.is_valid(), (editor.form.errors, editor.items.errors))
        editor.save()
        self.assertEqual(str(order.charges.order_by("pk").first().unit_price), "12.35")
        self.assertEqual(str(order.charges.get(item__isnull=True).unit_price), "50.00")

    def test_archived_service_cannot_be_selected_for_another_product(self):
        order = self.create_order()
        Service.objects.filter(pk=self.service.pk).update(is_archived=True)
        data = self.edit_payload(order)
        data["items-0-product"] = str(self.other_product.pk)
        self.assertFalse(
            OrderEditor(user=self.user, instance=order, data=data).is_valid()
        )

    def test_catalogue_archive_between_validation_and_save_rolls_back_order(self):
        for model, record in [(Product, self.product), (Service, self.service)]:
            with self.subTest(model=model.__name__):
                editor = OrderEditor(user=self.user, data=self.payload())
                self.assertTrue(editor.is_valid())
                model.objects.filter(pk=record.pk).update(is_archived=True)
                with self.assertRaises(OrderConflict):
                    editor.save()
                self.assertFalse(ServiceOrder.objects.exists())
                model.objects.filter(pk=record.pk).update(is_archived=False)

    def test_archiving_retained_service_during_product_change_is_checked_on_save(self):
        order = self.create_order()
        self.service.products.add(self.other_product)
        data = self.edit_payload(order)
        data["items-0-product"] = str(self.other_product.pk)
        editor = OrderEditor(user=self.user, instance=order, data=data)
        self.assertTrue(editor.is_valid())
        Service.objects.filter(pk=self.service.pk).update(is_archived=True)
        with self.assertRaises(OrderConflict):
            editor.save()
        order.refresh_from_db()
        self.assertEqual(order.revision, 1)
        self.assertEqual(order.items.get().product_id, self.product.pk)

    def test_archiving_requires_permission_and_post_and_restoring_keeps_order(self):
        order = self.create_order()
        for kind, record in [("product", self.product), ("service", self.service)]:
            url = reverse("archive_" + kind, args=[record.pk])
            self.assertEqual(self.client.post(url).status_code, 403)
            self.client.force_login(self.admin)
            self.assertEqual(self.client.get(url).status_code, 405)
            self.assertEqual(self.client.post(url).status_code, 302)
            record.refresh_from_db()
            self.assertTrue(record.is_archived)
            self.assertEqual(
                self.client.post(
                    reverse("restore_" + kind, args=[record.pk])
                ).status_code,
                302,
            )
            record.refresh_from_db()
            self.assertFalse(record.is_archived)
            self.assertTrue(ServiceOrder.objects.filter(pk=order.pk).exists())
            self.client.force_login(self.user)

    def test_stale_catalogue_edit_preserves_archived_flag(self):
        product_form = ProductForm(
            {"name": "Updated", "category": "", "description": ""},
            instance=self.product,
        )
        service_form = ServiceForm(
            {
                "name": "Updated service",
                "price": "20",
                "products": [self.product.pk],
                "description": "",
            },
            instance=self.service,
        )
        self.assertTrue(product_form.is_valid())
        self.assertTrue(service_form.is_valid())
        Product.objects.filter(pk=self.product.pk).update(is_archived=True)
        Service.objects.filter(pk=self.service.pk).update(is_archived=True)
        product_form.save()
        service_form.save()
        self.product.refresh_from_db()
        self.service.refresh_from_db()
        self.assertTrue(self.product.is_archived)
        self.assertTrue(self.service.is_archived)

    def test_staff_deactivation_keeps_history_and_prevents_deletion(self):
        order = self.make_order(
            status="in_progress", assigned_to=self.worker, created_by=self.worker
        )
        self.client.force_login(self.admin)
        self.assertEqual(
            self.client.get(
                reverse("deactivate_user", args=[self.worker.pk])
            ).status_code,
            405,
        )
        self.client.post(reverse("deactivate_user", args=[self.worker.pk]))
        self.worker.refresh_from_db()
        self.assertFalse(self.worker.is_active)
        order.refresh_from_db()
        self.assertEqual(order.assigned_to, self.worker)
        self.client.post(reverse("delete_user", args=[self.worker.pk]))
        self.assertTrue(get_user_model().objects.filter(pk=self.worker.pk).exists())
        with self.assertRaises(ProtectedError):
            self.worker.delete()
        self.client.post(reverse("reactivate_user", args=[self.worker.pk]))
        self.worker.refresh_from_db()
        self.assertTrue(self.worker.is_active)

    def test_staff_deactivation_protects_self_and_requires_permission(self):
        self.assertEqual(
            self.client.post(
                reverse("deactivate_user", args=[self.worker.pk])
            ).status_code,
            403,
        )
        self.client.force_login(self.admin)
        self.assertEqual(
            self.client.post(
                reverse("deactivate_user", args=[self.admin.pk])
            ).status_code,
            403,
        )

    def test_directories_paginate_and_preserve_query_parameters(self):
        self.client.force_login(self.admin)
        Customer.objects.bulk_create(
            [
                Customer(
                    first_name=f"Paged {i:02d}",
                    last_name="Person",
                    email=f"page{i}@example.com",
                    primary_phone="0123",
                )
                for i in range(28)
            ]
        )
        Product.objects.bulk_create([Product(name=f"Paged {i:02d}") for i in range(28)])
        Service.objects.bulk_create(
            [Service(name=f"Paged {i:02d}", price=1) for i in range(28)]
        )
        ProductCategory.objects.bulk_create(
            [ProductCategory(name=f"Paged {i:02d}") for i in range(28)]
        )
        get_user_model().objects.bulk_create(
            [get_user_model()(username=f"paged{i:02d}") for i in range(28)]
        )
        for name in [
            "customers",
            "products",
            "services",
            "product_categories",
            "users",
        ]:
            with self.subTest(name=name):
                response = self.client.get(
                    reverse(name), {"q": "Paged", "page": "2", "status": "all"}
                )
                self.assertEqual(len(response.context["page_obj"]), 3)
                self.assertEqual(response.context["page_obj"].number, 2)
                self.assertContains(response, "q=Paged&amp;status=all&amp;page=1")

    def test_return_navigation_preserves_filters_and_rejects_external_redirect(self):
        factory = RequestFactory()
        for value in [
            "https://evil.example/orders/",
            "//evil.example",
            "javascript:alert(1)",
            "\\\\evil.example",
        ]:
            self.assertEqual(return_url(factory.get("/", {"next": value})), "")
        destination = "/customers/?q=Alex&page=2&status=all"
        self.assertEqual(
            return_url(factory.get("/", {"next": destination})), destination
        )
        response = self.client.post(
            reverse("edit_customer", args=[self.customer.pk]),
            {
                "first_name": "Alex",
                "last_name": "Dancer",
                "email": "alex@example.com",
                "primary_phone": "0123456789",
                "next": destination,
            },
        )
        self.assertEqual(response.url, destination)
        response = self.client.get(
            reverse("edit_customer", args=[self.customer.pk]), {"next": destination}
        )
        self.assertContains(
            response, 'href="/customers/?q=Alex&amp;page=2&amp;status=all"'
        )
        self.assertContains(response, "Customer: Alex Dancer")

    def test_business_timezone_validation_and_legacy_settings_save(self):
        settings = SystemSettings.get_solo()
        invalid = SystemSettingsForm(
            {
                "company_name": "Business",
                "default_currency": "ZAR",
                "business_timezone": "not/a-zone",
            },
            instance=settings,
        )
        self.assertFalse(invalid.is_valid())
        valid = SystemSettingsForm(
            {
                "company_name": "Business",
                "default_currency": "ZAR",
                "business_timezone": "Europe/London",
            },
            instance=settings,
        )
        self.assertTrue(valid.is_valid())
        valid.save()
        legacy = SystemSettingsForm(
            {"company_name": "Business 2", "default_currency": "USD"}, instance=settings
        )
        self.assertTrue(legacy.is_valid())
        self.assertEqual(legacy.save().business_timezone, "Europe/London")

    def test_discard_and_delete_draft_preserve_return_url(self):
        destination = "/orders/?view=unassigned&page=2"
        response = self.client.get(reverse("create_order"), {"next": destination})
        self.assertContains(response, 'href="/orders/?view=unassigned&amp;page=2"')
        order = self.create_order()
        response = self.client.post(
            reverse("delete_order", args=[order.pk]),
            {"revision": order.revision, "next": destination},
        )
        self.assertEqual(response.url, destination)
        self.assertFalse(ServiceOrder.objects.filter(pk=order.pk).exists())

    @unittest.skipUnless(
        shutil.which("node") and Path("node_modules/jsdom").exists(),
        "Run npm ci to enable rendered DOM tests",
    )
    def test_rendered_order_ui_and_duplicate_payload(self):
        order = self.create_order()
        Service.objects.filter(pk=self.service.pk).update(price="20.00")
        draft = self.client.get(reverse("edit_order", args=[order.pk])).content.decode()
        order.status = "in_progress"
        order.assigned_to = self.worker
        order.save()
        progress = self.client.get(
            reverse("edit_order", args=[order.pk])
        ).content.decode()
        # A separate unlinked record provides a list Delete button.
        Customer.objects.create(
            first_name="Alex",
            last_name="Other",
            email="other@example.com",
            primary_phone="0123",
        )
        customers = self.client.get(
            reverse("customers"), {"q": "Alex"}
        ).content.decode()
        result = subprocess.run(
            [shutil.which("node"), "crm/tests/js/rendered-order.cjs"],
            input=json.dumps(
                {"draft": draft, "progress": progress, "customers": customers}
            ),
            text=True,
            capture_output=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        outcome = json.loads(result.stdout)
        self.assertGreaterEqual(len(outcome["checks"]), 8)
        order.status = "draft"
        order.save()
        response = self.client.post(
            reverse("edit_order", args=[order.pk]), outcome["duplicated"]
        )
        self.assertEqual(
            response.status_code,
            302,
            response.context and response.context["editor"].items.errors,
        )
        order.refresh_from_db()
        self.assertEqual(order.items.count(), 2)
        self.assertEqual(str(order.total), "179.40")  # 4x12.35 + 4x20 + 50 extra
        self.assertEqual(
            list(order.items.values_list("due_date", flat=True)), [date(2027, 2, 3)] * 2
        )
