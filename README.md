# My CRM

My CRM is a Django 6 application for managing customers, users, products, services, and system settings in a lightweight CRM workflow.

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

## What Else To Consider

- If `db.sqlite3` was already committed earlier, remove it from git tracking once with `git rm --cached db.sqlite3` and commit that change.
- If you add new environment variables later, update `.env.example` and this README in the same change.
- Consider adding a deployment-specific settings module or environment-driven database configuration before moving beyond local SQLite usage.
- Consider adding CI to run `python manage.py test` and `python manage.py check` on every push or pull request.
