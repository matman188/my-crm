from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from crm.models import Product, ProductCategory, Service, SystemSettings
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
