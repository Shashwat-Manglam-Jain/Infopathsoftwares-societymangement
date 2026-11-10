from datetime import date


def get_transaction_date(branch):
    """Get the current transaction date for a branch from WorkingDay.
    Falls back to date.today() if no working day is open."""
    from apps.dayend.models import WorkingDay

    try:
        wd = WorkingDay.objects.get(branch=branch)
        if wd.is_day_open:
            return wd.current_date
    except WorkingDay.DoesNotExist:
        pass
    return date.today()
