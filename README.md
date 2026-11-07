# InfoSociety — Society Banking Software

> Cloud-hosted banking SaaS for cooperative societies | By **InfopathSolutions** — *To innovate your business process*

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Django](https://img.shields.io/badge/Django-5.1-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue)
![License](https://img.shields.io/badge/License-Proprietary-red)

---

## Overview

InfoSociety is a multi-tenant banking platform purpose-built for **credit cooperative societies**, **multistate cooperatives**, **nidhi companies**, and **thrift societies** in India. Each society signs up via a self-service portal, gets its own isolated database schema, and is operational within minutes.

Societies pay a monthly subscription. All hosting, updates, backups, and security are managed centrally on AWS.

---

## Features

### Core Banking
- **Member Management** — KYC (Aadhaar/PAN), nominees (with primary flag), photos, documents. Category flags for senior citizen, widow, ex-military, physically disabled, employee, director (auto FD interest bonus +0.25%–0.50%). Member exit date tracking. Excel import/export with sample template.
- **Share Capital** — Purchase, transfer, surrender. Auto certificate numbers. Dividend calculation.
- **Savings Accounts** — Deposit, withdrawal, daily interest accrual. Passbook printing (paginated, date-filtered). Printable dual-copy receipts. Security deposit accounts.
- **Loan Management** — Mortgage and non-mortgage types. SBI Reducing Balance EMI formula. Non-mortgage: one active at a time; mortgage: multiple allowed. Guarantor validation (must be shareholder, active guarantee count tracking). Director recommendation workflow. Standing instructions (form fees, legal fees, court fees). NPA classification.
- **Fixed Deposits** — Slab-based interest by tenure. Quarterly/half-yearly/yearly/cumulative compounding. Auto-renewal, premature closure with penalty. TDS tracking. Senior citizen bonus rates.
- **Recurring Deposits** — Monthly installment tracking. Default penalty. Maturity calculation.

### Agent / Pigmmy Collection
- **Field Agents** — Register agents who collect deposits door-to-door.
- **Pigmmy Accounts** — Daily/weekly/monthly micro-deposit accounts linked to members. One per member enforced. Agent must have savings + security deposit accounts.
- **Daily Collections** — Record agent collections with matching. Auto-post to member savings. Commission calculation with TDS. Journal entries for collections.

### Accounting & Day Operations
- **Double-Entry Bookkeeping** — Every transaction auto-generates balanced journal entries. Manual voucher entry for adjustments. Chart of accounts with 60+ default heads (asset/liability/income/expense) using `related_table_name` to link GL codes to modules.
- **Day Operations Workflow** — Begin Day (set working date) → Transactions → Day End (savings interest accrual, loan interest accrual, overdue marking, NPA classification, auto cashbook posting) → Month End (loan demand generation, RD installments) → Year End (P&L transfer to reserves via journal entry, opening balance carryover for assets/liabilities/equity).
- **Rollback** — Day End can be rolled back if needed before opening a new day.

### Reports & Compliance
- 16+ reports: Trial Balance, Balance Sheet, P&L, Day Book, Cash Book, Passbook, Loan Outstanding, Overdue, NPA, Collection, FD Register, RD Register, Share Register, TDS, Member Statement.
- PDF (WeasyPrint) and Excel (openpyxl) export.
- Branch-wise and consolidated views.

### Platform
- **Self-Service Signup** — Society fills a form, schema is created, head office branch + admin user + chart of accounts + default products are auto-provisioned. 90-day free trial.
- **Dashboard** — Setup wizard (6 steps), quick actions bar, KPI cards, alerts (expiring FDs, overdue loans, pending approvals), today's summary, recent transactions.
- **Multi-Branch** — Head office + unlimited sub-branches. Branch-level access control. Inter-branch transactions.
- **Audit Trail** — Immutable log of every create/update/delete with old/new values, user, IP.
- **REST API** — JWT-authenticated DRF endpoints for mobile app.
- **SMS/Email Notifications** — Transaction alerts, EMI reminders, FD maturity. Celery-powered async delivery.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Django 5.x, Django REST Framework, Celery + Redis |
| Frontend | Django Templates, Tailwind CSS (CDN), HTMX, Alpine.js, Chart.js |
| Database | PostgreSQL 16 with django-tenants (schema-based multi-tenancy) |
| Auth | Django auth + django-allauth + SimpleJWT (API) |
| Reports | WeasyPrint (PDF), openpyxl (Excel) |
| Money | Python `Decimal` + PostgreSQL `NUMERIC(15,2)` — never `float` |
| Currency | Indian format: ₹1,23,456.00. Short format: ₹1.2L, ₹45K, ₹3.5Cr |

### Account Number Format

```
SocietyCode(3) + BranchCode(2) + AccountCode(3) + Sequential(7)
Example: 001 + 01 + 003 + 0000001 → 001010030000001
Max 99,99,999 accounts per head — sufficient for all society sizes.
```

---

## Django Apps (16)

| App | Schema | Purpose |
|-----|--------|---------|
| `tenants` | Shared | Society registry, domains, subscriptions |
| `core` | Tenant | Utilities — account number generation |
| `accounts` | Tenant | User auth, roles, permissions |
| `branches` | Tenant | Branch management, middleware, access control |
| `members` | Tenant | Member CRUD, KYC, categories, import/export |
| `shares` | Tenant | Share capital, certificates, dividends |
| `savings` | Tenant | Savings/current accounts, transactions, passbook |
| `loans` | Tenant | Loan products, accounts, EMI, guarantors, standing instructions |
| `deposits` | Tenant | Fixed deposits, recurring deposits |
| `agents` | Tenant | Pigmmy agents, accounts, daily collections, commissions |
| `accounting` | Tenant | Chart of accounts, journal entries, vouchers |
| `dayend` | Tenant | Working day, day-end, month-end, year-end processing |
| `reports` | Tenant | Report views + PDF/Excel generators |
| `audit` | Tenant | Immutable audit trail |
| `notifications` | Tenant | SMS/email templates and delivery |
| `dashboard` | Tenant | KPIs, setup wizard, quick actions |
| `api` | Tenant | DRF REST API with JWT auth |

---

## Project Structure

```
society_software/
├── config/                     # Settings, URLs, WSGI, Celery
│   ├── settings/               #   base.py, development.py, production.py
│   ├── urls.py                 #   Tenant URL config (16 app includes)
│   ├── urls_public.py          #   Public schema (landing, signup)
│   └── celery.py
├── apps/                       # 16 Django apps (see table above)
├── templates/                  # Global templates
│   ├── base.html               #   Main layout (sidebar + topbar + content)
│   ├── landing.html            #   Marketing landing page
│   ├── signup.html             #   Self-service society signup
│   ├── signup_success.html     #   Signup confirmation with credentials
│   ├── includes/               #   sidebar, topbar, branch_switcher
│   ├── components/             #   modal, table, pagination, alerts
│   └── receipts/               #   deposit, withdrawal, EMI, share, passbook
├── static/img/logo.png         # InfopathSolutions logo
├── tests/                      # Test suite (12 modules)
├── infrastructure/             # Nginx, Gunicorn, Celery, backup, deploy
└── docker/                     # Dockerfile + docker-compose
```

---

## Quick Start

### Docker (Recommended)

```bash
git clone <repo-url>
cd society_software
cp .env.example .env            # Edit with your credentials

cd docker
docker-compose up -d            # Django, PostgreSQL, Redis, Celery

docker-compose exec web python manage.py migrate_schemas --shared
docker-compose exec web python manage.py migrate_schemas --tenant
docker-compose exec web python manage.py create_demo_tenant

# Open http://localhost:8000 — Login: admin / admin123
```

### Local Setup

Prerequisites: Python 3.12+, PostgreSQL 16+, Redis 7+

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
createdb society_software

cp .env.example .env            # Set DB_NAME, DB_USER, DB_PASSWORD, SECRET_KEY

python manage.py migrate_schemas --shared
python manage.py migrate_schemas --tenant
python manage.py create_demo_tenant

redis-server &                  # Background
celery -A config worker -l info &
celery -A config beat -l info &
python manage.py runserver

# Open http://localhost:8000 — Login: admin / admin123
```

---

## Multi-Tenancy

Each society gets its own PostgreSQL schema via [django-tenants](https://github.com/django-tenants/django-tenants).

```
PostgreSQL Database
├── public schema         → societies, domains, subscriptions (shared)
├── society_abc schema    → members, accounts, loans, ... (isolated)
├── society_xyz schema    → members, accounts, loans, ... (isolated)
└── ...
```

- Societies access the app via subdomains: `abc.infosociety.in`
- Data is fully isolated between tenants
- Public schema serves the landing page and signup flow (`PUBLIC_SCHEMA_URLCONF`)

---

## Running Tests

```bash
python manage.py test tests/ -v 2           # Full suite
python manage.py test tests.test_savings    # Single module

# With coverage
pip install coverage
coverage run manage.py test tests/
coverage report -m
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key | `django-insecure-change-this-in-production` |
| `DEBUG` | Debug mode | `False` |
| `ALLOWED_HOSTS` | Comma-separated hosts | `localhost,127.0.0.1` |
| `DB_NAME` | PostgreSQL database | `society_software` |
| `DB_USER` | PostgreSQL user | `society_user` |
| `DB_PASSWORD` | PostgreSQL password | `society_pass` |
| `DB_HOST` | PostgreSQL host | `localhost` |
| `DB_PORT` | PostgreSQL port | `5432` |
| `REDIS_URL` | Redis URL | `redis://localhost:6379/0` |
| `AWS_ACCESS_KEY_ID` | AWS key (S3 backups) | — |
| `AWS_SECRET_ACCESS_KEY` | AWS secret | — |
| `AWS_STORAGE_BUCKET_NAME` | S3 bucket | — |
| `AWS_S3_REGION_NAME` | AWS region | `ap-south-1` |
| `EMAIL_HOST` | SMTP host | `localhost` |
| `EMAIL_HOST_USER` | SMTP user | — |
| `EMAIL_HOST_PASSWORD` | SMTP password | — |
| `SMS_API_KEY` | SMS provider API key | — |
| `RAZORPAY_KEY_ID` | Razorpay key | — |
| `RAZORPAY_KEY_SECRET` | Razorpay secret | — |

---

## AWS Hosting — Budget Path

| Stage | Societies | Setup | Cost/mo |
|-------|-----------|-------|---------|
| **1** | 0–20 | Single EC2 t4g.small (app + DB + Redis) + Cloudflare (free SSL/CDN) | ~₹1,200 |
| **2** | 20–100 | EC2 t4g.medium + RDS db.t4g.micro | ~₹4,500 |
| **3** | 100+ | ECS Fargate + RDS Multi-AZ + ElastiCache | ~₹15,000+ |

Stage 1 handles ~2,000 transactions/day comfortably. Backups via `pg_dump` to S3 every 6 hours.

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
