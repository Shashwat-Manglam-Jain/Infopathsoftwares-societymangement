from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.core.account_utils import amount_to_words as _amount_to_words

from . import services
from .forms import SharePurchaseForm, ShareSurrenderForm, ShareTransferForm
from .models import ShareHolding, ShareTransaction


@login_required
def share_list(request):
    holdings = ShareHolding.objects.filter(status='active').select_related('member', 'branch')
    if not request.user.can_access_all_branches:
        holdings = holdings.filter(branch=request.current_branch)
    return render(request, 'shares/list.html', {'holdings': holdings})


@login_required
def share_purchase(request):
    if request.method == 'POST':
        form = SharePurchaseForm(request.POST)
        if form.is_valid():
            try:
                holding = services.purchase_shares(
                    member=form.cleaned_data['member'],
                    branch=request.current_branch,
                    count=form.cleaned_data['share_count'],
                    user=request.user,
                )
                messages.success(request, f'{holding.share_count} shares purchased for {form.cleaned_data["member"].name}.')
                return redirect('shares:list')
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = SharePurchaseForm()
    return render(request, 'shares/purchase.html', {'form': form})


@login_required
def share_transfer(request):
    if request.method == 'POST':
        form = ShareTransferForm(request.POST)
        if form.is_valid():
            try:
                services.transfer_shares(
                    from_member=form.cleaned_data['from_member'],
                    to_member=form.cleaned_data['to_member'],
                    count=form.cleaned_data['share_count'],
                    user=request.user,
                )
                messages.success(request, f'{form.cleaned_data["share_count"]} shares transferred.')
                return redirect('shares:list')
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = ShareTransferForm()
    return render(request, 'shares/transfer.html', {'form': form})


@login_required
def share_surrender(request):
    if request.method == 'POST':
        form = ShareSurrenderForm(request.POST)
        if form.is_valid():
            try:
                services.surrender_shares(
                    member=form.cleaned_data['member'],
                    count=form.cleaned_data['share_count'],
                    user=request.user,
                )
                messages.success(request, f'{form.cleaned_data["share_count"]} shares surrendered.')
                return redirect('shares:list')
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = ShareSurrenderForm()
    return render(request, 'shares/surrender.html', {'form': form})


@login_required
def share_detail(request, pk):
    holding = get_object_or_404(
        ShareHolding.objects.select_related('member', 'branch'),
        pk=pk,
    )
    transactions = ShareTransaction.objects.filter(member=holding.member).order_by('-txn_date')[:20]
    return render(request, 'shares/detail.html', {
        'holding': holding,
        'transactions': transactions,
    })


class ShareReceiptView(LoginRequiredMixin, View):
    def get(self, request, txn_id):
        txn = get_object_or_404(
            ShareTransaction.objects.select_related(
                'member',
                'branch',
                'created_by',
                'transfer_to_member',
            ),
            id=txn_id,
        )
        holding = ShareHolding.objects.filter(member=txn.member, status='active').first()
        return render(
            request,
            'receipts/share_receipt.html',
            {
                'txn': txn,
                'amount_words': _amount_to_words(txn.amount),
                'face_value': txn.amount / txn.shares_count if txn.shares_count else txn.amount,
                'certificate_no': holding.certificate_no if holding else '',
            },
        )
