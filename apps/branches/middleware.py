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
            if branch_id:
                try:
                    request.current_branch = branches.get(id=branch_id)
                except Branch.DoesNotExist:
                    pass

            if request.current_branch is None and branches.exists():
                if request.user.branch_id:
                    request.current_branch = request.user.branch
                else:
                    request.current_branch = branches.first()
                request.session['current_branch_id'] = request.current_branch.id

        response = self.get_response(request)
        return response
