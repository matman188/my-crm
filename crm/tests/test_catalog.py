from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from crm.models import Product, ProductCategory, Service
from crm.tests.helpers import create_admin_user


class CatalogViewTests(TestCase):
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
        user = create_admin_user()
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
        user = create_admin_user()
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
        user = create_admin_user()
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
        user = create_admin_user()
        networking = ProductCategory.objects.create(name="Networking")
        office = ProductCategory.objects.create(name="Office")
        Product.objects.create(name="Switch", category=networking)
        Product.objects.create(name="Desk", category=office)
        self.client.force_login(user)

        response = self.client.get(reverse("products"), {"q": "network"})

        self.assertContains(response, "Switch")
        self.assertNotContains(response, "Desk")

    def test_products_page_shows_plain_category_and_linked_service_badges(self):
        user = create_admin_user()
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
        user = create_admin_user()
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
        user = create_admin_user()
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
        user = create_admin_user()
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
        user = create_admin_user()
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
        user = create_admin_user()
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
        user = create_admin_user()
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
        user = create_admin_user()
        category = ProductCategory.objects.create(name="Temporary")
        product = Product.objects.create(name="Monitor", category=category)
        self.client.force_login(user)

        response = self.client.post(reverse("delete_product_category", args=[category.id]), follow=True)

        self.assertRedirects(response, reverse("product_categories"))
        product.refresh_from_db()
        self.assertIsNone(product.category)
