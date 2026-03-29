from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from crm.authz import CRM_ADMIN_GROUP, SYSTEM_ADMIN_GROUP

from .helpers import create_admin_user


class ProfileAndUserManagementTests(TestCase):
    def test_user_can_update_own_profile(self):
        user = get_user_model().objects.create_user(
            username="agent",
            email="agent@example.com",
            password="testpass123",
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("edit_profile"),
            {
                "username": "agent-updated",
                "email": "updated@example.com",
                "first_name": "Alex",
                "last_name": "Morgan",
            },
            follow=True,
        )

        self.assertRedirects(response, reverse("home"))
        user.refresh_from_db()
        self.assertEqual(user.username, "agent-updated")
        self.assertEqual(user.first_name, "Alex")

    def test_create_user_form_explains_access_levels(self):
        admin_user = get_user_model().objects.create_superuser(
            username="crm_admin",
            email="admin@example.com",
            password="adminpass123",
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse("create_user"))

        self.assertContains(response, "Access Level")
        self.assertContains(response, "System Admin: includes Admin access and can sign in to Django admin at /admin/.")

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

    def test_users_page_sorts_alphabetically_by_username(self):
        admin_user = get_user_model().objects.create_superuser(
            username="crm_admin",
            email="admin@example.com",
            password="adminpass123",
        )
        get_user_model().objects.create_user(username="charlie", password="testpass123")
        get_user_model().objects.create_user(username="Alpha", password="testpass123")
        get_user_model().objects.create_user(username="bravo", password="testpass123")
        self.client.force_login(admin_user)

        response = self.client.get(reverse("users"))
        content = response.content.decode()

        self.assertLess(content.index("@Alpha"), content.index("@bravo"))
        self.assertLess(content.index("@bravo"), content.index("@charlie"))

    def test_users_page_can_search_for_user(self):
        admin_user = get_user_model().objects.create_superuser(
            username="crm_admin",
            email="admin@example.com",
            password="adminpass123",
        )
        get_user_model().objects.create_user(
            username="agent-jane",
            first_name="Jane",
            email="jane@example.com",
            password="testpass123",
        )
        get_user_model().objects.create_user(
            username="agent-john",
            first_name="John",
            email="john@example.com",
            password="testpass123",
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse("users"), {"q": "jane"})

        self.assertContains(response, "agent-jane")
        self.assertNotContains(response, "agent-john")

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
                "access_level": "system_admin",
                "password1": "safePassword123",
                "password2": "safePassword123",
            },
            follow=True,
        )

        self.assertRedirects(response, reverse("users"))
        created_user = get_user_model().objects.get(username="newagent")
        self.assertEqual(created_user.email, "newagent@example.com")
        self.assertTrue(created_user.is_staff)
        self.assertTrue(created_user.groups.filter(name=SYSTEM_ADMIN_GROUP).exists())

    def test_non_admin_cannot_open_users_page(self):
        user = get_user_model().objects.create_user(
            username="agent",
            password="testpass123",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("users"))

        self.assertEqual(response.status_code, 403)

    def test_admin_can_open_users_page(self):
        user = create_admin_user()
        self.client.force_login(user)

        response = self.client.get(reverse("users"))

        self.assertEqual(response.status_code, 200)

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
                "access_level": "admin",
                "is_active": "on",
            },
            follow=True,
        )

        self.assertRedirects(response, reverse("users"))
        editable_user.refresh_from_db()
        self.assertEqual(editable_user.username, "agent-updated")
        self.assertEqual(editable_user.email, "updated@example.com")
        self.assertFalse(editable_user.is_staff)
        self.assertTrue(editable_user.groups.filter(name=CRM_ADMIN_GROUP).exists())

    def test_admin_cannot_grant_system_admin_access(self):
        admin_user = create_admin_user()
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("create_user"),
            {
                "username": "newsys",
                "email": "newsys@example.com",
                "first_name": "New",
                "last_name": "Sys",
                "access_level": "system_admin",
                "password1": "safePassword123",
                "password2": "safePassword123",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a valid choice")
        self.assertFalse(get_user_model().objects.filter(username="newsys").exists())

    def test_superuser_edit_form_hides_protected_flags_for_superuser(self):
        admin_user = get_user_model().objects.create_superuser(
            username="crm_admin",
            email="admin@example.com",
            password="adminpass123",
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse("edit_user", args=[admin_user.id]))

        self.assertNotContains(response, 'name="access_level"')
        self.assertNotContains(response, 'name="is_active"')

    def test_superuser_cannot_change_own_access_level_or_active_flag_from_edit_form(self):
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
