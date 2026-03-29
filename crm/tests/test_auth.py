from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from crm.tests.helpers import create_admin_user


class AuthenticationFlowTests(TestCase):
    def test_home_redirects_anonymous_users_to_login(self):
        response = self.client.get(reverse("home"))

        self.assertRedirects(response, "/login/?next=/")

    def test_login_page_renders(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)

    def test_home_hides_admin_navigation_for_non_admin_user(self):
        user = get_user_model().objects.create_user(
            username="agent",
            first_name="Alex",
            password="testpass123",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("home"))

        self.assertContains(response, reverse("customers"))
        self.assertNotContains(response, "Configuration")
        self.assertNotContains(response, reverse("system_settings"))
        self.assertContains(response, "My CRM")
        self.assertContains(response, "Alex")
        self.assertContains(response, reverse("edit_profile"))

    def test_home_shows_configuration_and_system_settings_for_staff_user(self):
        user = create_admin_user(username="admin_agent")
        user.first_name = "Admin"
        user.save(update_fields=["first_name"])
        self.client.force_login(user)

        response = self.client.get(reverse("home"))

        self.assertContains(response, "Configuration")
        self.assertContains(response, reverse("products"))
        self.assertContains(response, reverse("product_categories"))
        self.assertContains(response, reverse("services"))
        self.assertContains(response, reverse("system_settings"))
        self.assertContains(response, reverse("users"))

    def test_home_shows_users_link_for_superuser(self):
        user = get_user_model().objects.create_superuser(
            username="crm_admin",
            email="admin@example.com",
            password="adminpass123",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("home"))

        self.assertContains(response, "Configuration")
        self.assertContains(response, reverse("users"))
