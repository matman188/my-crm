# Quality-of-life implementation

This pass implements the accepted review suggestions while retaining the existing
four order statuses and stage-specific field locks.

- Shared unsaved-change protection, save feedback, required markers, error focus,
  and confirmation modals for list actions.
- Orders work queues, nearest-deadline sorting and urgency labels, backed by a
  configurable business timezone and clickable dashboard counts.
- Return navigation that preserves list filters, page, and scroll position.
- Duplicate item, apply deadlines to all items, and undo item/service removal.
- Preserve staff history through deactivation and deletion protection.
- Consistent captured prices and explicit Global service labels.
- Product/service archiving with existing-order preservation.
- Pagination across directories, neutral customer headings, and contact links.

## Behaviour

The directory pages show 25 records at a time. Opening a record carries its list
URL into the form; Back and successful saves retain search, filters and page.
Scroll restoration uses browser session storage and stores only the list URL and
scroll position. Unsaved form data is not stored in the browser. Refresh/closing
the tab uses the browser's own unsaved-change prompt; normal links use the app's
modal. Save itself does not require confirmation.

Orders has All orders, Open Orders, My Orders, Unassigned, Due Today, Overdue and
Awaiting Collection views. Counts respect the customer/search scope. Changing
queues resets stage/payment/collection filters; further filtering works within
the selected queue. Open Orders includes Draft and In Progress, independently of
assignment, payment or collection. It also has a matching dashboard count.
My Orders includes all stages assigned to the signed-in user.
Unassigned includes Draft and In Progress. The redundant Unpaid shortcut is removed
from Orders; use the Payment status dropdown. The existing Unpaid dashboard/legacy
view still means In Progress or Complete with Unpaid payment status, and displays
Unpaid in the dropdown; choosing another payment filter exits that legacy queue.
Awaiting Collection means Complete and not collected, independently of payment.
Raw stage/payment filters can still find other records.

List filters now share a search row with a Search button alongside the text field,
and a separate row of labelled dropdowns. Dropdown changes apply immediately;
typing or leaving the text field alone does not submit. Search/Enter applies text,
and changing a dropdown applies the form's current search and filter values.
Keep selected queue/customer scope and restart pagination when applying controls.
This behaviour applies to Orders and the customer/catalogue directories; Users
and Product Categories retain manual text search using the same layout.

Due Today/Overdue count only Draft and In Progress. An optional time makes today's
item overdue once that time passes. A date without a time becomes overdue the
next day. System Settings > Business timezone controls these rules; the initial
value is Africa/Johannesburg. Deadline sorting puts open work first, then earliest
item date/time, with date-only items after timed items on the same day.

Duplicate item copies the product, active service rows, quantities, notes and
deadline into a new item. It uses today's catalogue prices for the new charges;
the source keeps its captured prices. An archived product/service cannot become
a new selection, so check the duplicated item before saving. Apply to all items
copies a date and optional time to undeleted items; a blank time clears their
times. It is available in Draft and In Progress. Undo removal restores a row until
the order is successfully saved. Save buttons remain at the top and in a sticky
bottom bar. Orders use a stacked table layout on narrow screens.

Archive/Restore products and services from their directories. Archived entries
are hidden from new selections, while existing orders retain their selections
and prices. Previously linked archived products stay visible when maintaining a
service's product links. Concurrent archiving is checked again during order save.
Staff can be deactivated/reactivated from Users; assignment and creator history
remain intact. Users linked to orders cannot be deleted, including through Django
admin. System admins and the signed-in account cannot be deactivated there.

Migrations 0013 and 0014 add catalogue archive flags, business timezone and staff
deletion protection. They are applied locally. A SQLite backup was taken first;
all pre-existing values across 19 tables were verified unchanged. Other checkouts
run `python manage.py migrate`.

## Verification

Run `npm ci` once to install the development-only DOM test dependency. It is not
needed to run Django or use the app.

```powershell
python manage.py test crm.tests --noinput
npm test
python manage.py makemigrations --check --dry-run
python -m ruff check crm
```

The Django suite includes a rendered-form DOM test when Node and `npm ci` are
available. It exercises actual template output and posts the duplicated item back
to Django, checking fresh IDs, current versus captured prices, quantities,
deadlines, undo, locks, independent customer saves, dirty state, confirmations,
double-submit protection and return navigation.

Validation on 15 November 2026: 202 tests passed in the full Django run, followed
by all 18 QOL tests after the final Discard/Delete return-navigation refinement.
All 23 standalone JavaScript tests pass. Ruff reports no issues, migration
consistency reports no changes, and `git diff --check` reports no whitespace
errors. The rendered DOM test is enabled locally and passes.

Authenticated local HTTP checks cover the dashboard, orders, customers, products,
services, users, settings and new-order screens. Browser visual inspection remains
pending because the desktop browser tool fails during initialization with
`failed to write kernel assets: The system cannot find the path specified. (os error 3)`.

## Browser tool setup

The browser tool is exposed to this conversation but fails before connecting to
the CRM. This appears to be a desktop tool initialization issue, rather than a
Django problem; that diagnosis is an inference from the error.

- The built-in browser installs with the desktop app. Mention `@Browser` and ask
  it to open `http://127.0.0.1:8000/`. Check Settings > Browser > Agent permissions
  if access to the local site is restricted. See the [official browser guide](https://learn.chatgpt.com/docs/browser).
- Update/restart the desktop app and retry in a fresh chat. If the kernel-assets
  error continues, use `/feedback` and include the exact error and chat ID.
- To use your existing Chrome/Edge tabs, install/enable the extension from
  Settings > Computer Use, use the right browser profile, and restart the browser
  after enabling it. See [extension setup and troubleshooting](https://learn.chatgpt.com/docs/chrome-extension).
- Native app access is separate: Settings > Computer use > Control > Any App,
  install if prompted, and enable it. Browser-only CRM testing does not require
  broad native app access. See [computer-use setup](https://learn.chatgpt.com/docs/computer-use).
