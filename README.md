# My CRM

My CRM is a Django 6 application for managing customers, users, products, services, and system settings in a lightweight CRM workflow.

## Development Scope

See the [scope of work](docs/scope-of-work.md) for the planned service-order,
invoicing, payment, dashboard, and reporting workflow, confirmed decisions, and
open questions.

Service orders with Status, Collected, and Payment status are available from
**Orders** in the sidebar. See
[development status](docs/development-status.md) for the implemented workflow,
pricing rules, setup instructions, and remaining milestones.

The [QOL implementation notes](docs/qol-improvements.md) describe work queues,
archiving, safer forms, order-entry shortcuts and browser-tool setup.

Available now: [invoice settings and sample PDF preview](docs/invoice-preview.md)
under **System Settings > Invoicing**, including logo upload and previews using
unsaved settings. All Python dependencies, including PDF inspection/rendering
tools, are in `requirements.txt`. Run migrations after updating.

Next milestone: order-linked [invoice design and delivery](docs/invoice-design.md), covering
the proposed Invoice record, stored PDF, layout/configuration, order actions,
open correction rules and a checklist for resuming development.

The same plan records [simple order-based refunds and reporting](docs/invoice-design.md#simple-refunds-and-reporting-directly-on-orders)
for later implementation: attached refund entries, Total Refunded and Net Order
Value, and reports filtered directly on Service Orders. Separate cash-flow and
accounting screens are deferred.

For development checks, run `python manage.py test crm.tests --noinput`.
Install Node test dependencies with `npm ci`, then run `npm test` for JavaScript
checks; the Django suite also uses them to exercise rendered order forms. Node
dependencies are only needed for these development checks.

## Stack

- Python
- Django 6
- SQLite for local development
- `python-dotenv` for local environment variables

## Clone And Run Locally

### 1. Clone the repository

```powershell
git clone <your-github-url>
cd my-crm
```

### 2. Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If you are using Command Prompt instead of PowerShell:

```bat
.\.venv\Scripts\activate.bat
```

### 3. Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Create your local environment file

```powershell
Copy-Item .env.example .env
```

The app will still run without a `.env` file because `config/settings.py` has development fallbacks, but keeping a local `.env` is the safer and clearer option.

### 5. Create a fresh database

```powershell
python manage.py migrate
```

This creates `db.sqlite3` locally from the tracked migration files. The database file is intentionally ignored by git.

### 6. Optional: create your own admin user

```powershell
python manage.py createsuperuser
```

### 7. Start the development server

```powershell
python manage.py runserver
```

Open http://127.0.0.1:8000/ in your browser.

## Common Django Commands

### Activate virtual environment

```powershell
.\.venv\Scripts\Activate.ps1
```

### Start the development server

```powershell
python manage.py runserver
```

### Start the server on a custom port

```powershell
python manage.py runserver 8080
```

### Create migration files after changing models

```powershell
python manage.py makemigrations
```

### Apply database migrations

```powershell
python manage.py migrate
```

### Show migration status

```powershell
python manage.py showmigrations
```

### Create an admin user

```powershell
python manage.py createsuperuser
```

### Change a user's password

```powershell
python manage.py changepassword <username>
```

### Recover local admin access

There is no built-in password for `admin`. Its password is chosen when the
superuser is created, and Django stores only a password hash in the local
database. Passwords used in the tests are unrelated to your local accounts.

From the project directory, use the existing virtual environment to reset it:

```powershell
.\.venv\Scripts\python.exe manage.py changepassword admin
```

Enter your new password twice. The terminal does not show characters while you
type a password. Run this in a separate terminal if the development server is
already running. If Django reports that the user does not exist, create a
superuser with `.\.venv\Scripts\python.exe manage.py createsuperuser`.

Loading demo data creates `demo.sysadmin` with the demo password `DemoPass123!`.
This account is a System Admin, but it is not a Django superuser and cannot
change the `admin` superuser through the CRM user management screen. Resetting
`admin` with the command above does not require its old password.

### Run tests

```powershell
python manage.py test
```

### Run project checks

```powershell
python manage.py check
```

### Open the Django shell

```powershell
python manage.py shell
```

### Collect static files

```powershell
python manage.py collectstatic
```

### See all available commands

```powershell
python manage.py help
```

## Development Workflow

When you change models:

1. Run `python manage.py makemigrations`
2. Run `python manage.py migrate`
3. Run `python manage.py test`

When you pull model changes from GitHub:

1. Activate the virtual environment
2. Install dependencies if `requirements.txt` changed
3. Run `python manage.py migrate`

## Project Notes

- `db.sqlite3` should stay local and should not be committed.
- Migration files in `crm/migrations/` should be committed so a fresh clone can build the database schema.
- `.env` should stay local and should not be committed.
- `.env.example` is the tracked template for local setup.
- The CRM app automatically bootstraps its permission groups after migrations via a `post_migrate` signal.
- Demo data should be loaded from the CRM System Settings screen when needed.

## Demo Data

Use **System Settings → Load demo data** for an industry-neutral sample catalog:
standard items, special items, and item sets; basic services, customisation,
assessment, express service, and delivery; and a mix of individual and business
customers. Express service and delivery are global services, so they can also be
added as order-wide extras. Sample prices are illustrative.

Refreshing the original demo catalog renames its records in place, preserving
order references and captured order prices. Demo usernames and the demo password
are unchanged. Reloading still refreshes demo account details and passwords.

## What Else To Consider

- If `db.sqlite3` was already committed earlier, remove it from git tracking once with `git rm --cached db.sqlite3` and commit that change.
- If you add new environment variables later, update `.env.example` and this README in the same change.
- Consider adding a deployment-specific settings module or environment-driven database configuration before moving beyond local SQLite usage.
- Consider adding CI to run `python manage.py test` and `python manage.py check` on every push or pull request.
