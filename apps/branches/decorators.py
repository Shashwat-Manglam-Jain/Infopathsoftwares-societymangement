from functools import wraps

from django.http import HttpResponseForbidden


def branch_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not getattr(request, 'current_branch', None):
            return HttpResponseForbidden('No branch selected.')
        return view_func(request, *args, **kwargs)

    return wrapper


def head_office_only(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        branch = getattr(request, 'current_branch', None)
        if not branch or not branch.is_head_office:
            return HttpResponseForbidden('This action is restricted to Head Office.')
        return view_func(request, *args, **kwargs)

    return wrapper
