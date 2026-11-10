from .models import Branch


class BranchMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.current_branch = None
        request.available_branches = []

        if request.user.is_authenticated:
            branches = Branch.objects.filter(status='active')
            request.available_branches = list(branches)

            branch_id = request.session.get('current_branch_id')
            if branch_id and branch_id != 'all':
                try:
                    request.current_branch = branches.get(id=int(branch_id))
                except (Branch.DoesNotExist, ValueError, TypeError):
                    pass

            if request.current_branch is None and branches.exists():
                if request.user.can_access_all_branches:
                    pass
                elif request.user.branch_id:
                    request.current_branch = request.user.branch
                    request.session['current_branch_id'] = request.current_branch.id
                else:
                    request.current_branch = branches.first()
                    request.session['current_branch_id'] = request.current_branch.id

        response = self.get_response(request)
        return response
