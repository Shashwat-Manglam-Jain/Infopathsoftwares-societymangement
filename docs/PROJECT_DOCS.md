# InfoSociety — Society Banking Software

**By InfopathSolutions** — *To innovate your business process*

A multi-tenant SaaS platform for cooperative credit societies, multistate cooperatives, nidhi companies, and thrift societies. Each society gets an isolated database schema, its own subdomain, and pays a monthly subscription.

---

## Table of Contents

1. [Tech Stack](#tech-stack)
2. [Architecture](#architecture)
3. [Multi-Tenancy Model](#multi-tenancy-model)
4. [Multi-Branch Architecture](#multi-branch-architecture)
5. [Account Number Format](#account-number-format)
6. [Application Modules](#application-modules)
7. [System Flows](#system-flows)
8. [Setup & Configuration Masters](#setup--configuration-masters)
9. [Accounting Engine](#accounting-engine)
10. [Reports](#reports)
11. [Day End / Month End / Year End](#day-end--month-end--year-end)
12. [Money Handling Rules](#money-handling-rules)
13. [AWS Hosting Strategy](#aws-hosting-strategy)
14. [Pricing Model](#pricing-model)
15. [Project Structure](#project-structure)
16. [Development Setup](#development-setup)
17. [Key Design Decisions](#key-design-decisions)
18. [Regulatory Compliance](#regulatory-compliance)
19. [Swimlane Flows](#swimlane-flows)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+ / Django 5.x |
| API | Django REST Framework + SimpleJWT |
| Multi-Tenancy | django-tenants (PostgreSQL schema isolation) |
| Database | PostgreSQL 15+ |
| Frontend | Django Templates + Tailwind CSS (CDN) + HTMX + Alpine.js |
| Background Jobs | Celery + Redis |
| API Docs | drf-spectacular (OpenAPI/Swagger) |
| Deployment | Docker + Docker Compose |
| Hosting | AWS (staged approach) |

---

## Architecture

### Multi-Tenancy Model

```
Public Schema (shared)              Tenant Schema (per society)
+------------------------+          +--------------------------------+
| Society                |          | Members                        |
| Domain                 |          | SavingsAccount                 |
| Subscription           |          | LoanAccount / LoanProduct      |
| Plan                   |          | FixedDeposit / RecurringDeposit |
|                        |          | ChartOfAccounts / JournalEntry  |
|                        |          | ShareHolding                   |
|                        |          | Branch                         |
|                        |          | AuditTrail                     |
|                        |          | StandardSetup / SetupMaster    |
|                        |          | DescriptionMaster              |
|                        |          | JointAccountHolder             |
|                        |          | Agent / PigmmyAccount          |
|                        |          | WorkingDay / DayEndLog         |
+------------------------+          +--------------------------------+
```

- **django-tenants** routes requests via subdomain: `society1.yoursaas.com`
- Each society has its own PostgreSQL schema with completely isolated data
- Shared apps (tenants, auth) live in the `public` schema

### Multi-Branch Architecture

```
Society (Tenant)
|-- Head Office (Branch, is_head_office=True)
|   |-- Members assigned to HO
|   |-- Savings / Loans / Deposits
|   +-- Own Chart of Accounts (cash account: 1001-BRANCH_CODE)
|-- Branch A
|   |-- Members assigned to Branch A
|   |-- Own financial transactions
|   +-- Own cash account
+-- Branch B
    +-- ...
```

- Every financial table has a `branch` ForeignKey
- Day-end processing runs per-branch
- Users can be assigned to specific branches
- Branch switcher in the UI for multi-branch users

---

## Account Number Format

All accounts follow a structured 15-digit format:

```
+-----------+-----------+------------+--------------+
| Society   |  Branch   |  Account   |  Sequential  |
| Code (3)  |  Code (2) |  Code (3)  |  Number (7)  |
+-----------+-----------+------------+--------------+
|   001     |    01     |    201     |  0000001     |
+-----------+-----------+------------+--------------+
Example: 001-01-201-0000001
```

**Account Code Mapping:**

| Code | Account Type |
|------|-------------|
| 101 | Savings Account |
| 201 | Fixed Deposit |
| 202 | Recurring Deposit |
| 301 | Mortgage Loan |
| 302 | Non-Mortgage Loan |
| 401 | Share Account |
| 501 | Pigmmy Account |

---

## Application Modules

### 1. Tenants (`apps/tenants/`)
- Society registration and domain management
- Subscription plans and billing
- Demo tenant creation command
- Society regional name (`name_regional`) and fax support

### 2. Accounts (`apps/accounts/`)
- Custom User model (`AUTH_USER_MODEL = 'accounts.CustomUser'`)
- Role-based access: Admin, Manager, Cashier, Clerk
- Branch-level permissions
- Login/logout, password management, profile

### 3. Branches (`apps/branches/`)
- Branch CRUD with head office designation
- IFSC code, locker facility, NEFT/IMPS service flags
- Branch middleware for current branch context
- Decorators for branch-level access control

### 4. Core (`apps/core/`)
- **StandardSetup** — System-wide configuration (share face value, penal interest code, cash GL code, depreciation codes, max guarantees per member, printing message)
- **SetupMaster** — Deduction GL codes and amounts applied at loan disbursement (shares, admission fee, building fund, welfare fund, computer fund, etc.)
- **DescriptionMaster** — Maps account head codes to transaction descriptions for auto-narration
- **JointAccountHolder** — Joint account holder details (name, address, phone)
- **Account Utilities** — Account number generation following the society format

### 5. Members (`apps/members/`)
- Member registration with KYC details (PAN, Aadhaar, voter ID)
- Member categories: nominal member, director, chairman, guarantor
- Regional language fields (name_regional, address_regional)
- Guardian information for minor accounts
- Area/sub-area/city-village classification
- Nominee management with percentage allocation
- Member search and filtering by status, category
- Photo upload support
- Member statements (cross-product summary)

### 6. Shares (`apps/shares/`)
- Share capital management with face value from StandardSetup
- Share purchase, transfer, and refund
- Board meeting number and date tracking
- Share certificate generation
- Dividend calculation

### 7. Savings (`apps/savings/`)
- Savings account opening with auto-generated account numbers
- Deposits and withdrawals with automatic journal entries
- Daily product method interest calculation
- Interest posting (monthly/quarterly)
- Passbook and account statements
- Transaction reversal support

### 8. Loans (`apps/loans/`)
- Loan products with configurable interest types (flat/reducing balance)
- Loan application workflow with approval/rejection
- Board meeting number and date on loan accounts
- EMI schedule generation (SBI reducing balance formula)
- Guarantor and collateral tracking
- EMI collection with principal/interest split
- Prepayment and closure
- Overdue marking and NPA classification (90+ days)
- Loan deduction at disbursement via SetupMaster

### 9. Deposits (`apps/deposits/`)
- **Fixed Deposits:** Products with tenure-based interest rate slabs (JSONB), compounding options (quarterly/half-yearly/yearly/cumulative), maturity calculation, premature closure with penalty, auto-renewal, transfer-to-account, FD certificate
- **Recurring Deposits:** Monthly installment collection, installment tracking with overdue marking, maturity processing

### 10. Agents / Pigmmy (`apps/agents/`)
- Agent (field collection officer) management
- Security deposit account and loan account tracking
- Security document upload
- Pigmmy (daily deposit) account management
- Daily collection recording and reconciliation

### 11. Accounting (`apps/accounting/`)
- Hierarchical Chart of Accounts with `related_table_name` field determining module behavior
- Double-entry journal entries with voucher types (Receipt, Payment, Journal, Contra)
- Automatic voucher number generation per branch
- Receipt and Payment transaction entry
- Cashbook view with summary
- Trial balance generation
- General ledger with opening/closing balances
- Day book view
- Journal entry reversal

### 12. Day End (`apps/dayend/`)
- Per-branch day-end batch processing
- Working day management (open/close)
- Financial year management with year-end closing
- Month-end interest posting
- Processing logs with summary and error tracking

### 13. Reports (`apps/reports/`)
- Financial: Trial Balance, Profit & Loss, Balance Sheet
- Operational: Cash Book, Day Book
- Loan: Outstanding, Overdue, NPA Report
- Deposit: FD Report, RD Report
- Member: Statement, Passbook
- Other: Share Register, Collection Report, TDS Report
- Excel and PDF export generators
- All reports generated in English (Hindi/Marathi conversion planned)

### 14. Audit (`apps/audit/`)
- Append-only audit trail (no update/delete on audit records)
- Logs: user, action, table, record ID, old/new values, IP address, timestamp
- AuditMiddleware captures client IP
- Searchable/filterable audit log UI

### 15. Notifications (`apps/notifications/`)
- SMS notification templates
- Bulk SMS sending
- SMS delivery log tracking
- Celery task for async delivery

### 16. Dashboard (`apps/dashboard/`)
- Summary cards: total members, deposits, loans, collections
- Quick access: deposit, withdrawal, EMI collection
- Branch-filtered dashboard data

### 17. API (`apps/api/`)
- RESTful API with JWT authentication
- Serializers for members, savings, loans
- Tenant-aware API permissions
- API docs via Swagger/OpenAPI at `/api/docs/`

---

## System Flows

### Society Onboarding Flow

```
New Society Registration
        |
        v
+------------------+     +------------------+
| Create Tenant    |---->| Create Schema    |
| (public schema)  |     | (isolated DB)    |
+------------------+     +------------------+
        |                        |
        v                        v
+------------------+     +------------------+
| Assign Domain    |     | Run Migrations   |
| (subdomain)      |     | in tenant schema |
+------------------+     +------------------+
        |                        |
        v                        v
+------------------+     +------------------+
| Create Admin     |     | Setup Head Office|
| User             |     | Branch           |
+------------------+     +------------------+
        |                        |
        v                        v
+------------------+     +------------------+
| Configure        |     | Initialize Chart |
| StandardSetup    |     | of Accounts      |
+------------------+     +------------------+
```

### Member Registration Flow

```
New Member Application
        |
        v
+------------------------------------------+
| Enter Personal Details                   |
| (Name, DOB, Gender, Photo, Guardian)     |
+------------------------------------------+
| Enter KYC Details                        |
| (PAN, Aadhaar, Voter ID)                |
+------------------------------------------+
| Enter Address & Contact                  |
| (Area, Sub-Area, City, Phone, Email)     |
+------------------------------------------+
| Set Member Type Flags                    |
| (Nominal, Director, Chairman, etc.)      |
+------------------------------------------+
| Add Nominee(s) with Percentage           |
+------------------------------------------+
        |
        v
+--------------------------+
| Generate Member ID       |
| Assign to Branch         |
| Create Audit Trail Entry |
+--------------------------+
        |
        v
+--------------------------+
| Optional: Open Savings   |
| Account, Buy Shares,     |
| Add Joint Account Holders|
+--------------------------+
```

### Savings Account Flow

```
Open Account                    Daily Operations
     |                               |
     v                               v
+----------+                +----------------+
| Select   |                |   Deposit      |
| Member   |                |   (Cash/Cheque) |
| + Branch |                |        |        |
+----------+                |        v        |
     |                      | Dr. Cash (1001) |
     v                      | Cr. Savings     |
+--------------+            |    (2001)       |
| Auto-generate|            +----------------+
| Account No.  |
| (15-digit)   |            +----------------+
+--------------+            |   Withdrawal   |
     |                      |   (Cash/Cheque) |
     v                      |        |        |
+--------------+            |        v        |
| Initialize   |            | Dr. Savings     |
| Balance = 0  |            |    (2001)       |
| Create GL    |            | Cr. Cash (1001) |
| Entry        |            +----------------+
+--------------+
                            +----------------+
                            | Day End:       |
                            | Calculate daily|
                            | interest using |
                            | product method |
                            +----------------+
```

### Loan Application & Disbursement Flow

```
Loan Application
        |
        v
+------------------+
| Select Member    |
| Select Product   |
| Enter Amount,    |
| Tenure, Purpose  |
| Board Meeting    |
| No. & Date       |
+------------------+
        |
        v
+------------------+       +------------------+
| Add Guarantors   |------>| Check: Member's  |
| Add Collateral   |       | guarantee count  |
+------------------+       | <= max_guarantees|
        |                  | from StandardSetup|
        |                  +------------------+
        v
+------------------+
| Status: APPLIED  |
+------------------+
        |
        v
+------------------+
| Manager/Admin    |
| Reviews & Approves|
| (or Rejects)     |
+------------------+
        |
        v
+------------------+
| Status: APPROVED |
+------------------+
        |
        v
+------------------------------------------+
| DISBURSEMENT                             |
|                                          |
| 1. Calculate EMI (SBI Reducing Balance)  |
| 2. Generate EMI Schedule                 |
| 3. Apply Loan Deductions (SetupMaster):  |
|    - Shares deduction                    |
|    - Admission/Building/Welfare fund     |
|    - Computer fund                       |
|    - Any other configured deductions     |
| 4. Net disbursement = Amount - Deductions|
|                                          |
| Journal Entry:                           |
|   Dr. Loans & Advances (1003)            |
|   Cr. Cash (1001)                        |
|   Cr. Various deduction GL heads         |
+------------------------------------------+
        |
        v
+------------------+
| Status: DISBURSED|
| (Active Loan)    |
+------------------+
```

### EMI Collection Flow

```
EMI Due (from Schedule)
        |
        v
+------------------------------------------+
| Collect EMI Payment                      |
|                                          |
| Split:                                   |
|   Principal = EMI - Interest Component   |
|   Interest  = Outstanding x Monthly Rate |
|                                          |
| If overdue:                              |
|   Penal Interest = Outstanding x         |
|                    Penal Rate x Days     |
|                                          |
| Journal Entry:                           |
|   Dr. Cash (1001)                        |
|   Cr. Loans & Advances (1003) [Principal]|
|   Cr. Interest on Loans (3001) [Interest]|
|   Cr. Penalty Interest (3003) [if any]   |
+------------------------------------------+
        |
        v
+------------------+
| Update EMI       |
| Schedule (paid)  |
| Update Loan      |
| Outstanding      |
+------------------+
        |
        v (if all EMIs paid)
+------------------+
| Status: CLOSED   |
+------------------+
```

### Loan Lifecycle States

```
Applied --> Approved --> Disbursed --> Active --> Closed
   |            |                         |
   v            v                         v
Rejected    Cancelled               Overdue --> NPA
                                   (EMI 1+ day  (90+ days
                                    overdue)     overdue)
```

### Fixed Deposit Flow

```
Open FD                         Maturity
   |                               |
   v                               v
+------------------+       +------------------+
| Select Member    |       | Calculate Maturity|
| Select Product   |       | Amount using      |
| Enter Amount,    |       | compound interest |
| Tenure           |       | (quarterly/half-  |
| Transfer Account |       |  yearly/yearly/   |
+------------------+       |  cumulative)      |
   |                       +------------------+
   v                               |
+------------------+               v
| Calculate Rate   |       +------------------+
| from slab table  |       | Credit maturity  |
| (JSONB rates)    |       | to member savings|
| Calculate maturity|      | or transfer acct |
| date & amount    |       |                  |
+------------------+       | Dr. FD (2002)    |
   |                       | Cr. Cash/Savings |
   v                       | Cr. Int Expense  |
+------------------+       +------------------+
| Journal Entry:   |
| Dr. Cash (1001)  |       OR
| Cr. FD (2002)    |       +------------------+
+------------------+       | Premature Close  |
                           | Apply penalty %  |
                           | Reduced interest |
                           +------------------+
```

### Recurring Deposit Flow

```
Open RD
   |
   v
+------------------+
| Set monthly      |
| installment &    |
| tenure           |
+------------------+
   |
   v (every month)
+------------------+
| Collect Monthly  |
| Installment      |
|                  |
| Dr. Cash (1001)  |
| Cr. RD (2003)    |
|                  |
| Mark installment |
| as paid          |
+------------------+
   |
   v (on maturity)
+------------------+
| Calculate total  |
| with interest    |
| Pay out to member|
+------------------+
```

### Share Purchase Flow

```
Buy Shares
   |
   v
+--------------------------------------+
| Select Member                        |
| Enter number of shares               |
| Amount = Shares x Face Value         |
| (Face value from StandardSetup)      |
| Enter Board Meeting No. & Date       |
|                                      |
| Journal Entry:                       |
|   Dr. Cash (1001)                    |
|   Cr. Share Capital (2501)           |
|                                      |
| Create ShareHolding record           |
| Generate Share Certificate           |
+--------------------------------------+
```

### Pigmmy (Daily Deposit Agent) Flow

```
Agent Setup                     Daily Collection
     |                               |
     v                               v
+------------------+       +----------------------+
| Register Agent   |       | Agent collects from  |
| Assign branch,   |       | members door-to-door |
| security deposit |       |                      |
| account, loan    |       | Record each          |
| account          |       | collection amount    |
+------------------+       +----------------------+
     |                               |
     v                               v
+------------------+       +----------------------+
| Create Pigmmy    |       | Day End: Reconcile   |
| Accounts for     |       | agent's total        |
| members          |       | collection vs        |
| (Account code:   |       | deposited amount     |
|  501-XXXXXXX)    |       +----------------------+
+------------------+
```

### Receipt / Payment Transaction Flow

```
Receipt (Money In)                  Payment (Money Out)
        |                                  |
        v                                  v
+----------------------+          +----------------------+
| Date, Voucher No     |          | Date, Voucher No     |
| Member/Account       |          | Member/Account       |
| Mode (Cash/Cheque/   |          | Mode (Cash/Cheque/   |
|  Transfer/UPI)       |          |  Transfer/UPI)       |
|                      |          |                      |
| Line Items:          |          | Line Items:          |
|  GL Head + Amount    |          |  GL Head + Amount    |
|  (multiple lines)    |          |  (multiple lines)    |
|                      |          |                      |
| Narration            |          | Narration            |
+----------------------+          +----------------------+
        |                                  |
        v                                  v
+----------------------+          +----------------------+
| Journal Entry:       |          | Journal Entry:       |
| Dr. Cash/Bank        |          | Dr. Expense/Liability|
| Cr. Income/Liability |          | Cr. Cash/Bank        |
| (balanced double     |          | (balanced double     |
|  entry)              |          |  entry)              |
+----------------------+          +----------------------+
```

---

## Setup & Configuration Masters

### StandardSetup (DEFAULT_SETUP_MASTER)

System-wide settings for the society:

| Field | Description |
|-------|-------------|
| `share_face_value` | Face value per share (e.g., 10, 25, 50) |
| `penal_interest_code` | GL code for penal interest income |
| `cash_gl_code` | GL code for cash-in-hand account |
| `depreciation_code` | GL code for depreciation |
| `max_guarantees` | Maximum times a member can be a guarantor |
| `printing_message` | Footer message on printed receipts |
| `interest_calc_method` | Method for interest calculation |

### SetupMaster (Loan Deductions)

Configures deductions applied when a loan is disbursed:

| Field | Description |
|-------|-------------|
| `deduction_name` | e.g., "Share Deduction", "Admission Fee" |
| `gl_code` | GL head to credit |
| `amount_or_percentage` | Fixed amount or percentage of loan |
| `is_percentage` | Whether value is a percentage |
| `is_active` | Enable/disable this deduction |

### DescriptionMaster

Maps GL account codes to auto-narration text for transactions:

| Field | Description |
|-------|-------------|
| `account_code` | ChartOfAccounts code |
| `description_text` | Default narration for this head |

---

## Accounting Engine

### Chart of Accounts Structure

```
1xxx -- Assets
|-- 1001  Cash in Hand
|-- 1002  Bank Account
|-- 1003  Loans & Advances
+-- 1xxx  Other Assets

2xxx -- Liabilities
|-- 2001  Savings Deposits
|-- 2002  Fixed Deposits
|-- 2003  Recurring Deposits
+-- 2xxx  Other Liabilities

25xx -- Equity
+-- 2501  Share Capital

3xxx -- Income
|-- 3001  Interest on Loans
|-- 3002  Processing Fees
|-- 3003  Penalty Interest
+-- 3xxx  Other Income

4xxx -- Expenses
|-- 4001  Interest on Savings
|-- 4002  Interest on FD
|-- 4003  Interest on RD
+-- 4xxx  Other Expenses
```

The `related_table_name` field on `ChartOfAccounts` links a GL head to its functional module (savings, loans, deposits, shares), enabling the system to auto-route transactions.

### Standard Journal Entries

| Transaction | Debit | Credit |
|-------------|-------|--------|
| Savings Deposit | Cash (1001) | Savings Deposits (2001) |
| Savings Withdrawal | Savings Deposits (2001) | Cash (1001) |
| Loan Disbursement | Loans & Advances (1003) | Cash (1001) + Deduction heads |
| EMI Collection | Cash (1001) | Loans (1003) + Interest Income (3001) |
| FD Creation | Cash (1001) | Fixed Deposits (2002) |
| FD Maturity | Fixed Deposits (2002) | Cash (1001) + Interest Expense (4002) |
| RD Installment | Cash (1001) | Recurring Deposits (2003) |
| Share Purchase | Cash (1001) | Share Capital (2501) |
| Interest on Savings | Interest Expense (4001) | Savings Deposits (2001) |

---

## Reports

All reports are generated in English. Hindi and Marathi localization will be added as a future enhancement.

### Financial Reports

| Report | Description | Key Data |
|--------|-------------|----------|
| **Trial Balance** | All GL heads with debit/credit totals | Date range filter, balanced check |
| **Profit & Loss** | Income vs Expenditure statement | Income heads (3xxx) vs Expense heads (4xxx), net profit/loss |
| **Balance Sheet** | Assets & Liabilities as on date | Asset heads (1xxx) vs Liability+Equity (2xxx+25xx), balance check |

### Operational Reports

| Report | Description |
|--------|-------------|
| **Cash Book** | Daily cash transactions with opening/closing balance |
| **Day Book** | All transactions for a given day |
| **Collection Report** | Agent-wise and branch-wise collection summary |

### Loan Reports

| Report | Description |
|--------|-------------|
| **Loan Outstanding** | All active loans with outstanding principal |
| **Loan Overdue** | EMIs past due date |
| **NPA Report** | Loans classified as non-performing (90+ days overdue) |

### Deposit Reports

| Report | Description |
|--------|-------------|
| **FD Report** | Active FDs with maturity dates and amounts |
| **RD Report** | Active RDs with installment status |

### Member Reports

| Report | Description |
|--------|-------------|
| **Member Statement** | Cross-product account summary for a member |
| **Passbook** | Transaction-level passbook for savings |
| **Share Register** | Member-wise share holdings |
| **TDS Report** | Tax deducted at source on interest payments |

### Report Features
- Date range filtering on all period reports
- Print-optimized layouts (CSS `@media print`)
- Excel and PDF export generators
- Branch-level filtering

---

## Day End / Month End / Year End

### Day Begin (Working Day Open)

```
1. Set transaction date for the branch
2. Verify previous day is closed
3. Branch is now open for transactions
```

### Day End Process

```
For each branch:
  1. Accrue savings interest (daily product method)
     - Daily product = balance x 1 day
     - Accumulated over the period
  2. Accrue loan interest on outstanding balances
  3. Mark overdue EMIs (due date < current date, unpaid)
  4. Classify NPA loans (90+ consecutive days overdue)
  5. Auto-post cashbook (aggregate day's transactions into GL)
  6. Close the working day
  7. Write DayEndLog with summary and any errors
```

### Month End Process

```
For each branch:
  1. Post accrued savings interest to accounts
     (interest_on_minimum_balance or daily_product)
  2. Post accrued loan interest
  3. Generate monthly reports
  4. Write MonthEndLog
```

### Year End Process

```
1. Verify all months are closed
2. Calculate final P&L
3. Transfer Net Profit/Loss to reserves
4. Close all income and expense GL heads (zero out)
5. Carry forward asset/liability/equity balances
   as opening balances for new year
6. Create new FinancialYear record
7. Write YearEndLog
```

---

## Money Handling Rules

1. **All monetary values use Python `Decimal`, never `float`**
2. **PostgreSQL stores money as `NUMERIC(15,2)`**
3. **All calculations round to 2 decimal places using `ROUND_HALF_UP`**
4. **Every financial transaction creates balanced journal entries** (total debit == total credit)
5. **Interest calculations use the daily product method** for savings
6. **Loan EMI uses SBI reducing balance formula**: `EMI = P x r x (1+r)^n / ((1+r)^n - 1)` where r = monthly rate
7. **Flat interest also supported**: `Total Interest = P x R x T / (12 x 100)`

---

## AWS Hosting Strategy (3 Stages)

### Stage 1: Startup (0-10 societies) — ~$15/month

```
+-------------------------------------+
|  EC2 t3.micro (1 vCPU, 1GB RAM)     |
|  |-- Django (Gunicorn)              |
|  |-- PostgreSQL                     |
|  |-- Redis                          |
|  |-- Celery Worker                  |
|  +-- Nginx                          |
|                                     |
|  EBS: 20GB gp3                      |
|  Cloudflare: DNS + CDN + SSL (Free) |
+-------------------------------------+
```

- Everything on a single EC2 instance
- Cloudflare free tier for DNS, CDN, SSL
- Daily pg_dump backups to S3
- Cost: ~$8 EC2 + $2 EBS + $3 S3 + $2 misc

### Stage 2: Growth (10-50 societies) — ~$50/month

```
+----------------+     +--------------+
|  EC2 t3.small  |---->|  RDS db.t3   |
|  (App Server)  |     |  (PostgreSQL)|
|                |     +--------------+
|  Django        |     +--------------+
|  Celery        |---->|  ElastiCache |
|  Nginx         |     |  (Redis)     |
+----------------+     +--------------+
```

- Separate RDS for database (automated backups)
- ElastiCache for Redis
- Single app server

### Stage 3: Scale (50+ societies) — ~$150+/month

```
+----------+     +---------------+     +----------+
|CloudFlare|---->|  ECS Fargate  |---->|  RDS     |
|   CDN    |     |  (Auto-scale) |     |  Multi-AZ|
+----------+     +---------------+     +----------+
                         |
                   +-----+-----+
                   |ElastiCache|
                   |  (Redis)  |
                   +-----------+
```

- ECS Fargate for auto-scaling
- RDS Multi-AZ for high availability
- S3 for static/media files

---

## Pricing Model

| Plan | Target | Price/Month | Limits |
|------|--------|-------------|--------|
| Starter | Small societies | Rs 2,000 | 1 branch, 500 members, basic reports |
| Standard | Medium societies | Rs 5,000 | 3 branches, 2000 members, all reports |
| Premium | Large societies | Rs 8,000 | 10 branches, 5000 members, API access |
| Enterprise | Multistate coops | Rs 12,000 | Unlimited branches, custom features |

---

## Project Structure

```
society_software/
|-- config/
|   |-- settings/
|   |   |-- base.py              # Common settings
|   |   |-- development.py       # Dev overrides
|   |   +-- production.py        # Prod settings
|   |-- urls.py                  # Root URL configuration
|   |-- celery.py                # Celery configuration
|   |-- wsgi.py / asgi.py
|   +-- __init__.py
|-- apps/
|   |-- tenants/                 # Multi-tenancy & subscription
|   |-- accounts/                # User auth & roles
|   |-- branches/                # Branch management
|   |-- core/                    # Setup masters, joint accounts, utilities
|   |-- members/                 # Member management & KYC
|   |-- shares/                  # Share capital
|   |-- savings/                 # Savings accounts
|   |-- loans/                   # Loan management
|   |-- deposits/                # FD & RD
|   |-- agents/                  # Pigmmy agents & daily deposits
|   |-- accounting/              # Double-entry GL & transactions
|   |-- dayend/                  # Day/month/year-end processing
|   |-- reports/                 # Financial & operational reports
|   |-- audit/                   # Audit trail
|   |-- notifications/           # SMS/Email notifications
|   |-- dashboard/               # Dashboard & quick actions
|   +-- api/                     # REST API
|-- templates/                   # Global templates (Tailwind + HTMX)
|   |-- base.html                # Base layout with sidebar
|   |-- includes/                # Sidebar, topbar, branch switcher
|   |-- components/              # Reusable: alerts, modal, pagination, table
|   |-- members/                 # Member list, detail, form
|   |-- accounting/              # Transaction entry, cashbook, vouchers
|   |-- reports/                 # Trial balance, P&L, balance sheet, index
|   |-- savings/                 # Savings list
|   |-- loans/                   # Loan list
|   |-- deposits/                # FD list, RD list
|   |-- shares/                  # Share list
|   |-- branches/                # Branch list
|   |-- audit/                   # Audit log
|   |-- receipts/                # Deposit, EMI, withdrawal, share, passbook
|   +-- registration/            # Login
|-- static/
|   +-- img/                     # Logo and images
|-- infrastructure/              # Deployment configs
|   |-- nginx.conf
|   |-- gunicorn.conf.py
|   |-- celery.service / celerybeat.service
|   |-- deploy.sh
|   +-- backup.sh
|-- docker/
|   |-- Dockerfile
|   +-- docker-compose.yml
|-- docs/                        # Documentation
|   +-- PROJECT_DOCS.md          # This file
|-- .github/workflows/           # CI/CD pipelines
|   |-- ci.yml
|   +-- deploy.yml
|-- manage.py
+-- requirements.txt
```

---

## URL Structure

| URL Pattern | App | Description |
|-------------|-----|-------------|
| `/` | dashboard | Dashboard with summary cards |
| `/members/` | members | Member list |
| `/members/new/` | members | Create member |
| `/members/<id>/` | members | Member detail |
| `/members/<id>/edit/` | members | Edit member |
| `/savings/` | savings | Savings account list |
| `/loans/` | loans | Loan list |
| `/deposits/` | deposits | FD & RD lists |
| `/shares/` | shares | Share holdings |
| `/agents/` | agents | Pigmmy agents |
| `/branches/` | branches | Branch list |
| `/accounting/` | accounting | Chart of accounts & GL |
| `/accounting/receipt/` | accounting | Receipt transaction entry |
| `/accounting/payment/` | accounting | Payment transaction entry |
| `/accounting/cashbook/` | accounting | Cashbook view |
| `/dayend/` | dayend | Day-end processing |
| `/reports/` | reports | Report index |
| `/reports/trial-balance/` | reports | Trial Balance |
| `/reports/profit-loss/` | reports | Profit & Loss |
| `/reports/balance-sheet/` | reports | Balance Sheet |
| `/audit/` | audit | Audit trail |
| `/notifications/` | notifications | SMS management |
| `/accounts/login/` | accounts | Login |
| `/accounts/profile/` | accounts | User profile |
| `/api/` | api | REST API root |
| `/api/docs/` | api | Swagger documentation |
| `/admin/` | django | Django admin |

---

## Development Setup

```bash
# 1. Clone and create virtual environment
git clone <repo-url>
cd society_software
python -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up PostgreSQL
createdb society_software
# Or use Docker: docker-compose -f docker/docker-compose.yml up -d db

# 4. Configure environment
cp .env.example .env
# Edit .env with your database credentials

# 5. Run migrations
python manage.py migrate_schemas --shared
python manage.py migrate_schemas --tenant

# 6. Create public tenant
python manage.py create_demo_tenant

# 7. Run development server
python manage.py runserver
```

---

## Key Design Decisions

1. **Schema-based multi-tenancy** — Stronger data isolation than row-level filtering, simpler queries, meets financial regulation requirements
2. **Double-entry accounting built-in** — Every financial operation creates balanced journal entries automatically
3. **Daily product method** — Industry standard for cooperative society savings interest calculation
4. **Per-branch day-end** — Allows branches to close at different times
5. **Append-only audit trail** — Regulatory requirement for financial software
6. **Decimal everywhere** — Never float for money, prevents rounding errors
7. **Cloudflare free tier** — DNS, CDN, SSL instead of AWS Route53/CloudFront, saves ~$20/month
8. **Django templates + HTMX + Alpine.js** — Faster development, simpler deployment, sufficient UX for banking operations
9. **Tailwind CSS via CDN** — Rapid UI development, responsive out of the box
10. **SetupMaster-driven deductions** — Loan disbursement deductions are configurable per society, not hard-coded
11. **Account number format** — 15-digit structured format for unique identification across society, branch, and product
12. **Reports in English first** — Hindi/Marathi localization planned as a configurable option

---

## Regulatory Compliance

- All financial records are immutable (append-only audit trail)
- Interest calculations follow RBI guidelines for cooperative societies
- NPA classification follows standard asset quality norms (90-day rule)
- TDS calculation and reporting support
- Share capital management per cooperative society regulations
- Data isolation per society (schema-level) meets data protection requirements
- Board meeting number and date tracked on shares and loan approvals
- Guarantor count limits enforced system-wide

---

## Swimlane Flows

Detailed swimlane flow diagrams showing interactions between all actors (Member, Cashier, Manager, System, Accounting Engine) are maintained in a separate document:

**[SWIMLANE_FLOWS.md](SWIMLANE_FLOWS.md)** — Mermaid code (paste into [mermaid.live](https://mermaid.live) to render)

25 diagrams covering:
- Society Onboarding, Member Registration
- Savings (Opening, Deposit, Withdrawal)
- Share Purchase & Transfer
- Loan (Application, Approval, Disbursement, EMI Collection, Overdue/NPA, Lifecycle States)
- Fixed Deposit (Opening, Maturity/Premature/Auto-Renewal)
- Recurring Deposit Full Lifecycle
- Pigmmy/Agent Daily Collection
- Receipt & Payment Transactions
- Day End, Month End, Year End Processing
- Complete System Lifecycle (end-to-end flowchart)
- Accounting Double-Entry Flow
- Daily Operations Timeline (Gantt chart)
