from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from crm.models import SystemSettings
from crm.tests.helpers import create_admin_user


class AuthenticationFlowTests(TestCase):
    def test_home_redirects_anonymous_users_to_login(self):
        response = self.client.get(reverse("home"))

        self.assertRedirects(response, "/login/?next=/")

    def test_login_page_renders(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)

    def test_login_page_uses_configured_company_name(self):
        settings = SystemSettings.get_solo()
        settings.company_name = "Studio & Co."
        settings.save()

        response = self.client.get(reverse("login"))

        self.assertContains(response, "Studio &amp; Co.")
        self.assertContains(response, 'autocomplete="username"')
        self.assertContains(response, 'autocomplete="current-password"')

    def test_login_accepts_csrf_protected_form_and_retains_next_destination(self):
        user = get_user_model().objects.create_user(
            username="sign_in_user", password="ExamplePass123!"
        )
        client = Client(enforce_csrf_checks=True)
        response = client.get(reverse("login"), {"next": "/profile/"})
        self.assertContains(response, 'name="next" value="/profile/"')

        response = client.post(
            reverse("login"),
            {
                "username": user.username,
                "password": "ExamplePass123!",
                "next": "/profile/",
                "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
            },
        )

        self.assertRedirects(response, "/profile/")
        self.assertEqual(client.session["_auth_user_id"], str(user.pk))

    def test_invalid_login_preserves_username_but_not_password(self):
        get_user_model().objects.create_user(
            username="sign_in_user", password="ExamplePass123!"
        )

        response = self.client.post(
            reverse("login"),
            {
                "username": "sign_in_user",
                "password": "IncorrectPassword123!",
                "next": "/profile/",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'role="alert"')
        self.assertContains(response, 'value="sign_in_user"')
        self.assertContains(response, 'name="next" value="/profile/"')
        self.assertNotContains(response, "IncorrectPassword123!")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_does_not_redirect_to_an_external_destination(self):
        get_user_model().objects.create_user(
            username="sign_in_user", password="ExamplePass123!"
        )

        response = self.client.post(
            reverse("login"),
            {
                "username": "sign_in_user",
                "password": "ExamplePass123!",
                "next": "https://external.example.com/",
            },
        )

        self.assertRedirects(response, "/")

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
