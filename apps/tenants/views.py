from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.views import View
from django_tenants.utils import tenant_context

from apps.tenants.forms import SocietySignupForm
from apps.tenants.models import Domain, Society, SubscriptionPlan


def landing_page(request):
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price_monthly')
    return render(request, 'landing.html', {'plans': plans})


class SocietySignupView(View):
    def get(self, request):
        form = SocietySignupForm()
        plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price_monthly')
        return render(request, 'signup.html', {'form': form, 'plans': plans})

    def post(self, request):
        form = SocietySignupForm(request.POST)
        if not form.is_valid():
            plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price_monthly')
            return render(request, 'signup.html', {'form': form, 'plans': plans})

        society_name = form.cleaned_data['society_name']
        schema_name = ''.join(c for c in society_name.lower().replace(' ', '_') if c.isalnum() or c == '_')[:30]

        base_schema = schema_name
        counter = 1
        while Society.objects.filter(schema_name=schema_name).exists():
            schema_name = f'{base_schema}_{counter}'
            counter += 1

        with transaction.atomic():
            society = Society.objects.create(
                schema_name=schema_name,
                name=society_name,
                registration_no=form.cleaned_data.get('registration_no', ''),
                address=form.cleaned_data.get('address', ''),
                city=form.cleaned_data.get('city', ''),
                state=form.cleaned_data.get('state', ''),
                pincode=form.cleaned_data.get('pincode', ''),
                phone=form.cleaned_data['phone'],
                email=form.cleaned_data['email'],
                society_type=form.cleaned_data.get('society_type', 'credit_cooperative'),
            )

            subdomain = schema_name.replace('_', '-')
            domain_name = f'{subdomain}.localhost'
            Domain.objects.create(
                domain=domain_name,
                tenant=society,
                is_primary=True,
            )

        with tenant_context(society):
            self._setup_tenant(form, society)

        return render(
            request,
            'signup_success.html',
            {
                'society_name': society_name,
                'domain': domain_name,
                'username': form.cleaned_data['admin_username'],
                'port': ':8000' if 'localhost' in domain_name else '',
            },
        )

    def _setup_tenant(self, form, society):
        from apps.branches.models import Branch

        ho = Branch.objects.create(
            branch_code='HO',
            branch_name='Head Office',
            address=form.cleaned_data.get('address', ''),
            city=form.cleaned_data.get('city', ''),
            state=form.cleaned_data.get('state', ''),
            pincode=form.cleaned_data.get('pincode', ''),
            phone=form.cleaned_data['phone'],
            is_head_office=True,
            opening_date=date.today(),
            status='active',
        )

        from apps.accounts.models import CustomUser

        admin_name = form.cleaned_data.get('admin_name', '')
        first_name = admin_name.split()[0] if admin_name else ''
        last_name = ' '.join(admin_name.split()[1:]) if admin_name and len(admin_name.split()) > 1 else ''
        CustomUser.objects.create_superuser(
            username=form.cleaned_data['admin_username'],
            email=form.cleaned_data['email'],
            password=form.cleaned_data['password'],
            phone=form.cleaned_data['phone'],
            first_name=first_name,
            last_name=last_name,
            role='super_admin',
            branch=ho,
            can_access_all_branches=True,
        )

        from apps.dayend.models import FinancialYear

        fy_start = date(date.today().year, 4, 1)
        if date.today().month < 4:
            fy_start = date(date.today().year - 1, 4, 1)
        fy_end = date(fy_start.year + 1, 3, 31)
        FinancialYear.objects.create(
            fy_code=f'{fy_start.year}-{str(fy_end.year)[-2:]}',
            start_date=fy_start,
            end_date=fy_end,
            is_current=True,
        )

        from apps.accounting.initial_coa import setup_chart_of_accounts

        setup_chart_of_accounts(branches=[ho])

        from apps.loans.models import LoanProduct

        for name, rate, max_amt, tenure, int_type in [
            ('Personal Loan', Decimal('12.00'), Decimal('500000'), 60, 'reducing_monthly'),
            ('Gold Loan', Decimal('10.00'), Decimal('1000000'), 36, 'reducing_monthly'),
            ('Emergency Loan', Decimal('14.00'), Decimal('100000'), 24, 'flat'),
        ]:
            LoanProduct.objects.create(
                name=name,
                interest_rate=rate,
                max_amount=max_amt,
                max_tenure_months=tenure,
                interest_type=int_type,
                requires_guarantor=True,
                max_guarantors=2,
                processing_fee_percent=Decimal('1.00'),
                penal_interest_rate=Decimal('18.00'),
                npa_days_threshold=90,
                is_active=True,
            )

        from apps.deposits.models import FDProduct

        FDProduct.objects.create(
            name='Regular Fixed Deposit',
            min_amount=Decimal('10000'),
            max_amount=Decimal('5000000'),
            min_tenure_days=90,
            max_tenure_days=3650,
            interest_rates=[
                {'min_days': 90, 'max_days': 180, 'rate': 6.0, 'senior_rate': 6.5},
                {'min_days': 181, 'max_days': 365, 'rate': 7.0, 'senior_rate': 7.5},
                {'min_days': 366, 'max_days': 3650, 'rate': 7.5, 'senior_rate': 8.0},
            ],
            compounding='quarterly',
            premature_penalty_percent=Decimal('1.00'),
            is_active=True,
        )

        from apps.shares.models import ShareConfig

        ShareConfig.objects.create(
            face_value_per_share=Decimal('100.00'),
            max_shares_per_member=500,
            min_shares_required=10,
            is_active=True,
        )

        plan = SubscriptionPlan.objects.filter(is_active=True).order_by('price_monthly').first()
        if plan:
            from apps.tenants.models import Subscription

            Subscription.objects.create(
                society=society,
                plan=plan,
                start_date=date.today(),
                is_trial=True,
                status='trial',
            )


def subscription_expired_view(request):
    tenant = getattr(request, 'tenant', None)
    sub = None
    if tenant:
        try:
            sub = tenant.subscription
        except Exception:
            pass
    return render(request, 'tenants/subscription_expired.html', {
        'subscription': sub,
        'tenant': tenant,
    })


@login_required
def subscription_recharge_view(request):
    tenant = getattr(request, 'tenant', None)
    sub = None
    if tenant:
        try:
            sub = tenant.subscription
        except Exception:
            pass
    if request.method == 'POST' and sub:
        sub.end_date = date.today() + timedelta(days=30)
        sub.status = 'active'
        sub.save()
        messages.success(request, 'Subscription renewed for 30 days.')
        return redirect('dashboard:index')
    return render(request, 'tenants/subscription_recharge.html', {
        'subscription': sub,
        'tenant': tenant,
    })
