# Scope of Work: Service Orders, Invoicing, and Business Reporting

Status: Draft for ongoing refinement. This document defines planned work; it does
not indicate that the features below have already been implemented.

See [development status](development-status.md) for delivered features and current
implementation choices.

Created: 14 November 2026  
Primary example: Ballet shoe sewing service  
Application: My CRM

## 1. Purpose

Extend the CRM into a practical system for a small service business to record
customer work, calculate charges, assign staff, track deadlines, issue invoices,
record payment, and report on business activity.

The first business is a ballet shoe sewing service. The underlying concepts and
data model must also suit other businesses that perform one or more services on
customer items. Use general terms such as customer, product, service, order item,
and assigned user in the core application. A sewist is an example of an assigned
user, rather than a separate type of account required by the system.

In this scope, "service order" names the main work record also described as a
"sales order" or "work item" in the original brief. Its order items are the
customer's physical items; its invoice is a separate billing record.

## 2. Confirmed decisions

| Topic | Decision |
| --- | --- |
| Order status | One status for the whole order: Draft, In Progress, Complete, or Cancelled. No item-level progress/status tracking. |
| Collected (D09) | A separate order-level checkbox, unchecked by default, editable only while the saved order is Complete. No per-item or partial collection tracking. |
| Payment status | A separate order-level field: Unpaid, Paid, or Refunded, editable only in In Progress and Complete. Refunded is a manual indicator; full payment only in the first version. |
| Payments in the first version | Full payment only. Deposits, partial payments, and payment instalments are outside the initial scope. |
| Business setup | One business per installation initially. The software should be reusable for other businesses through configuration. |
| Customer selection | A single searchable dropdown shows clickable matches. A Create New button opens a customer modal while retaining the order being entered. |
| Customer editing from orders | In Draft, Edit customer opens a prefilled modal for the selected customer. Save customer updates that shared customer immediately, independently of order saving, and refreshes the label and notes without losing unsaved order edits. Customer-change and order-edit/create permissions are required. Cancel/Escape discards unsaved modal edits. |
| Customer details | First name, Last name, Email, and Primary phone are required and marked with *. Email is unique across customers, ignoring surrounding whitespace and case. The same rules apply in the customer pages, admin, and order modal. |
| Customer Notes on orders | Show the selected customer's current notes as read-only text on the order, including line breaks, separately from order/item/service notes. Update the display when the selected customer changes. |
| Customer archiving | Archive instead of deleting customers with linked orders. Preserve customer details and history; hide archived customers from new-order selection and default directory results. Offer Active/Archived/All directory filters and Restore. Existing orders retain their customer and remain usable; archived emails stay reserved. |
| Product units (D01) | Whether a product represents a shoe, pair, or another unit depends on product setup. No shoe-specific unit is imposed by the order workflow. |
| Services per item | An item may have multiple services, including repeated selections of the same service. Each occurrence is charged separately. |
| Quantities (D03) | Quantities are entered only on services. Each charge is service quantity × unit price. Products have no separate quantity or item label/description field. |
| Service notes | Each selected service occurrence supports its own optional text note for internal instructions; this note is excluded from the invoice. |
| Order notes | Provide a global notes section for the whole order, separate from individual service notes and customer-visible invoice notes. |
| Additional charges | Additional requests, such as overnight turnaround, can be represented as services. |
| Global services | Some services must be available without a link to a specific product. |
| Deadlines (D02) | Each order item has its own deadline date, with an optional time in the business timezone. |
| Assignment | Assigned To and Assign to Me are editable only in In Progress and Complete. A user must be assigned before Complete. |
| Order editing | Order Notes are editable in every state. Customer selection, products, services, and quantities are editable only in Draft. Deadlines, optional times, and internal item/service notes are also editable in In Progress without changing charges or invoice data. Complete locks deadlines and item/service notes until reopened. Cancelled permits only Order Notes, for example a cancellation reason; other fields stay locked until restored. Collected is editable only in Complete. |
| Submission | A Submit button saves the draft and moves it to In Progress. Draft field locks still apply during this request, so assignment/payment edits happen afterwards. |
| Draft disposal | Delete draft permanently removes a saved Draft and its items/service charges; Discard leaves an unsaved draft. Cancel order is available only in In Progress and retains the Cancelled order. |
| Status controls | Show the current status in a clear, labelled badge near the order heading, alongside the total and currency. Only stage-specific action buttons can change Status, with allowed transitions enforced on the server. |
| Completion | A user must be set in Assigned To before the order can be marked Complete. |
| Invoice trigger | Confirming an order generates its invoice. |
| Invoice delivery | The invoice can be printed or emailed to the customer. |

The detailed defaults and controls proposed below remain recommendations unless
explicitly identified as confirmed. Open decisions are listed in section 13.

## 3. Current implementation baseline

This records the baseline before the draft service-order milestone. See the
development status linked above for subsequent implementation progress.

The initial repository provides:

- Login, logout, profile editing, and User, Admin, and System Admin access levels.
- Customer creation, editing, deletion, and searching, including contact details,
  company, notes, and the user who created/owns the customer record.
- Product categories, products, and services, with a service price and optional
  product associations.
- Company name and default currency settings.
- Demo data, a basic dashboard page, and existing automated tests.

The customer owner currently stored in the CRM is not the same concept as the
worker assigned to a particular order.

Orders, item deadlines, order assignment, invoices/PDF generation, invoice email,
payment tracking, and order reporting are new work. Although services can already
have no product associations, the rules for presenting and applying global
services during order entry still need to be implemented explicitly.

## 4. Main workflow

1. A customer brings in one or more items, for example two pairs of ballet shoes.
2. The operator searches for the customer or creates their record without losing
   the order being entered.
3. The operator creates a draft service order and adds a separate order item for
   each physical item or group that needs its own instructions or deadline.
4. For each order item, the operator selects the product/type, records any
   instructions, selects one or more applicable services (including
   repeated selections), optionally notes each service occurrence, and sets a
   deadline date with an optional time.
5. The operator adds any general extra services, such as an order-wide overnight
   surcharge, and any order-wide notes. The application calculates the total.
6. The operator saves the draft. Assigned To, Payment status, and Collected remain
   read-only while the saved order is Draft.
7. The operator reviews and submits the order, moving it from Draft to In
   Progress. The application assigns its invoice number and generates an invoice
   using the confirmed information. Confirmation is an action, not another status.
8. The invoice is downloaded/printed or emailed. Work is tracked using the single
   status on the whole order.
9. The supervisor assigns or reassigns the worker as needed and monitors deadlines.
10. When the work is finished, an authorized user manually marks the order Complete.
    A user must be assigned before this change can be saved.
11. The operator marks Collected and records full payment independently, in
    whichever sequence occurs in practice. Completing an order does not mark it
    collected or paid, and payment/collection does not change its work status.
    Payment status is editable in In Progress and Complete; Collected can be changed only
    after the order has been saved as Complete.

An In Progress order that will not proceed can be marked Cancelled. A saved Draft
that will not proceed is deleted instead; an unsaved draft can be discarded.
There is no separate Closed status or payment-dependent closure step.

## 5. Functional requirements

### 5.1 Customers and order entry

- Reuse the existing customer records and search capabilities. Allow quick
  customer creation from order entry, with duplicate suggestions using available
  contact details.
- Use one customer field that filters a dropdown as the operator types. Provide
  a Create New button above it to open customer details in a modal, with clear
  apply/cancel actions that preserve the draft.
- Offer Edit customer for the selected customer while Draft, with the existing
  details prefilled. Save customer updates the shared customer immediately without
  saving/submitting or reloading the order, preserving its identity and owner.
  Refresh the displayed label and Customer Notes while retaining unsaved order
  fields. Respect customer-change permission and the existing locks after
  submission. Required fields and unique email validation must work for edits,
  excluding that customer's own email. Reject stale/submitted order contexts
  before changing the customer. Save failures remain in the modal with entered
  values available for correction/retry. New customer creation remains tied to
  saving the order.
- Require First name, Last name, Email, and Primary phone in customer creation
  and editing, including the order modal. Mark required fields with * and validate
  them in both the browser and server. Keep company, secondary phone, and notes
  optional. Reject duplicate email addresses regardless of case or surrounding
  whitespace, including concurrent saves; a customer can retain its own email.
- Show a smaller Delete button beside Save on existing customer edit pages.
  Confirm deletion in an app-styled modal identifying the customer, with Cancel
  focused initially. Cancel or Escape must leave the form unchanged. Submit
  deletion separately from customer edits so incomplete fields do not prevent
  it, and retain protection for customers linked to service orders.
- Offer Archive/Restore on customer forms with a confirmation modal, customer-change
  permission, POST, and CSRF. Preserve the customer, notes, order references, and
  counts. Hide Delete for linked customers and keep the database deletion
  protection. Default the directory to active customers and offer Archived/All
  filters with search. Restoration makes the same record available again.
- Exclude archived customers from new-order selection in the browser and server,
  including an archive between validation and saving. Existing orders can retain
  their current archived customer and continue through the workflow. Keep all
  customers available to historical order filters; maintain email uniqueness
  across archive status. Ordinary contact edits must not reset archive status.
- Show Customer Notes directly below the customer selection on every order stage.
  These are the current customer-record instructions, not an editable order field
  or an invoice snapshot. Preserve line breaks and display notes as plain text.
  Keep this display in sync when choosing or creating a customer, and restore it
  when customer creation is cancelled. Keep customer notes internal.
- Replace the customer-directory Owner column with an Orders count. On existing
  customer forms show Total Orders and Open Orders, where Open means Draft or
  In Progress. Include View Orders to list all orders for that exact customer,
  retaining the customer filter when filtering or paging. Do not match customers
  by name or email text; identical names must remain separate. Respect order-view
  permission on navigation links.
- Use the main Orders search for customer names, email, company, and phone;
  do not display a separate customer filter dropdown. Preserve exact customer-ID
  filtering for customer-history links, with a visible customer context label.
- Keep labels brief. Put Order Details at the top and label the assignment field
  Assigned To. Above it, show the current status in a labelled badge near the
  order heading and show the total with its currency. Keep header and bottom
  totals in sync as draft charges change. Show only the actions available in the
  saved stage, using ordinary accessible buttons.
- Show an app-styled confirmation modal before status-changing actions, deleting
  a draft, or discarding an unsaved order. Use wording specific to the chosen
  action in both top and bottom controls. Focus Cancel initially; Cancel or Escape
  must leave entered changes on screen. Confirming must revalidate and submit the
  originally chosen action. Save actions do not require confirmation.
- Keep customer, item, service, and order-note fields editable in Draft. Submit
  saves the draft and moves it to In Progress. Afterwards, lock customer selection,
  products, services, quantities, and adding/removing rows on both the server and
  screen until an allowed action returns the order to Draft. Deadlines, optional
  times, and internal notes remain editable while In Progress.
- Disable Assigned To, Assign to Me, Payment status, and Collected in Draft and
  Cancelled, on both the screen and server. Assigned To and Payment status are
  editable only in In Progress and Complete; Collected only in Complete. Preserve
  stored values when a field becomes read-only. Cancelled allows only Order Notes
  to be updated, with a Save notes action for adding a cancellation reason.
- Give each order a unique reference, customer, creation date, creator, order-wide notes,
  confirmation date, and optional assigned user.
- Provide a global notes section for general order instructions, alongside optional
  notes on individual service occurrences. Editing one must not overwrite the other.
- Keep order-wide notes and service notes as internal work instructions, separate
  from customer-visible invoice notes. Internal notes must not appear in the invoice
  PDF or customer invoice email.
- Allow deadline dates, optional times, and internal notes at order, item, and
  service/extra level to change while In Progress. Keep customer selection,
  products, services, quantities, prices, and adding/removing rows locked until
  the order is returned to Draft. Operational changes must preserve charges and
  issued invoice data, and must be protected against stale saves.
- Allow draft orders to be saved and resumed. Confirmation requires a customer,
  at least one item, required item details and deadlines, and valid service prices.
- Use the customer's required email for invoice delivery and revalidate the
  recipient before sending. Printing does not depend on email delivery succeeding.

### 5.2 Products and physical order items

The product catalog describes reusable types of items, such as a ballet shoe type.
An order item describes the actual customer item being worked on. Two pairs of
the same catalog product can therefore appear as separate items on one order.

Each order item must support:

- A catalog product/type. A product can represent a shoe, pair, or another unit
  according to catalog setup. Do not add a separate item label or product quantity.
- Work instructions and a deadline date with an optional time.
- One or more selected service occurrences, including repeats of the same service,
  each with its own charge and optional internal text note.

Work status and the Collected checkbox belong to the whole order. Items do not
have their own progress, completion state, or collection tracking.

Items with different deadlines or work instructions must be separate order lines.
The order's next deadline is the earliest of its item deadlines while the order
is Draft or In Progress; it must not replace individual deadlines. Complete and
Cancelled orders are excluded from overdue-work indicators.

A deadline without a time remains date-only when saved and displayed; the user
must not be forced to supply a time. Deadline sorting and overdue indicators must
respect that distinction in the business timezone rather than presenting an
invented midnight deadline.

### 5.3 Services and extra charges

- Services linked to products are available for those product types.
- Allow the same service to be selected more than once on the same order item.
  Keep each selection as a separate occurrence so its optional note can differ,
  for example two sewing operations on the same shoe with different instructions.
- Allow an optional free-text note when choosing each service occurrence. Notes
  belong to that order's selection, not to the reusable catalog service, and are
  available to the worker/supervisor as internal instructions.
- Global services are available without any product association. Their global
  applicability must be explicit in the interface and documented in the model.
- Support services applied to a specific order item and general charges applied
  once to the whole order. The user must see which level a charge applies to.
- An overnight charge can therefore apply to a particular pair or to the whole
  order according to how the operator adds it. Do not automatically add it at both
  levels.
- Calculate totals from the selected services, their captured prices, and explicit
  charge quantities. Show the item breakdown, general charges, and order total.
  Each charge is service quantity × unit price, with no product quantity multiplier.
  Count each repeated occurrence once at its applicable charge quantity; selecting
  a service twice must not be collapsed into one charge. Editing or removing one
  occurrence must not modify the other occurrence or its note.
- Recommended first version: fixed monetary service prices. Percentage surcharges,
  automatic rush rules, discounts, and product-specific price overrides need
  separate agreement before inclusion.
- Keep money in decimal values. Snapshot prices and currency on confirmation so
  later catalog price or default currency changes do not alter existing invoices.

### 5.4 Assignment and staff workload

- Allow a single assigned user per order, including an unassigned state while
  Draft or In Progress. Assigned To is editable only in In Progress and Complete.
  Complete requires an assigned user.
- Support assignment and reassignment after confirmation, with actor and timestamp
  history. Assignment changes must not create another invoice.
- Make the assigned user, outstanding work, instructions, and deadlines visible to
  the supervisor and to the worker according to agreed permissions.
- Show order-wide notes alongside the individual service occurrence notes so the
  worker can see both general instructions and the details of repeated services.
- Use the existing user accounts. Multiple workers per order, per-item assignment,
  and calculation of worker pay are outside the first version.

### 5.5 Order status, collection, and payment status

Keep these dimensions independent:

| Field | Confirmed values or behavior |
| --- | --- |
| Status | Draft, In Progress, Complete, Cancelled |
| Collected | Checkbox: unchecked or checked, for the whole order |
| Payment status | Unpaid, Paid, or Refunded; full payment only |
| Assignment | Unassigned or an assigned user |

Draft means the order is being prepared; In Progress means the job is active;
Complete means the work on the whole order is finished; Cancelled means the order
will not proceed. An authorized user changes the order status manually.

Keep the current status badge read-only. A normal Save action preserves the stage.
Expose the following status-changing actions:

| Current stage | Action | Destination |
| --- | --- | --- |
| Draft | Submit | In Progress |
| Draft | Delete draft (saved orders only) | Draft and its items/service charges are removed |
| In Progress | Cancel order | Cancelled |
| In Progress | Mark complete | Complete |
| In Progress | Return to draft | Draft |
| Complete | Reopen | In Progress |
| Cancelled | Restore to draft | Draft |

Mark complete without Assigned To must be rejected with a clear message. Reject
actions that are unavailable in the current stage, including forged direct POST
requests and arbitrary status values. Repeated clicks or stale forms must not
repeat an action or overwrite a newer save.

Complete may be unpaid or uncollected. Collected may be checked independently of
Payment status while the saved order is Complete. Outside Complete, the checkbox
is read-only and its stored value is preserved. Recording payment does not automatically mark the order Complete
or Collected. These fields must remain individually visible and filterable.

Refunded is a manual payment-status option, available in the same editable stages
as Paid/Unpaid and included in order-list filters. It does not change work status,
collection, charges, or invoice amounts and does not itself process a refund.

Do not add a separate Closed state, derived item-progress summary, or partial
collection states. This replaces the earlier manual closure proposal and its
requirement for payment before closure. Changes back from Complete or Cancelled
are status changes subject to the agreed permissions and financial correction
rules, not an additional reopening workflow.

Cancellation of an In Progress order must preserve its reference and history.
Draft deletion is a separate explicit action, requires deletion permission and
an unchanged draft revision, and must not delete shared customers or catalog
entries. A stale deletion request must not remove a submitted or modified order.
The treatment of an
already-issued invoice or payment on cancellation must be agreed before that
operation is implemented; cancellation must not silently erase financial records.

### 5.6 Full-payment recording

- Allow an authorized user to record the full outstanding invoice amount, payment
  date/time, payment method, reference, and recording user.
- Derive paid/unpaid from the recorded financial information. Reject accidental
  duplicate settlement and unsupported partial-payment amounts.
- Recording payment updates the order and invoice payment display without
  changing their original charges, order status, or Collected checkbox.
- Payment recording is manual in the first version. Online card payments, bank
  feeds, automatic bank reconciliation, deposits, and partial payments are excluded.
- Corrections to an incorrectly recorded payment require an authorized action,
  reason, and history rather than silent deletion. Refund transaction handling
  remains an open decision, separate from the manual Refunded status indicator.

## 6. Invoices, PDF layout, and email

### 6.1 Confirmation and invoice integrity

- Generate one uniquely numbered invoice when an order is confirmed. Confirmation
  must be atomic and safe to retry: repeated clicks must not create duplicate
  invoices or consume the same number for different invoices.
- Confirmation is the first Draft-to-In Progress transition; it does not introduce
  a Confirmed status. Subsequent status changes do not issue another invoice.
- Preserve a snapshot of the customer billing details, business invoice settings,
  service descriptions, quantities, prices, currency, and totals at issue time.
- Reprinting or emailing an invoice reuses that issued invoice, rather than
  rebuilding its commercial contents from subsequently edited catalog/settings
  records. Payment information may be displayed as a separate current status.
- Agree on the correction/void/reissue process before permitting financial edits
  to a confirmed order. Do not silently overwrite issued invoices.

### 6.2 Proposed invoice contents

- Business name, logo, address, and contact details.
- Customer name, contact/billing details, and relevant business identifiers.
- Invoice number and issue date, order reference, and payment due date/terms.
- Item descriptions, selected services, quantities/units, unit prices, line totals,
  general charges, subtotal, applicable tax breakdown, currency, and invoice total.
- Banking/payment instructions and payment reference guidance.
- Customer-facing notes, disclaimers, and terms.
- Relevant service deadlines where useful, separate from the payment due date.
- Repeated services must be reflected in the billed quantities or lines and totals.
  Internal service occurrence notes and order-wide notes are excluded; only
  explicitly customer-facing invoice notes are included.
- Page numbering and consistent headers/footers on multi-page documents.

Tax registration, invoice wording, numbering requirements, and tax calculations
need confirmation for the actual business before finalizing the invoice design.
This scope does not establish tax or legal compliance requirements.

### 6.3 Configurable versus fixed layout

| Business-configurable content | Application-controlled structure |
| --- | --- |
| Name, logo, address, contact information, applicable registration details | Clear placement of invoice identity, customer block, lines, and totals |
| Banking details and payment instructions | Consistent amounts, currency formatting, pagination, and readable print layout |
| Customer-facing disclaimer, terms, and default invoice note | Escaping/validation of text; no arbitrary executable HTML templates |
| Default currency and business timezone | Historical snapshots so setting changes affect future invoices |
| Agreed invoice prefix/numbering settings and default payment terms | Uniqueness and integrity of issued invoice numbers |
| Email subject/body defaults | Correct invoice attachment and delivery history |

Start with one polished, branded invoice template. Review a sample PDF with the
business owner before implementing the final layout. An HTML/CSS template rendered
to PDF is a candidate approach; select the renderer after checking Windows/local
development support, deployment support, pagination, and fonts. A drag-and-drop
template designer and multiple layout themes are outside the initial scope.

### 6.4 Printing and emailing

- Provide PDF preview/download and printing from the invoice view.
- Provide an explicit email action with recipient, subject/body preview, and the
  correct invoice PDF attached. Automatic sending on confirmation is not assumed.
- Record send attempts, recipient, timestamp, result, and sender; support retry
  after failure. Email failure must not undo confirmation or generate a new invoice.
- Keep email provider credentials outside source control and ordinary business
  settings screens. Do not put credentials into invoice documents or logs.

## 7. Dashboard and reporting

### 7.1 Home dashboard

Provide summary counts/totals and lists that link to filtered order views:

- Active orders (Draft and In Progress) and unassigned orders.
- Items due today, due soon, and overdue, with their worker and order reference.
- Orders with status In Progress and Complete orders awaiting collection.
- Collected and uncollected orders, using the single order checkbox.
- Unpaid invoices/orders, their outstanding value, and overdue payments when
  payment due dates are configured.
- Payments received in a selected period and workload by assigned user.

Dashboard categories can overlap. For example, an order can be Complete, Unpaid,
and not Collected at the same time. Complete orders must remain visible in the
unpaid and awaiting-collection lists where applicable. Status counts use the four
whole-order values rather than item progress.

### 7.2 Searchable order report

Start with a sortable, paginated table and filters rather than a custom report
builder. Use one row per order, with a link to item/service detail.

Suggested columns: order reference, invoice number, customer, created date,
confirmed date, earliest deadline, Assigned To, Status, Collected, Payment status,
invoice amount/currency, paid amount, outstanding amount, payment
date/method/reference, and order completion date.

Suggested filters: text search, date range and date basis, assigned user including
unassigned, order status, Collected, Payment status, overdue active orders, and
product/service. Provide totals for the filtered result and CSV export.

Use related order, item, service, invoice, and payment records as the source of
truth. The report table is a view of those records, rather than a second manually
maintained sales table. Avoid counting an order's total repeatedly when it has
multiple items or services.

Distinguish payments received (by payment date) from invoiced sales (by invoice
date). Label the date basis and treatment of cancelled/void records clearly. Do
not treat unpaid invoices as cash received or label sales as profit. Reporting by
worker should identify current assignment; attribution to the worker at payment
or completion time needs a separate business decision. Never sum different
currencies into one unlabeled monetary total.

## 8. Access, history, and reliability

- Extend the current role system with specific order, assignment, invoice, payment,
  reporting, status-change, and collection permissions. Supervisor is a business capability whose
  mapping to the existing roles still needs agreement.
- Recommended split: operators capture orders; workers update permitted whole-order
  statuses; supervisors assign users, manage status changes, and view financial
  reports; administrators manage catalogs and business settings.
- Enforce permissions on the server as well as in navigation. Decide whether
  workers see only assigned orders and whether they can see prices/customer data.
- Record important transitions: confirmation, assignment changes, deadline changes,
  order status changes, Collected changes, and payment/corrections.
- Validate totals and state changes on the server. Use transactions and concurrency
  controls where needed to prevent duplicate confirmation, invoices, or payment.
- Preserve historical financial references when a customer, product, service, or
  worker is changed or retired; prefer archiving referenced records to deletion.
- Use the configured business timezone for deadlines, reports, and display.
- Ensure database backups and any stored invoice files can be restored together.
- Keep the initial one-business installation simple. Supporting several isolated
  businesses in one installation would require separate tenancy and access design.

## 9. Suggested conceptual records

These are planning concepts, not a final database schema:

| Record | Purpose |
| --- | --- |
| Customer | Existing customer/contact record |
| Product / Service | Existing reusable catalogs, extended for explicit global service applicability |
| ServiceOrder | Customer, reference, four-value Status, Collected checkbox, Payment status, assigned user, key dates, and order-wide internal notes |
| OrderItem | Customer product/type, optional item notes, deadline date with optional time; no item status, progress, collection, label, or product quantity |
| OrderServiceCharge | One selected service occurrence, item-or-order scope, charge quantity, captured price, and optional internal text note; repeated occurrences are allowed |
| Invoice / InvoiceLine | Issued identity and financial/business/customer snapshots |
| Payment | Full settlement amount, date, method, reference, and correction history |
| OrderEvent | Who changed an operational state, when, and why |
| InvoiceEmailAttempt | Recipient, send result, timestamp, and retry history |
| Business settings | Existing settings extended for invoices, banking, timezone, and payment terms |

## 10. Proposed delivery phases

1. **Order foundation:** agree open workflow decisions; add orders, items, customer
   lookup/creation, deadline dates with optional times, service applicability,
   repeated service occurrences and notes, order-wide notes, extra charges, and
   price totals.
2. **Work management:** the four whole-order statuses, Collected checkbox, separate
   Payment status field, assignment/reassignment, permissions, and change history.
3. **Invoices:** confirmation, numbering and snapshots, business invoice settings,
   approved PDF sample, download/print, email configuration, and delivery history.
4. **Settlement:** full-payment recording and corrections behind Payment status,
   cancellation rules, and financial history. No separate closure workflow.
5. **Visibility and release:** dashboard, filtered reports/CSV, workflow tests,
   backup/restore checks, and end-to-end business acceptance.

These phases are a suggested implementation order, not a time or cost estimate.

## 11. Acceptance scenarios

1. An operator finds an existing customer or creates one during draft order entry
   without losing the order. The same workflow works for a non-sewing service.
2. An order contains two pairs of the same product with different instructions and
   deadlines. Each can have several services, and their prices contribute correctly.
3. A global overnight service can be added without a product link. An order-level
   charge is counted once and is visibly distinct from item-level services.
4. An order can be saved and confirmed while unassigned. A supervisor assigns and
   later reassigns a user, with the changes recorded.
5. Repeated confirmation does not create duplicate invoices. Changing catalog
   prices, customer details, or banking settings does not rewrite an issued invoice.
6. A long invoice with multiple items/services prints legibly across pages and can
   be emailed. A failed email can be retried without another invoice being issued.
7. An authorized user marks the whole order Complete without updating individual
   item progress. It remains visible as uncollected and/or unpaid where appropriate.
8. Full payment records the expected amount and reference. Partial or duplicate
   settlement is rejected. Payment status becomes Paid without changing Status
   or Collected automatically.
9. The order has exactly four work statuses: Draft, In Progress, Complete, Cancelled.
   Changing Status or the Collected checkbox preserves the other fields; authorized
   changes are recorded. No item status or separate Closed state is needed.
10. A supervisor filters orders by worker, deadline, status, and date range. Cash
    totals reflect actual payments in the selected period and do not double-count
    orders that have several services.
11. A worker cannot perform supervisor or financial actions by directly requesting
    a restricted URL. Unassigned and overdue orders remain easy to identify.
12. Product setup determines whether an order item represents a shoe, pair, or
    another unit. The order workflow does not impose a single unit across products.
13. An operator can save a deadline date with or without a time. Both forms survive
    saving/reopening and display correctly; a missing time is not shown as midnight.
14. An operator selects the same service twice for one product, supplies different
    optional notes, and sees both charges in the total. Removing one selection
    removes only its charge and note; the other selection remains intact.
15. A worker can read general order notes and the notes for each selected service.
    Those internal notes are absent from the customer invoice PDF and invoice email,
    while any explicitly customer-facing invoice note is included.
16. Typing in the customer field shows selectable matches. Creating a customer in
    the modal or cancelling it preserves the order's other fields and selections.
17. An operator enters quantities only on service rows, sees each charge calculated
    as quantity × unit price, and finds Assigned To and order notes in Order Details
    at the top, below the current status badge and order total.
18. Submit saves a valid draft and moves it to In Progress. Assigned To, Payment
    status, and Collected stay read-only for that request; assignment/payment can
    be edited afterwards. Invalid drafts stay unchanged. Customer/product/service/
    quantity changes and row additions/removals are rejected or ignored after
    submission until the order is saved back as Draft through an allowed action.
    In Progress permits deadline dates, optional times, and internal order/item/
    service notes to change, preserving charges and invoice data. Invalid deadlines
    prevent the whole save; stale requests cannot overwrite newer edits.
    Order Notes remain editable in every state. Complete locks deadlines and
    item/service notes until reopened. Cancelled allows only
    order-level notes, including a cancellation reason; other fields remain
    locked, including during restoration. Assignment/payment are editable only
    in In Progress and Complete; collection only in Complete.
19. Complete cannot be saved without Assigned To, including direct POST requests.
    Selecting a user and clicking Mark complete in the same request succeeds.
20. The current status badge is not interactive. Each stage shows only its allowed action
    buttons; actions from another stage and direct status editing are rejected.
    Reopen returns Complete to In Progress, Restore to draft returns Cancelled
    to Draft, and a normal Save preserves the stage.
21. Saved drafts show Delete draft, unsaved drafts show Discard, and only In
    Progress shows Cancel order. Draft deletion removes that draft and its items/
    charges only, requires permission and CSRF, and rejects stale revisions or
    drafts that have since been submitted. No real customer/catalog records are
    deleted with the draft.

## 12. Outside the initial scope

- Multiple businesses sharing one installation with isolated accounts/data.
- Deposits, partial payments, payment plans, online payment processing, and bank feeds.
- Inventory purchasing/stock control or selling physical products as retail stock.
- Payroll, commissions, worker compensation, and automated accounting integration.
- Customer self-service portals, online booking, SMS/WhatsApp notifications, and
  automatic deadline reminders.
- Multiple assignees or different workers per item on the same order.
- Item-level progress/status, partial collection/delivery tracking, and a separate
  Closed status or closure workflow.
- Arbitrary invoice layout builders, advanced report builders, and currency conversion.

Refunds, credit notes, discounts, and correction of issued financial documents
need an explicit decision; they are not assumed to be included automatically.

## 13. Open decisions and suggestions

Decisions D01 (product-defined units), D02 (deadline date with optional time),
and D03 (service-only quantities) are resolved in section 2. The remaining IDs
are kept stable for future reference.

D04 (payment-dependent closure) is superseded by the four-status workflow in
section 5.5. D09 is resolved as one whole-order Collected checkbox, with no partial
collection tracking.

| ID | Decision to confirm | Suggested starting point |
| --- | --- | --- |
| D05 | Who can create/confirm orders, change Status or Collected, assign workers, record payment, and see finances? | Agree the operator/worker/supervisor permissions before adding roles or changing existing ones. |
| D06 | Which business and tax details, payment terms, invoice numbering, and disclaimers are needed? | Review actual business details and a sample invoice; do not invent tax status or final disclaimer wording. |
| D07 | How are confirmed orders corrected, cancelled, or refunded? | Preserve issued records and record reasons; agree void/reissue/credit behavior before financial edits are allowed. |
| D08 | Which email sender/provider should deliver invoices, and is sending always manual? | Explicit send with a preview initially; store provider credentials securely outside the repository. |
| D10 | What dates and worker attribution should financial reports use? | Separate invoice-date sales and payment-date receipts; current worker for workload, with historical attribution agreed separately. |
| D11 | What target date/time does an overnight request mean for the business? | Let the operator enter the agreed deadline and optional time; do not silently calculate one from the service name. |

## 14. Maintaining this scope

Update this document when decisions are confirmed, identifying what changed and
whether it affects earlier phases. Keep implementation progress separate from
requirements so planned features are not mistaken for delivered functionality.

| Date | Decision/change |
| --- | --- |
| 15 November 2026 | Made Order Notes editable in every order state, including Complete. Notes can be updated or cleared without reopening; item/service notes and other stage locks retain their existing rules. |
| 15 November 2026 | Accepted and implemented the QOL pass: safe forms and confirmations, order work queues and business-timezone deadline rules, workload dashboard, preserved list navigation, item duplication/bulk deadlines/undo, catalogue archiving, staff deactivation/history protection, directory pagination and contact links. These retain the existing stages and locks. See qol-improvements.md for behaviour and checks. |
| 14 November 2026 | Initial scope captured from the business workflow. Confirmed manual closure, full payment only, and one business per installation initially. |
| 14 November 2026 | Confirmed product-defined units, deadline dates with optional times, repeated service selections on one product, optional internal notes per service occurrence, and a global order notes section. Updated requirements and acceptance scenarios; resolved D01/D02 and retained overnight interpretation as D11. |
| 14 November 2026 | Implemented the draft service-order milestone. Delivery details, provisional pricing/permission choices, verification, and remaining work are recorded separately in development-status.md. |
| 14 November 2026 | Simplified the order form: searchable customer dropdown and creation modal, order details at the bottom, Assignee label, no item label/description or product quantity, service-only quantities, and shorter wording. Resolved D03. |
| 15 November 2026 | Simplified the planned workflow to whole-order Status (Draft, In Progress, Complete, Cancelled), an independent Collected checkbox, and Payment status (Unpaid/Paid). Removed item progress, partial collection, and the separate closure workflow; supersedes D04 and resolves D09. |
| 15 November 2026 | Implemented the three order-level fields and list filters. All statuses remain editable; payment status is a manual indicator for now. Invoice generation, payment records, and detailed change history remain later work; see development-status.md. |
| 15 November 2026 | Moved Order Details to the top, renamed the assignment field Assigned To, and added a clickable status banner and Submit order action. Confirmed Draft-only editing for customer/items/services/order notes, reopening by saving as Draft, editable assignment/payment/collection after submission, and required assignment before Complete. |
| 15 November 2026 | Replaced the clickable banner with a read-only stage display and explicit Submit, Mark complete, Cancel order, Return to draft, Reopen, and Restore to draft actions. Enforced permitted transitions on the server; normal saves preserve the stage. |
| 15 November 2026 | Made Assigned To, Payment status, and Collected read-only in Draft, with Collected editable only in Complete. Draft disposal now deletes saved drafts or discards unsaved drafts; Cancel order applies only in In Progress. Added server validation and permission/revision/CSRF protection for draft deletion. |
| 15 November 2026 | Allowed In Progress deadline dates, optional times, and internal order/item/service/extra notes to be updated while retaining locks on customer selection, products, services, quantities, prices, and row additions/removals. Changes preserve captured charges and invoice data; Complete/Cancelled continue to lock these details until reopened/restored. |
| 15 November 2026 | Replaced the four-stage banner with a labelled current-status badge near the order heading and a labelled total with currency. Header and bottom totals update together while editing; existing orders open through View and use a neutral Order heading. |
| 15 November 2026 | Made Cancelled orders read-only except for Order Notes, so cancellation reasons can be added. Added Save notes and locked Assigned To, Assign to Me, and Payment status; retained Restore to draft with source-stage locks and stale-save protection. |
| 15 November 2026 | Added Refunded as a manual payment status, including the form, list badge, and filter. Retained stage field locks and captured order charges; migration 0010 extends the database constraint without changing existing values. Refund transactions remain later work. |
| 15 November 2026 | Required First name, Last name, Email, and Primary phone on customer forms and the order modal, with * markers. Added case-insensitive, trimmed email uniqueness and duplicate-save errors. Orders now show the selected customer's current notes separately from order notes. Migration 0011 preserves existing customer/order data; this supersedes the earlier allowance for customers without email. |
| 15 November 2026 | Added Edit customer to Draft orders using a prefilled modal. Edits to the existing customer save atomically with the order, preserve identity/owner, enforce customer-change permission and email uniqueness, and support Cancel/Escape without losing order edits. Submitted orders keep customer editing locked. |
| 15 November 2026 | Changed Edit customer to save immediately through Save customer in the modal, independently of the order. The label and Customer Notes update without a reload; unsaved order fields and saved order revisions/items/charges remain unchanged. Retained permission, CSRF, Draft-stage, stale-context, and unique-email checks. |
| 15 November 2026 | Removed Owner from customer screens, added the directory Orders count, and added Total Orders/Open Orders with View Orders on customer forms. Open means Draft or In Progress; order navigation uses an exact customer filter retained during filtering and pagination. Retained internal ownership metadata. |
| 15 November 2026 | Added reversible customer archiving with Archive/Restore confirmation modals and Active/Archived/All directory filters. Archived customers are hidden from new-order choices while existing orders and counts remain intact. Linked customers remain protected from deletion; their Delete controls are hidden. Migration 0012 defaults all existing customers to active. |
