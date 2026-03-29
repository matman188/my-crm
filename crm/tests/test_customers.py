from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from crm.models import Customer


class CustomerViewTests(TestCase):
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
