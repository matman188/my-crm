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

    def test_users_page_requires_login(self):
        response = self.client.get(reverse("users"))

        self.assertRedirects(response, "/login/?next=/users/")

    def test_users_page_shows_create_link_and_existing_users(self):
        admin_user = get_user_model().objects.create_superuser(
            username="crm_admin",
            email="admin@example.com",
            password="adminpass123",
        )
        get_user_model().objects.create_user(
            username="agent",
            email="agent@example.com",
            password="testpass123",
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse("users"))

        self.assertContains(response, reverse("create_user"))
        self.assertContains(response, reverse("change_user_password", args=[admin_user.id]))
        self.assertContains(response, "crm_admin")
        self.assertContains(response, "agent")

    def test_superuser_can_create_user(self):
        admin_user = get_user_model().objects.create_superuser(
            username="crm_admin",
            email="admin@example.com",
            password="adminpass123",
        )
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("create_user"),
            {
                "username": "newagent",
                "email": "newagent@example.com",
                "first_name": "New",
                "last_name": "Agent",
                "is_staff": "on",
                "password1": "safePassword123",
                "password2": "safePassword123",
            },
            follow=True,
        )

        self.assertRedirects(response, reverse("users"))
        created_user = get_user_model().objects.get(username="newagent")
        self.assertEqual(created_user.email, "newagent@example.com")
        self.assertTrue(created_user.is_staff)

    def test_non_superuser_cannot_open_users_page(self):
        user = get_user_model().objects.create_user(
            username="agent",
            password="testpass123",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("users"))

        self.assertEqual(response.status_code, 403)

    def test_superuser_can_edit_user(self):
        admin_user = get_user_model().objects.create_superuser(
            username="crm_admin",
            email="admin@example.com",
            password="adminpass123",
        )
        editable_user = get_user_model().objects.create_user(
            username="agent",
            email="agent@example.com",
            password="testpass123",
        )
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("edit_user", args=[editable_user.id]),
            {
                "username": "agent-updated",
                "email": "updated@example.com",
                "first_name": "Updated",
                "last_name": "User",
                "is_staff": "on",
                "is_active": "on",
            },
            follow=True,
        )

        self.assertRedirects(response, reverse("users"))
        editable_user.refresh_from_db()
        self.assertEqual(editable_user.username, "agent-updated")
        self.assertEqual(editable_user.email, "updated@example.com")
        self.assertTrue(editable_user.is_staff)

    def test_superuser_edit_form_hides_protected_flags_for_superuser(self):
        admin_user = get_user_model().objects.create_superuser(
            username="crm_admin",
            email="admin@example.com",
            password="adminpass123",
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse("edit_user", args=[admin_user.id]))

        self.assertNotContains(response, 'name="is_staff"')
        self.assertNotContains(response, 'name="is_active"')

    def test_superuser_cannot_change_own_staff_or_active_flags_from_edit_form(self):
        admin_user = get_user_model().objects.create_superuser(
            username="crm_admin",
            email="admin@example.com",
            password="adminpass123",
        )
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("edit_user", args=[admin_user.id]),
            {
                "username": "crm_admin_updated",
                "email": "updated-admin@example.com",
                "first_name": "CRM",
                "last_name": "Admin",
                "is_staff": "",
                "is_active": "",
            },
            follow=True,
        )

        self.assertRedirects(response, reverse("users"))
        admin_user.refresh_from_db()
        self.assertEqual(admin_user.username, "crm_admin_updated")
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_active)

    def test_superuser_can_change_user_password(self):
        admin_user = get_user_model().objects.create_superuser(
            username="crm_admin",
            email="admin@example.com",
            password="adminpass123",
        )
        target_user = get_user_model().objects.create_user(
            username="agent",
            email="agent@example.com",
            password="oldpass123",
        )
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("change_user_password", args=[target_user.id]),
            {
                "new_password1": "newStrongPass123",
                "new_password2": "newStrongPass123",
            },
            follow=True,
        )

        self.assertRedirects(response, reverse("users"))
        target_user.refresh_from_db()
        self.assertTrue(target_user.check_password("newStrongPass123"))

    def test_superuser_can_delete_standard_user(self):
        admin_user = get_user_model().objects.create_superuser(
            username="crm_admin",
            email="admin@example.com",
            password="adminpass123",
        )
        deletable_user = get_user_model().objects.create_user(
            username="agent",
            email="agent@example.com",
            password="testpass123",
        )
        self.client.force_login(admin_user)

        response = self.client.post(reverse("delete_user", args=[deletable_user.id]), follow=True)

        self.assertRedirects(response, reverse("users"))
        self.assertFalse(get_user_model().objects.filter(id=deletable_user.id).exists())

    def test_superuser_cannot_delete_superuser(self):
        admin_user = get_user_model().objects.create_superuser(
            username="crm_admin",
            email="admin@example.com",
            password="adminpass123",
        )
        self.client.force_login(admin_user)

        response = self.client.post(reverse("delete_user", args=[admin_user.id]), follow=True)

        self.assertRedirects(response, reverse("users"))
        self.assertTrue(get_user_model().objects.filter(id=admin_user.id).exists())
