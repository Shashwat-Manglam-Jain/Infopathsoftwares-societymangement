import logging

from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect

logger = logging.getLogger(__name__)


class TenantSetupMiddleware:
    """Auto-heal missing tenant setup data (COA, products, etc.) once per session."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)

        tenant = getattr(request, 'tenant', None)
        if not tenant or tenant.schema_name == 'public':
            return self.get_response(request)

        if request.session.get('_tenant_setup_ok'):
            return self.get_response(request)

        self._ensure_tenant_setup(tenant)
        request.session['_tenant_setup_ok'] = True

        return self.get_response(request)

    def _ensure_tenant_setup(self, tenant):
        from apps.accounting.models import ChartOfAccounts
        from apps.branches.models import Branch

        if ChartOfAccounts.objects.exists():
            return

        branches = list(Branch.objects.all())
        if not branches:
            logger.warning('Tenant %s has no branches — cannot auto-generate COA', tenant.schema_name)
            return

        from apps.accounting.initial_coa import setup_chart_of_accounts

        try:
            setup_chart_of_accounts(branches=branches)
            count = ChartOfAccounts.objects.count()
            logger.info('Auto-generated %d GL heads for tenant %s', count, tenant.schema_name)
        except Exception:
            logger.exception('Failed to auto-generate COA for tenant %s', tenant.schema_name)


class SubscriptionMiddleware:
    EXEMPT_URLS = ['/accounts/login/', '/accounts/logout/', '/subscription/']

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)

        if any(request.path.startswith(url) for url in self.EXEMPT_URLS):
            return self.get_response(request)

        tenant = getattr(request, 'tenant', None)
        if tenant:
            try:
                sub = tenant.subscription
                if sub.is_expired:
                    request.subscription_expired = True
                    if request.path != '/subscription/expired/':
                        return redirect('/subscription/expired/')
                else:
                    request.subscription_expired = False
                    request.subscription = sub
            except ObjectDoesNotExist:
                request.subscription_expired = False
                request.subscription = None

        return self.get_response(request)
