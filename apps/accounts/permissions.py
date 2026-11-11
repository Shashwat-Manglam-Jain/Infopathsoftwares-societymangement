from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.role not in roles and request.user.role != 'admin':
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def admin_required(view_func):
    """Only admin (super admin)."""

    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_admin:
            raise PermissionDenied('Admin access required.')
        return view_func(request, *args, **kwargs)

    return wrapper


def manager_required(view_func):
    """Admin or branch manager."""

    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_manager:
            raise PermissionDenied('Manager access required.')
        return view_func(request, *args, **kwargs)

    return wrapper


def staff_required(view_func):
    """Operational staff: admin, branch_manager, cashier, accountant. NOT auditor/member."""

    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff_role:
            raise PermissionDenied('Staff access required.')
        return view_func(request, *args, **kwargs)

    return wrapper


def cashier_required(view_func):
    """Counter transactions: admin, branch_manager, cashier."""

    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_cashier:
            raise PermissionDenied('Cashier access required.')
        return view_func(request, *args, **kwargs)

    return wrapper


def accountant_required(view_func):
    """Cashbook, vouchers, day-end: admin, branch_manager, accountant."""

    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_accountant:
            raise PermissionDenied('Accountant access required.')
        return view_func(request, *args, **kwargs)

    return wrapper


def auditor_or_above(view_func):
    """Everyone except member — read access to all data."""

    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.is_member_only:
            raise PermissionDenied('Access denied.')
        return view_func(request, *args, **kwargs)

    return wrapper


class AdminRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_admin:
            raise PermissionDenied('Admin access required.')
        return super().dispatch(request, *args, **kwargs)


class ManagerRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_manager:
            raise PermissionDenied('Manager access required.')
        return super().dispatch(request, *args, **kwargs)


class StaffRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_staff_role:
            raise PermissionDenied('Staff access required.')
        return super().dispatch(request, *args, **kwargs)


class CashierRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_cashier:
            raise PermissionDenied('Cashier access required.')
        return super().dispatch(request, *args, **kwargs)


class AccountantRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_accountant:
            raise PermissionDenied('Accountant access required.')
        return super().dispatch(request, *args, **kwargs)


class AuditorOrAboveMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.is_member_only:
            raise PermissionDenied('Access denied.')
        return super().dispatch(request, *args, **kwargs)


def day_open_required(view_func):
    """Block transaction creation (POST) when the working day is closed."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.method == 'POST':
            from apps.dayend.models import WorkingDay

            branch = getattr(request, 'current_branch', None)
            if branch:
                wd = WorkingDay.objects.filter(branch=branch).order_by('-current_date').first()
                if not wd or not wd.is_day_open:
                    messages.error(
                        request,
                        'Day is closed. Open the working day before making transactions.',
                    )
                    return redirect(request.path)
        return view_func(request, *args, **kwargs)

    return wrapper


def branch_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not hasattr(request, 'current_branch') or request.current_branch is None:
            raise PermissionDenied('No branch selected.')
        return view_func(request, *args, **kwargs)

    return wrapper


def head_office_only(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.can_access_all_branches and not request.user.is_admin:
            raise PermissionDenied('Head office access required.')
        return view_func(request, *args, **kwargs)

    return wrapper
