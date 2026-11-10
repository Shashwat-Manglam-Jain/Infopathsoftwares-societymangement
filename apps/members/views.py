import csv
import io
from datetime import date, datetime

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import models
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from openpyxl import Workbook, load_workbook

from apps.accounts.permissions import (
    AuditorOrAboveMixin,
    ManagerRequiredMixin,
    auditor_or_above,
    staff_required,
)
from apps.branches.models import Branch

from .models import Member


@auditor_or_above
def member_list(request):
    members = Member.objects.select_related('branch').all()
    if not request.user.can_access_all_branches and request.current_branch:
        members = members.filter(branch=request.current_branch)

    q = request.GET.get('q', '').strip()
    if q:
        members = members.filter(
            models.Q(name__icontains=q) | models.Q(member_no__icontains=q) | models.Q(phone__icontains=q)
        )

    status = request.GET.get('status', '')
    if status:
        members = members.filter(status=status)

    category = request.GET.get('category', '')
    if category:
        members = members.filter(category=category)

    paginator = Paginator(members, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'members/list.html', {
        'members': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'paginator': paginator,
    })


GENDER_MAP = {
    'M': 'male',
    'F': 'female',
    'O': 'other',
    'MALE': 'male',
    'FEMALE': 'female',
    'OTHER': 'other',
}


class MemberImportView(ManagerRequiredMixin, View):
    def get(self, request):
        branches = Branch.objects.filter(status='active')
        return render(request, 'members/member_import.html', {'branches': branches})

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            messages.error(request, 'Please select a file to import.')
            return redirect('members:import')

        branch_id = request.POST.get('branch')
        try:
            branch = Branch.objects.get(id=branch_id)
        except Branch.DoesNotExist:
            messages.error(request, 'Please select a valid branch.')
            return redirect('members:import')

        filename = file.name.lower()
        results = {'created': 0, 'skipped': 0, 'errors': []}

        try:
            if filename.endswith('.csv'):
                rows = self._parse_csv(file)
            elif filename.endswith(('.xlsx', '.xls')):
                rows = self._parse_excel(file)
            else:
                messages.error(request, 'Please upload a .csv or .xlsx file.')
                return redirect('members:import')

            for i, row in enumerate(rows, start=2):
                try:
                    name = str(row.get('name') or '').strip()
                    if not name:
                        continue

                    member_no = str(row.get('member_no') or '').strip()
                    if not member_no:
                        last = Member.objects.order_by('-id').first()
                        if last and last.member_no:
                            try:
                                num = int(''.join(filter(str.isdigit, last.member_no))) + 1
                            except ValueError:
                                num = Member.objects.count() + 1
                        else:
                            num = 1
                        member_no = f'M{num:04d}'

                    if Member.objects.filter(member_no=member_no).exists():
                        results['skipped'] += 1
                        continue

                    dob = None
                    dob_raw = str(row.get('dob') or '').strip()
                    if dob_raw:
                        for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%m/%d/%Y'):
                            try:
                                dob = datetime.strptime(dob_raw, fmt).date()
                                break
                            except ValueError:
                                continue

                    gender_raw = str(row.get('gender') or '').strip().upper()
                    gender = GENDER_MAP.get(gender_raw, 'male')

                    phone = str(row.get('phone') or '').strip()
                    if phone.endswith('.0'):
                        phone = phone[:-2]

                    pincode = str(row.get('pincode') or '').strip()
                    if pincode.endswith('.0'):
                        pincode = pincode[:-2]

                    aadhar = str(row.get('aadhar_no') or '').strip()
                    if aadhar.endswith('.0'):
                        aadhar = aadhar[:-2]

                    Member.objects.create(
                        member_no=member_no,
                        branch=branch,
                        name=name,
                        father_name=str(row.get('father_name') or '').strip(),
                        dob=dob,
                        gender=gender,
                        phone=phone,
                        email=str(row.get('email') or '').strip(),
                        address=str(row.get('address') or '').strip(),
                        city=str(row.get('city') or '').strip(),
                        state=str(row.get('state') or '').strip(),
                        pincode=pincode,
                        aadhar_no=aadhar,
                        pan_no=str(row.get('pan_no') or '').strip(),
                        occupation=str(row.get('occupation') or '').strip(),
                        join_date=date.today(),
                        status='active',
                        category=str(row.get('category') or 'A').strip().upper()[:1] or 'A',
                        created_by=request.user,
                    )
                    results['created'] += 1
                except Exception as e:
                    results['errors'].append(f'Row {i}: {e}')

            if results['created'] > 0:
                messages.success(request, f'Successfully imported {results["created"]} members.')
            if results['skipped'] > 0:
                messages.warning(request, f'Skipped {results["skipped"]} duplicate members.')
            if results['errors']:
                messages.error(request, f'{len(results["errors"])} errors. First: {results["errors"][0]}')

        except Exception as e:
            messages.error(request, f'Error reading file: {e}')

        return render(request, 'members/member_import_results.html', {'results': results})

    def _parse_csv(self, file):
        decoded = file.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(decoded))
        return list(reader)

    def _parse_excel(self, file):
        wb = load_workbook(file, read_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []
        headers = [str(h).strip().lower().replace(' ', '_') if h else f'col_{i}' for i, h in enumerate(rows[0])]
        return [dict(zip(headers, row)) for row in rows[1:] if any(row)]


class MemberExportView(AuditorOrAboveMixin, View):
    def get(self, request):
        wb = Workbook()
        ws = wb.active
        ws.title = 'Members'

        headers = [
            'Member No',
            'Name',
            'Father Name',
            'DOB',
            'Gender',
            'Phone',
            'Email',
            'Address',
            'City',
            'State',
            'Pincode',
            'Aadhar No',
            'PAN No',
            'Category',
            'Branch',
            'Join Date',
            'Status',
        ]
        ws.append(headers)

        for cell in ws[1]:
            cell.font = cell.font.copy(bold=True)

        members = Member.objects.select_related('branch').order_by('member_no')
        user = request.user
        branch = getattr(request, 'current_branch', None)
        if branch and not user.can_access_all_branches:
            members = members.filter(branch=branch)

        for m in members:
            ws.append(
                [
                    m.member_no,
                    m.name,
                    m.father_name,
                    m.dob.strftime('%d-%m-%Y') if m.dob else '',
                    m.gender,
                    m.phone,
                    m.email or '',
                    m.address or '',
                    m.city or '',
                    m.state or '',
                    m.pincode or '',
                    m.aadhar_no or '',
                    m.pan_no or '',
                    m.category,
                    m.branch.branch_name if m.branch else '',
                    m.join_date.strftime('%d-%m-%Y') if m.join_date else '',
                    m.status,
                ]
            )

        for col in ws.columns:
            max_length = max(len(str(cell.value or '')) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = min(max_length + 2, 30)

        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=members.xlsx'
        wb.save(response)
        return response


class SampleImportTemplateView(ManagerRequiredMixin, View):
    def get(self, request):
        wb = Workbook()
        ws = wb.active
        ws.title = 'Members'

        headers = [
            'member_no',
            'name',
            'father_name',
            'dob',
            'gender',
            'phone',
            'email',
            'address',
            'city',
            'state',
            'pincode',
            'aadhar_no',
            'pan_no',
            'occupation',
            'category',
        ]
        ws.append(headers)

        ws.append(
            [
                'M0001',
                'Rajesh Kumar',
                'Suresh Kumar',
                '15-05-1985',
                'M',
                '9876543210',
                'rajesh@email.com',
                '123 Main St',
                'Pune',
                'Maharashtra',
                '411001',
                '123456789012',
                'ABCDE1234F',
                'Business',
                'A',
            ]
        )
        ws.append(
            [
                'M0002',
                'Priya Sharma',
                'Amit Sharma',
                '20-08-1990',
                'F',
                '9876543211',
                'priya@email.com',
                '456 Oak Ave',
                'Pune',
                'Maharashtra',
                '411002',
                '234567890123',
                'BCDEF2345G',
                'Service',
                'A',
            ]
        )
        ws.append(
            [
                '',
                'Leave blank for auto-generation',
                '',
                'DD-MM-YYYY',
                'M/F/O',
                '10 digits',
                '',
                '',
                '',
                '',
                '6 digits',
                '12 digits',
                '',
                '',
                'A/B/C',
            ]
        )

        for cell in ws[1]:
            cell.font = cell.font.copy(bold=True)
        for cell in ws[4]:
            cell.font = cell.font.copy(italic=True, color='808080')

        for col in ws.columns:
            max_length = max(len(str(cell.value or '')) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = min(max_length + 2, 30)

        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=member_import_template.xlsx'
        wb.save(response)
        return response


@auditor_or_above
def member_detail(request, pk):
    member = get_object_or_404(Member, pk=pk)
    from decimal import Decimal
    from apps.agents.models import PigmmyAccount
    from apps.deposits.models import FixedDeposit, RecurringDeposit
    from apps.loans.models import LoanAccount, LoanGuarantor
    from apps.savings.models import SavingsAccount
    from apps.shares.models import ShareHolding

    shares_list = list(ShareHolding.objects.filter(member=member, status='active'))
    savings_list = list(SavingsAccount.objects.filter(member=member))
    loans_list = list(LoanAccount.objects.filter(member=member).select_related('loan_product'))
    fds_list = list(FixedDeposit.objects.filter(member=member, status='active'))
    rds_list = list(RecurringDeposit.objects.filter(member=member, status='active'))
    pigmmy_list = list(PigmmyAccount.objects.filter(member=member))

    context = {
        'member': member,
        'shares': shares_list,
        'savings': savings_list,
        'loans': loans_list,
        'fds': fds_list,
        'rds': rds_list,
        'pigmmy': pigmmy_list,
        'guaranteed_loans': LoanGuarantor.objects.filter(
            guarantor_member=member
        ).select_related('loan', 'loan__member', 'loan__loan_product'),
        'nominees': member.nominees.all(),
        'documents': member.documents.all(),
        'total_shares_amount': sum((s.total_amount for s in shares_list), Decimal('0.00')),
        'total_savings_balance': sum((s.current_balance for s in savings_list), Decimal('0.00')),
        'total_fd_amount': sum((f.deposit_amount for f in fds_list), Decimal('0.00')),
        'total_rd_installment': sum((r.monthly_installment for r in rds_list), Decimal('0.00')),
        'total_loan_outstanding': sum((l.outstanding_principal for l in loans_list), Decimal('0.00')),
        'total_pigmmy_balance': sum((p.current_balance for p in pigmmy_list), Decimal('0.00')),
    }
    return render(request, 'members/detail.html', context)


def _next_member_no():
    last = Member.objects.order_by('-id').first()
    if last and last.member_no:
        digits = ''.join(filter(str.isdigit, last.member_no))
        num = int(digits) + 1 if digits else Member.objects.count() + 1
    else:
        num = 1
    return f'M{num:04d}'


@staff_required
def member_create(request):
    from .forms import MemberForm, MemberNomineeFormSet

    branches = Branch.objects.filter(status='active')
    branch = getattr(request, 'current_branch', None)
    if request.method == 'POST':
        form = MemberForm(request.POST, request.FILES, current_branch=branch)
        nominee_formset = MemberNomineeFormSet(request.POST, prefix='nominees')
        if form.is_valid() and nominee_formset.is_valid():
            member = form.save(commit=False)
            if not member.member_no:
                member.member_no = _next_member_no()
            if not member.branch_id and branch:
                member.branch = branch
            member.created_by = request.user
            member.save()
            nominee_formset.instance = member
            nominee_formset.save()
            messages.success(request, f'Member {member.name} created successfully.')
            return redirect('members:detail', pk=member.pk)
    else:
        initial = {
            'join_date': date.today(),
            'status': 'active',
        }
        form = MemberForm(initial=initial, current_branch=branch)
        nominee_formset = MemberNomineeFormSet(prefix='nominees')

    return render(
        request,
        'members/form.html',
        {
            'form': form,
            'nominee_formset': nominee_formset,
            'branches': branches,
            'title': 'New Member',
        },
    )


@staff_required
def member_edit(request, pk):
    member = get_object_or_404(Member, pk=pk)
    from .forms import MemberForm, MemberNomineeFormSet

    branches = Branch.objects.filter(status='active')
    if request.method == 'POST':
        form = MemberForm(request.POST, request.FILES, instance=member)
        nominee_formset = MemberNomineeFormSet(request.POST, instance=member, prefix='nominees')
        if form.is_valid() and nominee_formset.is_valid():
            form.save()
            nominee_formset.save()
            messages.success(request, f'Member {member.name} updated.')
            return redirect('members:detail', pk=member.pk)
    else:
        form = MemberForm(instance=member)
        nominee_formset = MemberNomineeFormSet(instance=member, prefix='nominees')
    return render(
        request,
        'members/form.html',
        {
            'form': form,
            'nominee_formset': nominee_formset,
            'branches': branches,
            'title': 'Edit Member',
            'member': member,
        },
    )


@staff_required
def member_document_upload(request, pk):
    member = get_object_or_404(Member, pk=pk)
    if request.method == 'POST':
        from .forms import MemberDocumentForm

        form = MemberDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.member = member
            doc.save()
            messages.success(request, f'{doc.get_document_type_display()} uploaded.')
        else:
            messages.error(request, 'Invalid document upload.')
    return redirect('members:detail', pk=member.pk)
