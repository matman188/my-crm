# Scope of Work: Service Orders, Invoicing, and Business Reporting

Status: Draft for ongoing refinement. This document defines planned work; it does
not indicate that the features below have already been implemented.

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
| Order closure | Closure is a manual action. Payment must be settled before an order can be closed; payment does not close it automatically. |
| Payments in the first version | Full payment only. Deposits, partial payments, and payment instalments are outside the initial scope. |
| Business setup | One business per installation initially. The software should be reusable for other businesses through configuration. |
| Customer selection | Search existing customers or create a customer while capturing an order. |
| Product units (D01) | Whether a product represents a shoe, pair, or another unit depends on product setup. No shoe-specific unit is imposed by the order workflow. |
| Services per item | An item may have multiple services, including repeated selections of the same service. Each occurrence is charged separately. |
| Service notes | Each selected service occurrence supports its own optional text note for internal instructions; this note is excluded from the invoice. |
| Order notes | Provide a global notes section for the whole order, separate from individual service notes and customer-visible invoice notes. |
| Additional charges | Additional requests, such as overnight turnaround, can be represented as services. |
| Global services | Some services must be available without a link to a specific product. |
| Deadlines (D02) | Each order item has its own deadline date, with an optional time in the business timezone. |
| Assignment | One user is assigned to an order; assignment may happen at creation or later. |
| Invoice trigger | Confirming an order generates its invoice. |
| Invoice delivery | The invoice can be printed or emailed to the customer. |

The detailed defaults and controls proposed below remain recommendations unless
explicitly identified as confirmed. Open decisions are listed in section 13.

## 3. Current implementation baseline

The repository already provides:

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
4. For each order item, the operator selects the product/type, records identifying
   details and instructions, selects one or more applicable services (including
   repeated selections), optionally notes each service occurrence, and sets a
   deadline date with an optional time.
5. The operator adds any general extra services, such as an order-wide overnight
   surcharge, and any order-wide notes. The application calculates the total.
6. A worker may be assigned immediately or the order may remain unassigned.
7. The operator reviews and confirms the order. The application assigns its
   invoice number and generates an invoice using the confirmed information.
8. The invoice is downloaded/printed or emailed. Work can then be started and
   completion tracked per order item.
9. The supervisor assigns or reassigns the worker as needed and monitors deadlines.
10. The operator records full payment and collection/delivery independently, in
    whichever sequence occurs in practice.
11. Once fully paid, an authorized user manually closes the order. Closure does
    not silently mark unfinished work complete or mark items delivered.

## 5. Functional requirements

### 5.1 Customers and order entry

- Reuse the existing customer records and search capabilities. Allow quick
  customer creation from order entry, with duplicate suggestions using available
  contact details.
- Give each order a unique reference, customer, creation date, creator, order-wide notes,
  confirmation date, and optional assigned user.
- Provide a global notes section for general order instructions, alongside optional
  notes on individual service occurrences. Editing one must not overwrite the other.
- Keep order-wide notes and service notes as internal work instructions, separate
  from customer-visible invoice notes. Internal notes must not appear in the invoice
  PDF or customer invoice email.
- Allow draft orders to be saved and resumed. Confirmation requires a customer,
  at least one item, required item details and deadlines, and valid service prices.
- Use the customer's email for invoice delivery when available. A missing email
  must not prevent order creation, confirmation, or printing; email delivery must
  request a valid address before sending.

### 5.2 Products and physical order items

The product catalog describes reusable types of items, such as a ballet shoe type.
An order item describes the actual customer item being worked on. Two pairs of
the same catalog product can therefore appear as separate items on one order.

Each order item must support:

- A catalog product/type and a description or identifying label.
- Quantity/unit according to the selected product's setup, without requiring a
  fixed shoe-versus-pair choice for all businesses.
- Work instructions and a deadline date with an optional time.
- One or more selected service occurrences, including repeats of the same service,
  each with its own charge and optional internal text note.
- Work progress and completion date/time.
- Collection/delivery tracking. The proposed minimum supports item-level tracking
  and derives the overall delivery state, so partial collection can be represented.

Items with different deadlines or work instructions must be separate order lines.
The order's next outstanding deadline is derived from unfinished items; it must
not replace or overwrite the deadlines on individual items.

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
  Count each repeated occurrence once at its applicable charge quantity; selecting
  a service twice must not be collapsed into one charge. Editing or removing one
  occurrence must not modify the other occurrence or its note.
- Recommended first version: fixed monetary service prices. Percentage surcharges,
  automatic rush rules, discounts, and product-specific price overrides need
  separate agreement before inclusion.
- Keep money in decimal values. Snapshot prices and currency on confirmation so
  later catalog price or default currency changes do not alter existing invoices.

### 5.4 Assignment and staff workload

- Allow a single assigned user per order, including an unassigned state.
- Support assignment and reassignment after confirmation, with actor and timestamp
  history. Assignment changes must not create another invoice.
- Make the assigned user, outstanding work, instructions, and deadlines visible to
  the supervisor and to the worker according to agreed permissions.
- Show order-wide notes alongside the individual service occurrence notes so the
  worker can see both general instructions and the details of repeated services.
- Use the existing user accounts. Multiple workers per order, per-item assignment,
  and calculation of worker pay are outside the first version.

### 5.5 Statuses and manual closure

Keep these dimensions independent:

| Dimension | Proposed values or behavior |
| --- | --- |
| Order lifecycle | Draft, Confirmed/Open, Closed, Cancelled |
| Item work progress | Not started, In progress, Completed |
| Overall work progress | Derived from the items, including partially completed work |
| Delivery | Not delivered, Partially delivered, Delivered/Collected |
| Payment | Unpaid, Paid in full |
| Assignment | Unassigned or an assigned user |

Completed work does not imply payment or collection. Payment does not imply
completion, collection, or closure. Delivery does not imply payment.

Manual closure requires a confirmed, fully paid order. Closing an order with
unfinished or undelivered items should display a clear warning; those facts must
remain visible on the dashboard and in reports even after closure. Whether to
block such closure entirely remains an open decision. Reopening should be a
supervisor action with a recorded reason.

Cancellation must preserve the order reference and history. The treatment of an
already-issued invoice or payment on cancellation must be agreed before that
operation is implemented; cancellation must not silently erase financial records.

### 5.6 Full-payment recording

- Allow an authorized user to record the full outstanding invoice amount, payment
  date/time, payment method, reference, and recording user.
- Derive paid/unpaid from the recorded financial information. Reject accidental
  duplicate settlement and unsupported partial-payment amounts.
- Recording payment updates the order and invoice payment display without
  changing their original charges or closing the order automatically.
- Payment recording is manual in the first version. Online card payments, bank
  feeds, automatic bank reconciliation, deposits, and partial payments are excluded.
- Corrections to an incorrectly recorded payment require an authorized action,
  reason, and history rather than silent deletion. Refund handling is an open
  decision and must not be implied by a payment correction.

## 6. Invoices, PDF layout, and email

### 6.1 Confirmation and invoice integrity

- Generate one uniquely numbered invoice when an order is confirmed. Confirmation
  must be atomic and safe to retry: repeated clicks must not create duplicate
  invoices or consume the same number for different invoices.
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

- Open orders and unassigned orders.
- Items due today, due soon, and overdue, with their worker and order reference.
- Orders in progress and completed work awaiting collection/delivery.
- Partially delivered and delivered/collected orders.
- Unpaid invoices/orders, their outstanding value, and overdue payments when
  payment due dates are configured.
- Payments received in a selected period and workload by assigned user.

Dashboard categories can overlap. An order can be open, completed, and unpaid at
the same time. Closed orders with unfinished or uncollected items must not vanish
from the relevant operational lists.

### 7.2 Searchable order report

Start with a sortable, paginated table and filters rather than a custom report
builder. Use one row per order, with a link to item/service detail.

Suggested columns: order reference, invoice number, customer, created date,
confirmed date, earliest outstanding deadline, assigned user, order lifecycle,
work progress, delivery status/date, invoice amount/currency, paid amount,
outstanding amount, payment date/method/reference, and closure date.

Suggested filters: text search, date range and date basis, assigned user including
unassigned, lifecycle, work progress, delivery status, payment status, overdue
items, and product/service. Provide totals for the filtered result and CSV export.

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
  reporting, and closure permissions. Supervisor is a business capability whose
  mapping to the existing roles still needs agreement.
- Recommended split: operators capture orders; workers update permitted work
  progress; supervisors assign users, close/reopen orders, and view financial
  reports; administrators manage catalogs and business settings.
- Enforce permissions on the server as well as in navigation. Decide whether
  workers see only assigned orders and whether they can see prices/customer data.
- Record important transitions: confirmation, assignment changes, deadline changes,
  work completion, delivery, payment/corrections, closure/reopening, and cancellation.
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
| ServiceOrder | Customer, reference, lifecycle, assigned user, key dates, and order-wide internal notes |
| OrderItem | Actual customer item/type, description, product-defined quantity/unit, deadline date with optional time, work and delivery state |
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
2. **Work management:** assignment/reassignment, work and delivery statuses,
   operational lists, permissions, and change history.
3. **Invoices:** confirmation, numbering and snapshots, business invoice settings,
   approved PDF sample, download/print, email configuration, and delivery history.
4. **Settlement and closure:** full-payment recording and corrections, manual
   closure/reopening, cancellation rules, and financial history.
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
7. One item can be completed before another. A completed order remains visible
   as awaiting collection and/or unpaid where appropriate.
8. Full payment records the expected amount and reference. Partial or duplicate
   settlement is rejected. Payment does not close the order automatically.
9. An authorized user closes a fully paid order manually. Delivery and work facts
   remain accurate; any permitted reopening records the actor and reason.
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

## 12. Outside the initial scope

- Multiple businesses sharing one installation with isolated accounts/data.
- Deposits, partial payments, payment plans, online payment processing, and bank feeds.
- Inventory purchasing/stock control or selling physical products as retail stock.
- Payroll, commissions, worker compensation, and automated accounting integration.
- Customer self-service portals, online booking, SMS/WhatsApp notifications, and
  automatic deadline reminders.
- Multiple assignees or different workers per item on the same order.
- Arbitrary invoice layout builders, advanced report builders, and currency conversion.

Refunds, credit notes, discounts, and correction of issued financial documents
need an explicit decision; they are not assumed to be included automatically.

## 13. Open decisions and suggestions

Decisions D01 (product-defined units) and D02 (deadline date with optional time)
are resolved in section 2. The remaining IDs are kept stable for future reference.

| ID | Decision to confirm | Suggested starting point |
| --- | --- | --- |
| D03 | How are charge quantities derived from product quantities and service occurrences, and which extras apply once per order? | Keep charge quantities explicit, charge every selected service occurrence, and show order-level extras separately. |
| D04 | Can an order be closed while work or delivery is incomplete? | Always require full payment; warn before manual closure with outstanding work/collection. Confirm whether a hard block is preferred. |
| D05 | Who can create/confirm orders, assign workers, record payment, close/reopen, and see finances? | Agree the operator/worker/supervisor permissions before adding roles or changing existing ones. |
| D06 | Which business and tax details, payment terms, invoice numbering, and disclaimers are needed? | Review actual business details and a sample invoice; do not invent tax status or final disclaimer wording. |
| D07 | How are confirmed orders corrected, cancelled, or refunded? | Preserve issued records and record reasons; agree void/reissue/credit behavior before financial edits are allowed. |
| D08 | Which email sender/provider should deliver invoices, and is sending always manual? | Explicit send with a preview initially; store provider credentials securely outside the repository. |
| D09 | Can different items be collected separately? Is a collected-by name/reference needed? | Track delivery per item and derive order-level status; confirm the information staff need at collection. |
| D10 | What dates and worker attribution should financial reports use? | Separate invoice-date sales and payment-date receipts; current worker for workload, with historical attribution agreed separately. |
| D11 | What target date/time does an overnight request mean for the business? | Let the operator enter the agreed deadline and optional time; do not silently calculate one from the service name. |

## 14. Maintaining this scope

Update this document when decisions are confirmed, identifying what changed and
whether it affects earlier phases. Keep implementation progress separate from
requirements so planned features are not mistaken for delivered functionality.

| Date | Decision/change |
| --- | --- |
| 14 November 2026 | Initial scope captured from the business workflow. Confirmed manual closure, full payment only, and one business per installation initially. |
| 14 November 2026 | Confirmed product-defined units, deadline dates with optional times, repeated service selections on one product, optional internal notes per service occurrence, and a global order notes section. Updated requirements and acceptance scenarios; resolved D01/D02 and retained overnight interpretation as D11. |
