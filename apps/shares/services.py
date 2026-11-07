from decimal import Decimal

from django.db import models, transaction
from django.utils import timezone

from .models import ShareConfig, ShareHolding, ShareTransaction


def _get_config():
    return ShareConfig.objects.filter(is_active=True).first()


@transaction.atomic
def purchase_shares(member, branch, count, user):
    config = _get_config()
    if not config:
        raise ValueError('Share configuration not found.')
    if count < config.min_shares_required:
        raise ValueError(f'Minimum {config.min_shares_required} shares required.')

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

    _create_share_journal(branch, total_amount, user, 'purchase', holding.pk)
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

    config = _get_config()
    amount = Decimal(count) * config.face_value_per_share
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
        txn_type='purchase',
        shares_count=count,
        amount=amount,
        txn_date=today,
        narration=f'Transfer received from {from_member.name}',
        created_by=user,
    )


@transaction.atomic
def surrender_shares(member, count, user):
    holdings = ShareHolding.objects.filter(member=member, status='active')
    total_held = sum(h.share_count for h in holdings)
    if total_held < count:
        raise ValueError(f'Member only holds {total_held} shares.')

    config = _get_config()
    amount = Decimal(count) * config.face_value_per_share
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
    _create_share_journal(member.branch, amount, user, 'surrender')
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
