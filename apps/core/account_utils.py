from django.db import transaction
from django.db.models import Max


def amount_to_words(amount):
    ones = [
        '',
        'One',
        'Two',
        'Three',
        'Four',
        'Five',
        'Six',
        'Seven',
        'Eight',
        'Nine',
        'Ten',
        'Eleven',
        'Twelve',
        'Thirteen',
        'Fourteen',
        'Fifteen',
        'Sixteen',
        'Seventeen',
        'Eighteen',
        'Nineteen',
    ]
    tens = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety']

    num = int(amount)
    paise = round(abs(amount - num) * 100)

    def two_digits(n):
        if n < 20:
            return ones[n]
        return tens[n // 10] + (' ' + ones[n % 10] if n % 10 else '')

    if num == 0 and paise == 0:
        return 'Zero Rupees Only'

    parts = []
    if num >= 10000000:
        parts.append(two_digits(num // 10000000) + ' Crore')
        num %= 10000000
    if num >= 100000:
        parts.append(two_digits(num // 100000) + ' Lakh')
        num %= 100000
    if num >= 1000:
        parts.append(two_digits(num // 1000) + ' Thousand')
        num %= 1000
    if num >= 100:
        parts.append(ones[num // 100] + ' Hundred')
        num %= 100
    if num > 0:
        parts.append(two_digits(num))

    if parts:
        result = ' '.join(parts) + ' Rupees'
    else:
        result = 'Zero Rupees'
    if paise:
        result += f' and {two_digits(paise)} Paise'
    result += ' Only'
    return result


@transaction.atomic
def generate_account_number(branch, account_code):
    """Generate account number: SocietyCode(3) + BranchCode(2) + AccountCode(3) + Sequential(7).

    Uses select_for_update to prevent race conditions — concurrent calls block
    until the first transaction commits.
    """
    from apps.agents.models import PigmmyAccount
    from apps.deposits.models import FixedDeposit, RecurringDeposit
    from apps.loans.models import LoanAccount
    from apps.savings.models import SavingsAccount

    society = getattr(branch, 'society', None)
    society_code = getattr(society, 'society_code', None) or getattr(branch, 'society_code', None) or '001'
    branch_part = branch.branch_code[:2].zfill(2)
    acct_part = account_code[:3].zfill(3)

    prefix = f'{society_code}{branch_part}{acct_part}'

    max_nums = []
    for model, field in [
        (SavingsAccount, 'account_no'),
        (LoanAccount, 'loan_no'),
        (FixedDeposit, 'fd_no'),
        (RecurringDeposit, 'rd_no'),
        (PigmmyAccount, 'account_no'),
    ]:
        qs = model.objects.select_for_update().filter(**{f'{field}__startswith': prefix})
        result = qs.aggregate(max_no=Max(field))
        if result['max_no']:
            try:
                seq = int(result['max_no'][-7:])
                max_nums.append(seq)
            except (ValueError, IndexError):
                pass

    next_seq = max(max_nums, default=0) + 1
    return f'{prefix}{next_seq:07d}'
