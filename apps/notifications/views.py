from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import FormView, ListView, UpdateView

from apps.accounts.permissions import ManagerRequiredMixin
from apps.members.models import Member

from .forms import BulkSMSForm, NotificationTemplateForm
from .models import NotificationTemplate, SMSLog
from .services import send_sms


class NotificationTemplateListView(ManagerRequiredMixin, ListView):
    model = NotificationTemplate
    template_name = 'notifications/template_list.html'
    context_object_name = 'templates'


class NotificationTemplateUpdateView(ManagerRequiredMixin, UpdateView):
    model = NotificationTemplate
    form_class = NotificationTemplateForm
    template_name = 'notifications/template_form.html'
    success_url = reverse_lazy('notifications:template_list')

    def form_valid(self, form):
        messages.success(self.request, 'Template updated successfully.')
        return super().form_valid(form)


class SMSLogListView(ManagerRequiredMixin, ListView):
    model = SMSLog
    template_name = 'notifications/sms_log.html'
    context_object_name = 'logs'
    paginate_by = 50

    def get_queryset(self):
        qs = super().get_queryset()
        status = self.request.GET.get('status')
        msg_type = self.request.GET.get('type')
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')

        if status:
            qs = qs.filter(status=status)
        if msg_type:
            qs = qs.filter(message_type=msg_type)
        if date_from:
            qs = qs.filter(sent_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(sent_at__date__lte=date_to)

        return qs


class SendBulkSMSView(ManagerRequiredMixin, FormView):
    form_class = BulkSMSForm
    template_name = 'notifications/send_bulk.html'
    success_url = reverse_lazy('notifications:sms_log')

    def form_valid(self, form):
        recipient_type = form.cleaned_data['recipient_type']
        message = form.cleaned_data['message']

        if recipient_type == 'all':
            members = Member.objects.filter(status='active', phone__isnull=False).exclude(phone='')
        elif recipient_type == 'branch':
            branch_id = form.cleaned_data.get('branch')
            members = Member.objects.filter(status='active', branch_id=branch_id, phone__isnull=False).exclude(phone='')
        else:
            ids_str = form.cleaned_data.get('member_ids', '')
            ids = [int(x.strip()) for x in ids_str.split(',') if x.strip().isdigit()]
            members = Member.objects.filter(pk__in=ids, phone__isnull=False).exclude(phone='')

        sent = 0
        for member in members:
            send_sms(member.phone, message, member=member, message_type='custom')
            sent += 1

        messages.success(self.request, f'Sent {sent} SMS messages.')
        return super().form_valid(form)
