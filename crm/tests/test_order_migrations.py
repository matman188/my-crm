from datetime import date
from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ServiceQuantityMigrationTests(TransactionTestCase):
    def test_legacy_product_quantities_and_labels_are_preserved(self):
        before = [("crm", "0007_serviceorder_orderitem_orderservicecharge_and_more")]
        after = [("crm", "0008_remove_orderitem_order_item_quantity_positive_and_more")]
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(after))
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
