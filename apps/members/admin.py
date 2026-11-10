from django.contrib import admin

from .models import AccountNominee, Member, MemberDocument, MemberNominee


class MemberNomineeInline(admin.TabularInline):
    model = MemberNominee
    extra = 1


class MemberDocumentInline(admin.TabularInline):
    model = MemberDocument
    extra = 0


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = [
        'member_no',
        'name',
        'phone',
        'branch',
        'status',
        'category',
    ]
    list_filter = ['status', 'category', 'branch', 'kyc_verified']
    search_fields = ['member_no', 'name', 'phone', 'aadhar_no']
    inlines = [MemberNomineeInline, MemberDocumentInline]
    readonly_fields = ['created_at', 'updated_at']


@admin.register(AccountNominee)
class AccountNomineeAdmin(admin.ModelAdmin):
    list_display = ['account_number', 'name', 'relation', 'nj_type']
    list_filter = ['nj_type']
    search_fields = ['account_number', 'name']
