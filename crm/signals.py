from django.db.models.signals import post_migrate
from django.dispatch import receiver

from crm.authz import ensure_crm_groups


@receiver(post_migrate)
def bootstrap_crm_groups(sender, using, **kwargs):
    if sender.label != "crm":
        return
    ensure_crm_groups(using=using)
