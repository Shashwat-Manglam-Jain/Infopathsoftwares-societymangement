# InfoSociety — Society Banking Software

> Cloud-hosted banking SaaS for cooperative societies | By **InfopathSolutions** — *To innovate your business process*

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Django](https://img.shields.io/badge/Django-5.1-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue)
![Tests](https://img.shields.io/badge/Tests-299_passing-brightgreen)
![i18n](https://img.shields.io/badge/i18n-EN_|_HI_|_MR-orange)
![License](https://img.shields.io/badge/License-Proprietary-red)

---

## Overview

InfoSociety is a multi-tenant banking platform purpose-built for **credit cooperative societies**, **multistate cooperatives**, **nidhi companies**, and **thrift societies** in India. Each society signs up via a self-service portal, gets its own isolated database schema, and is operational within minutes.

Societies pay a monthly subscription. All hosting, updates, backups, and security are managed centrally on AWS.

---

## Features

### Core Banking
- **Member Management** — KYC (Aadhaar/PAN), nominees, photos, documents. Category flags for senior citizen, widow, ex-military, employee, director (auto interest bonus). Member exit tracking. Excel import/export.
- **Share Capital** — Purchase, transfer, surrender. Auto certificate numbers. Dividend calculation.
- **Savings Accounts** — Deposit, withdrawal, daily interest accrual. Passbook printing. Security deposit accounts.
- **Loan Management** — Mortgage and non-mortgage types. SBI Reducing Balance EMI formula. Guarantor validation. Director recommendation workflow. Standing instructions. NPA classification.
- **Fixed Deposits** — Slab-based interest by tenure. Quarterly/half-yearly/yearly/cumulative compounding. Auto-renewal, premature closure with penalty. TDS tracking. Senior citizen bonus rates.
- **Recurring Deposits** — Monthly installment tracking. Default penalty. Maturity calculation.

### Agent / Pigmmy Collection
- **Field Agents** — Register agents who collect deposits door-to-door.
- **Pigmmy Accounts** — Daily/weekly/monthly micro-deposit accounts linked to members.
- **Daily Collections** — Record agent collections with matching. Auto-post to member savings. Commission calculation with TDS.

### Accounting & Day Operations
- **Double-Entry Bookkeeping** — Every transaction auto-generates balanced journal entries. Manual voucher entry for adjustments. Chart of accounts with 60+ default heads.
- **Day Operations Workflow** — Begin Day → Transactions → Day End (interest accrual, overdue marking, NPA classification, cashbook posting) → Month End → Year End.
- **Day Controls** — All financial views blocked when working day is closed (`day_open_required` decorator).
- **Rollback** — Day End can be rolled back before opening a new day.

### Reports & Compliance
- **30+ reports**: Trial Balance, Balance Sheet, P&L, Day Book, Cash Book, Personal Ledger, Deposit Reports, Loan Reports, Balance Reports, Pigmmy Reports, Enquiry.
- **CSV export** on every report via `?format=csv`.
- **Notice printing**: Balance confirmation, FD maturity, dividend certificates.
- **Ready Reckoner**: Interest, EMI, and deposit calculators.
- Branch-wise and consolidated views.

### Platform
- **Self-Service Signup** — 90-day free trial. Auto-provisioned schema, branches, chart of accounts.
- **Dashboard** — Setup wizard, quick actions, KPI cards, alerts, today's summary, recent transactions.
- **Multi-Branch** — Head office + unlimited sub-branches. Branch-level access control.
- **Dark / Light Theme** — User-toggleable, persisted in localStorage.
- **i18n** — English, Hindi (हिंदी), Marathi (मराठी). Language switcher in topbar.
- **Responsive UI** — Mobile-first design with Tailwind CSS, overflow-safe tables, responsive grids. Glass-effect topbar, clickable table rows, section workflow tabs.
- **Audit Trail** — Immutable log of every create/update/delete with old/new values, user, IP.
- **REST API** — JWT-authenticated DRF endpoints for mobile app.
- **SMS/Email Notifications** — Transaction alerts, EMI reminders, FD maturity. Celery-powered async delivery.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Django 5.1, Django REST Framework, Celery + Redis |
| Frontend | Django Templates, Tailwind CSS (CDN), HTMX, Alpine.js, Chart.js |
| Database | PostgreSQL 16 with django-tenants (schema-based multi-tenancy) |
| Fonts | Inter (body) + JetBrains Mono (monospace) via Google Fonts |
| Auth | Django auth + django-allauth + SimpleJWT (API) |
| i18n | Django i18n — English, Hindi, Marathi |
| Money | Python `Decimal` + PostgreSQL `NUMERIC(15,2)` — never `float` |
| Currency | Indian format: ₹1,23,456.00. Short: ₹1.2L, ₹45K, ₹3.5Cr |

---

## Django Apps (17)

| App | Schema | Purpose |
|-----|--------|---------|
| `tenants` | Shared | Society registry, domains, subscriptions |
| `core` | Tenant | Utilities — account number generation, avatars |
| `accounts` | Tenant | User auth, roles (Admin/Manager/Cashier/Accountant/Auditor) |
| `branches` | Tenant | Branch management, middleware, access control |
| `members` | Tenant | Member CRUD, KYC, categories, import/export |
| `shares` | Tenant | Share capital, certificates, dividends |
| `savings` | Tenant | Savings/current accounts, transactions, passbook |
| `loans` | Tenant | Loan products, accounts, EMI, guarantors |
| `deposits` | Tenant | Fixed deposits, recurring deposits |
| `agents` | Tenant | Pigmmy agents, accounts, daily collections, commissions |
| `accounting` | Tenant | Chart of accounts, journal entries, vouchers, interest master |
| `dayend` | Tenant | Working day, day-end, month-end, year-end processing |
| `reports` | Tenant | 30+ report views with CSV export |
| `audit` | Tenant | Immutable audit trail |
| `notifications` | Tenant | SMS/email templates and delivery |
| `dashboard` | Tenant | KPIs, setup wizard, quick actions |
| `api` | Tenant | DRF REST API with JWT auth |

---

## Project Structure

```
society_software/
├── config/                     # Settings, URLs, WSGI, Celery
│   ├── settings/               #   base.py, development.py, production.py, testing.py
│   ├── urls.py                 #   Tenant URL config (17 app includes)
│   ├── urls_public.py          #   Public schema (landing, signup)
│   └── celery.py
├── apps/                       # 17 Django apps (see table above)
├── templates/                  # 119 templates
│   ├── base.html               #   Main layout (sidebar + topbar + content)
│   ├── includes/               #   sidebar, topbar, navbar, branch_switcher
│   ├── components/             #   modal, table, pagination, alerts
│   └── <app>/                  #   Per-app templates
├── locale/                     # i18n translations
│   ├── hi/LC_MESSAGES/         #   Hindi
│   └── mr/LC_MESSAGES/         #   Marathi
├── static/img/logo.png         # InfopathSolutions logo
├── tests/                      # 299 tests across 14 modules
└── infrastructure/             # Nginx, Gunicorn, Celery, backup, deploy
```

---

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL 16+
- Redis 7+ (for Celery)

### Setup

```bash
git clone <repo-url>
cd society_software

python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

createdb society_software
cp .env.example .env            # Set DB_NAME, DB_USER, DB_PASSWORD, SECRET_KEY

python manage.py migrate_schemas --shared
python manage.py migrate_schemas --tenant
python manage.py create_demo_tenant

python manage.py runserver
# Open http://demo.localhost:8000 — Login: admin / admin123
```

### Load Test Data

```bash
python manage.py tenant_command load_mock_data --schema=demo
```

---

## Multi-Tenancy

Each society gets its own PostgreSQL schema via [django-tenants](https://github.com/django-tenants/django-tenants).

```
PostgreSQL Database
├── public schema         → societies, domains, subscriptions (shared)
├── demo schema           → members, accounts, loans, ... (isolated)
├── society_abc schema    → members, accounts, loans, ... (isolated)
└── ...
```

- Societies access the app via subdomains: `abc.infosociety.in`
- Data is fully isolated between tenants
- Public schema serves the landing page and signup flow

---

## Running Tests

```bash
# Full suite (299 tests)
python manage.py test tests/ --settings=config.settings.testing

# Single module
python manage.py test tests.test_savings --settings=config.settings.testing

# With coverage
pip install coverage
coverage run manage.py test tests/ --settings=config.settings.testing
coverage report -m
```

---

## Internationalization (i18n)

Supported languages: **English**, **Hindi (हिंदी)**, **Marathi (मराठी)**.

Users can switch languages from the topbar. Translation files are in `locale/{hi,mr}/LC_MESSAGES/`.

To add or update translations:
```bash
# Edit .po files in locale/<lang>/LC_MESSAGES/django.po
python manage.py compilemessages    # Requires GNU gettext
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key | `django-insecure-...` |
| `DEBUG` | Debug mode | `False` |
| `ALLOWED_HOSTS` | Comma-separated hosts | `localhost,127.0.0.1` |
| `DB_NAME` | PostgreSQL database | `society_software` |
| `DB_USER` | PostgreSQL user | `society_user` |
| `DB_PASSWORD` | PostgreSQL password | `society_pass` |
| `DB_HOST` / `DB_PORT` | Database connection | `localhost:5432` |
| `REDIS_URL` | Redis URL (Celery) | `redis://localhost:6379/0` |
| `AWS_ACCESS_KEY_ID` | AWS key (S3 backups) | — |
| `AWS_SECRET_ACCESS_KEY` | AWS secret | — |
| `AWS_STORAGE_BUCKET_NAME` | S3 bucket | — |
| `EMAIL_HOST` / `EMAIL_HOST_USER` | SMTP config | — |
| `SMS_API_KEY` | SMS provider API key | — |
| `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` | Payment gateway | — |

---

## AWS Hosting — Budget Path

| Stage | Societies | Setup | Cost/mo |
|-------|-----------|-------|---------|
| **1** | 0–20 | Single EC2 t4g.small + Cloudflare | ~₹1,200 |
| **2** | 20–100 | EC2 t4g.medium + RDS db.t4g.micro | ~₹4,500 |
| **3** | 100+ | ECS Fargate + RDS Multi-AZ + ElastiCache | ~₹15,000+ |

Stage 1 handles ~2,000 transactions/day. Backups via `pg_dump` to S3 every 6 hours.

---

## Code Standards

- All money: `DecimalField(max_digits=15, decimal_places=2)` — never `FloatField`
- All calculations: Python `Decimal` — never `float`
- Financial transactions are never updated/deleted — create reversals
- Every financial operation creates balanced double-entry journals
- Every model change is logged in the audit trail

---

## License

Proprietary. Copyright 2026 InfopathSolutions. All rights reserved.
