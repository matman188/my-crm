# Development Status

Updated: 15 November 2026

The [scope of work](scope-of-work.md) describes the intended complete workflow.
This file records what is implemented.

## Service orders: implemented

Open **Orders** in the sidebar, then **Create order**.

- Type into the customer field and click a filtered result, or use the arrow keys
  and Enter. **Create New** opens a customer modal with **Use customer** and
  **Cancel** actions. New customers are saved together with the order.
- In Draft, **Edit Customer** opens the selected customer's details in the same
  modal. **Save customer** updates the existing customer immediately without
  saving, submitting, or reloading the order. The selected label and Customer
  Notes refresh, while unsaved order fields stay intact. Its owner and identity
  are retained. Cancel/Escape discards edits that have not been saved. Customer
  creation still saves with the order. Customer-change and order-edit/create
  permissions are required; editing remains unavailable after submission.
- Customer forms, Django admin, and the order modal require First name, Last
  name, Email, and Primary phone. The app forms mark these with *. Email is
  trimmed and lowercased on save, and a database constraint rejects case/whitespace
  duplicates. Editing a customer can retain its own email. Duplicate-save races
  return an email error without partial customer/order changes.
- The customer directory displays an Orders count instead of Owner. Existing
  customer forms show Total Orders and Open Orders with View Orders. Total
  includes every order stage; Open includes Draft and In Progress, independently
  of payment or collection. View Orders and the directory count link open the
  orders list with an exact customer filter, retained during filtering/paging.
  Links respect order-view permission. Creator/owner metadata is retained
  internally, with Owner removed from customer-facing lists and the admin list.
- Existing customer edit pages show Archive or Restore beside Save, with a
  confirmation modal. Archiving retains the customer, email, notes, order counts,
  and history. The directory defaults to Active, with Archived and All filters;
  archived records remain directly accessible and can be restored. These actions
  require customer-change permission, POST, and CSRF.
- Archived customers are excluded from new-order choices on both the client and
  server. Existing orders retain their customer and can continue through every
  stage. A saved order's current archived customer remains available for display
  and saving; it is not offered in the search dropdown. Archive status is
  independent of order/payment/collection status. Emails stay unique across
  active and archived customers, and contact saves do not reset archive status.
- Customer edit pages without linked orders show a smaller Delete button beside Save. A
  separate Delete customer modal names the persisted customer and focuses Cancel.
  Confirming sends a CSRF-protected delete request; Cancel or Escape returns to
  the form. Required-field errors do not block deletion. Customers referenced by
  orders remain protected; Delete is hidden when orders exist. New customer forms
  do not show Delete, Archive, or Restore.
- Customer Notes appear as read-only plain text below customer selection in all
  order stages. They use the current customer record, remain separate from Order
  Notes, and update on selection or inline creation. Cancelling inline customer
  edits restores the previous notes; line breaks are preserved.
- Add products as individual order items with optional notes, a deadline date,
  and optional deadline time. Item descriptions and product quantities are not
  part of the form.
- Add services to each item. The same service can be added several times, with
  separate optional internal notes and quantities for every occurrence.
- Add order-wide extras from global services and general internal order notes.
- The order heading shows the current status in a labelled, colour-coded badge
  beside a labelled total with its currency. The four-stage banner is removed.
  Use the stage-specific action buttons to move the order forward, cancel,
  reopen, or restore it. Existing orders use an Order heading and View list link.
- The same action buttons appear beside the order heading and below the total,
  in the same order and share one template. Draft deletion uses its own form so
  unfinished edits do not block deletion.
- Submit, Mark complete, Cancel order, Return to draft, Reopen, Restore to draft,
  Delete draft, and Discard show action-specific confirmation modals that match
  the app. The heading and confirmation button name the selected action. Cancel
  has initial focus; Cancel or Escape dismisses the modal and
  leaves entered changes on screen. Confirming revalidates and submits the
  original action, or follows Discard. Save buttons do not prompt.
- **Order Details** is at the top, with **Assigned To**, **Collected**, **Payment
  status**, and order notes. New orders default to Draft, not collected, and Unpaid.
- **Assign to Me** beside Assigned To selects the signed-in user. Save or use a
  stage action to persist the selection with the other changes. It is disabled
  in Draft and Cancelled, along with Assigned To and Payment status.
- Drafts allow editing the customer, items, services, and order notes. **Submit**
  saves the draft and moves it to In Progress. Assigned To and Payment status
  become editable after submission; changes posted while Draft are ignored.
- In Progress orders allow deadline dates, optional times, and internal notes at
  order, item, and service/extra level to be updated. Customer selection, products,
  services, quantities, prices, and adding/removing rows remain locked. These
  operational edits preserve captured charges, currency, and totals.
- Use Return to draft (or Restore to draft for a cancelled order) to edit customer
  selection, products, and services again. Complete and Cancelled also lock
  deadlines and item/service notes; a Complete order must be reopened to In
  Progress to edit those. Cancelled permits only Order Notes, for example a
  cancellation reason, with a Save notes button. Assigned To, Assign to Me, and
  Payment status are editable only in In Progress and Complete. Collected is
  editable only in Complete.
- Order Notes can be updated or cleared in every state, including Complete,
  without reopening the order. Complete uses Save changes for notes, collection
  and payment; deadline and item/service note locks still apply.
- Payment status supports Unpaid, Paid, and Refunded. Refunded is a manual status
  indicator, with a distinct badge and list filter; it preserves order charges,
  totals, work status, and collection state.
- Saved drafts show **Delete draft**, with a confirmation prompt. Unsaved drafts
  show **Discard**. In Progress orders still use **Cancel order**, preserving
  their record as Cancelled.
- An assigned user is required before marking an order Complete.
- Preview individual charges, item subtotals, and the order total while editing.
  The total is shown in both the header and bottom action area, and both update
  as draft charges change.
- Save and edit orders in every status using their `SO-000001` style references.
  Search by reference, customer, assigned user, or order notes, and filter by Status,
  Collected, and Payment status. Filters are retained when paging through results.
- The Orders list uses its main Search field for customer names (including full
  names), email, company, and phone numbers. It has no separate customer dropdown.
  View Orders links retain an exact customer-ID filter as a hidden field, with an
  Orders for label, so customer history stays scoped while filtering and paging.

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
- Each order retains its creation currency if the business default changes.
  Multi-currency catalogs and currency conversion are not implemented.

This quantity rule reflects the confirmed form simplification (scope decision
D03). Migration 0008 converts any earlier product quantities into service
quantities to preserve totals, moves old item descriptions into item notes, and
invalidates stale edits before removing the redundant fields.

### Permissions and data integrity

- Existing CRM User, Admin, and System Admin groups can view, create, and edit
  orders, including assignment and the three workflow fields. Updating these
  fields requires the existing order change permission; finer worker/supervisor
  and payment permissions remain future work.
- Creating a customer inline also requires the existing customer creation permission.
- Order/customer/item/service changes save in one transaction. Invalid submissions
  do not leave a partial order or customer behind.
- Editing an outdated revision is rejected with a message to reload, rather than
  overwriting a newer save. IDs from other orders/items are rejected.
- Customer, product, and service deletion is blocked with a useful message if an
  order references the record.
- Up to 50 items per order and 50 service occurrences per item or general-extra
  section are supported. Service quantities must be positive whole numbers.
- A saved order requires a customer, at least one item, a deadline date on each
  item, and at least one service per item. Deadline time is optional.

### Local setup and verification

Apply the new migration after pulling this change:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

JavaScript must be enabled for adding items/services, customer filtering, and
live totals. Forms and totals are validated again on the server when saving.

Order milestone validation: all 73 tests passed at completion, including 23 order
workflow/data-migration tests covering the simplified form, service-only quantities,
and preservation of earlier draft totals and notes. Django's
system check, the new Python code's Ruff checks, and JavaScript syntax checks pass.
Authenticated HTTP checks of the live Orders list and create form pass, and both
the order JavaScript and stylesheet are served successfully. Initial form field
IDs are unique and the deadline time is optional in the rendered form.
Browser automation was unavailable during this implementation; visual and
interactive browser acceptance remains to be checked.

## Generic demo data

The sample data now uses standard items, special items, and item sets rather than
an IT-specific catalog. Services include basic/detailed work, customisation,
assessment, and two global extras: express service and delivery. Customers include
both individuals and businesses, with general contact and collection notes.

Use **System Settings → Load demo data** to refresh it. Original demo categories,
products, and services are renamed in place so existing order references and
captured prices remain valid. Demo account usernames and credentials are unchanged.

## Sign-in page

The sign-in page now uses the app's navy/teal theme and configured company name,
with a responsive layout, labelled fields, visible errors, password-manager
autocomplete, and a Show/Hide password button. Standard Django authentication,
CSRF protection, and safe return-to-page redirects are retained.

All 9 authentication tests pass, including successful sign-in, rejected passwords,
company branding, and redirect handling. The live sign-in flow and new stylesheet
and JavaScript were checked successfully. The requested development password was
set only in the local database; it is not applied automatically at startup.

## Simplified order workflow: implemented

The order form and list now use three independent order-level fields:

| Field | Values |
| --- | --- |
| Status | Draft, In Progress, Complete, Cancelled |
| Collected | Checkbox |
| Payment status | Unpaid, Paid, Refunded |

Complete describes finished work, independently of collection and payment. There
is no item progress/status, partial collection, or separate Closed state. Items
retain their individual deadlines and notes. Complete requires a user in Assigned
To; clearing the assigned user
while keeping Complete is rejected.

| Saved stage | Customer/products/services/quantities | Deadlines and item/service notes | Order Notes | Assigned To / Payment status | Collected |
| --- | --- | --- | --- | --- | --- |
| Draft | Editable | Editable | Editable | Read-only | Read-only |
| In Progress | Read-only | Editable | Editable | Editable | Read-only |
| Complete | Read-only | Read-only | Read-only | Editable | Editable |
| Cancelled | Read-only | Read-only | Editable | Read-only | Read-only |

Field locks are based on the saved stage, including a Submit or Mark complete
request. Submit first, then assign or update payment; mark Complete first, then
record collection. Existing values are retained when a field becomes read-only,
including after reopening/restoring an order; status changes do not erase them.

The current status is shown in a labelled badge with text and a stage-specific
colour. It has no radio buttons, dropdown, or editable status input. The server
validates actions against the saved stage:

| Current stage | Status-changing actions |
| --- | --- |
| Draft | Submit → In Progress; Delete draft removes a saved draft; Discard leaves an unsaved draft |
| In Progress | Mark complete → Complete; Cancel order → Cancelled; Return to draft → Draft |
| Complete | Reopen → In Progress |
| Cancelled | Restore to draft → Draft |

Each stage also has a Save button for its editable fields; saving alone never
changes the status. Submit validates and saves the whole draft. Mark complete
requires Assigned To. In Progress cancellation/restoration keeps the same order,
items, service charges, and payment/collection values.

Delete draft requires the order-delete permission, POST with CSRF, and the exact
saved revision. A conditional database write protects against deletion after
another user edits or submits the draft. It deletes only that draft and its
items/service charges, retaining shared customer and catalog records. Standard
CRM roles receive the permission when migrations/bootstrap permissions are run.

Customer/product/service/quantity locking is enforced on the server, including
forged requests. In Progress saves bind only deadlines and internal notes on rows
loaded from that order. Posted IDs, management counts, add/delete flags, and
prices cannot change its commercial contents. Only the allowed fields are
written; captured prices are retained even after catalog prices or links change.
Invalid deadlines prevent the entire save or transition, and revision checking
protects these edits from stale requests. Omitted details are preserved; blank
optional times and notes explicitly clear them.

Returning to Draft unlocks commercial fields on the next page load rather than
accepting those edits in the same request that changes the status. In Progress
deadline/note changes can be saved with Mark complete, Cancel order, or Return to
draft. Complete/Cancelled must first be reopened/restored before deadlines or
item/service notes can change. Cancelled allows only order-level notes, including
on a Restore to draft request; assignment/payment and other fields stay locked
for that request. Existing stored values are preserved. Direct status values and
obsolete transition parameters cannot bypass the action rules.

The fields are saved manually and do not change one another automatically. Paid
and Refunded are currently manual indicators, not recorded transactions with an
amount, date, method, or reference. Selecting Refunded does not transfer money or
change captured charges. Detailed payment/refund recording is still later work.

Migration 0009 preserves existing orders and adds safe defaults of not collected
and Unpaid. The allowed status/payment values are validated in the form and
database. Revision checking protects all three fields from stale saves.

Focused validation includes 102 order tests for stage-specific locks, status changes,
submission, required assignment before completion, server-enforced locks,
returning to Draft, permissions, stale edits, filters, and pagination. Locked
orders retain their captured services and prices even after catalog links change.

Migrations 0009 and 0010 are applied locally. Migration 0010 extends payment choices
and the database constraint to accept Refunded, preserving all existing orders and
charges. The order list also correctly handles orders without an assigned user.
Migration 0011 is also applied locally. It makes customer contact fields required and adds the normalized
email uniqueness constraint, preserving customer and order records. Before
applying it locally, all 11 customers had the required fields and no duplicate
emails; no customer data needed to be changed.

Additional action checks cover draft deletion and its dependent rows, retained
customer/catalog records, deletion permissions, CSRF, stale-delete conflicts, and
the buttons available in each stage, rejected
out-of-stage actions, forged status submissions, duplicate Submit requests, and
Save preserving the current status.

Customer/order validation and migration tests cover
required fields and markers,
case-insensitive email uniqueness, retaining a customer's own email, simultaneous
save conflicts, read-only customer notes, and preservation of existing records.
Rendered HTML checks confirm enabled
In Progress deadlines/notes and disabled commercial controls, including parent
fieldset behavior. Tests cover price preservation after catalog changes, invalid
deadlines, stale edits, row ownership, clearing optional details, and locks after
completion. Cancellation checks cover notes-only saves, preservation of omitted
notes, explicit clearing, stale-save protection, and field locks during
restoration. Refund checks cover saving in In Progress/Complete, the list badge
and combined filters, preserved field locks in Draft/Cancelled, and migration
preservation of existing orders/charges. Draft deletion and Complete-only
collection remain covered.

Seven JavaScript confirmation tests pass with
`node --test crm/tests/js/order-confirmation.test.cjs`, covering immediate Save,
top/bottom submitters, cancellation/Escape, revalidation, Delete draft, Discard,
and already-cancelled events. Rendered stage-control checks also pass.
Twelve customer-selector tests also pass with
`node --test crm/tests/js/order-customer.test.cjs`, covering notes display and
selection changes, inline creation/editing, prefilling, cancellation restoration,
duplicate emails, independent saves, request failures, and duplicate-click
prevention. Server tests also cover edit permission, Draft-only editing,
required fields, retaining the customer's own email, preserving owner/charges,
and rolling back customer edits after stale orders or duplicate-save conflicts.
Independent save requests require POST and CSRF, reject stale/submitted orders,
and do not change order revisions, timestamps, items, or charges. An unchanged
conditional revision write locks the draft during the customer transaction so a
concurrent submission cannot bypass the stage rule. No additional schema
migration is needed for inline editing.

Customer deletion checks pass: 16 focused Django tests cover the customer forms,
CSRF, confirmation markup, and linked-order protection; four JavaScript checks
cover modal opening, cancellation/Escape focus restoration, and creation forms
without Delete, including Archive/Restore dialogs when Delete is hidden.

All 118 customer/order tests and 11 customer-modal JavaScript tests pass after
adding counts, exact-customer filtering, and repairing wrapped order-template
tags. Counts cover all stages and zero-order customers; filters handle duplicate
names, invalid IDs, additional filters, permissions, and pagination. No schema
change was required for the counts/filtering milestone. Keep Django template tags (`{% ... %}` and `{{ ... }}`) on one
line when formatting HTML; wrapping the contents prevents correct parsing.

Migration 0012 adds indexed `Customer.is_archived`, defaulting existing customers
to active and retaining all prior data. It is applied locally; all 11 existing
customers remain active, and customer/order/item/charge data was verified
unchanged. Other checkouts apply it with `python manage.py migrate`.
Archive checks cover active/archived/all filtering, restoration, permissions,
CSRF, preserved orders/counts, archived email uniqueness, existing-order saves,
blocked new selections, and an archive occurring between validation and saving.
All 184 Django tests and 23 JavaScript checks pass for the archive milestone.

## Subsequent milestones

The accepted QOL pass adds shared form protection and confirmations, order work
queues/deadline sorting, dashboard workload counts, list return navigation,
duplicate items/deadline bulk updates/undo, catalogue archiving, staff
deactivation/deletion protection, contact links and directory pagination. See
[QOL implementation](qol-improvements.md) for the exact queue definitions,
behaviour, migration and verification details, and browser-tool setup.

Invoice/PDF/email generation, full-payment records, finer permissions and change
history, and financial dashboards/reports remain to be implemented. Currently,
saving or changing an order's status does not issue an invoice.

The next milestone is [invoice design and delivery](invoice-design.md), captured
on 15 November 2026. The latest proposal is a small Invoice record with immutable
billing snapshots and a stored PDF, managed from the order. Preview does not issue
or number an invoice; explicit Generate after submission replaces the earlier
automatic-on-Submit assumption in the working plan. Confirm the final trigger
and eligible stages before implementation. View/download/print and later email
reuse the issued PDF.

Start with business invoice settings and a sample A4 PDF. The handover specifies
configurable content versus fixed layout, internal-note exclusions, numbering and
storage expectations, and a resume checklist. Agree how invoiced orders may be
corrected/returned to Draft before implementing issuance. Connect email delivery
later when the mail server is configured. These are planned changes; no invoicing
code was implemented in this documentation update.

The latest reporting plan keeps Service Orders as the primary work/reporting
record. Plan a Record refund action with amount, date, reason and optional affected
item/service, plus Total Refunded and Net Order Value (Order Total minus refunds).
The initial report uses one row per order, order-date range, status/payment/assignee
filters and totals/CSV. Later refunds update the older order's net value and its
earlier order-date report when rerun. These are live order-value totals; separate
cash-flow/accounting reports are deferred. See
[the simple refund/reporting plan](invoice-design.md#simple-refunds-and-reporting-directly-on-orders)
and [scope section 7.2](scope-of-work.md#72-searchable-order-report). Refund entries,
refund/net columns and the new report are not implemented yet; today's payment
statuses remain manual indicators. Invoice correction and refund validation rules
still require agreement before those actions are built.
