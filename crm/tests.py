from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse


class AuthenticationFlowTests(TestCase):
    def test_home_redirects_anonymous_users_to_login(self):
        response = self.client.get(reverse("home"))

        self.assertRedirects(response, "/login/?next=/")

    def test_login_page_renders(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)

    def test_home_shows_sidebar_link_for_logged_in_user(self):
        user = get_user_model().objects.create_user(
            username="agent",
            password="testpass123",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("home"))

        self.assertContains(response, reverse("customers"))

    def test_customers_page_requires_login(self):
        response = self.client.get(reverse("customers"))

        self.assertRedirects(response, "/login/?next=/customers/")
