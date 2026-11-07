from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import AuditTrail


@login_required
def audit_log(request):
    logs = AuditTrail.objects.select_related('user')[:100]
    return render(request, 'audit/log.html', {'logs': logs})
