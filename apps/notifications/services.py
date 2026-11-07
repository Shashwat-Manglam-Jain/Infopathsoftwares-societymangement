import logging
import re

from django.conf import settings
from django.core.mail import send_mail

from .models import EmailLog, NotificationTemplate, SMSLog

logger = logging.getLogger(__name__)


def render_template(template_name, context_dict):
    try:
        template = NotificationTemplate.objects.get(name=template_name, is_active=True)
    except NotificationTemplate.DoesNotExist:
        logger.warning('Notification template "%s" not found or inactive.', template_name)
        return None

    text = template.template_text
    for key, value in context_dict.items():
        text = text.replace('{{' + key + '}}', str(value))

    unresolved = re.findall(r'\{\{(\w+)\}\}', text)
    if unresolved:
        logger.warning('Unresolved placeholders in template "%s": %s', template_name, unresolved)

    return text


def send_sms(phone, message, member=None, message_type='custom'):
    log = SMSLog.objects.create(
        member=member,
        phone_number=phone,
        message_type=message_type,
        message_text=message,
        status='queued',
    )

    try:
        if getattr(settings, 'SMS_BACKEND', 'console') == 'console':
            logger.info('SMS [console] to %s: %s', phone, message)
            log.status = 'sent'
            log.provider_message_id = 'console-mock'
        else:
            # Production: integrate MSG91 or other provider here
            # import requests
            # response = requests.post(
            #     'https://control.msg91.com/api/v5/flow/',
            #     headers={'authkey': settings.SMS_API_KEY},
            #     json={...}
            # )
            # log.provider_message_id = response.json().get('request_id')
            log.status = 'sent'

        log.save()
    except Exception as e:
        log.status = 'failed'
        log.error_message = str(e)
        log.save()
        logger.exception('Failed to send SMS to %s', phone)

    return log


def send_email(email, subject, body, member=None):
    log = EmailLog.objects.create(
        member=member,
        email_address=email,
        subject=subject,
        body=body,
        status='queued',
    )

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        log.status = 'sent'
        log.save()
    except Exception as e:
        log.status = 'failed'
        log.error_message = str(e)
        log.save()
        logger.exception('Failed to send email to %s', email)

    return log


def send_transaction_alert(member, txn_type, amount, balance):
    template_name = 'deposit_confirmation' if txn_type == 'deposit' else 'withdrawal_confirmation'
    context = {
        'member_name': member.name,
        'amount': f'{amount:,.2f}',
        'balance': f'{balance:,.2f}',
    }
    message = render_template(template_name, context)
    if message and member.phone:
        return send_sms(member.phone, message, member=member, message_type='txn_alert')
    return None


def send_emi_reminder(member, loan_no, emi_amount, due_date):
    context = {
        'member_name': member.name,
        'loan_no': loan_no,
        'amount': f'{emi_amount:,.2f}',
        'due_date': due_date.strftime('%d-%m-%Y'),
    }
    message = render_template('emi_reminder', context)
    if message and member.phone:
        return send_sms(member.phone, message, member=member, message_type='emi_reminder')
    return None


def send_fd_maturity_alert(member, fd_no, maturity_date, maturity_amount):
    context = {
        'member_name': member.name,
        'fd_no': fd_no,
        'maturity_date': maturity_date.strftime('%d-%m-%Y'),
        'maturity_amount': f'{maturity_amount:,.2f}',
    }
    message = render_template('fd_maturity', context)
    if message and member.phone:
        return send_sms(member.phone, message, member=member, message_type='fd_maturity')
    return None
