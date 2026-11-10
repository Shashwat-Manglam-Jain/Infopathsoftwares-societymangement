# fmt: off
DEFAULT_CHART_OF_ACCOUNTS = [
    # =========================================================================
    # ASSETS (1xxx) — Balance Sheet
    # =========================================================================
    {
        'code': '1000', 'name': 'Assets', 'group': 'asset', 'type': 'other',
        'parent': None, 'related': 'group', 'report': 'balance_sheet',
        'allow_txn': False, 'order': 100,
    },
    {
        'code': '1001', 'name': 'Cash in Hand', 'group': 'asset', 'type': 'cash',
        'parent': '1000', 'related': 'general', 'report': 'balance_sheet',
        'per_branch': True, 'order': 101,
    },
    {
        'code': '1002', 'name': 'Bank Accounts', 'group': 'asset', 'type': 'bank',
        'parent': '1000', 'related': 'bank', 'report': 'balance_sheet', 'order': 102,
    },
    {
        'code': '1003', 'name': 'Loans & Advances (Members)', 'group': 'asset', 'type': 'loans_given',
        'parent': '1000', 'related': 'loan', 'report': 'balance_sheet',
        'interest_affected': True, 'overdue_affected': True, 'int_code': '3001', 'order': 103,
    },
    {
        'code': '1004', 'name': 'Fixed Assets', 'group': 'asset', 'type': 'other',
        'parent': '1000', 'related': 'group', 'report': 'balance_sheet',
        'allow_txn': False, 'order': 104,
    },
    {
        'code': '1004A', 'name': 'Building', 'group': 'asset', 'type': 'other',
        'parent': '1004', 'related': 'general', 'report': 'balance_sheet', 'order': 105,
    },
    {
        'code': '1004B', 'name': 'Furniture & Dead Stock', 'group': 'asset', 'type': 'other',
        'parent': '1004', 'related': 'general', 'report': 'balance_sheet', 'order': 106,
    },
    {
        'code': '1004C', 'name': 'Computer Hardware', 'group': 'asset', 'type': 'other',
        'parent': '1004', 'related': 'general', 'report': 'balance_sheet', 'order': 107,
    },
    {
        'code': '1005', 'name': 'Interest Accrued on Loans', 'group': 'asset', 'type': 'other',
        'parent': '1000', 'related': 'interest_receivable', 'report': 'balance_sheet', 'order': 110,
    },
    {
        'code': '1006', 'name': 'Advance Accounts', 'group': 'asset', 'type': 'other',
        'parent': '1000', 'related': 'advance', 'report': 'balance_sheet', 'order': 111,
    },
    {
        'code': '1007', 'name': 'Employee Advance', 'group': 'asset', 'type': 'other',
        'parent': '1000', 'related': 'advance', 'report': 'balance_sheet', 'order': 112,
    },
    {
        'code': '1008', 'name': 'TDS Receivable', 'group': 'asset', 'type': 'other',
        'parent': '1000', 'related': 'general', 'report': 'balance_sheet', 'order': 113,
    },
    {
        'code': '1009', 'name': 'Bank FD Investments', 'group': 'asset', 'type': 'bank',
        'parent': '1000', 'related': 'bank', 'report': 'balance_sheet', 'order': 114,
    },
    {
        'code': '1010', 'name': 'Interest Receivable on Bank FD', 'group': 'asset', 'type': 'other',
        'parent': '1000', 'related': 'interest_receivable', 'report': 'balance_sheet', 'order': 115,
    },
    {
        'code': '1011', 'name': 'Other Assets', 'group': 'asset', 'type': 'other',
        'parent': '1000', 'related': 'other', 'report': 'balance_sheet', 'order': 119,
    },

    # =========================================================================
    # LIABILITIES (2xxx) — Balance Sheet
    # =========================================================================
    {
        'code': '2000', 'name': 'Liabilities', 'group': 'liability', 'type': 'other',
        'parent': None, 'related': 'group', 'report': 'balance_sheet',
        'allow_txn': False, 'order': 200,
    },
    {
        'code': '2001', 'name': 'Savings Deposits', 'group': 'liability', 'type': 'deposits_taken',
        'parent': '2000', 'related': 'saving', 'report': 'balance_sheet',
        'interest_given': True, 'int_code': '4001', 'order': 201,
    },
    {
        'code': '2002', 'name': 'Fixed Deposits', 'group': 'liability', 'type': 'deposits_taken',
        'parent': '2000', 'related': 'fixed', 'report': 'balance_sheet',
        'interest_given': True, 'int_code': '4002', 'order': 202,
    },
    {
        'code': '2003', 'name': 'Recurring Deposits', 'group': 'liability', 'type': 'deposits_taken',
        'parent': '2000', 'related': 'recurring', 'report': 'balance_sheet',
        'interest_given': True, 'int_code': '4003', 'order': 203,
    },
    {
        'code': '2004', 'name': 'Current Accounts', 'group': 'liability', 'type': 'deposits_taken',
        'parent': '2000', 'related': 'current', 'report': 'balance_sheet', 'order': 204,
    },
    {
        'code': '2005', 'name': 'Daily / Pigmmy Deposits', 'group': 'liability', 'type': 'deposits_taken',
        'parent': '2000', 'related': 'client', 'report': 'balance_sheet',
        'interest_given': True, 'int_code': '4004', 'order': 205,
    },
    {
        'code': '2006', 'name': 'Security Deposits', 'group': 'liability', 'type': 'deposits_taken',
        'parent': '2000', 'related': 'security', 'report': 'balance_sheet', 'order': 206,
    },
    {
        'code': '2007', 'name': 'Agent Security Deposit', 'group': 'liability', 'type': 'deposits_taken',
        'parent': '2000', 'related': 'security', 'report': 'balance_sheet', 'order': 207,
    },
    {
        'code': '2008', 'name': 'Interest Payable on Deposits', 'group': 'liability', 'type': 'other',
        'parent': '2000', 'related': 'interest_payable', 'report': 'balance_sheet', 'order': 208,
    },
    {
        'code': '2009', 'name': 'TDS Payable', 'group': 'liability', 'type': 'other',
        'parent': '2000', 'related': 'general', 'report': 'balance_sheet', 'order': 209,
    },
    {
        'code': '2010', 'name': 'Sundry Creditors', 'group': 'liability', 'type': 'other',
        'parent': '2000', 'related': 'general', 'report': 'balance_sheet', 'order': 210,
    },
    {
        'code': '2011', 'name': 'Other Liabilities', 'group': 'liability', 'type': 'other',
        'parent': '2000', 'related': 'other', 'report': 'balance_sheet', 'order': 219,
    },

    # =========================================================================
    # EQUITY (25xx) — Balance Sheet
    # =========================================================================
    {
        'code': '2500', 'name': 'Equity', 'group': 'equity', 'type': 'other',
        'parent': None, 'related': 'group', 'report': 'balance_sheet',
        'allow_txn': False, 'order': 250,
    },
    {
        'code': '2501', 'name': 'Share Capital', 'group': 'equity', 'type': 'share_capital',
        'parent': '2500', 'related': 'shares', 'report': 'balance_sheet', 'order': 251,
    },
    {
        'code': '2502', 'name': 'Statutory Reserve Fund (25%)', 'group': 'equity', 'type': 'reserve_fund',
        'parent': '2500', 'related': 'general', 'report': 'balance_sheet', 'order': 252,
    },
    {
        'code': '2503', 'name': 'Building Fund', 'group': 'equity', 'type': 'other',
        'parent': '2500', 'related': 'general', 'report': 'balance_sheet', 'order': 253,
    },
    {
        'code': '2504', 'name': 'Education Fund', 'group': 'equity', 'type': 'other',
        'parent': '2500', 'related': 'general', 'report': 'balance_sheet', 'order': 254,
    },
    {
        'code': '2505', 'name': 'Dividend Equalization Fund', 'group': 'equity', 'type': 'other',
        'parent': '2500', 'related': 'general', 'report': 'balance_sheet', 'order': 255,
    },
    {
        'code': '2506', 'name': 'Profit & Loss Account', 'group': 'equity', 'type': 'other',
        'parent': '2500', 'related': 'general', 'report': 'balance_sheet', 'order': 256,
    },

    # =========================================================================
    # INCOME (3xxx) — Profit & Loss
    # =========================================================================
    {
        'code': '3000', 'name': 'Income', 'group': 'income', 'type': 'other',
        'parent': None, 'related': 'group', 'report': 'profit_loss',
        'allow_txn': False, 'order': 300,
    },
    {
        'code': '3001', 'name': 'Interest Received on Loans', 'group': 'income', 'type': 'interest_income',
        'parent': '3000', 'related': 'interest_received', 'report': 'profit_loss', 'order': 301,
    },
    {
        'code': '3002', 'name': 'Processing Fees / Loan Form Fees', 'group': 'income', 'type': 'other',
        'parent': '3000', 'related': 'processing_fee_income', 'report': 'profit_loss', 'order': 302,
    },
    {
        'code': '3003', 'name': 'Penal Interest Received', 'group': 'income', 'type': 'other',
        'parent': '3000', 'related': 'interest_received', 'report': 'profit_loss', 'order': 303,
    },
    {
        'code': '3004', 'name': 'Entry / Membership Fees', 'group': 'income', 'type': 'other',
        'parent': '3000', 'related': 'general', 'report': 'profit_loss', 'order': 304,
    },
    {
        'code': '3005', 'name': 'Interest on Bank Investments', 'group': 'income', 'type': 'interest_income',
        'parent': '3000', 'related': 'interest_received', 'report': 'profit_loss', 'order': 305,
    },
    {
        'code': '3006', 'name': 'Late Fees', 'group': 'income', 'type': 'other',
        'parent': '3000', 'related': 'general', 'report': 'profit_loss', 'order': 306,
    },
    {
        'code': '3007', 'name': 'Locker Rent Received', 'group': 'income', 'type': 'other',
        'parent': '3000', 'related': 'general', 'report': 'profit_loss', 'order': 307,
    },
    {
        'code': '3008', 'name': 'Administrative Fees', 'group': 'income', 'type': 'other',
        'parent': '3000', 'related': 'general', 'report': 'profit_loss', 'order': 308,
    },
    {
        'code': '3009', 'name': 'Advocate & Notice Fees Received', 'group': 'income', 'type': 'other',
        'parent': '3000', 'related': 'general', 'report': 'profit_loss', 'order': 309,
    },
    {
        'code': '3010', 'name': 'Agent Commission Received', 'group': 'income', 'type': 'other',
        'parent': '3000', 'related': 'general', 'report': 'profit_loss', 'order': 310,
    },
    {
        'code': '3011', 'name': 'Miscellaneous Income', 'group': 'income', 'type': 'other',
        'parent': '3000', 'related': 'general', 'report': 'profit_loss', 'order': 319,
    },

    # =========================================================================
    # EXPENSES (4xxx) — Profit & Loss
    # =========================================================================
    {
        'code': '4000', 'name': 'Expenses', 'group': 'expense', 'type': 'other',
        'parent': None, 'related': 'group', 'report': 'profit_loss',
        'allow_txn': False, 'order': 400,
    },
    {
        'code': '4001', 'name': 'Interest Paid on Savings Deposits', 'group': 'expense', 'type': 'interest_expense',
        'parent': '4000', 'related': 'interest_paid', 'report': 'profit_loss', 'order': 401,
    },
    {
        'code': '4002', 'name': 'Interest Paid on Fixed Deposits', 'group': 'expense', 'type': 'interest_expense',
        'parent': '4000', 'related': 'interest_paid', 'report': 'profit_loss', 'order': 402,
    },
    {
        'code': '4003', 'name': 'Interest Paid on Recurring Deposits', 'group': 'expense', 'type': 'interest_expense',
        'parent': '4000', 'related': 'interest_paid', 'report': 'profit_loss', 'order': 403,
    },
    {
        'code': '4004', 'name': 'Interest Paid on Daily / Pigmmy', 'group': 'expense', 'type': 'interest_expense',
        'parent': '4000', 'related': 'interest_paid', 'report': 'profit_loss', 'order': 404,
    },
    {
        'code': '4005', 'name': 'Interest Paid on Security Deposits', 'group': 'expense', 'type': 'interest_expense',
        'parent': '4000', 'related': 'interest_paid', 'report': 'profit_loss', 'order': 405,
    },
    {
        'code': '4010', 'name': 'Salary & Allowances', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 410,
    },
    {
        'code': '4011', 'name': 'Rent', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 411,
    },
    {
        'code': '4012', 'name': 'Audit Fees', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 412,
    },
    {
        'code': '4013', 'name': 'Stationery & Printing', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 413,
    },
    {
        'code': '4014', 'name': 'Depreciation', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 414,
    },
    {
        'code': '4015', 'name': 'Postage Expenses', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 415,
    },
    {
        'code': '4016', 'name': 'Travelling Expenses', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 416,
    },
    {
        'code': '4017', 'name': 'Legal / Court / Notice Fees', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 417,
    },
    {
        'code': '4018', 'name': 'Insurance Expenses', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 418,
    },
    {
        'code': '4019', 'name': 'Agent Commission Paid', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 419,
    },
    {
        'code': '4020', 'name': 'Dividend on Shares', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 420,
    },
    {
        'code': '4021', 'name': 'Software Expenses', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 421,
    },
    {
        'code': '4022', 'name': 'Office Expenses', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 422,
    },
    {
        'code': '4023', 'name': 'Electricity Expenses', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 423,
    },
    {
        'code': '4024', 'name': 'Director Meeting Expenses', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 424,
    },
    {
        'code': '4025', 'name': 'Annual Meeting / Advertisement', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 425,
    },
    {
        'code': '4026', 'name': 'Training Expenses', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 426,
    },
    {
        'code': '4027', 'name': 'Nagar Parishad / Municipal Tax', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 427,
    },
    {
        'code': '4028', 'name': 'Income Tax / Return Filing', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 428,
    },
    {
        'code': '4029', 'name': 'Loan Recovery / Travelling', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 429,
    },
    {
        'code': '4099', 'name': 'Miscellaneous Expenses', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 499,
    },
]
# fmt: on


def setup_chart_of_accounts(branches=None):
    from apps.accounting.models import ChartOfAccounts

    parent_map = {}
    # First pass: create all heads so interest_code FK can be resolved
    created_objects = {}

    for item in DEFAULT_CHART_OF_ACCOUNTS:
        parent = parent_map.get(item['parent']) if item['parent'] else None
        allow_txn = item.get('allow_txn', True)

        defaults = {
            'name': item['name'],
            'account_group': item['group'],
            'account_type': item['type'],
            'parent': parent,
            'is_system': True,
            'related_table_name': item.get('related', 'general'),
            'interest_affected': item.get('interest_affected', False),
            'overdue_affected': item.get('overdue_affected', False),
            'interest_given': item.get('interest_given', False),
            'report_position': item.get('report', 'balance_sheet'),
            'display_order': item.get('order', 0),
            'allow_transactions': allow_txn,
            'default_code': True,
        }

        if item.get('per_branch') and branches:
            for branch in branches:
                code = f'{item["code"]}-{branch.branch_code}'
                obj, _ = ChartOfAccounts.objects.get_or_create(
                    code=code,
                    defaults={
                        **defaults,
                        'name': f'{item["name"]} ({branch.branch_name})',
                        'branch': branch,
                    },
                )
                parent_map[code] = obj
                created_objects[code] = obj
        else:
            obj, _ = ChartOfAccounts.objects.get_or_create(
                code=item['code'],
                defaults=defaults,
            )
            parent_map[item['code']] = obj
            created_objects[item['code']] = obj

    # Second pass: link interest_code FKs
    for item in DEFAULT_CHART_OF_ACCOUNTS:
        int_code = item.get('int_code')
        if not int_code:
            continue
        head = created_objects.get(item['code'])
        interest_head = created_objects.get(int_code)
        if head and interest_head and head.interest_code_id != interest_head.id:
            head.interest_code = interest_head
            head.save(update_fields=['interest_code'])

    return parent_map
