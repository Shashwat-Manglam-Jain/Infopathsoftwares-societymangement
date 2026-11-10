def get_gl_code(related_table_name, fallback_code):
    """Look up GL code from ChartOfAccounts by related_table_name, falling back gracefully."""
    from apps.accounting.models import ChartOfAccounts

    head = ChartOfAccounts.objects.filter(
        related_table_name=related_table_name,
        allow_transactions=True,
        is_active=True,
    ).first()
    return head.code if head else fallback_code


def get_interest_head_code(gl_head, fallback_code):
    """Get the interest expense/income head linked to a GL head via interest_code FK."""
    if gl_head and gl_head.interest_code_id:
        return gl_head.interest_code.code
    return fallback_code


def get_account_gl_code(account, related_table_name, fallback_code):
    """Get GL code from the account's gl_head FK, or fall back to related_table_name lookup."""
    if hasattr(account, 'gl_head') and account.gl_head_id:
        return account.gl_head.code
    return get_gl_code(related_table_name, fallback_code)
