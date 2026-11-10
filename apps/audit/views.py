from django.shortcuts import render

from apps.accounts.permissions import auditor_or_above

from .models import AuditTrail


@auditor_or_above
def audit_log(request):
    logs = AuditTrail.objects.select_related('user', 'branch')[:100]
    return render(request, 'audit/log.html', {'logs': logs})
