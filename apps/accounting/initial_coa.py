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
        'code': '1000A', 'name': 'Cash & Bank Balances', 'group': 'asset', 'type': 'other',
        'parent': '1000', 'related': 'group', 'report': 'balance_sheet',
        'allow_txn': False, 'order': 100,
    },
    {
        'code': '1001', 'name': 'Cash in Hand', 'group': 'asset', 'type': 'cash',
        'parent': '1000A', 'related': 'general', 'report': 'balance_sheet',
        'per_branch': True, 'order': 101,
    },
    {
        'code': '1002', 'name': 'Bank Accounts', 'group': 'asset', 'type': 'bank',
        'parent': '1000A', 'related': 'group', 'report': 'balance_sheet',
        'allow_txn': False, 'order': 102,
    },
    {
        'code': '1003', 'name': 'Loans & Advances (Members)', 'group': 'asset', 'type': 'loans_given',
        'parent': '1000', 'related': 'group', 'report': 'balance_sheet',
        'allow_txn': False, 'order': 103,
    },
    {
        'code': '1004', 'name': 'Fixed Assets', 'group': 'asset', 'type': 'other',
        'parent': '1000', 'related': 'group', 'report': 'balance_sheet',
        'allow_txn': False, 'order': 140,
    },
    {
        'code': '1004A', 'name': 'Building', 'group': 'asset', 'type': 'other',
        'parent': '1004', 'related': 'general', 'report': 'balance_sheet', 'order': 141,
    },
    {
        'code': '1004B', 'name': 'Furniture & Dead Stock', 'group': 'asset', 'type': 'other',
        'parent': '1004', 'related': 'general', 'report': 'balance_sheet', 'order': 142,
    },
    {
        'code': '1004C', 'name': 'Computer Hardware', 'group': 'asset', 'type': 'other',
        'parent': '1004', 'related': 'general', 'report': 'balance_sheet', 'order': 143,
    },
    {
        'code': '1004D', 'name': 'Printer', 'group': 'asset', 'type': 'other',
        'parent': '1004', 'related': 'general', 'report': 'balance_sheet', 'order': 144,
    },
    {
        'code': '1004E', 'name': 'CCTV Camera', 'group': 'asset', 'type': 'other',
        'parent': '1004', 'related': 'general', 'report': 'balance_sheet', 'order': 145,
    },
    {
        'code': '1004F', 'name': 'Cash Counting Machine', 'group': 'asset', 'type': 'other',
        'parent': '1004', 'related': 'general', 'report': 'balance_sheet', 'order': 146,
    },
    {
        'code': '1006', 'name': 'Other Receivables', 'group': 'asset', 'type': 'other',
        'parent': '1000', 'related': 'group', 'report': 'balance_sheet',
        'allow_txn': False, 'order': 160,
    },
    {
        'code': '1005', 'name': 'Interest Accrued on Loans', 'group': 'asset', 'type': 'other',
        'parent': '1006', 'related': 'interest_receivable', 'report': 'balance_sheet', 'order': 150,
    },
    {
        'code': '1006A', 'name': 'Advance Deposit (House Owner)', 'group': 'asset', 'type': 'other',
        'parent': '1006', 'related': 'advance', 'report': 'balance_sheet', 'order': 161,
    },
    {
        'code': '1006B', 'name': 'Advance Deposit (Telephone)', 'group': 'asset', 'type': 'other',
        'parent': '1006', 'related': 'advance', 'report': 'balance_sheet', 'order': 162,
    },
    {
        'code': '1006C', 'name': 'Software Advance', 'group': 'asset', 'type': 'other',
        'parent': '1006', 'related': 'advance', 'report': 'balance_sheet', 'order': 163,
    },
    {
        'code': '1006D', 'name': 'Audit Fee Advance', 'group': 'asset', 'type': 'other',
        'parent': '1006', 'related': 'advance', 'report': 'balance_sheet', 'order': 164,
    },
    {
        'code': '1007', 'name': 'Employee Advance', 'group': 'asset', 'type': 'other',
        'parent': '1006', 'related': 'advance', 'report': 'balance_sheet', 'order': 165,
    },
    {
        'code': '1007A', 'name': 'Court Case Expenses Advance', 'group': 'asset', 'type': 'other',
        'parent': '1006', 'related': 'advance', 'report': 'balance_sheet', 'order': 166,
    },
    {
        'code': '1007B', 'name': 'Legal Expenses Advance', 'group': 'asset', 'type': 'other',
        'parent': '1006', 'related': 'advance', 'report': 'balance_sheet', 'order': 167,
    },
    {
        'code': '1007C', 'name': 'RRC Expenses Advance', 'group': 'asset', 'type': 'other',
        'parent': '1006', 'related': 'advance', 'report': 'balance_sheet', 'order': 168,
    },
    {
        'code': '1007D', 'name': 'Insurance Advance', 'group': 'asset', 'type': 'other',
        'parent': '1006', 'related': 'advance', 'report': 'balance_sheet', 'order': 169,
    },
    {
        'code': '1008', 'name': 'TDS Receivable', 'group': 'asset', 'type': 'other',
        'parent': '1006', 'related': 'general', 'report': 'balance_sheet', 'order': 170,
    },
    {
        'code': '1009', 'name': 'Investments', 'group': 'asset', 'type': 'bank',
        'parent': '1000', 'related': 'group', 'report': 'balance_sheet',
        'allow_txn': False, 'order': 130,
    },
    {
        'code': '1010', 'name': 'Interest Receivable on Bank FD', 'group': 'asset', 'type': 'other',
        'parent': '1006', 'related': 'interest_receivable', 'report': 'balance_sheet', 'order': 135,
    },
    {
        'code': '1010A', 'name': 'Bank FD TDS Receivable', 'group': 'asset', 'type': 'other',
        'parent': '1006', 'related': 'general', 'report': 'balance_sheet', 'order': 136,
    },
    {
        'code': '1011', 'name': 'Other Assets', 'group': 'asset', 'type': 'other',
        'parent': '1000', 'related': 'other', 'report': 'balance_sheet', 'order': 180,
    },
    {
        'code': '1011A', 'name': 'Society Fixed Asset (Property)', 'group': 'asset', 'type': 'other',
        'parent': '1011', 'related': 'general', 'report': 'balance_sheet', 'order': 181,
    },
    {
        'code': '1011B', 'name': 'Share Purchase (Other Cooperatives)', 'group': 'asset', 'type': 'other',
        'parent': '1009', 'related': 'group', 'report': 'balance_sheet',
        'allow_txn': False, 'order': 182,
    },
    {
        'code': '1011C', 'name': 'Reserve Fund FD Investment', 'group': 'asset', 'type': 'other',
        'parent': '1009', 'related': 'general', 'report': 'balance_sheet', 'order': 183,
    },

    # --- Loan sub-heads (ac_codes from legacy head_master) ---
    {
        'code': '1012', 'name': 'Regular Loan', 'group': 'asset', 'type': 'loans_given',
        'parent': '1003', 'related': 'loan', 'report': 'balance_sheet',
        'interest_affected': True, 'overdue_affected': True, 'int_code': '3001', 'ac_code': '026', 'order': 110,
    },
    {
        'code': '1013', 'name': 'Emergency Loan', 'group': 'asset', 'type': 'loans_given',
        'parent': '1003', 'related': 'loan', 'report': 'balance_sheet',
        'interest_affected': True, 'overdue_affected': True, 'int_code': '3001', 'ac_code': '027', 'order': 111,
    },
    {
        'code': '1014', 'name': 'Loan Against FD', 'group': 'asset', 'type': 'loans_given',
        'parent': '1003', 'related': 'loan', 'report': 'balance_sheet',
        'interest_affected': True, 'overdue_affected': True, 'int_code': '3001', 'ac_code': '028', 'order': 112,
    },
    {
        'code': '1015', 'name': 'Loan Against Pigmmy', 'group': 'asset', 'type': 'loans_given',
        'parent': '1003', 'related': 'loan', 'report': 'balance_sheet',
        'interest_affected': True, 'overdue_affected': True, 'int_code': '3001', 'ac_code': '029', 'order': 113,
    },
    {
        'code': '1016', 'name': 'Gold Loan', 'group': 'asset', 'type': 'loans_given',
        'parent': '1003', 'related': 'loan', 'report': 'balance_sheet',
        'interest_affected': True, 'overdue_affected': True, 'int_code': '3001', 'ac_code': '092', 'order': 114,
    },
    {
        'code': '1017', 'name': 'Property Mortgage Loan', 'group': 'asset', 'type': 'loans_given',
        'parent': '1003', 'related': 'loan', 'report': 'balance_sheet',
        'interest_affected': True, 'overdue_affected': True, 'int_code': '3001', 'ac_code': '063', 'order': 115,
    },
    {
        'code': '1018', 'name': 'Loan Against RD', 'group': 'asset', 'type': 'loans_given',
        'parent': '1003', 'related': 'loan', 'report': 'balance_sheet',
        'interest_affected': True, 'overdue_affected': True, 'int_code': '3001', 'ac_code': '033', 'order': 116,
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
        'code': '2000A', 'name': 'Deposits', 'group': 'liability', 'type': 'other',
        'parent': '2000', 'related': 'group', 'report': 'balance_sheet',
        'allow_txn': False, 'order': 209,
    },
    {
        'code': '2001', 'name': 'Savings Deposits', 'group': 'liability', 'type': 'deposits_taken',
        'parent': '2000A', 'related': 'saving', 'report': 'balance_sheet',
        'interest_given': True, 'int_code': '4001', 'ac_code': '006', 'order': 210,
    },
    {
        'code': '2002', 'name': 'Fixed Deposits', 'group': 'liability', 'type': 'deposits_taken',
        'parent': '2000A', 'related': 'fixed', 'report': 'balance_sheet',
        'interest_given': True, 'int_code': '4002', 'ac_code': '008', 'order': 211,
    },
    {
        'code': '2003', 'name': 'Recurring Deposits', 'group': 'liability', 'type': 'deposits_taken',
        'parent': '2000A', 'related': 'recurring', 'report': 'balance_sheet',
        'interest_given': True, 'int_code': '4003', 'ac_code': '011', 'order': 212,
    },
    {
        'code': '2004', 'name': 'Current Accounts', 'group': 'liability', 'type': 'deposits_taken',
        'parent': '2000A', 'related': 'current', 'report': 'balance_sheet', 'ac_code': '002', 'order': 213,
    },
    {
        'code': '2005', 'name': 'Daily / Pigmmy Deposits', 'group': 'liability', 'type': 'deposits_taken',
        'parent': '2000A', 'related': 'client', 'report': 'balance_sheet',
        'interest_given': True, 'int_code': '4004', 'ac_code': '007', 'order': 214,
    },
    {
        'code': '2005A', 'name': 'Monthly Recurring (Pigmmy)', 'group': 'liability', 'type': 'deposits_taken',
        'parent': '2000A', 'related': 'client', 'report': 'balance_sheet',
        'interest_given': True, 'int_code': '4003', 'ac_code': '034', 'order': 215,
    },
    {
        'code': '2006', 'name': 'Security Deposits', 'group': 'liability', 'type': 'deposits_taken',
        'parent': '2000A', 'related': 'security', 'report': 'balance_sheet', 'ac_code': '003', 'order': 216,
    },
    {
        'code': '2007', 'name': 'Agent Security Deposit', 'group': 'liability', 'type': 'deposits_taken',
        'parent': '2000A', 'related': 'security', 'report': 'balance_sheet', 'ac_code': '074', 'order': 217,
    },
    {
        'code': '2000B', 'name': 'Other Liabilities & Provisions', 'group': 'liability', 'type': 'other',
        'parent': '2000', 'related': 'group', 'report': 'balance_sheet',
        'allow_txn': False, 'order': 228,
    },
    {
        'code': '2008', 'name': 'Interest Payable on Deposits', 'group': 'liability', 'type': 'other',
        'parent': '2000B', 'related': 'interest_payable', 'report': 'balance_sheet', 'order': 230,
    },
    {
        'code': '2008A', 'name': 'FD Interest Payable', 'group': 'liability', 'type': 'other',
        'parent': '2000B', 'related': 'interest_payable', 'report': 'balance_sheet', 'order': 231,
    },
    {
        'code': '2009', 'name': 'TDS Payable', 'group': 'liability', 'type': 'other',
        'parent': '2000B', 'related': 'general', 'report': 'balance_sheet', 'order': 232,
    },
    {
        'code': '2009A', 'name': 'Agent TDS Payable', 'group': 'liability', 'type': 'other',
        'parent': '2000B', 'related': 'general', 'report': 'balance_sheet', 'order': 233,
    },
    {
        'code': '2010', 'name': 'Sundry Creditors', 'group': 'liability', 'type': 'other',
        'parent': '2000B', 'related': 'general', 'report': 'balance_sheet', 'order': 234,
    },
    {
        'code': '2011', 'name': 'Other Payable Provisions', 'group': 'liability', 'type': 'other',
        'parent': '2000B', 'related': 'group', 'report': 'balance_sheet',
        'allow_txn': False, 'order': 235,
    },
    {
        'code': '2011A', 'name': 'Training Fund Payable', 'group': 'liability', 'type': 'other',
        'parent': '2011', 'related': 'general', 'report': 'balance_sheet', 'order': 236,
    },
    {
        'code': '2011B', 'name': 'Audit Fees Payable', 'group': 'liability', 'type': 'other',
        'parent': '2011', 'related': 'general', 'report': 'balance_sheet', 'order': 237,
    },
    {
        'code': '2011C', 'name': 'Advertisement Fund Payable', 'group': 'liability', 'type': 'other',
        'parent': '2011', 'related': 'general', 'report': 'balance_sheet', 'order': 238,
    },
    {
        'code': '2011D', 'name': 'Employee Bonus Payable', 'group': 'liability', 'type': 'other',
        'parent': '2011', 'related': 'general', 'report': 'balance_sheet', 'order': 239,
    },
    {
        'code': '2011E', 'name': 'Agent Development Fund', 'group': 'liability', 'type': 'other',
        'parent': '2011', 'related': 'general', 'report': 'balance_sheet', 'order': 240,
    },
    {
        'code': '2011F', 'name': 'Co-operative Society Contribution', 'group': 'liability', 'type': 'other',
        'parent': '2011', 'related': 'general', 'report': 'balance_sheet', 'order': 241,
    },
    {
        'code': '2011G', 'name': 'Loan Recovery Pathak Nidhi', 'group': 'liability', 'type': 'other',
        'parent': '2011', 'related': 'general', 'report': 'balance_sheet', 'order': 242,
    },
    {
        'code': '2011H', 'name': 'NPA Provision', 'group': 'liability', 'type': 'other',
        'parent': '2011', 'related': 'general', 'report': 'balance_sheet', 'order': 243,
    },
    {
        'code': '2011I', 'name': 'Building Fund Provision', 'group': 'liability', 'type': 'other',
        'parent': '2011', 'related': 'general', 'report': 'balance_sheet', 'order': 244,
    },
    {
        'code': '2012', 'name': 'Director Security Deposit', 'group': 'liability', 'type': 'deposits_taken',
        'parent': '2000A', 'related': 'security', 'report': 'balance_sheet', 'ac_code': '075', 'order': 218,
    },
    {
        'code': '2011J', 'name': 'Election Fund Provision', 'group': 'liability', 'type': 'other',
        'parent': '2011', 'related': 'general', 'report': 'balance_sheet', 'order': 245,
    },
    {
        'code': '2011K', 'name': 'Member Welfare Fund Provision', 'group': 'liability', 'type': 'other',
        'parent': '2011', 'related': 'general', 'report': 'balance_sheet', 'order': 246,
    },
    {
        'code': '2011L', 'name': 'Salary Payable', 'group': 'liability', 'type': 'other',
        'parent': '2011', 'related': 'general', 'report': 'balance_sheet', 'order': 247,
    },
    {
        'code': '2014', 'name': 'Uttam Jindagi (Insurance Deposit)', 'group': 'liability', 'type': 'other',
        'parent': '2000B', 'related': 'general', 'report': 'balance_sheet', 'order': 248,
    },
    {
        'code': '2015', 'name': 'Fixed Asset Sale Advance', 'group': 'liability', 'type': 'other',
        'parent': '2000B', 'related': 'general', 'report': 'balance_sheet', 'order': 249,
    },
    {
        'code': '2013', 'name': 'Bank Overdraft', 'group': 'liability', 'type': 'other',
        'parent': '2000B', 'related': 'group', 'report': 'balance_sheet',
        'allow_txn': False, 'order': 250,
    },

    # =========================================================================
    # CAPITAL & RESERVES (25xx) — Balance Sheet (Liabilities side)
    # =========================================================================
    {
        'code': '2500', 'name': 'Capital & Reserves', 'group': 'liability', 'type': 'other',
        'parent': None, 'related': 'group', 'report': 'balance_sheet',
        'allow_txn': False, 'order': 260,
    },
    {
        'code': '2501', 'name': 'Share Capital', 'group': 'liability', 'type': 'share_capital',
        'parent': '2500', 'related': 'shares', 'report': 'balance_sheet', 'ac_code': '003', 'order': 261,
    },
    {
        'code': '2501A', 'name': 'Nominal Share Holder', 'group': 'liability', 'type': 'share_capital',
        'parent': '2500', 'related': 'shares', 'report': 'balance_sheet', 'ac_code': '094', 'order': 262,
    },
    {
        'code': '2502', 'name': 'Statutory Reserve Fund (25%)', 'group': 'liability', 'type': 'reserve_fund',
        'parent': '2500', 'related': 'general', 'report': 'balance_sheet', 'order': 263,
    },
    {
        'code': '2503', 'name': 'Building Fund', 'group': 'liability', 'type': 'other',
        'parent': '2500', 'related': 'general', 'report': 'balance_sheet', 'order': 264,
    },
    {
        'code': '2504', 'name': 'Education Fund', 'group': 'liability', 'type': 'other',
        'parent': '2500', 'related': 'general', 'report': 'balance_sheet', 'order': 265,
    },
    {
        'code': '2505', 'name': 'Depreciation Fund', 'group': 'liability', 'type': 'other',
        'parent': '2500', 'related': 'general', 'report': 'balance_sheet', 'order': 266,
    },
    {
        'code': '2506', 'name': 'Profit & Loss Account', 'group': 'liability', 'type': 'other',
        'parent': '2500', 'related': 'general', 'report': 'balance_sheet', 'order': 270,
    },
    {
        'code': '2506A', 'name': 'Accumulated Profit', 'group': 'liability', 'type': 'other',
        'parent': '2506', 'related': 'general', 'report': 'balance_sheet', 'order': 271,
    },
    {
        'code': '2507', 'name': 'Social Welfare Fund', 'group': 'liability', 'type': 'other',
        'parent': '2500', 'related': 'general', 'report': 'balance_sheet', 'order': 272,
    },
    {
        'code': '2508', 'name': 'Member Welfare Fund', 'group': 'liability', 'type': 'other',
        'parent': '2500', 'related': 'general', 'report': 'balance_sheet', 'order': 273,
    },
    {
        'code': '2509', 'name': 'Election Fund', 'group': 'liability', 'type': 'other',
        'parent': '2500', 'related': 'general', 'report': 'balance_sheet', 'order': 274,
    },
    {
        'code': '2510', 'name': 'Investment Up/Down Fund', 'group': 'liability', 'type': 'other',
        'parent': '2500', 'related': 'general', 'report': 'balance_sheet', 'order': 275,
    },
    {
        'code': '2511', 'name': 'Dividend', 'group': 'liability', 'type': 'other',
        'parent': '2500', 'related': 'shares', 'report': 'balance_sheet', 'ac_code': '056', 'order': 276,
    },
    {
        'code': '2512', 'name': 'NPA Profit & Loss Reserve', 'group': 'liability', 'type': 'other',
        'parent': '2500', 'related': 'general', 'report': 'balance_sheet', 'order': 277,
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
        'parent': '3000', 'related': 'general', 'report': 'profit_loss', 'order': 302,
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
        'code': '3009', 'name': 'Transfer Charges Received', 'group': 'income', 'type': 'other',
        'parent': '3000', 'related': 'general', 'report': 'profit_loss', 'order': 309,
    },
    {
        'code': '3010', 'name': 'Agent Commission Received', 'group': 'income', 'type': 'other',
        'parent': '3000', 'related': 'general', 'report': 'profit_loss', 'order': 310,
    },
    {
        'code': '3011', 'name': 'Miscellaneous Income', 'group': 'income', 'type': 'other',
        'parent': '3000', 'related': 'general', 'report': 'profit_loss', 'order': 325,
    },
    {
        'code': '3012', 'name': 'Daily Collection Commission', 'group': 'income', 'type': 'other',
        'parent': '3000', 'related': 'general', 'report': 'profit_loss', 'order': 311,
    },
    {
        'code': '3013', 'name': 'FD Commission Received', 'group': 'income', 'type': 'other',
        'parent': '3000', 'related': 'general', 'report': 'profit_loss', 'order': 312,
    },
    {
        'code': '3014', 'name': 'RD Commission Received', 'group': 'income', 'type': 'other',
        'parent': '3000', 'related': 'general', 'report': 'profit_loss', 'order': 313,
    },
    {
        'code': '3015', 'name': 'Share Transfer Fees', 'group': 'income', 'type': 'other',
        'parent': '3000', 'related': 'general', 'report': 'profit_loss', 'order': 314,
    },
    {
        'code': '3016', 'name': 'Passbook Fees Received', 'group': 'income', 'type': 'other',
        'parent': '3000', 'related': 'general', 'report': 'profit_loss', 'order': 315,
    },
    {
        'code': '3017', 'name': 'Notice Fee Received', 'group': 'income', 'type': 'other',
        'parent': '3000', 'related': 'general', 'report': 'profit_loss', 'order': 316,
    },
    {
        'code': '3018', 'name': 'Insurance Fees Received', 'group': 'income', 'type': 'other',
        'parent': '3000', 'related': 'general', 'report': 'profit_loss', 'order': 317,
    },
    {
        'code': '3019', 'name': 'Court Case Charges Received', 'group': 'income', 'type': 'other',
        'parent': '3000', 'related': 'general', 'report': 'profit_loss', 'order': 318,
    },
    {
        'code': '3020', 'name': 'Bank Interest Received', 'group': 'income', 'type': 'interest_income',
        'parent': '3000', 'related': 'group', 'report': 'profit_loss',
        'allow_txn': False, 'order': 319,
    },
    {
        'code': '3021', 'name': 'TDS Received', 'group': 'income', 'type': 'other',
        'parent': '3000', 'related': 'general', 'report': 'profit_loss', 'order': 320,
    },
    {
        'code': '3022', 'name': 'FD Interest Recovered', 'group': 'income', 'type': 'other',
        'parent': '3000', 'related': 'interest_received', 'report': 'profit_loss', 'order': 321,
    },
    {
        'code': '3023', 'name': 'Loan Recovery Charges Received', 'group': 'income', 'type': 'other',
        'parent': '3000', 'related': 'general', 'report': 'profit_loss', 'order': 322,
    },
    {
        'code': '3024', 'name': 'Bank Charges Received', 'group': 'income', 'type': 'other',
        'parent': '3000', 'related': 'general', 'report': 'profit_loss', 'order': 323,
    },
    {
        'code': '3025', 'name': 'Cheque Return Charges Received', 'group': 'income', 'type': 'other',
        'parent': '3000', 'related': 'general', 'report': 'profit_loss', 'order': 324,
    },
    {
        'code': '3026', 'name': 'FD Investment Interest Received', 'group': 'income', 'type': 'interest_income',
        'parent': '3000', 'related': 'interest_received', 'report': 'profit_loss', 'order': 326,
    },
    {
        'code': '3027', 'name': 'Fixed Asset Sale Profit', 'group': 'income', 'type': 'other',
        'parent': '3000', 'related': 'general', 'report': 'profit_loss', 'order': 327,
    },
    {
        'code': '3028', 'name': 'Incidental Charges Received', 'group': 'income', 'type': 'other',
        'parent': '3000', 'related': 'general', 'report': 'profit_loss', 'order': 328,
    },
    {
        'code': '3029', 'name': 'Service Tax / GST Received', 'group': 'income', 'type': 'other',
        'parent': '3000', 'related': 'general', 'report': 'profit_loss', 'order': 329,
    },
    {
        'code': '3030', 'name': 'Penalty Received', 'group': 'income', 'type': 'other',
        'parent': '3000', 'related': 'general', 'report': 'profit_loss', 'order': 330,
    },
    {
        'code': '3031', 'name': 'Saanugrah Anudan Received', 'group': 'income', 'type': 'other',
        'parent': '3000', 'related': 'general', 'report': 'profit_loss', 'order': 331,
    },
    {
        'code': '3032', 'name': 'Dividend Received', 'group': 'income', 'type': 'other',
        'parent': '3000', 'related': 'general', 'report': 'profit_loss', 'order': 332,
    },

    # =========================================================================
    # EXPENSES (4xxx) — Profit & Loss
    # =========================================================================
    {
        'code': '4000', 'name': 'Expenses', 'group': 'expense', 'type': 'other',
        'parent': None, 'related': 'group', 'report': 'profit_loss',
        'allow_txn': False, 'order': 400,
    },

    # --- Interest Expenses ---
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
        'code': '4006', 'name': 'FD Interest Payable Expense', 'group': 'expense', 'type': 'interest_expense',
        'parent': '4000', 'related': 'interest_paid', 'report': 'profit_loss', 'order': 406,
    },
    {
        'code': '4030', 'name': 'Interest on Bank Overdraft', 'group': 'expense', 'type': 'interest_expense',
        'parent': '4000', 'related': 'interest_paid', 'report': 'profit_loss', 'order': 407,
    },

    # --- Administrative Expenses ---
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
        'code': '4019', 'name': 'Daily Agent Commission Paid', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 419,
    },
    {
        'code': '4019A', 'name': 'RD Agent Commission Paid', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 420,
    },
    {
        'code': '4019B', 'name': 'FD Commission Paid', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 421,
    },
    {
        'code': '4020', 'name': 'Dividend on Shares', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 422,
    },
    {
        'code': '4021', 'name': 'Software Expenses', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 423,
    },
    {
        'code': '4022', 'name': 'Office Expenses', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 424,
    },
    {
        'code': '4023', 'name': 'Electricity Expenses', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 425,
    },
    {
        'code': '4024', 'name': 'Director Meeting Expenses', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 426,
    },
    {
        'code': '4025', 'name': 'Annual Meeting / Advertisement', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 427,
    },
    {
        'code': '4026', 'name': 'Training Expenses', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 428,
    },
    {
        'code': '4027', 'name': 'Nagar Parishad / Municipal Tax', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 429,
    },
    {
        'code': '4028', 'name': 'Income Tax / Return Filing', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 430,
    },
    {
        'code': '4029', 'name': 'Loan Recovery Expenses', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 431,
    },
    {
        'code': '4031', 'name': 'NPA Provision Expense', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 440,
    },
    {
        'code': '4032', 'name': 'Election Fund Expense', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 441,
    },
    {
        'code': '4033', 'name': 'Training Fund Expense', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 442,
    },
    {
        'code': '4034', 'name': 'Building Fund Expense', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 443,
    },
    {
        'code': '4035', 'name': 'Bank Charges', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 432,
    },
    {
        'code': '4036', 'name': 'Telephone Expenses', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 433,
    },
    {
        'code': '4037', 'name': 'Typing & Xerox Expenses', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 434,
    },
    {
        'code': '4038', 'name': 'Professional Tax', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 435,
    },
    {
        'code': '4039', 'name': 'Annual Contribution', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 436,
    },
    {
        'code': '4040', 'name': 'Office Insurance', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 437,
    },
    {
        'code': '4041', 'name': 'Employee Bonus', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 438,
    },
    {
        'code': '4042', 'name': 'Data Entry Expenses', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 439,
    },
    {
        'code': '4043', 'name': 'GST Paid', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 444,
    },
    {
        'code': '4044', 'name': 'TDS on Bank FD', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 445,
    },
    {
        'code': '4045', 'name': 'Co-operative Contribution Expense', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 446,
    },
    {
        'code': '4046', 'name': 'Agent Development Expense', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 447,
    },
    {
        'code': '4047', 'name': 'Member Welfare Fund Expense', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 448,
    },
    {
        'code': '4048', 'name': 'Loan Recovery Pathak Nidhi Expense', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 449,
    },
    {
        'code': '4049', 'name': 'Petrol Charges', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 450,
    },
    {
        'code': '4050', 'name': 'Saanugrah Anudan', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 451,
    },
    {
        'code': '4051', 'name': 'Employee Payment / Gratuity', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 452,
    },
    {
        'code': '4052', 'name': 'Pending Loan Commission', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 453,
    },
    {
        'code': '4053', 'name': 'Painting / Maintenance', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 454,
    },
    {
        'code': '4054', 'name': 'TDS Expenses', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 455,
    },
    {
        'code': '4055', 'name': 'Corporation Tax', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 456,
    },
    {
        'code': '4056', 'name': 'Notice Expenses', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 457,
    },
    {
        'code': '4057', 'name': 'Provision for Bad Debts', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 460,
    },
    {
        'code': '4058', 'name': 'Provision for Standard Assets', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 461,
    },
    {
        'code': '4059', 'name': 'Provision for Overdue Interest', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 462,
    },
    {
        'code': '4060', 'name': 'Provision for Contingency', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 463,
    },
    {
        'code': '4061', 'name': 'Fixed Asset Sale Loss', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 464,
    },
    {
        'code': '4099', 'name': 'Miscellaneous Expenses', 'group': 'expense', 'type': 'other',
        'parent': '4000', 'related': 'general', 'report': 'profit_loss', 'order': 499,
    },
]
# fmt: on


def setup_chart_of_accounts(branches=None, force=False):
    """Create default COA heads. With force=True, updates existing heads to match defaults."""
    from apps.accounting.models import ChartOfAccounts

    parent_map = {}
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
            'account_code': item.get('ac_code', ''),
        }

        if item.get('per_branch') and branches:
            for branch in branches:
                code = f'{item["code"]}-{branch.branch_code}'
                if force:
                    obj, _ = ChartOfAccounts.objects.update_or_create(
                        code=code,
                        defaults={
                            **defaults,
                            'name': f'{item["name"]} ({branch.branch_name})',
                            'branch': branch,
                        },
                    )
                else:
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
            if force:
                obj, _ = ChartOfAccounts.objects.update_or_create(
                    code=item['code'],
                    defaults=defaults,
                )
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
