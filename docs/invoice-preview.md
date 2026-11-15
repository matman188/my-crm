# Invoice settings and sample PDF preview

Implemented on 15 November 2026. This is step 1 of the
[invoice plan](invoice-design.md). Issuing invoices for actual orders, numbering,
invoice history/storage and email delivery remain future work.

## Using it

Open **System Settings > Invoicing** with an account that can change System
Settings. General settings retain Company Name, Default Currency, Business
Timezone and Demo Data. Invoicing has three sections:

| Section | Settings |
| --- | --- |
| Business details | Shared business name, logo, address, email, phone, optional registration and tax identifiers |
| Payment details | Multiline banking details and payment instructions |
| Invoice appearance and wording | Prefix (default INV), Teal/Navy/Forest/Plum/Slate accent, terms/disclaimer and default customer-facing Invoice Note |

Business name is shared with the rest of the CRM. Currency and timezone are read
from General. Invoice and General saves update their own fields so saving one
section does not reset the other. Blank optional details are omitted from PDFs.
Tax identifiers are display text only; no tax calculations are introduced here.

**Save settings** persists the form. **Preview sample invoice** opens an actual
PDF in a modal using the current form values, including an unsaved logo upload or
logo removal. Choose Short invoice or Multi-page invoice beside the button. The
modal supports closing/Escape and downloading the sample. Closing it retains
unsaved form values; previewing does not clear the form's dirty state. Existing
navigation/refresh warnings continue to protect unsaved changes.

Preview uses fictional customer/order details, the current business-local issue
date and configured currency. Payment terms and calculated payment due dates
were removed for now on 15 November 2026. It is visibly marked
PREVIEW, uses a prefix-PREVIEW reference, and never allocates a real invoice
number. No service orders, customers, charges or issued invoice records are
created or changed. Preview PDFs and staged logo uploads are not stored on the
server. Responses are private and not cacheable.

## Layout

The fixed A4 renderer uses ReportLab with embedded bundled fonts, consistent
margins, product groups with service quantity/rate/amount rows, order-wide extras,
subtotal/total, optional banking/payment blocks, Invoice Note and terms. The
short sample has one product; the long sample has eight products and exercises
wrapping and repeated table headings. Product groups stay together in the sample,
and each page has a preview watermark and page number. Long user-entered wording
can flow onto additional pages.

Logo, business content, prefix, terms and controlled accent colour are configurable.
Fonts, columns, spacing, page breaks and totals remain application-controlled.
Internal customer/order/item/service notes are never sourced for these samples.
The explicitly customer-facing Invoice Note is included when provided.

The supplied review PDFs use fictional Sample Services Studio settings and a
sample logo; these values were not saved over the installation's business details:

- `output/pdf/sample-invoice-short.pdf`: one-page layout review.
- `output/pdf/sample-invoice-multipage.pdf`: two-page layout review.

These local review artifacts are ignored by Git. Actual page count depends on
the configured business text and logo. The output is a layout sample for review,
not an issued billing document or a statement of tax compliance.

## Uploads and access

Logos accept PNG/JPEG up to 2 MB and 4096 pixels per side. Accepted uploads are
normalized to PNG, resized to at most 1600 pixels per side, and assigned random
filenames. Upload constraints also apply through Django admin. Replacing or
removing a logo changes the current selection; old stored assets are not deleted
automatically. Any cleanup policy should account for future issued snapshots.

Saved logos are accessed through the permission-protected
`/system-settings/invoice-logo/` endpoint, rather than public media links.
Media files are stored under `MEDIA_ROOT` (local `media/`) and ignored by Git.
Back up saved settings and media together. The preview endpoint requires POST,
CSRF and the same System Settings permission; client-supplied logo URLs are not
fetched.

## Development and verification

Install all Python dependencies, including PDF test/extraction/rendering tools,
with `python -m pip install -r requirements.txt`. Node checks use `npm ci` once.

```powershell
python manage.py migrate
python manage.py test crm.tests --noinput
npm test
python manage.py makemigrations --check --dry-run
python -m ruff check crm
```

Migration 0015 adds invoice settings with blank/default values. It is applied
locally; a SQLite backup was taken and all existing values across 19 tables were
verified unchanged. No invoice or refund models are added by this migration.
Migration 0016 subsequently removes the payment-terms setting only. It is also
applied locally, with a backup taken first and all retained values verified
unchanged. The removal passes 30 focused invoice/settings/migration tests.

PDF checks use pypdf for content and PDFium to render pages to PNGs because
Poppler is unavailable in this Windows environment. Both supplied review PDFs
have been visually inspected for wrapping, alignment, page breaks and footers.
Server tests cover unsaved previews, settings isolation, logo validation/removal,
permission/CSRF checks, sample totals, optional sections, dates/currency and long
content. DOM tests cover modal preview, preserved dirty state, duplicate clicks,
cancellation, error handling and retry. Live authenticated HTTP checks confirm
settings and PDF endpoints respond without persisting the preview business name.

The full Django suite passes (222 tests), as do all 32 JavaScript checks. Ruff,
migration consistency, dependency checks and whitespace checks pass.

Next: confirm the issued-invoice correction rules, then implement invoices linked
to real orders. Keep the simple order-based refund/reporting plan separate from
this completed settings/preview milestone.
