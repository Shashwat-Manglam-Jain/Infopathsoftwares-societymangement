import logging
from decimal import Decimal

from django.db import models, transaction
from django.utils import timezone

from .models import ShareConfig, ShareHolding, ShareTransaction

logger = logging.getLogger(__name__)


def _get_config():
    return ShareConfig.objects.filter(is_active=True).first()


@transaction.atomic
def purchase_shares(member, branch, count, user):
    config = _get_config()
    if not config:
        raise ValueError('Share configuration not found.')
    if count < config.min_shares_required:
        raise ValueError(f'Minimum {config.min_shares_required} shares required.')

    existing_holding = ShareHolding.objects.filter(member=member, status='active').first()
    existing = (
        ShareHolding.objects.filter(
            member=member,
            status='active',
        ).aggregate(total=models.Sum('share_count'))['total']
        or 0
    )
    if existing + count > config.max_shares_per_member:
        raise ValueError(f'Maximum {config.max_shares_per_member} shares allowed. Member already holds {existing}.')

    total_amount = Decimal(count) * config.face_value_per_share

    if existing_holding:
        existing_holding.share_count += count
        existing_holding.total_amount += total_amount
        existing_holding.save()
        holding = existing_holding
    else:
        holding = ShareHolding.objects.create(
            member=member,
            branch=branch,
            share_count=count,
            face_value_per_share=config.face_value_per_share,
            total_amount=total_amount,
            purchase_date=timezone.now().date(),
            certificate_no=_generate_certificate_no(),
            status='active',
            created_by=user,
        )

    ShareTransaction.objects.create(
        member=member,
        branch=branch,
        txn_type='purchase',
        shares_count=count,
        amount=total_amount,
        txn_date=timezone.now().date(),
        narration=f'Purchase of {count} shares',
        created_by=user,
    )

    try:
        _create_share_journal(branch, total_amount, user, 'purchase', holding.pk)
    except ValueError as e:
        logger.warning('Share journal entry failed: %s', e)
    return holding


@transaction.atomic
def transfer_shares(from_member, to_member, count, user):
    holdings = ShareHolding.objects.filter(
        member=from_member,
        status='active',
    )
    total_held = sum(h.share_count for h in holdings)
    if total_held < count:
        raise ValueError(f'Member only holds {total_held} shares.')

    remaining_shares = total_held - count
    if remaining_shares == 0:
        from apps.loans.models import LoanAccount, LoanGuarantor

        if LoanGuarantor.objects.filter(
            guarantor_member=from_member,
            loan__status__in=['disbursed', 'npa'],
            loan__outstanding_principal__gt=Decimal('0'),
        ).exists():
            raise ValueError(
                'Cannot transfer all shares: member is an active guarantor on one or more loans. '
                'Guarantors must maintain active share holdings.'
            )

        if LoanAccount.objects.filter(
            member=from_member,
            status__in=['disbursed', 'npa'],
            outstanding_principal__gt=Decimal('0'),
        ).exists():
            raise ValueError(
                'Cannot transfer all shares: member has outstanding loan(s). '
                'Clear loan balance before transferring all shares.'
            )

    config = _get_config()
    amount = Decimal(count) * config.face_value_per_share

    if remaining_shares > 0 and config and config.min_shares_required:
        if remaining_shares < config.min_shares_required:
            raise ValueError(
                f'Transfer would leave {from_member.name} with {remaining_shares} shares, '
                f'below minimum required ({config.min_shares_required}).'
            )

    today = timezone.now().date()

    remaining = count
    for h in holdings:
        if remaining <= 0:
            break
        if h.share_count <= remaining:
            h.status = 'transferred'
            h.save()
            remaining -= h.share_count
        else:
            h.share_count -= remaining
            h.total_amount = Decimal(h.share_count) * config.face_value_per_share
            h.save()
            remaining = 0

    branch = from_member.branch
    ShareTransaction.objects.create(
        member=from_member,
        branch=branch,
        txn_type='transfer',
        shares_count=-count,
        amount=amount,
        txn_date=today,
        narration=f'Transfer of {count} shares to {to_member.name}',
        transfer_to_member=to_member,
        created_by=user,
    )

    existing_to = ShareHolding.objects.filter(member=to_member, status='active').first()
    if config and config.max_shares_per_member:
        total_after = (existing_to.share_count if existing_to else 0) + count
        if total_after > config.max_shares_per_member:
            raise ValueError(
                f'Transfer would give {to_member.name} {total_after} shares, '
                f'exceeding maximum ({config.max_shares_per_member}).'
            )

    if existing_to:
        existing_to.share_count += count
        existing_to.total_amount = Decimal(existing_to.share_count) * config.face_value_per_share
        existing_to.save()
    else:
        ShareHolding.objects.create(
            member=to_member,
            branch=to_member.branch,
            share_count=count,
            face_value_per_share=config.face_value_per_share,
            total_amount=amount,
            purchase_date=today,
            certificate_no=_generate_certificate_no(),
            status='active',
            created_by=user,
        )
    ShareTransaction.objects.create(
        member=to_member,
        branch=to_member.branch,
        txn_type='transfer',
        shares_count=count,
        amount=amount,
        txn_date=today,
        narration=f'Transfer received from {from_member.name}',
        transfer_to_member=from_member,
        created_by=user,
    )

    try:
        _create_share_journal(branch, amount, user, 'transfer')
    except ValueError as e:
        logger.warning('Share transfer journal entry failed: %s', e)


@transaction.atomic
def surrender_shares(member, count, user):
    holdings = ShareHolding.objects.filter(member=member, status='active')
    total_held = sum(h.share_count for h in holdings)
    if total_held < count:
        raise ValueError(f'Member only holds {total_held} shares.')

    remaining_shares = total_held - count
    if remaining_shares == 0:
        from apps.loans.models import LoanAccount, LoanGuarantor

        if LoanGuarantor.objects.filter(
            guarantor_member=member,
            loan__status__in=['disbursed', 'npa'],
            loan__outstanding_principal__gt=Decimal('0'),
        ).exists():
            raise ValueError(
                'Cannot surrender all shares: member is an active guarantor on one or more loans.'
            )

        if LoanAccount.objects.filter(
            member=member,
            status__in=['disbursed', 'npa'],
            outstanding_principal__gt=Decimal('0'),
        ).exists():
            raise ValueError(
                'Cannot surrender all shares: member has outstanding loan(s). '
                'Clear loan balance before surrendering all shares.'
            )

    config = _get_config()
    amount = Decimal(count) * config.face_value_per_share

    if remaining_shares > 0:
        if config and config.min_shares_required and remaining_shares < config.min_shares_required:
            raise ValueError(
                f'Surrender would leave {member.name} with {remaining_shares} shares, '
                f'below minimum required ({config.min_shares_required}).'
            )

    today = timezone.now().date()

    remaining = count
    for h in holdings:
        if remaining <= 0:
            break
        if h.share_count <= remaining:
            h.status = 'surrendered'
            h.save()
            remaining -= h.share_count
        else:
            h.share_count -= remaining
            h.total_amount = Decimal(h.share_count) * config.face_value_per_share
            h.save()
            remaining = 0

    ShareTransaction.objects.create(
        member=member,
        branch=member.branch,
        txn_type='surrender',
        shares_count=-count,
        amount=amount,
        txn_date=today,
        narration=f'Surrender of {count} shares',
        created_by=user,
    )
    try:
        _create_share_journal(member.branch, amount, user, 'surrender')
    except ValueError as e:
        logger.warning('Share journal entry failed: %s', e)
    return amount


def calculate_dividend(rate, financial_year=None):
    results = []
    holdings = ShareHolding.objects.filter(status='active').select_related('member')
    for holding in holdings:
        dividend = holding.total_amount * Decimal(str(rate)) / Decimal('100')
        results.append(
            {
                'member': holding.member,
                'shares': holding.share_count,
                'amount': holding.total_amount,
                'dividend': dividend,
            }
        )
    return results


def _generate_certificate_no():
    last = ShareHolding.objects.order_by('-id').first()
    num = (last.id + 1) if last else 1
    return f'SC-{num:06d}'


def _create_share_journal(branch, amount, user, txn_type, ref_id=None):
    from apps.accounting.services import create_journal_entry
    from apps.savings.services import _get_cash_code

    if txn_type == 'purchase':
        lines = [
            {'account_code': _get_cash_code(branch), 'debit': amount, 'credit': Decimal('0')},
            {'account_code': '2501', 'debit': Decimal('0'), 'credit': amount},
        ]
        narration = 'Share capital received'
        voucher_type = 'receipt'
    else:
        lines = [
            {'account_code': '2501', 'debit': amount, 'credit': Decimal('0')},
            {'account_code': _get_cash_code(branch), 'debit': Decimal('0'), 'credit': amount},
        ]
        narration = 'Share capital refunded'
        voucher_type = 'payment'

    create_journal_entry(
        entry_date=timezone.now().date(),
        voucher_type=voucher_type,
        branch=branch,
        narration=narration,
        lines=lines,
        user=user,
        reference_type=f'share_{txn_type}',
        reference_id=ref_id,
    )
