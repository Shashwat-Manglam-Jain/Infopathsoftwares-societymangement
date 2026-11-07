from apps.audit.models import AuditTrail


def log_action(user, branch, action, table_name, record_id, old_values=None, new_values=None, ip_address=None):
    return AuditTrail.objects.create(
        user=user,
        branch=branch,
        action=action,
        table_name=table_name,
        record_id=record_id,
        old_values=old_values,
        new_values=new_values,
        ip_address=ip_address,
    )
