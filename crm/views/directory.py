from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Exists
from django.db.models.deletion import ProtectedError
from django.shortcuts import redirect
from django.utils import timezone

from .common import LIST_PAGE_SIZE


def directory_status(request):
    status = request.GET.get("status", "active")
    return status if status in ("active", "archived", "all") else "active"


def directory_actions(user, model, status):
    permission = model._meta.model_name
    actions = {}
    if user.has_perm(f"crm.change_{permission}"):
        if status != "archived":
            actions["archive"] = "Archive"
        if status != "active":
            actions["restore"] = "Restore"
    if user.has_perm(f"crm.delete_{permission}"):
        actions["delete"] = "Delete"
    return actions


def apply_directory_action(request, records, actions, order_references):
    action = request.POST.get("bulk_action")
    if action not in actions:
        raise PermissionDenied

    model = records.model
    destination = redirect(request.get_full_path())
    with transaction.atomic():
        if request.POST.get("scope") == "all":
            count = records.count()
            if not count or request.POST.get("total") != str(count):
                messages.error(
                    request, "The matching results changed. Select the entries again."
                )
                return destination
            selected = records.order_by().values("pk")
        else:
            page = Paginator(records, LIST_PAGE_SIZE).get_page(request.GET.get("page"))
            visible_ids = {
                str(pk): pk for pk in page.object_list.values_list("pk", flat=True)
            }
            posted_ids = set(request.POST.getlist("selected"))
            if not posted_ids or not posted_ids <= visible_ids.keys():
                messages.error(
                    request, "Select entries from the current page and try again."
                )
                return destination
            selected = [visible_ids[pk] for pk in posted_ids]
            count = len(selected)
        targets = model.objects.filter(pk__in=selected)

        if action == "delete":
            try:
                deleted = targets.filter(~Exists(order_references)).delete()[1]
            except ProtectedError:
                messages.error(
                    request,
                    "Order references changed. Review your selection and try again.",
                )
                return destination
            changed = deleted.get(model._meta.label, 0)
        else:
            archived = action == "archive"
            changed = targets.filter(is_archived=not archived).update(
                is_archived=archived, updated_at=timezone.now()
            )

        if changed:
            verb = {"archive": "Archived", "restore": "Restored", "delete": "Deleted"}[
                action
            ]
            name = (
                model._meta.verbose_name
                if changed == 1
                else model._meta.verbose_name_plural
            )
            messages.success(request, f"{verb} {changed} {name}.")
        elif action != "delete":
            messages.info(request, "The selected entries already have that status.")
        if action == "delete" and count > changed:
            skipped = count - changed
            entries = "entry" if skipped == 1 else "entries"
            messages.warning(
                request,
                f"Kept {skipped} {entries} linked to service orders. Use Archive to hide linked entries.",
            )
    return destination
