from functools import wraps

from django.core.exceptions import PermissionDenied


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise PermissionDenied
            if request.user.role not in roles and request.user.role != 'super_admin':
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


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
        if not request.user.can_access_all_branches and not request.user.role == 'super_admin':
            raise PermissionDenied('Head office access required.')
        return view_func(request, *args, **kwargs)

    return wrapper
