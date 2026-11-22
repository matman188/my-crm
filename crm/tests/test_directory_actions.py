from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase
from django.urls import reverse

from crm.models import Customer, OrderServiceCharge, Product, Service, ServiceOrder
from crm.tests.helpers import create_admin_user


class DirectoryActionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = create_admin_user()
        cls.customers = Customer.objects.bulk_create(
            Customer(
                first_name=f"Batch {index:02d}", email=f"batch-{index}@example.com"
            )
            for index in range(27)
        )
        cls.services = Service.objects.bulk_create(
            Service(name=f"Batch {index:02d}", price="12.00") for index in range(27)
        )
        Customer.objects.create(
            first_name="Batch archived", email="archived@example.com", is_archived=True
        )
        Customer.objects.create(
            first_name="Different customer", email="different@example.com"
        )
        Service.objects.create(name="Batch archived", price="11.00", is_archived=True)
        Service.objects.create(name="Different service", price="11.00")
        cls.order = ServiceOrder.objects.create(
            customer=cls.customers[0], currency="ZAR"
        )
        cls.charge = OrderServiceCharge.objects.create(
            order=cls.order, service=cls.services[0], quantity=1, unit_price="12.00"
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def directories(self):
        return (
            ("customers", Customer, self.customers),
            ("services", Service, self.services),
        )

    def test_page_selection_changes_only_current_page_and_keeps_filters(self):
        for name, model, batch in self.directories():
            with self.subTest(directory=name):
                url = f"{reverse(name)}?q=Batch&status=active&page=2"
                response = self.client.get(url)
                self.assertContains(response, "Page 2 of 2")
                self.assertContains(response, "data-directory-link", count=2)
                self.assertContains(response, 'name="selected"', count=2)
                self.assertNotContains(response, "<th>Actions</th>", html=True)
                response = self.client.post(
                    url,
                    {
                        "bulk_action": "archive",
                        "scope": "page",
                        "selected": [batch[0].pk, batch[25].pk],
                    },
                    follow=True,
                )
                self.assertContains(response, "Select entries from the current page")
                self.assertEqual(model.objects.filter(is_archived=True).count(), 1)
                response = self.client.post(
                    url,
                    {
                        "bulk_action": "archive",
                        "scope": "page",
                        "selected": [batch[25].pk, batch[26].pk],
                    },
                )
                self.assertRedirects(response, url)
                archived = model.objects.filter(
                    is_archived=True, pk__in=[row.pk for row in batch]
                )
                self.assertCountEqual(
                    archived.values_list("pk", flat=True), [batch[25].pk, batch[26].pk]
                )

    def test_all_matching_delete_skips_linked_records_and_preserves_other_results(self):
        for name, model, batch in self.directories():
            with self.subTest(directory=name):
                url = f"{reverse(name)}?q=Batch&status=active"
                response = self.client.post(
                    url,
                    {"bulk_action": "delete", "scope": "all", "total": 28},
                    follow=True,
                )
                self.assertContains(response, "The matching results changed")
                self.assertEqual(model.objects.count(), 29)
                response = self.client.post(
                    url,
                    {"bulk_action": "delete", "scope": "all", "total": 27},
                    follow=True,
                )
                self.assertContains(response, f"Deleted 26 {name}.")
                self.assertContains(response, "Kept 1 entry linked to service orders")
                self.assertEqual(model.objects.count(), 3)
                self.assertTrue(model.objects.filter(pk=batch[0].pk).exists())
                self.assertEqual(model.objects.filter(is_archived=True).count(), 1)
        self.assertTrue(ServiceOrder.objects.filter(pk=self.order.pk).exists())
        self.assertTrue(OrderServiceCharge.objects.filter(pk=self.charge.pk).exists())

    def test_all_matching_service_archive_deduplicates_linked_product_matches(self):
        product_1 = Product.objects.create(name="Fitting match one")
        product_2 = Product.objects.create(name="Fitting match two")
        self.services[0].products.add(product_1, product_2)
        self.services[1].products.add(product_2)
        url = f"{reverse('services')}?q=Fitting"
        self.assertRedirects(
            self.client.post(
                url, {"bulk_action": "archive", "scope": "all", "total": 2}
            ),
            url,
        )
        self.assertEqual(Service.objects.filter(is_archived=True).count(), 3)
        self.assertTrue(OrderServiceCharge.objects.filter(pk=self.charge.pk).exists())
        archived_url = f"{url}&status=archived"
        self.assertRedirects(
            self.client.post(
                archived_url, {"bulk_action": "restore", "scope": "all", "total": 2}
            ),
            archived_url,
        )
        self.assertEqual(Service.objects.filter(is_archived=True).count(), 1)

    def test_bulk_actions_require_csrf_and_the_corresponding_permission(self):
        viewer = get_user_model().objects.create_user(username="directory-reader")
        viewer.user_permissions.add(
            *Permission.objects.filter(codename__in=("view_customer", "view_service"))
        )
        self.client.force_login(viewer)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.admin)
        for name, model, batch in self.directories():
            with self.subTest(directory=name):
                url = reverse(name)
                self.assertNotContains(self.client.get(url), "data-directory-apply")
                for action in ("archive", "delete"):
                    payload = {
                        "bulk_action": action,
                        "scope": "page",
                        "selected": [batch[0].pk],
                    }
                    self.assertEqual(self.client.post(url, payload).status_code, 403)
                    self.assertEqual(protected.post(url, payload).status_code, 403)
                self.assertEqual(model.objects.count(), 29)
