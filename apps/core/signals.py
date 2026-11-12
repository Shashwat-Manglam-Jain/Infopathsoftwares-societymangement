import logging

from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from apps.accounts.models import CustomUser
from apps.agents.models import Agent
from apps.loans.models import LoanCollateral
from apps.members.models import Member, MemberDocument
from apps.tenants.models import Society

logger = logging.getLogger(__name__)

FILE_FIELDS = [
    (Member, 'photo'),
    (Member, 'signature'),
    (MemberDocument, 'file'),
    (CustomUser, 'profile_photo'),
    (Agent, 'security_document'),
    (LoanCollateral, 'document'),
    (Society, 'logo'),
]


def _delete_file(instance, field_name):
    field_file = getattr(instance, field_name, None)
    if field_file and field_file.name:
        try:
            field_file.delete(save=False)
        except Exception:
            logger.exception('Failed to delete file %s', field_file.name)


@receiver(post_delete, sender=Member)
@receiver(post_delete, sender=MemberDocument)
@receiver(post_delete, sender=CustomUser)
@receiver(post_delete, sender=Agent)
@receiver(post_delete, sender=LoanCollateral)
@receiver(post_delete, sender=Society)
def delete_files_on_record_delete(sender, instance, **kwargs):
    for model, field_name in FILE_FIELDS:
        if sender == model:
            _delete_file(instance, field_name)


@receiver(pre_save, sender=Member)
@receiver(pre_save, sender=MemberDocument)
@receiver(pre_save, sender=CustomUser)
@receiver(pre_save, sender=Agent)
@receiver(pre_save, sender=LoanCollateral)
@receiver(pre_save, sender=Society)
def delete_old_file_on_update(sender, instance, **kwargs):
    if not instance.pk:
        return
    for model, field_name in FILE_FIELDS:
        if sender != model:
            continue
        try:
            old_instance = model.objects.get(pk=instance.pk)
        except model.DoesNotExist:
            return
        old_file = getattr(old_instance, field_name, None)
        new_file = getattr(instance, field_name, None)
        if old_file and old_file.name and old_file.name != getattr(new_file, 'name', ''):
            _delete_file(old_instance, field_name)
