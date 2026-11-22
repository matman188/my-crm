"""Shared work-queue and dashboard rules. No order state is derived or changed."""

from django.db.models import (
    BooleanField,
    Case,
    Count,
    Exists,
    F,
    OuterRef,
    Q,
    Subquery,
    Value,
    When,
)
from django.utils import timezone

from crm.models import OrderItem, ServiceOrder, SystemSettings

ACTIVE = (ServiceOrder.Status.DRAFT, ServiceOrder.Status.IN_PROGRESS)
WORK_VIEWS = (
    ("all", "All orders"),
    ("open", "Open Orders"),
    ("mine", "My Orders"),
    ("unassigned", "Unassigned"),
    ("due_today", "Due Today"),
    ("overdue", "Overdue"),
    ("unpaid", "Unpaid"),
    ("awaiting_collection", "Awaiting Collection"),
)


def with_deadlines(queryset, now=None):
    local = timezone.localtime(
        now or timezone.now(), SystemSettings.get_solo().business_zone
    )
    items = OrderItem.objects.filter(order_id=OuterRef("pk"))
    earliest = items.order_by("due_date", F("due_time").asc(nulls_last=True), "pk")
    overdue = items.filter(
        Q(due_date__lt=local.date())
        | Q(due_date=local.date(), due_time__lt=local.time().replace(tzinfo=None))
    )
    return queryset.annotate(
        next_due_date=Subquery(earliest.values("due_date")[:1]),
        next_due_time=Subquery(earliest.values("due_time")[:1]),
        is_overdue=Case(
            When(status__in=ACTIVE, then=Exists(overdue)),
            default=Value(False),
            output_field=BooleanField(),
        ),
        is_due_today=Case(
            When(status__in=ACTIVE, then=Exists(items.filter(due_date=local.date()))),
            default=Value(False),
            output_field=BooleanField(),
        ),
    )


def work_condition(view, user):
    return {
        "all": Q(),
        "open": Q(status__in=ACTIVE),
        "mine": Q(assigned_to=user),
        "unassigned": Q(status__in=ACTIVE, assigned_to__isnull=True),
        "due_today": Q(is_due_today=True),
        "overdue": Q(is_overdue=True),
        "unpaid": Q(
            status__in=(ServiceOrder.Status.IN_PROGRESS, ServiceOrder.Status.COMPLETE),
            payment_status="unpaid",
        ),
        "awaiting_collection": Q(status=ServiceOrder.Status.COMPLETE, collected=False),
    }[view]


def work_counts(queryset, user):
    return queryset.aggregate(
        **{key: Count("pk", filter=work_condition(key, user)) for key, _ in WORK_VIEWS}
    )


def deadline_order(queryset):
    return queryset.annotate(
        work_priority=Case(When(status__in=ACTIVE, then=Value(0)), default=Value(1))
    ).order_by(
        "work_priority",
        F("next_due_date").asc(nulls_last=True),
        F("next_due_time").asc(nulls_last=True),
        "pk",
    )
