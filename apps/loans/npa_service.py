from collections import defaultdict
from datetime import date
from decimal import Decimal

from apps.loans.models import LoanAccount

NPA_TIERS_REGULAR = [
    # (max_months, category, provision_percent)
    (3, 'standard', Decimal('0.25')),
    (12, 'sub_standard', Decimal('6')),
    (36, 'doubtful_1', Decimal('70')),
    (48, 'doubtful_2', Decimal('80')),
    (999, 'doubtful_3', Decimal('90')),
]

NPA_TIERS_MORTGAGE = [
    (6, 'standard', Decimal('0.25')),
    (12, 'sub_standard', Decimal('6')),
    (36, 'doubtful_1', Decimal('20')),
    (48, 'doubtful_2', Decimal('25')),
    (999, 'doubtful_3', Decimal('30')),
]


def classify_loan(loan):
    """Classify a single loan's NPA category and provision."""
    if loan.status not in ('disbursed', 'npa'):
        return {'category': 'standard', 'provision_percent': Decimal('0'), 'provision_amount': Decimal('0')}

    overdue_months = loan.overdue_days / 30
    is_mortgage = loan.loan_product.mortgage_type == 'property'
    tiers = NPA_TIERS_MORTGAGE if is_mortgage else NPA_TIERS_REGULAR

    category = 'standard'
    provision_percent = Decimal('0.25')
    for max_months, cat, pct in tiers:
        if overdue_months <= max_months:
            category = cat
            provision_percent = pct
            break

    outstanding = loan.outstanding_principal + loan.bal_interest + loan.bal_penal
    provision_amount = (outstanding * provision_percent / 100).quantize(Decimal('0.01'))

    return {
        'category': category,
        'provision_percent': provision_percent,
        'provision_amount': provision_amount,
    }


def classify_all_loans():
    """Classify all active loans and update their NPA fields. Returns summary dict."""
    loans = LoanAccount.objects.filter(
        status__in=['disbursed', 'npa'],
    ).select_related('loan_product', 'member')

    updated = 0
    for loan in loans:
        result = classify_loan(loan)
        changed = False
        if loan.npa_category != result['category']:
            loan.npa_category = result['category']
            changed = True
        if loan.npa_provision_percent != result['provision_percent']:
            loan.npa_provision_percent = result['provision_percent']
            changed = True
        if loan.npa_provision_amount != result['provision_amount']:
            loan.npa_provision_amount = result['provision_amount']
            changed = True
        if loan.npa_category != 'standard' and not loan.npa_date:
            loan.npa_date = date.today()
            changed = True
        if loan.npa_category == 'standard' and loan.npa_date:
            loan.npa_date = None
            changed = True
        if changed:
            loan.save(update_fields=[
                'npa_category', 'npa_provision_percent', 'npa_provision_amount', 'npa_date', 'updated_at',
            ])
            updated += 1

    return {'total': loans.count(), 'updated': updated}


def get_npa_report(branch=None):
    """Generate NPA report data grouped by loan product type."""
    qs = LoanAccount.objects.filter(
        status__in=['disbursed', 'npa'],
    ).select_related('loan_product', 'member', 'branch')

    if branch:
        qs = qs.filter(branch=branch)

    loans = list(qs)
    for loan in loans:
        result = classify_loan(loan)
        loan._computed_category = result['category']
        loan._computed_provision_pct = result['provision_percent']
        loan._computed_provision_amt = result['provision_amount']

    by_product = defaultdict(list)
    for loan in loans:
        by_product[loan.loan_product.name].append(loan)

    category_summary = defaultdict(lambda: {'count': 0, 'outstanding': Decimal('0'), 'provision': Decimal('0')})
    for loan in loans:
        cat = loan._computed_category
        category_summary[cat]['count'] += 1
        category_summary[cat]['outstanding'] += loan.outstanding_principal
        category_summary[cat]['provision'] += loan._computed_provision_amt

    total_outstanding = sum(ln.outstanding_principal for ln in loans) if loans else Decimal('0')
    total_provision = sum(ln._computed_provision_amt for ln in loans) if loans else Decimal('0')

    return {
        'loans': loans,
        'by_product': dict(by_product),
        'category_summary': dict(category_summary),
        'total_loans': len(loans),
        'total_outstanding': total_outstanding,
        'total_provision': total_provision,
    }
