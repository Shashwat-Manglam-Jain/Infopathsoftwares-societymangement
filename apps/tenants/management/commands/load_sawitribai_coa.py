from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import connection, transaction

# fmt: off
# Each entry: (code, name, group, related, report, opening_balance)
# opening_balance = abs(closing balance from FY 2025-2026 OPB)
# Income/Expense heads get 0 opening (fresh P&L year)
SAWITRIBAI_COA = [
    # ── Bank Savings Accounts (Assets) ──────────────────────────────────────
    ('S017', 'SB AC Maharashtra State Co-op Bank', 'asset', 'bank', 'balance_sheet', Decimal('46629.69')),
    ('S018', 'SB AC Nagpur Dist Central Co-op Bank', 'asset', 'bank', 'balance_sheet', Decimal('9061.77')),
    ('S055', 'SB AC Sadhna Sahakari Bank', 'asset', 'bank', 'balance_sheet', Decimal('20461.20')),
    ('S021', 'SB AC Tirupati Urban Co-op Bank', 'asset', 'bank', 'balance_sheet', Decimal('0')),
    # ── Bank Current Accounts (Assets) ──────────────────────────────────────
    ('S022', 'CA AC Maharashtra State Co-op Bank', 'asset', 'bank', 'balance_sheet', Decimal('19009.41')),
    ('S047', 'CA AC Nirmal Urban Co-op Bank', 'asset', 'bank', 'balance_sheet', Decimal('7784.16')),
    ('S065', 'CA AC Latur Urban Bank', 'asset', 'bank', 'balance_sheet', Decimal('585783.00')),
    ('S057', 'CA AC Yavatmal Co-op Bank', 'asset', 'bank', 'balance_sheet', Decimal('0')),
    # ── Bank Overdraft Accounts ─────────────────────────────────────────────
    ('S023', 'OD AC Maharashtra State Co-op Bank', 'liability', 'bank', 'balance_sheet', Decimal('109926.04')),
    ('L059', 'OD AC Nirmal Urban Bank', 'liability', 'bank', 'balance_sheet', Decimal('0')),
    # ── FD Investment Accounts (Assets) ─────────────────────────────────────
    ('S007', 'FD AC Maharashtra State Co-op Bank', 'asset', 'bank', 'balance_sheet', Decimal('25140458.00')),
    ('S029', 'FD AC MS State Bank Reserve Fund', 'asset', 'bank', 'balance_sheet', Decimal('366509.00')),
    ('S048', 'FD AC Nirmal Urban Co-op Bank', 'asset', 'bank', 'balance_sheet', Decimal('4000000.00')),
    ('S054', 'FD AC Sadhna Sahakari Bank', 'asset', 'bank', 'balance_sheet', Decimal('3437306.00')),
    ('S058', 'FD AC Shikshak Sahakari Bank', 'asset', 'bank', 'balance_sheet', Decimal('1044247.00')),
    ('S063', 'FD AC Arvind Sahakari Bank', 'asset', 'bank', 'balance_sheet', Decimal('3000000.00')),
    ('S064', 'FD AC Samruddhi Sahakari Bank', 'asset', 'bank', 'balance_sheet', Decimal('1000000.00')),
    ('S066', 'FD AC Swayamshakti Co-op Bank', 'asset', 'bank', 'balance_sheet', Decimal('0')),
    ('S067', 'FD AC Latur Urban Bank', 'asset', 'bank', 'balance_sheet', Decimal('2500000.00')),
    # ── Loan Accounts (Assets) ──────────────────────────────────────────────
    ('S011', 'Regular Loan', 'asset', 'loan', 'balance_sheet', Decimal('2601446.00')),
    ('S012', 'Emergency Loan', 'asset', 'loan', 'balance_sheet', Decimal('0')),
    ('S013', 'Loan Against Fixed Deposit', 'asset', 'loan', 'balance_sheet', Decimal('5164333.00')),
    ('S014', 'Loan Against Pigmmy Account', 'asset', 'loan', 'balance_sheet', Decimal('342000.00')),
    ('S015', 'Loan Against Recurring Deposit', 'asset', 'loan', 'balance_sheet', Decimal('88390.00')),
    ('S016', 'Property Mortgage Loan', 'asset', 'loan', 'balance_sheet', Decimal('28454619.00')),
    # ── Other Receivables (Assets) ──────────────────────────────────────────
    ('S061', 'MS State Bank Interest Receivable', 'asset', 'interest_receivable', 'balance_sheet', Decimal('1224551.00')),
    ('S062', 'MS State Bank TDS Receivable', 'asset', 'general', 'balance_sheet', Decimal('122552.00')),
    # ── Deposits (Liabilities) ──────────────────────────────────────────────
    ('L014', 'Saving Deposit', 'liability', 'saving', 'balance_sheet', Decimal('3553320.44')),
    ('L015', 'Daily Pigmmy Account', 'liability', 'client', 'balance_sheet', Decimal('8663666.00')),
    ('L016', 'Fixed Deposit Receipt', 'liability', 'fixed', 'balance_sheet', Decimal('52809755.00')),
    ('L017', 'Monthly Recurring Deposit', 'liability', 'recurring', 'balance_sheet', Decimal('5185200.00')),
    ('L049', 'Agent Security Deposit', 'liability', 'security', 'balance_sheet', Decimal('551288.00')),
    ('L035', 'Fixed Deposit Interest Payable', 'liability', 'interest_payable', 'balance_sheet', Decimal('3126375.00')),
    ('L062', 'Agent TDS Payable', 'liability', 'general', 'balance_sheet', Decimal('1374.00')),
    # ── Equity — Share Capital ──────────────────────────────────────────────
    ('L002', 'Share Capital', 'equity', 'shares', 'balance_sheet', Decimal('3626797.00')),
    # ── Equity — Funds & Reserves ───────────────────────────────────────────
    ('L004', 'Statutory Reserve Fund', 'equity', 'general', 'balance_sheet', Decimal('490388.89')),
    ('L005', 'Building Fund and Land', 'equity', 'general', 'balance_sheet', Decimal('1018898.52')),
    ('L008', 'Depreciation Fund', 'equity', 'general', 'balance_sheet', Decimal('530603.00')),
    ('L009', 'Deposit Fluctuation Fund', 'equity', 'general', 'balance_sheet', Decimal('35000.00')),
    ('L022', 'Training Fund', 'equity', 'general', 'balance_sheet', Decimal('31065.00')),
    ('L023', 'Audit Fee Fund', 'equity', 'general', 'balance_sheet', Decimal('57463.00')),
    ('L025', 'Uttam Jindagi Fund', 'equity', 'general', 'balance_sheet', Decimal('509815.00')),
    ('L048', 'Social Welfare Fund', 'equity', 'general', 'balance_sheet', Decimal('12399.00')),
    ('L053', 'Advertisement Fund', 'equity', 'general', 'balance_sheet', Decimal('23178.00')),
    ('L054', 'Employee Bonus Fund', 'equity', 'general', 'balance_sheet', Decimal('0')),
    ('L055', 'Agent Development Fund', 'equity', 'general', 'balance_sheet', Decimal('63985.00')),
    ('L057', 'Loan Recovery Fund', 'equity', 'general', 'balance_sheet', Decimal('32405.00')),
    ('L058', 'NPA Provision', 'equity', 'general', 'balance_sheet', Decimal('1159934.00')),
    ('L060', 'Co-operative Society Fund', 'equity', 'general', 'balance_sheet', Decimal('100000.00')),
    ('L044', 'Accumulated Profit (Sanchit Nafa)', 'equity', 'general', 'balance_sheet', Decimal('148991.52')),
    # ── Income ──────────────────────────────────────────────────────────────
    ('I003', 'Interest Received on Loan', 'income', 'interest_received', 'profit_loss', Decimal('0')),
    ('I006', 'Penal Interest Received on Loan', 'income', 'interest_received', 'profit_loss', Decimal('0')),
    ('I010', 'Daily Deposit Commission', 'income', 'general', 'profit_loss', Decimal('0')),
    ('I014', 'MS State Bank SB Interest Received', 'income', 'interest_received', 'profit_loss', Decimal('0')),
    ('I016', 'Nagpur DCC Bank Interest Received', 'income', 'interest_received', 'profit_loss', Decimal('0')),
    ('I018', 'Tirupati Urban Bank Interest Received', 'income', 'interest_received', 'profit_loss', Decimal('0')),
    ('I020', 'FD Investment Interest Received', 'income', 'interest_received', 'profit_loss', Decimal('0')),
    ('I022', 'Administrative Fees', 'income', 'general', 'profit_loss', Decimal('0')),
    ('I023', 'Transfer Charges', 'income', 'general', 'profit_loss', Decimal('0')),
    ('I024', 'Miscellaneous Income', 'income', 'general', 'profit_loss', Decimal('0')),
    ('I025', 'Incidental Charges Received', 'income', 'general', 'profit_loss', Decimal('0')),
    ('I026', 'Loan Form Fee Received', 'income', 'processing_fee_income', 'profit_loss', Decimal('0')),
    ('I027', 'Passbook Fees Received', 'income', 'general', 'profit_loss', Decimal('0')),
    ('I029', 'Court Case Charges Received', 'income', 'general', 'profit_loss', Decimal('0')),
    ('I031', 'Notice Fee Received', 'income', 'general', 'profit_loss', Decimal('0')),
    ('I032', 'Insurance Fees Received', 'income', 'general', 'profit_loss', Decimal('0')),
    ('I037', 'Bank Charge Received', 'income', 'general', 'profit_loss', Decimal('0')),
    ('I038', 'Loan Recovery Charges Received', 'income', 'general', 'profit_loss', Decimal('0')),
    ('I040', 'Sadhna Sahakari Bank SB Interest', 'income', 'interest_received', 'profit_loss', Decimal('0')),
    ('I041', 'TDS Received', 'income', 'general', 'profit_loss', Decimal('0')),
    ('I044', 'Fixed Deposit Interest Recovered', 'income', 'general', 'profit_loss', Decimal('0')),
    # ── Expenses ────────────────────────────────────────────────────────────
    ('E003', 'Interest on Deposit', 'expense', 'interest_paid', 'profit_loss', Decimal('0')),
    ('E012', 'Bank OD Interest Paid (MS State)', 'expense', 'general', 'profit_loss', Decimal('0')),
    ('E013', 'Daily Deposit Agent Commission', 'expense', 'general', 'profit_loss', Decimal('0')),
    ('E014', 'Recurring Deposit Agent Commission', 'expense', 'general', 'profit_loss', Decimal('0')),
    ('E016', 'Printing and Stationery Expenses', 'expense', 'general', 'profit_loss', Decimal('0')),
    ('E017', 'Typing and Xerox Expenses', 'expense', 'general', 'profit_loss', Decimal('0')),
    ('E018', 'Miscellaneous Expenses', 'expense', 'general', 'profit_loss', Decimal('0')),
    ('E019', 'Working Wages (Salary)', 'expense', 'general', 'profit_loss', Decimal('0')),
    ('E020', 'Electric Expenses', 'expense', 'general', 'profit_loss', Decimal('0')),
    ('E021', 'Office Rent', 'expense', 'general', 'profit_loss', Decimal('0')),
    ('E022', 'Laxmipujan Expenses', 'expense', 'general', 'profit_loss', Decimal('0')),
    ('E023', 'Bank Charges', 'expense', 'general', 'profit_loss', Decimal('0')),
    ('E025', 'Annual Meeting Expenses', 'expense', 'general', 'profit_loss', Decimal('0')),
    ('E027', 'Insurance Expenses', 'expense', 'general', 'profit_loss', Decimal('0')),
    ('E028', 'Advertisement Expenses', 'expense', 'general', 'profit_loss', Decimal('0')),
    ('E031', 'Court Case Expenses', 'expense', 'general', 'profit_loss', Decimal('0')),
    ('E033', 'Postage Expenses', 'expense', 'general', 'profit_loss', Decimal('0')),
    ('E035', 'Annual Contribution NGP Pathsanstha', 'expense', 'general', 'profit_loss', Decimal('0')),
    ('E036', 'Office Insurance', 'expense', 'general', 'profit_loss', Decimal('0')),
    ('E037', 'Professional Tax', 'expense', 'general', 'profit_loss', Decimal('0')),
    ('E040', 'Investment Fluctuation Fund Expense', 'expense', 'general', 'profit_loss', Decimal('0')),
    ('E041', 'Uttam Jindagi Expense', 'expense', 'general', 'profit_loss', Decimal('0')),
    ('E042', 'Training Fund Expense', 'expense', 'general', 'profit_loss', Decimal('0')),
    ('E043', 'Audit Fee Expense', 'expense', 'general', 'profit_loss', Decimal('0')),
    ('E044', 'FD Interest Payable Expense', 'expense', 'general', 'profit_loss', Decimal('0')),
    ('E052', 'Sawitribai Jayanti Utsav', 'expense', 'general', 'profit_loss', Decimal('0')),
    ('E053', 'Data Entry Expenses', 'expense', 'general', 'profit_loss', Decimal('0')),
    ('E054', 'Depreciation Expenses', 'expense', 'general', 'profit_loss', Decimal('0')),
    ('E058', 'Corporation Tax (NMC)', 'expense', 'general', 'profit_loss', Decimal('0')),
    ('E059', 'Loan Recovery Expenses', 'expense', 'general', 'profit_loss', Decimal('0')),
    ('E063', 'NPA Provision Expenses', 'expense', 'general', 'profit_loss', Decimal('0')),
    ('E064', 'Income Tax Expenses', 'expense', 'general', 'profit_loss', Decimal('0')),
    ('E065', 'Agent Development Expenses', 'expense', 'general', 'profit_loss', Decimal('0')),
    ('E071', 'TDS on Bank FD', 'expense', 'general', 'profit_loss', Decimal('0')),
    ('E072', 'Nirmal Urban Bank OD Interest Paid', 'expense', 'general', 'profit_loss', Decimal('0')),
    ('E073', 'Co-operative Society Contribution', 'expense', 'general', 'profit_loss', Decimal('0')),
    ('E074', 'Building Fund Provision Expense', 'expense', 'general', 'profit_loss', Decimal('0')),
]

EXISTING_HEAD_UPDATES = {
    '2001': Decimal('3553320.44'),    # Savings Deposits ← L014
    '2002': Decimal('52809755.00'),   # Fixed Deposits ← L016
    '2003': Decimal('5185200.00'),    # Recurring Deposits ← L017
    '2005': Decimal('8663666.00'),    # Daily/Pigmmy ← L015
    '2501': Decimal('3626797.00'),    # Share Capital ← L002
    '2007': Decimal('551288.00'),     # Agent Security ← L049
    '1003': Decimal('36650788.00'),   # Loans ← sum(S011..S016 abs closings)
    '1009': Decimal('40488520.00'),   # Bank FD Investments ← sum of S-FD heads
}

PARENT_MAP = {
    'asset': '1000',
    'liability': '2000',
    'equity': '2500',
    'income': '3000',
    'expense': '4000',
}
# fmt: on


class Command(BaseCommand):
    help = 'Load Sawitribai Society chart of accounts with opening balances'

    def add_arguments(self, parser):
        parser.add_argument(
            '--schema', default='demo', help='Tenant schema name (default: demo)'
        )

    def handle(self, *args, **options):
        schema = options['schema']
        connection.set_schema(schema)
        self.stdout.write(f'Loading Sawitribai COA into schema: {schema}')

        from apps.accounting.models import CashbookMaster, ChartOfAccounts
        from apps.branches.models import Branch

        parents = {}
        for group, code in PARENT_MAP.items():
            try:
                parents[group] = ChartOfAccounts.objects.get(code=code)
            except ChartOfAccounts.DoesNotExist:
                self.stderr.write(
                    self.style.ERROR(
                        f'Parent head {code} not found. '
                        f'Run create_demo_tenant first.'
                    )
                )
                return

        created = 0
        existed = 0

        with transaction.atomic():
            for code, name, group, related, report, opening in SAWITRIBAI_COA:
                obj, was_created = ChartOfAccounts.objects.get_or_create(
                    code=code,
                    defaults={
                        'name': name,
                        'account_group': group,
                        'account_type': 'other',
                        'parent': parents[group],
                        'related_table_name': related,
                        'report_position': report,
                        'display_order': 0,
                        'is_active': True,
                        'allow_transactions': True,
                        'opening_balance': opening,
                        'current_balance': opening,
                        'credit_balance': Decimal('0'),
                        'debit_balance': Decimal('0'),
                    },
                )
                if was_created:
                    created += 1
                else:
                    existed += 1

            updated = 0
            for code, opening in EXISTING_HEAD_UPDATES.items():
                try:
                    head = ChartOfAccounts.objects.get(code=code)
                    head.opening_balance = opening
                    head.current_balance = opening
                    head.save(update_fields=['opening_balance', 'current_balance'])
                    updated += 1
                    self.stdout.write(
                        f'  Updated {code} {head.name}: '
                        f'opening={opening:,.2f}'
                    )
                except ChartOfAccounts.DoesNotExist:
                    self.stderr.write(
                        self.style.WARNING(f'  Head {code} not found, skipping')
                    )

            # Set cash opening balance
            cash_heads = ChartOfAccounts.objects.filter(
                code__startswith='1001'
            )
            for ch in cash_heads:
                ch.opening_balance = Decimal('1612.00')
                ch.current_balance = Decimal('1612.00')
                ch.save(update_fields=['opening_balance', 'current_balance'])
                self.stdout.write(
                    f'  Cash head {ch.code}: opening=1,612.00'
                )

            # CashbookMaster opening entry
            ho_branch = Branch.objects.filter(branch_code='HO').first()
            if ho_branch:
                cb, cb_created = CashbookMaster.objects.get_or_create(
                    branch=ho_branch,
                    txn_date=date(2026, 4, 1),
                    defaults={
                        'opening_balance': Decimal('1612.00'),
                        'closing_balance': Decimal('1612.00'),
                    },
                )
                if cb_created:
                    self.stdout.write(
                        '  CashbookMaster created for HO: '
                        '2026-04-01, opening=1,612.00'
                    )
                else:
                    self.stdout.write(
                        '  CashbookMaster already exists for HO 2026-04-01'
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f'\nDone: {created} heads created, {existed} already existed, '
                f'{updated} existing heads updated with opening balances.'
            )
        )
        total_heads = ChartOfAccounts.objects.count()
        self.stdout.write(f'Total GL heads in {schema}: {total_heads}')
