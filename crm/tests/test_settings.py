from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from crm.authz import CRM_ADMIN_GROUP, CRM_USER_GROUP, SYSTEM_ADMIN_GROUP
from crm.demo_data import DEMO_PASSWORD, DEMO_USERNAMES
from crm.models import Customer, Product, ProductCategory, Service, SystemSettings
from crm.tests.helpers import create_admin_user


class SystemSettingsViewTests(TestCase):
    def test_system_settings_page_requires_login(self):
        response = self.client.get(reverse("system_settings"))

        self.assertRedirects(response, "/login/?next=/system-settings/")

    def test_non_admin_user_cannot_open_system_settings_page(self):
        user = get_user_model().objects.create_user(
            username="agent",
            password="testpass123",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("system_settings"))

        self.assertEqual(response.status_code, 403)

    def test_logged_in_user_can_open_system_settings_page(self):
        user = create_admin_user()
        self.client.force_login(user)

        response = self.client.get(reverse("system_settings"))

        self.assertContains(response, "System Settings")
        self.assertContains(response, "Company Name")
        self.assertContains(response, "Default Currency")
        self.assertContains(response, 'value="My CRM"', html=False)
        self.assertContains(response, "Load demo data")
        self.assertNotContains(response, "Open Django Admin")

    def test_system_admin_sees_django_admin_link_on_system_settings_page(self):
        user = create_admin_user(username="system_admin", system_admin=True)
        self.client.force_login(user)

        response = self.client.get(reverse("system_settings"))

        self.assertContains(response, 'href="/admin/"', html=False)
        self.assertContains(response, "Open Django Admin")

    def test_logged_in_user_can_submit_system_settings_and_values_are_used_across_the_app(self):
        user = create_admin_user()
        category = ProductCategory.objects.create(name="Networking")
        product = Product.objects.create(name="Router", category=category)
        service = Service.objects.create(name="Installation", price="250.00")
        service.products.add(product)
        self.client.force_login(user)

        response = self.client.post(
            reverse("system_settings"),
            {
                "company_name": "Northwind Systems",
                "default_currency": "USD",
            },
            follow=True,
        )

        self.assertRedirects(response, reverse("system_settings"))
        self.assertContains(response, "System settings were updated.")

        settings = SystemSettings.get_solo()
        self.assertEqual(settings.company_name, "Northwind Systems")
        self.assertEqual(settings.default_currency, "USD")

        home_response = self.client.get(reverse("home"))
        self.assertContains(home_response, "Northwind Systems")

        services_response = self.client.get(reverse("services"))
        self.assertContains(services_response, "USD 250.00")

        products_response = self.client.get(reverse("products"))
        self.assertContains(products_response, "USD 250.00")

    def test_service_form_uses_current_default_currency_in_price_label(self):
        user = create_admin_user()
        settings = SystemSettings.get_solo()
        settings.default_currency = "EUR"
        settings.save()
        self.client.force_login(user)

        response = self.client.get(reverse("create_service"))

        self.assertContains(response, "Price (EUR)")

    def test_admin_can_load_demo_data_from_system_settings(self):
        user = create_admin_user()
        self.client.force_login(user)

        response = self.client.post(
            reverse("system_settings"),
            {
                "action": "load_demo_data",
            },
            follow=True,
        )

        self.assertRedirects(response, reverse("system_settings"))
        self.assertContains(response, "Demo data refreshed")
        self.assertContains(response, DEMO_PASSWORD)

        self.assertEqual(ProductCategory.objects.filter(name__startswith="Demo ").count(), 3)
        self.assertEqual(Product.objects.filter(name__startswith="Demo ").count(), 10)
        self.assertEqual(Service.objects.filter(name__startswith="Demo ").count(), 6)
        self.assertEqual(
            get_user_model().objects.filter(username__in=DEMO_USERNAMES).count(),
            5,
        )
        self.assertEqual(
            Customer.objects.filter(email__endswith="@demo-customers.example.com").count(),
            10,
        )

        installation = Service.objects.get(name="Demo Installation and Setup")
        self.assertEqual(installation.products.count(), 3)
        self.assertTrue(
            installation.products.filter(name="Demo Edge Router X1").exists()
        )

        system_admin = get_user_model().objects.get(username="demo.sysadmin")
        self.assertTrue(system_admin.is_staff)
        self.assertTrue(system_admin.groups.filter(name=SYSTEM_ADMIN_GROUP).exists())

        admin_user = get_user_model().objects.get(username="demo.admin.sales")
        self.assertTrue(admin_user.groups.filter(name=CRM_ADMIN_GROUP).exists())

        standard_user = get_user_model().objects.get(username="demo.agent.lindi")
        self.assertFalse(standard_user.is_staff)
        self.assertTrue(standard_user.groups.filter(name=CRM_USER_GROUP).exists())
        self.assertTrue(standard_user.check_password(DEMO_PASSWORD))

    def test_loading_demo_data_twice_refreshes_existing_demo_records_without_duplicates(self):
        user = create_admin_user()
        self.client.force_login(user)

        self.client.post(reverse("system_settings"), {"action": "load_demo_data"})

        product = Product.objects.get(name="Demo Edge Router X1")
        product.description = "Changed description"
        product.save(update_fields=["description"])

        service = Service.objects.get(name="Demo Installation and Setup")
        service.products.clear()

        demo_user = get_user_model().objects.get(username="demo.agent.sam")
        demo_user.email = "changed@example.com"
        demo_user.save(update_fields=["email"])

        customer = get_user_model().objects.get(username="demo.admin.sales").customers.get(
            email="avery.mokoena@demo-customers.example.com"
        )
        customer.notes = "Changed notes"
        customer.save(update_fields=["notes"])

        response = self.client.post(
            reverse("system_settings"),
            {
                "action": "load_demo_data",
            },
            follow=True,
        )

        self.assertRedirects(response, reverse("system_settings"))
        self.assertEqual(ProductCategory.objects.filter(name__startswith="Demo ").count(), 3)
        self.assertEqual(Product.objects.filter(name__startswith="Demo ").count(), 10)
        self.assertEqual(Service.objects.filter(name__startswith="Demo ").count(), 6)
        self.assertEqual(
            get_user_model().objects.filter(username__in=DEMO_USERNAMES).count(),
            5,
        )
        self.assertEqual(
            Customer.objects.filter(email__endswith="@demo-customers.example.com").count(),
            10,
        )

        product.refresh_from_db()
        self.assertEqual(
            product.description,
            "Branch-ready router with VPN and traffic shaping support.",
        )

        service.refresh_from_db()
        self.assertEqual(service.products.count(), 3)

        demo_user.refresh_from_db()
        self.assertEqual(demo_user.email, "demo.agent.sam@example.com")
        self.assertTrue(demo_user.check_password(DEMO_PASSWORD))

        refreshed_customer = get_user_model().objects.get(username="demo.admin.sales").customers.get(
            email="avery.mokoena@demo-customers.example.com"
        )
        self.assertEqual(
            refreshed_customer.notes,
            "Interested in a full branch connectivity refresh.",
        )

    def test_non_admin_cannot_trigger_demo_data_load(self):
        user = get_user_model().objects.create_user(
            username="agent",
            password="testpass123",
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("system_settings"),
            {
                "action": "load_demo_data",
            },
        )

        self.assertEqual(response.status_code, 403)
