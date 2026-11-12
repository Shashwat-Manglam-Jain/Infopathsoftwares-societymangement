from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect


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
