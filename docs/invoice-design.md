# Next milestone: invoice design and delivery

Recorded: 15 November 2026. Status: settings and sample PDF preview implemented;
order-linked invoice issuance, storage/history and email remain planned.

This records the latest proposed approach discussed with the owner. Use it with
[scope section 6](scope-of-work.md#6-invoices-pdf-layout-and-email) and
[development status](development-status.md). Step 1 is complete: see
[invoice settings and sample preview](invoice-preview.md). Next implement order-linked
issuance and storage after agreeing the correction rules. Connect email
delivery after the mail server is configured.

Latest refinement, 15 November 2026: keep the Service Order as the primary work
and reporting record. See the simple refund/reporting plan below and
[scope section 7.2](scope-of-work.md#72-searchable-order-report). Separate payment
ledgers, cash-flow reports and accounting screens are not prerequisites for the
initial order-based report.

## Recommended approach

Keep invoice actions on the service-order screen, backed by a small Invoice
record and its stored PDF. The operator does not manually maintain a duplicate
order or need a separate invoice-management screen for the first version.

The order is the working record. An issued invoice preserves the billing details
at a particular point in time. Current orders capture service prices and currency,
but customer details and product/service names still come from mutable records.
Returning to Draft also permits commercial changes. Generating every download
from the current order could therefore produce a different document later.

Capture automatically when issuing:

- A unique invoice number, issue date/time, issuing user and service-order link.
- Business identity, customer billing details, and product/service descriptions.
- Product grouping, service quantities, captured unit prices, currency, line
  totals, subtotal and any agreed tax breakdown, and total.
- Banking instructions, disclaimer and customer-facing Invoice Note. Keep the
  instructions and wording used at issue time. Payment terms and automatic
  payment due dates are deferred for now (15 November 2026).
- The template version and a reference to the issued PDF file.
- The information needed to retain voided/replaced invoices, once the correction
  process has been agreed. Prefer one active invoice per order initially.

Use structured invoice/line snapshots as well as the stored PDF. Store the file
through application-managed storage, with a reference in the database, rather
than putting the PDF bytes into ordinary database columns. Local private file
storage is sufficient initially; keep downloads behind authenticated permissions.
Back up the database and invoice files together. Reprints, previews and email
attachments use the original issued file. Changes to business settings or the
PDF template affect future invoices.

## Proposed order-screen actions

| Action | Behaviour |
| --- | --- |
| Preview invoice | Render the current draft as an actual PDF, clearly marked Preview. Do not allocate an invoice number or create an issued invoice. A temporary preview can be generated on demand. |
| Generate invoice | Explicit action after order submission. Capture the billing snapshot, allocate a unique number and store the PDF. Agree eligible stages before implementing; In Progress/Complete are the proposed starting point, with no first issue on a Cancelled order. |
| View / Download / Print | Reuse the issued PDF. Repeated clicks do not issue another invoice or change its number. Display invoice number and issue date on the order. |
| Email invoice | Later, open a recipient/subject/message review and send the stored PDF. Record the actual recipient, sender, time and result of each attempt. |

This explicit Generate action is the latest working proposal and supersedes the
earlier automatic-on-Submit assumption in the implementation plan. Submit still
starts work by moving Draft to In Progress. Confirm the final issuance trigger
before implementation; no current submission behaviour has been changed.

Issuance must be safe under repeat clicks and concurrent requests. Do not mark an
invoice as successfully issued until its snapshot and PDF are available. Agree
retry/recovery behaviour for file-generation failures; repeated attempts must not
create duplicate issued invoices. Previewing is never an issuance action.

## PDF layout

Step 1 provides one fixed A4 sample template using ReportLab, selected for the
Windows/Python development setup and predictable PDF layout. It uses embedded
fonts, short/multi-page samples and a preview modal. This refines the earlier
HTML/CSS-renderer candidate. Review the sample before adapting the renderer to
real invoice snapshots; order-linked previews and issuance are still future work.

1. Header: business logo and details, invoice number and issue date.
2. Customer block: customer billing details, service-order reference and payment
   information. Payment terms and calculated payment due dates are omitted for now.
3. Charges: each product as a section heading with its service rows underneath.
   Service rows show quantity, unit price and line total. Products have no quantity
   field. Preserve repeated service occurrences in the billed lines/quantities.
4. Order-wide extras: a separate group after the item/service groups.
5. Totals: subtotal and any agreed tax breakdown, prominent total and currency.
6. Footer: banking details, payment-reference instructions, terms, disclaimer and
   an explicitly customer-facing Invoice Note when supplied.

Repeat table headings on long invoices, keep amounts aligned and readable, and
handle page breaks and page numbering consistently. Avoid splitting a service
row where practical. Preview must show the actual generated PDF, so preview and
download/print use the same document.

Order Notes, Customer Notes, item notes and service-occurrence notes are internal
and must be excluded from both the PDF and customer email. Add a separate Invoice
Note for content intentionally addressed to the customer. Whether to show work
deadlines remains open; if included, snapshot their issue-time values and clearly
identify them as work deadlines. Later operational deadline changes
must not silently rewrite the invoice.

## Business settings versus fixed formatting

| Configurable by the business | Controlled by the application |
| --- | --- |
| Business name, logo, address and contact details | Overall layout and placement of blocks |
| Applicable registration/tax identifiers, once confirmed | Required document identifiers and order reference |
| Banking details and payment instructions | Amount calculations, rounding, alignment and currency formatting |
| Disclaimer, default customer-facing footer/Invoice Note | Clear separation of internal and customer-facing content |
| One controlled accent colour | Fonts, spacing, table columns, page-break rules and image sizing |
| Agreed invoice prefix/numbering configuration | Unique numbers, historical references and safe repeat issuance |
| Email subject/message defaults | Correct issued PDF attachment and delivery history |

Currency and business timezone already exist in settings; retain their current
roles and snapshot invoice currency. Exact invoice numbering rules and whether
prefix changes should be permitted after first issue still need agreement.
No arbitrary HTML editor, drag-and-drop layout builder, or multiple themes are
planned for this first version. Tax status, tax calculations and final disclaimer
wording must be confirmed for the business; do not infer them from the currency.

## Corrections and cancellation: decide before issuing invoices

The current Return to draft action allows customer, product, service, quantity and
charge changes. Issued invoices introduce a new integrity rule that is not yet
implemented. Agree the correction process before enabling invoice issuance.

Recommended starting point: retain the original issued invoice and require an
explicit replacement process for changes to invoiced content. Preserve the old
document, number, reason, actor and relationship to its replacement. Prevent an
ordinary Return to draft/save from silently changing financial details while an
active invoice still represents the previous values. The precise void/reissue,
credit and already-paid-order rules remain open (scope D07).

Operational deadlines, assignment, collection and internal notes can continue to
follow their existing order-stage rules without rewriting the issued document.
Order Notes remain editable in every state. Current Paid/Unpaid/Refunded fields
remain manual indicators pending the agreed refund/payment rules; they must
not silently alter an issued PDF. Order cancellation must retain invoice history;
its financial treatment and any refund handling need explicit agreement.

## Simple refunds and reporting directly on orders

Planned for later implementation: the operator reports directly on Service
Orders and handles refunds on the same screen. Invoice versions and PDF history
stay attached supporting records. Keep one order for the piece of work; do not
require a separate accounting screen or manually maintained reporting table.

- Add Record refund with amount, date, reason and optional affected item/service.
  Retain each refund entry, including multiple refunds against the same order.
- Retain Order Total as the sum of original/current service charges. A refund
  does not reprice or delete those charges or rewrite an issued PDF.
- Show Total Refunded as the sum of the attached refunds and Net Order Value as
  Order Total minus Total Refunded: R500 total, R100 refunded, R400 net value.
- Report one row per order: Order, Customer, Order Date, Assigned To, Status,
  Payment Status, Currency, Total, Refunded and Net Order Value. Provide filtered
  totals and CSV export, grouping different currencies separately.
- Initially filter on order creation date in the business timezone, with text,
  status, payment-status and assignee filters. Paid work can be selected using
  the payment-status filter. No payment ledger is needed for this order-value view.
- Use current order values and all attached refunds. A refund against an older
  order updates its net value and the earlier period's totals when rerun, even if
  the refund happened outside that order-date period. Make that behaviour clear.
- Label this Net Order Value. It does not establish how much cash was actually
  received during the period. Defer separate cash-flow and accounting reports.

Refund recording does not itself transfer money. Refund alone need not reopen
the order. Agree refund permissions, positive amounts, duplicate/stale protection,
maximum refundable amount and validation against money received before building
the action. Partially Refunded/Refunded summary rules should use the entries;
the exact transition from today's manual payment statuses remains to be agreed.
Partial refunds do not imply accepting deposits or partial initial payments.

The simple reporting approach supersedes the earlier suggestion to make separate
payment-date/invoice-date reporting the initial focus. It does not remove the
need to preserve invoice versions or settle D07 before editing issued billing
details. Credit-note/payment records can be introduced where required by the
agreed invoice-correction rules, without turning the initial order report into
an accounting module.

## Email delivery later

Prepare the customer-facing recipient/subject/message preview and use the issued
PDF as the attachment. Agree the sender/provider and connect delivery when the
email server is available. Do not report a successful send before delivery is
configured. Development backends can test message construction without sending
real customer email. A failed send can be retried without issuing a new invoice.
Keep credentials outside source control and ordinary business settings.

## Resume here next time

1. Confirm the explicit Generate invoice trigger, eligible order stages, and the
   correction/cancellation rules (D07) before implementing issuance.
2. Gather real business/logo/contact/banking details, numbering
   preference, applicable tax details and approved disclaimer text (D06). Use
   clearly labelled sample data while designing; do not invent final details.
3. Completed: business invoice settings, logo upload and sample A4 PDF previews.
   See [the implemented preview milestone](invoice-preview.md). Review the layout
   with real business wording before issuing customer invoices.
4. Implement the Invoice/line snapshots, unique numbering, stored private PDF and
   duplicate/concurrent-generation protection, including failure recovery.
5. Add Preview, Generate, View, Download and Print on orders. Verify old invoices
   survive changes to customers, catalogue, settings, notes and operational dates.
6. Add the email review/delivery history flow, connecting actual sending when the
   mail server is configured (D08).
7. Add simple refund entries and the order-based report above: refund capture,
   derived refund/net totals, order-date filters, status/payment/assignee filters
   and CSV export. Confirm refund validation and payment-summary rules first.

Implemented: invoice settings, migration 0015, logo handling and ephemeral sample
PDF preview/download. Invoice records/numbering, actual order invoice generation,
issued PDF storage/history and email delivery remain planned.
Refund recording, net-order totals and the order-based report are also planned,
not implemented by this update.

## Technical references

- [Django file fields and storage](https://docs.djangoproject.com/en/6.0/ref/models/fields/#filefield)
- [Django email attachments and development backends](https://docs.djangoproject.com/en/6.0/topics/email/)
