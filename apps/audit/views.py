from django.shortcuts import render

from apps.accounts.permissions import auditor_or_above

from .models import AuditTrail


@auditor_or_above
def audit_log(request):
    qs = AuditTrail.objects.select_related('user', 'branch')

    action = request.GET.get('action')
    if action:
        qs = qs.filter(action=action)

    table = request.GET.get('table')
    if table:
        qs = qs.filter(table_name=table)

    logs = qs[:200]
    table_choices = AuditTrail.objects.values_list('table_name', flat=True).distinct().order_by('table_name')

    return render(
        request,
        'audit/log.html',
        {
            'logs': logs,
            'table_choices': table_choices,
        },
    )
