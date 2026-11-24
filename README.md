# DebtBlaster

DebtBlaster is a private, owner-managed accounts receivable app. It stores clients, debts/invoices, due dates, confirmed payments, outstanding balances, and reminder history. Each account can only see its own records.

## Features

- Add, edit, search, and archive clients.
- Record debts with amount, currency, invoice number, due date, and reminder preference.
- Record full or partial payments with a payment date, method, and reference.
- Automatically calculate paid and outstanding amounts and mark debts paid at a zero balance.
- Stop reminder schedules and cancel pending reminder emails when a debt is paid or reminders are disabled.
- Send email reminders before, on, and after the due date. The default frequency is weekly.
- Owner-scoped JSON endpoints at `/api/clients/` and `/api/debts/`.

## Run locally (Windows PowerShell)

Use Python 3.12 or newer. In this directory:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open <http://127.0.0.1:8000/> and sign in with the superuser you created. SQLite is used by default, so there is no database server to install for local use. Your local database is created as `db.sqlite3`.

## Email reminders

Email is sent through SMTP. Set these environment variables in the same PowerShell window before starting the server or running reminder commands:

```powershell
$env:EMAIL_HOST = "smtp.example.com"
$env:EMAIL_PORT = "587"
$env:EMAIL_HOST_USER = "your-smtp-user"
$env:EMAIL_HOST_PASSWORD = "your-smtp-password"
$env:EMAIL_USE_TLS = "True"
$env:DEFAULT_FROM_EMAIL = "DebtBlaster <billing@example.com>"
```

To queue upcoming reminders and preview the queue without sending any email:

```powershell
python manage.py schedule_reminders
python manage.py process_reminders --dry-run
```

Run these two commands on a recurring job (for example, every 15 minutes) while the app is in use. On Windows, `run_reminders.ps1` runs both commands and loads optional settings from a `.env` file:

```powershell
python manage.py schedule_reminders
python manage.py process_reminders
```

The first command creates due reminder events. The second sends them and retries temporary email failures. In Windows Task Scheduler, create a recurring task with `powershell.exe` and arguments `-NoProfile -ExecutionPolicy Bypass -File "C:\path\to\DebtBlaster\run_reminders.ps1"`. Copy `.env.example` to `.env` and enter SMTP credentials there for the scheduled task. Without a recurring job, reminders are recorded but are not sent automatically.

For local development without SMTP, set `EMAIL_BACKEND` to `django.core.mail.backends.console.EmailBackend`; messages will appear in the command output instead of being delivered.

## Configuration

Settings are read from environment variables:

`.env.example` documents the variables; Django does not automatically load a `.env` file. Export the values in your shell or configure them in your hosting provider.

| Variable | Default | Purpose |
|---|---|---|
| `DJANGO_SECRET_KEY` | Development-only key | Set a private random value for deployment. |
| `DJANGO_DEBUG` | `True` | Set to `False` in deployment. |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated host names. |
| `TIME_ZONE` | `Africa/Lagos` | Django display and reminder date timezone. |
| `DB_ENGINE` | `sqlite` | Set to `postgres` to use PostgreSQL. |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | — | PostgreSQL connection details when `DB_ENGINE=postgres`. |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Empty / port 587 | SMTP connection details. |
| `EMAIL_USE_TLS`, `EMAIL_USE_SSL` | `True` / `False` | SMTP transport security. |
| `DEFAULT_FROM_EMAIL` | `DebtBlaster <reminders@example.com>` | Sender displayed on reminders. |

Before public deployment, use a production WSGI/ASGI server, HTTPS, a strong secret key, a production database, and secure SMTP credentials. Do not commit credentials or a live `db.sqlite3` file.

## Main routes

- `/` — client dashboard (sign-in required)
- `/clients/` — client list and balances
- `/debts/` — debt and invoice list
- `/payments/create/` — record a payment
- `/admin/` — Django administration
- `/api/clients/`, `/api/debts/` — authenticated JSON endpoints
