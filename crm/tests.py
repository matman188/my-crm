from decimal import Decimal

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from crm.models import Customer, Product, ProductCategory, Service, SystemSettings
from crm.roles import (
    ACCESS_LEVEL_ADMIN,
    ACCESS_LEVEL_SYSTEM_ADMIN,
    CRM_ADMIN_GROUP,
    SYSTEM_ADMIN_GROUP,
    assign_access_level,
)


class AuthenticationFlowTests(TestCase):
    def create_admin_user(self, username="admin_agent", system_admin=False):
        user = get_user_model().objects.create_user(
            username=username,
            password="testpass123",
        )
        assign_access_level(
            user,
            ACCESS_LEVEL_SYSTEM_ADMIN if system_admin else ACCESS_LEVEL_ADMIN,
        )
        return user

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
        user = self.create_admin_user(username="admin_agent")
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

    def test_customers_page_requires_login(self):
        response = self.client.get(reverse("customers"))

        self.assertRedirects(response, "/login/?next=/customers/")

    def test_customers_page_shows_sorted_customer_list(self):
        user = get_user_model().objects.create_user(
            username="agent",
            password="testpass123",
        )
        Customer.objects.create(first_name="Charlie", owner=user)
        Customer.objects.create(first_name="alice", owner=user)
        Customer.objects.create(first_name="Bravo", owner=user)
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
        Customer.objects.create(first_name="Jane", company="Acme", owner=user)
        Customer.objects.create(first_name="John", company="Globex", owner=user)
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
        customer = Customer.objects.create(first_name="Jane", last_name="Doe", owner=user)
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

        response = self.client.post(reverse("delete_customer", args=[customer.id]), follow=True)

        self.assertRedirects(response, reverse("customers"))
        self.assertFalse(Customer.objects.filter(id=customer.id).exists())

    def test_product_categories_page_requires_login(self):
        response = self.client.get(reverse("product_categories"))

        self.assertRedirects(response, "/login/?next=/product-categories/")

    def test_non_admin_cannot_open_product_categories_page(self):
        user = get_user_model().objects.create_user(
            username="agent",
            password="testpass123",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("product_categories"))

        self.assertEqual(response.status_code, 403)

    def test_logged_in_user_can_create_product_category(self):
        user = self.create_admin_user()
        self.client.force_login(user)

        response = self.client.post(
            reverse("create_product_category"),
            {
                "name": "Electronics",
                "description": "Devices and equipment",
            },
            follow=True,
        )

        self.assertRedirects(response, reverse("product_categories"))
        self.assertTrue(ProductCategory.objects.filter(name="Electronics").exists())

    def test_logged_in_user_can_create_product_without_category(self):
        user = self.create_admin_user()
        self.client.force_login(user)

        response = self.client.post(
            reverse("create_product"),
            {
                "name": "Standalone Product",
                "category": "",
                "description": "No category needed",
            },
            follow=True,
        )

        self.assertRedirects(response, reverse("products"))
        product = Product.objects.get(name="Standalone Product")
        self.assertIsNone(product.category)

    def test_logged_in_user_can_create_product_with_category(self):
        user = self.create_admin_user()
        category = ProductCategory.objects.create(name="Hardware")
        self.client.force_login(user)

        response = self.client.post(
            reverse("create_product"),
            {
                "name": "Router",
                "category": str(category.id),
                "description": "Network router",
            },
            follow=True,
        )

        self.assertRedirects(response, reverse("products"))
        product = Product.objects.get(name="Router")
        self.assertEqual(product.category, category)

    def test_products_page_can_search_by_category_name(self):
        user = self.create_admin_user()
        networking = ProductCategory.objects.create(name="Networking")
        office = ProductCategory.objects.create(name="Office")
        Product.objects.create(name="Switch", category=networking)
        Product.objects.create(name="Desk", category=office)
        self.client.force_login(user)

        response = self.client.get(reverse("products"), {"q": "network"})

        self.assertContains(response, "Switch")
        self.assertNotContains(response, "Desk")

    def test_products_page_shows_plain_category_and_linked_service_badges(self):
        user = self.create_admin_user()
        category = ProductCategory.objects.create(name="Networking")
        product = Product.objects.create(name="Router", category=category)
        installation = Service.objects.create(name="Installation", price="150.00")
        support = Service.objects.create(name="Support", price="75.00")
        installation.products.add(product)
        support.products.add(product)
        self.client.force_login(user)

        response = self.client.get(reverse("products"))

        self.assertContains(response, "Networking")
        self.assertNotContains(response, '<span class="role-badge">Networking</span>', html=True)
        self.assertContains(response, "Installation")
        self.assertContains(response, "150.00")
        self.assertContains(response, "Support")
        self.assertContains(response, "75.00")
        self.assertContains(response, 'class="linked-service-badge"')

    def test_logged_in_user_can_create_service_and_link_products(self):
        user = self.create_admin_user()
        router = Product.objects.create(name="Router")
        switch = Product.objects.create(name="Switch")
        self.client.force_login(user)

        response = self.client.post(
            reverse("create_service"),
            {
                "name": "Installation",
                "price": "1500.00",
                "products": [str(router.id), str(switch.id)],
                "description": "Setup service",
            },
            follow=True,
        )

        self.assertRedirects(response, reverse("services"))
        service = Service.objects.get(name="Installation")
        self.assertEqual(service.price, Decimal("1500.00"))
        self.assertQuerySetEqual(
            service.products.order_by("name"),
            Product.objects.filter(id__in=[router.id, switch.id]).order_by("name"),
            transform=lambda product: product,
        )

    def test_logged_in_user_can_create_service_without_linked_products(self):
        user = self.create_admin_user()
        self.client.force_login(user)

        response = self.client.post(
            reverse("create_service"),
            {
                "name": "Remote Support",
                "price": "250.00",
                "description": "Ad hoc support",
            },
            follow=True,
        )

        self.assertRedirects(response, reverse("services"))
        service = Service.objects.get(name="Remote Support")
        self.assertEqual(service.products.count(), 0)

    def test_service_form_groups_products_under_category_headers(self):
        user = self.create_admin_user()
        category = ProductCategory.objects.create(name="Networking")
        Product.objects.create(name="Router", category=category)
        Product.objects.create(name="Audit", category=None)
        self.client.force_login(user)

        response = self.client.get(reverse("create_service"))

        self.assertContains(response, 'class="product-picker-group"')
        self.assertContains(response, "Networking")
        self.assertContains(response, "No category")
        self.assertContains(response, "Router")
        self.assertContains(response, "Audit")
        self.assertContains(response, "Leave all unchecked")
        self.assertContains(response, 'class="product-group-toggle"')
        self.assertContains(response, "Select all")

    def test_services_page_can_search_by_linked_product(self):
        user = self.create_admin_user()
        router = Product.objects.create(name="Router")
        unrelated = Product.objects.create(name="Desk")
        installation = Service.objects.create(name="Installation", price="100.00")
        installation.products.add(router)
        delivery = Service.objects.create(name="Delivery", price="50.00")
        delivery.products.add(unrelated)
        self.client.force_login(user)

        response = self.client.get(reverse("services"), {"q": "router"})

        self.assertContains(response, "Installation")
        self.assertNotContains(response, "Delivery")

    def test_services_page_shows_category_and_product_for_linked_products(self):
        user = self.create_admin_user()
        category = ProductCategory.objects.create(name="Networking")
        router = Product.objects.create(name="Router", category=category)
        audit = Product.objects.create(name="Audit")
        installation = Service.objects.create(name="Installation", price="100.00")
        installation.products.add(router, audit)
        self.client.force_login(user)

        response = self.client.get(reverse("services"))

        self.assertContains(response, "Networking")
        self.assertContains(response, "Router")
        self.assertContains(response, "No category")
        self.assertContains(response, "Audit")
        self.assertContains(response, 'class="linked-product-badge"')
        self.assertContains(response, 'class="linked-product-category"')

    def test_services_page_orders_linked_products_by_category_then_product(self):
        user = self.create_admin_user()
        appliances = ProductCategory.objects.create(name="Appliances")
        networking = ProductCategory.objects.create(name="Networking")
        toaster = Product.objects.create(name="Toaster", category=appliances)
        switch = Product.objects.create(name="Switch", category=networking)
        audit = Product.objects.create(name="Audit")
        installation = Service.objects.create(name="Installation", price="100.00")
        installation.products.add(audit, switch, toaster)
        self.client.force_login(user)

        response = self.client.get(reverse("services"))
        content = response.content.decode()

        self.assertLess(content.index("Appliances"), content.index("Networking"))
        self.assertLess(content.index("Networking"), content.index("No category"))

    def test_deleting_category_leaves_product_without_category(self):
        user = self.create_admin_user()
        category = ProductCategory.objects.create(name="Temporary")
        product = Product.objects.create(name="Monitor", category=category)
        self.client.force_login(user)

        response = self.client.post(reverse("delete_product_category", args=[category.id]), follow=True)

        self.assertRedirects(response, reverse("product_categories"))
        product.refresh_from_db()
        self.assertIsNone(product.category)

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
        user = self.create_admin_user()
        self.client.force_login(user)

        response = self.client.get(reverse("system_settings"))

        self.assertContains(response, "System Settings")
        self.assertContains(response, "Company Name")
        self.assertContains(response, "Default Currency")
        self.assertContains(response, 'value="My CRM"', html=False)
        self.assertNotContains(response, "Open Django Admin")

    def test_system_admin_sees_django_admin_link_on_system_settings_page(self):
        user = self.create_admin_user(username="system_admin", system_admin=True)
        self.client.force_login(user)

        response = self.client.get(reverse("system_settings"))

        self.assertContains(response, 'href="/admin/"', html=False)
        self.assertContains(response, "Open Django Admin")

    def test_logged_in_user_can_submit_system_settings_and_values_are_used_across_the_app(self):
        user = self.create_admin_user()
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
        user = self.create_admin_user()
        settings = SystemSettings.get_solo()
        settings.default_currency = "EUR"
        settings.save()
        self.client.force_login(user)

        response = self.client.get(reverse("create_service"))

        self.assertContains(response, "Price (EUR)")

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
        user = self.create_admin_user()
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
        admin_user = self.create_admin_user()
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
