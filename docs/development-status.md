# Development Status

Updated: 14 November 2026

The [scope of work](scope-of-work.md) describes the intended complete workflow.
This file records what is implemented.

## Draft service orders: implemented

Open **Orders** in the sidebar, then **Create order**.

- Type into the customer field and click a filtered result, or use the arrow keys
  and Enter. **Create New** opens a customer modal with **Use customer** and
  **Cancel** actions. New customers are saved together with the order.
- Add products as individual order items with optional notes, a deadline date,
  and optional deadline time. Item descriptions and product quantities are not
  part of the form.
- Add services to each item. The same service can be added several times, with
  separate optional internal notes and quantities for every occurrence.
- Add order-wide extras from global services and general internal order notes.
- Set the optional **Assignee** and order notes in **Order details** at the bottom.
- Preview individual charges, item subtotals, and the order total while editing.
- Save and reopen drafts using their `SO-000001` style references. Search orders
  by reference, customer, assigned user, or order notes.

### Pricing and service applicability

The first implementation uses these explicit rules:

- Every service charge is service quantity × captured unit price. Quantities are
  entered only on services. Every repeated service row contributes separately.
- Order-wide extras use the same quantity × unit price rule.
- Product units follow catalog setup, for example a product named "Ballet shoes
  (pair)". There is no sewing-specific shoe/pair rule in the order code.
- A service linked to products is available only for those products. A service
  without product links is global and is available for any item or as an
  order-wide extra. This meaning is also explained on the service catalog form.
- Prices come from the server's catalog, not submitted browser totals. A service's
  price is captured when its charge is saved and retained on later edits. Changing
  the selected service captures the replacement service's current price.
- Each draft retains its creation currency if the business default changes.
  Multi-currency catalogs and currency conversion are not implemented.

This quantity rule reflects the confirmed form simplification (scope decision
D03). Migration 0008 converts any earlier product quantities into service
quantities to preserve totals, moves old item descriptions into item notes, and
invalidates stale edits before removing the redundant fields.

### Permissions and data integrity

- Existing CRM User, Admin, and System Admin groups can view, create, and edit
  drafts, including optional assignment. Fine-grained worker/supervisor workflow
  permissions remain future work.
- Creating a customer inline also requires the existing customer creation permission.
- Order/customer/item/service changes save in one transaction. Invalid submissions
  do not leave a partial order or customer behind.
- Editing an outdated revision is rejected with a message to reload, rather than
  overwriting a newer save. IDs from other orders/items are rejected.
- Customer, product, and service deletion is blocked with a useful message if an
  order references the record.
- Up to 50 items per draft and 50 service occurrences per item or general-extra
  section are supported. Service quantities must be positive whole numbers.
- A saved draft requires a customer, at least one item, a deadline date on each
  item, and at least one service per item. Deadline time is optional.

### Local setup and verification

Apply the new migration after pulling this change:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

JavaScript must be enabled for adding items/services, customer filtering, and
live totals. Forms and totals are validated again on the server when saving.

Validation: 73 Django tests pass, including 23 order workflow/data-migration tests
covering the simplified form, service-only quantities, and preservation of earlier
draft totals and notes. Django's
system check, the new Python code's Ruff checks, and JavaScript syntax checks pass.
Authenticated HTTP checks of the live Orders list and create form pass, and both
the order JavaScript and stylesheet are served successfully. Initial form field
IDs are unique and the deadline time is optional in the rendered form.
Browser automation was unavailable during this implementation; visual and
interactive browser acceptance remains to be checked.

## Subsequent milestones

Order confirmation, work progress, delivery tracking, invoices/PDF/email,
full-payment recording, closure/reopening, and operational/financial dashboards
and reports are not implemented yet. Saving a draft does not issue an invoice.
