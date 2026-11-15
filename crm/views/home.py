from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from crm.models import ServiceOrder
from crm.order_queries import (
    ACTIVE,
    WORK_VIEWS,
    deadline_order,
    with_deadlines,
    work_counts,
)


@login_required
def home(request):
    context = {}
    if request.user.has_perm("crm.view_serviceorder"):
        orders = with_deadlines(
            ServiceOrder.objects.select_related("customer", "assigned_to")
        )
        counts = work_counts(orders, request.user)
        context["work_cards"] = [
            {"key": key, "label": label, "count": counts[key]}
            for key, label in WORK_VIEWS
        ]
        context["due_orders"] = deadline_order(
            orders.filter(status__in=ACTIVE, next_due_date__isnull=False)
        )[:5]
    return render(request, "crm/home.html", context)
