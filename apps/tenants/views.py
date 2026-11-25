from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.shortcuts import redirect, render
from django.views import View
from django_tenants.utils import tenant_context

from apps.accounts.permissions import admin_required, manager_required
from apps.tenants.forms import SocietySignupForm
from apps.tenants.models import Domain, Society, SubscriptionPlan


def landing_page(request):
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price_monthly')
    return render(request, 'landing.html', {'plans': plans})


def public_login(request):
    request_host = request.get_host().split(':')[0]
    is_localhost = request_host in ('localhost', '127.0.0.1') or request_host.endswith('.localhost')
    parent_domain = 'localhost' if is_localhost else request_host

    from apps.tenants.models import Society

    tenants_with_domains = []
    for tenant in Society.objects.filter(is_active=True).exclude(schema_name='public'):
        tenant_domains = tenant.domains.all()
        best_domain = None
        for d in tenant_domains:
            if is_localhost and d.domain.endswith('.localhost'):
                best_domain = d
                break
            if not is_localhost and d.domain.endswith(f'.{parent_domain}'):
                best_domain = d
                break
        if not best_domain and tenant_domains.exists():
            best_domain = tenant_domains.first()
        if best_domain:
            tenants_with_domains.append(best_domain)

    error = ''
    if request.method == 'POST':
        domain_id = request.POST.get('domain', '')
        domain_obj = Domain.objects.filter(pk=domain_id).first()
        if domain_obj:
            scheme = 'https' if request.is_secure() or request.META.get('HTTP_X_FORWARDED_PROTO') == 'https' else 'http'
            is_proxied = request.META.get('HTTP_X_FORWARDED_PROTO') or request.META.get('HTTP_X_FORWARDED_FOR')
            host = domain_obj.domain
            if not is_proxied:
                port = request.META.get('SERVER_PORT', '80')
                if port not in ('80', '443'):
                    host = f'{host}:{port}'
            return redirect(f'{scheme}://{host}/accounts/login/')
        error = 'Please select a valid society.'
    return render(
        request,
        'tenants/public_login.html',
        {
            'domains': tenants_with_domains,
            'error': error,
        },
    )


class SocietySignupView(View):
    def get(self, request):
        form = SocietySignupForm()
        plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price_monthly')
        return render(request, 'signup.html', {'form': form, 'plans': plans})

    def _get_parent_domain(self, request):
        host = request.get_host().split(':')[0]
        if host in ('localhost', '127.0.0.1'):
            return 'localhost'
        return host

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

        parent_domain = self._get_parent_domain(request)
        subdomain = schema_name.replace('_', '-')
        domain_name = f'{subdomain}.{parent_domain}'

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

            Domain.objects.create(
                domain=domain_name,
                tenant=society,
                is_primary=True,
            )

        import logging

        logger = logging.getLogger(__name__)
        with tenant_context(society):
            try:
                self._setup_tenant(form, society)
            except Exception:
                logger.exception('Tenant setup failed for %s — COA or seed data may be missing', schema_name)

        scheme = 'https' if request.is_secure() else 'http'
        is_proxied = request.META.get('HTTP_X_FORWARDED_PROTO') or request.META.get('HTTP_X_FORWARDED_FOR')
        port_suffix = ''
        if not is_proxied:
            port = request.META.get('SERVER_PORT', '')
            if port and port not in ('80', '443'):
                port_suffix = f':{port}'

        return render(
            request,
            'signup_success.html',
            {
                'society_name': society_name,
                'domain': domain_name,
                'username': form.cleaned_data['admin_username'],
                'scheme': scheme,
                'port': port_suffix,
            },
        )

    def _setup_tenant(self, form, society):
        import logging

        logger = logging.getLogger(__name__)

        from apps.branches.models import Branch

        ho = Branch.objects.filter(branch_code='HO').first()
        if not ho:
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

        if not CustomUser.objects.filter(username=form.cleaned_data['admin_username']).exists():
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
                role='admin',
                branch=ho,
                can_access_all_branches=True,
            )

        from apps.dayend.models import FinancialYear

        fy_start = date(date.today().year, 4, 1)
        if date.today().month < 4:
            fy_start = date(date.today().year - 1, 4, 1)
        fy_end = date(fy_start.year + 1, 3, 31)
        FinancialYear.objects.get_or_create(
            fy_code=f'{fy_start.year}-{str(fy_end.year)[-2:]}',
            defaults={
                'start_date': fy_start,
                'end_date': fy_end,
                'is_current': True,
            },
        )

        from apps.accounting.initial_coa import setup_chart_of_accounts

        try:
            setup_chart_of_accounts(branches=[ho])
        except Exception:
            logger.exception('Failed to create Chart of Accounts for %s', society.schema_name)

        from apps.loans.models import LoanProduct

        if not LoanProduct.objects.exists():
            default_products = [
                {
                    'name': 'Personal Loan',
                    'interest_rate': Decimal('12.00'),
                    'max_amount': Decimal('500000'),
                    'max_tenure_months': 60,
                    'interest_type': 'reducing_monthly',
                    'loan_category': 'regular',
                },
                {
                    'name': 'Emergency Loan',
                    'interest_rate': Decimal('14.00'),
                    'max_amount': Decimal('100000'),
                    'max_tenure_months': 24,
                    'interest_type': 'flat',
                    'loan_category': 'emergency',
                },
                {
                    'name': 'Gold Loan',
                    'interest_rate': Decimal('10.00'),
                    'max_amount': Decimal('1000000'),
                    'max_tenure_months': 36,
                    'interest_type': 'reducing_monthly',
                    'loan_category': 'mortgage',
                    'mortgage_type': 'gold',
                    'allow_multiple': True,
                    'requires_collateral': True,
                },
                {
                    'name': 'Loan Against FD',
                    'interest_rate': Decimal('10.00'),
                    'max_amount': Decimal('500000'),
                    'max_tenure_months': 60,
                    'interest_type': 'reducing_monthly',
                    'loan_category': 'mortgage',
                    'mortgage_type': 'fixed_deposit',
                    'allow_multiple': True,
                    'max_loan_to_deposit_ratio': Decimal('90.00'),
                },
                {
                    'name': 'Loan Against Pigmmy',
                    'interest_rate': Decimal('10.00'),
                    'max_amount': Decimal('500000'),
                    'max_tenure_months': 60,
                    'interest_type': 'reducing_monthly',
                    'loan_category': 'mortgage',
                    'mortgage_type': 'pigmmy',
                    'allow_multiple': True,
                    'max_loan_to_deposit_ratio': Decimal('90.00'),
                },
                {
                    'name': 'Property Mortgage Loan',
                    'interest_rate': Decimal('11.00'),
                    'max_amount': Decimal('2000000'),
                    'max_tenure_months': 120,
                    'interest_type': 'reducing_monthly',
                    'loan_category': 'mortgage',
                    'mortgage_type': 'property',
                    'allow_multiple': True,
                    'requires_collateral': True,
                },
            ]
            for prod in default_products:
                LoanProduct.objects.create(
                    requires_guarantor=True,
                    max_guarantors=2,
                    processing_fee_percent=Decimal('1.00'),
                    penal_interest_rate=Decimal('18.00'),
                    npa_days_threshold=90,
                    is_active=True,
                    **prod,
                )

        from apps.deposits.models import FDProduct

        if not FDProduct.objects.exists():
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

        if not ShareConfig.objects.exists():
            ShareConfig.objects.create(
                face_value_per_share=Decimal('100.00'),
                max_shares_per_member=500,
                min_shares_required=10,
                is_active=True,
            )

        plan = SubscriptionPlan.objects.filter(is_active=True).order_by('price_monthly').first()
        if plan:
            from apps.tenants.models import Subscription

            Subscription.objects.get_or_create(
                society=society,
                defaults={
                    'plan': plan,
                    'start_date': date.today(),
                    'is_trial': True,
                    'status': 'trial',
                },
            )


def subscription_expired_view(request):
    tenant = getattr(request, 'tenant', None)
    sub = None
    if tenant:
        try:
            sub = tenant.subscription
        except ObjectDoesNotExist:
            pass
    return render(
        request,
        'tenants/subscription_expired.html',
        {
            'subscription': sub,
            'tenant': tenant,
        },
    )


@admin_required
def subscription_recharge_view(request):
    tenant = getattr(request, 'tenant', None)
    sub = None
    if tenant:
        try:
            sub = tenant.subscription
        except ObjectDoesNotExist:
            pass

    plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price_monthly')

    if request.method == 'POST' and sub:
        plan_id = request.POST.get('plan_id')
        if plan_id:
            new_plan = SubscriptionPlan.objects.filter(pk=plan_id, is_active=True).first()
            if new_plan:
                sub.plan = new_plan
        sub.end_date = date.today() + timedelta(days=30)
        sub.status = 'active'
        sub.save()
        messages.success(request, 'Subscription renewed for 30 days.')
        return redirect('dashboard:index')

    return render(
        request,
        'tenants/subscription_recharge.html',
        {
            'subscription': sub,
            'tenant': tenant,
            'plans': plans,
        },
    )


@manager_required
def society_detail(request):
    society = request.tenant
    return render(request, 'tenants/detail.html', {'society': society})


@admin_required
def society_edit(request):
    from apps.tenants.forms import SocietyEditForm

    society = request.tenant
    if request.method == 'POST':
        form = SocietyEditForm(request.POST, request.FILES, instance=society)
        if form.is_valid():
            form.save()
            messages.success(request, 'Society details updated.')
            return redirect('society_detail')
    else:
        form = SocietyEditForm(instance=society)
    return render(request, 'tenants/edit.html', {'form': form, 'society': society})
