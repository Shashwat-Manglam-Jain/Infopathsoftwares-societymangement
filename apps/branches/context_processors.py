def branch_context(request):
    return {
        'current_branch': getattr(request, 'current_branch', None),
        'available_branches': getattr(request, 'available_branches', []),
    }
