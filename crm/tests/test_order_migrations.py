from datetime import date
from decimal import Decimal

from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ServiceQuantityMigrationTests(TransactionTestCase):
    @staticmethod
    def restore_latest_schema():
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_archiving_migration_keeps_existing_customers_active_and_preserves_history(
        self,
    ):
        before = [("crm", "0011_require_customer_contact_details_unique_email")]
        after = [("crm", "0012_customer_archiving")]
        self.addCleanup(self.restore_latest_schema)
        executor = MigrationExecutor(connection)
        executor.migrate(before)
        old = executor.loader.project_state(before).apps
        customer = old.get_model("crm", "Customer").objects.create(
            first_name="Alex",
            last_name="Smith",
            email="alex@example.com",
            primary_phone="0123456789",
            notes="Keep notes",
        )
        order = old.get_model("crm", "ServiceOrder").objects.create(
            customer=customer, currency="ZAR", status="complete"
        )
        before_customer = (
            old.get_model("crm", "Customer").objects.values().get(pk=customer.pk)
        )
        before_order = (
            old.get_model("crm", "ServiceOrder").objects.values().get(pk=order.pk)
        )
        executor = MigrationExecutor(connection)
        executor.migrate(after)
        current = executor.loader.project_state(after).apps
        migrated = (
            current.get_model("crm", "Customer").objects.values().get(pk=customer.pk)
        )
        self.assertFalse(migrated.pop("is_archived"))
        self.assertEqual(migrated, before_customer)
        self.assertEqual(
            current.get_model("crm", "ServiceOrder").objects.values().get(pk=order.pk),
            before_order,
        )

    def test_legacy_product_quantities_and_labels_are_preserved(self):
        before = [("crm", "0007_serviceorder_orderitem_orderservicecharge_and_more")]
        after = [("crm", "0008_remove_orderitem_order_item_quantity_positive_and_more")]
        self.addCleanup(self.restore_latest_schema)
        executor = MigrationExecutor(connection)
        executor.migrate(before)
        old = executor.loader.project_state(before).apps
        customer = old.get_model("crm", "Customer").objects.create(first_name="Dancer")
        product = old.get_model("crm", "Product").objects.create(name="Shoes")
        service = old.get_model("crm", "Service").objects.create(
            name="Sew", price="10.25"
        )
        order = old.get_model("crm", "ServiceOrder").objects.create(
            customer=customer, currency="ZAR"
        )
        item = old.get_model("crm", "OrderItem").objects.create(
            order=order,
            product=product,
            quantity=2,
            description="Blue pair",
            due_date=date(2026, 11, 20),
            notes="Keep ribbons",
        )
        Charge = old.get_model("crm", "OrderServiceCharge")
        charge = Charge.objects.create(
            order=order,
            item=item,
            service=service,
            quantity=3,
            unit_price="10.25",
            notes="Left side",
        )
        general = Charge.objects.create(
            order=order, service=service, quantity=1, unit_price="50.00"
        )
        executor = MigrationExecutor(connection)
        executor.migrate(after)
        current = executor.loader.project_state(after).apps
        item = current.get_model("crm", "OrderItem").objects.get(pk=item.pk)
        charge = current.get_model("crm", "OrderServiceCharge").objects.get(
            pk=charge.pk
        )
        general = current.get_model("crm", "OrderServiceCharge").objects.get(
            pk=general.pk
        )
        self.assertFalse(hasattr(item, "quantity"))
        self.assertFalse(hasattr(item, "description"))
        self.assertEqual(item.notes, "Blue pair\n\nKeep ribbons")
        self.assertEqual(charge.quantity, 6)
        self.assertEqual(charge.notes, "Left side")
        self.assertEqual(general.quantity, 1)
        self.assertEqual(
            charge.quantity * charge.unit_price + general.quantity * general.unit_price,
            Decimal("111.50"),
        )
        self.assertEqual(
            current.get_model("crm", "ServiceOrder").objects.get(pk=order.pk).revision,
            2,
        )

    def test_existing_orders_receive_safe_workflow_defaults(self):
        before = [
            ("crm", "0008_remove_orderitem_order_item_quantity_positive_and_more")
        ]
        self.addCleanup(self.restore_latest_schema)
        executor = MigrationExecutor(connection)
        executor.migrate(before)
        old = executor.loader.project_state(before).apps
        customer = old.get_model("crm", "Customer").objects.create(
            first_name="Existing customer"
        )
        order = old.get_model("crm", "ServiceOrder").objects.create(
            customer=customer, currency="USD", revision=7, notes="Keep these notes"
        )
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        executor.migrate(latest)
        current = executor.loader.project_state(latest).apps
        migrated = current.get_model("crm", "ServiceOrder").objects.get(pk=order.pk)
        self.assertEqual(migrated.status, "draft")
        self.assertEqual(migrated.payment_status, "unpaid")
        self.assertFalse(migrated.collected)
        self.assertEqual(migrated.currency, "USD")
        self.assertEqual(migrated.revision, 7)
        self.assertEqual(migrated.notes, "Keep these notes")

    def test_refund_migration_preserves_orders_and_extends_the_constraint(self):
        before = [
            ("crm", "0009_serviceorder_collected_serviceorder_payment_status_and_more")
        ]
        after = [("crm", "0010_add_refunded_payment_status")]
        self.addCleanup(self.restore_latest_schema)
        executor = MigrationExecutor(connection)
        executor.migrate(before)
        old = executor.loader.project_state(before).apps
        customer = old.get_model("crm", "Customer").objects.create(
            first_name="Customer"
        )
        Order = old.get_model("crm", "ServiceOrder")
        unpaid = Order.objects.create(customer=customer, currency="ZAR")
        paid = Order.objects.create(
            customer=customer,
            currency="USD",
            status="complete",
            payment_status="paid",
            collected=True,
            revision=7,
            notes="Keep refund context",
        )
        service = old.get_model("crm", "Service").objects.create(
            name="Service", price="25.00"
        )
        charge = old.get_model("crm", "OrderServiceCharge").objects.create(
            order=paid,
            service=service,
            quantity=2,
            unit_price="10.25",
            notes="Keep instructions",
        )
        orders_before = list(Order.objects.order_by("pk").values())
        charge_before = (
            old.get_model("crm", "OrderServiceCharge")
            .objects.values()
            .get(pk=charge.pk)
        )
        executor = MigrationExecutor(connection)
        executor.migrate(after)
        current = executor.loader.project_state(after).apps
        Order = current.get_model("crm", "ServiceOrder")
        self.assertEqual(list(Order.objects.order_by("pk").values()), orders_before)
        self.assertEqual(
            current.get_model("crm", "OrderServiceCharge")
            .objects.values()
            .get(pk=charge.pk),
            charge_before,
        )
        Order.objects.filter(pk=paid.pk).update(payment_status="refunded")
        self.assertEqual(Order.objects.get(pk=paid.pk).payment_status, "refunded")
        self.assertEqual(Order.objects.get(pk=unpaid.pk).payment_status, "unpaid")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Order.objects.filter(pk=paid.pk).update(payment_status="partial")

    def test_customer_contact_migration_preserves_records_and_enforces_unique_email(
        self,
    ):
        before = [("crm", "0010_add_refunded_payment_status")]
        after = [("crm", "0011_require_customer_contact_details_unique_email")]
        self.addCleanup(self.restore_latest_schema)
        executor = MigrationExecutor(connection)
        executor.migrate(before)
        old = executor.loader.project_state(before).apps
        Customer = old.get_model("crm", "Customer")
        customer = Customer.objects.create(
            first_name="Alex",
            last_name="Smith",
            email="Alex@Example.com",
            primary_phone="0123456789",
            notes="Keep special customer notes",
        )
        order = old.get_model("crm", "ServiceOrder").objects.create(
            customer=customer,
            currency="ZAR",
            notes="Separate order instructions",
            revision=5,
        )
        customer_before = Customer.objects.values().get(pk=customer.pk)
        order_before = (
            old.get_model("crm", "ServiceOrder").objects.values().get(pk=order.pk)
        )
        executor = MigrationExecutor(connection)
        executor.migrate(after)
        current = executor.loader.project_state(after).apps
        Customer = current.get_model("crm", "Customer")
        self.assertEqual(Customer.objects.values().get(pk=customer.pk), customer_before)
        self.assertEqual(
            current.get_model("crm", "ServiceOrder").objects.values().get(pk=order.pk),
            order_before,
        )
        for name in ("first_name", "last_name", "email", "primary_phone"):
            self.assertFalse(Customer._meta.get_field(name).blank)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Customer.objects.create(
                first_name="Other",
                last_name="Customer",
                email=" ALEX@example.com ",
                primary_phone="0987654321",
            )
