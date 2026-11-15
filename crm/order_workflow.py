from crm.models import ServiceOrder

# These are the permitted transitions, shared by validation and the action buttons.
ORDER_ACTIONS = {
    ServiceOrder.Status.DRAFT: (
        {
            "name": "submit",
            "label": "Submit",
            "confirmation": "Are you sure you wish to submit this order?",
            "target": ServiceOrder.Status.IN_PROGRESS,
            "style": "",
        },
    ),
    ServiceOrder.Status.IN_PROGRESS: (
        {
            "name": "complete",
            "label": "Mark complete",
            "confirmation": "Are you sure you wish to mark this order Complete?",
            "target": ServiceOrder.Status.COMPLETE,
            "style": "",
        },
        {
            "name": "cancel",
            "label": "Cancel order",
            "confirmation": "Are you sure you wish to cancel this order?",
            "target": ServiceOrder.Status.CANCELLED,
            "style": "danger",
        },
        {
            "name": "return_to_draft",
            "label": "Return to draft",
            "confirmation": "Are you sure you wish to return this order to Draft?",
            "target": ServiceOrder.Status.DRAFT,
            "style": "secondary",
        },
    ),
    ServiceOrder.Status.COMPLETE: (
        {
            "name": "reopen",
            "label": "Reopen",
            "confirmation": "Are you sure you wish to reopen this order and move it to In Progress?",
            "target": ServiceOrder.Status.IN_PROGRESS,
            "style": "",
        },
    ),
    ServiceOrder.Status.CANCELLED: (
        {
            "name": "restore_to_draft",
            "label": "Restore to draft",
            "confirmation": "Are you sure you wish to restore this order to Draft?",
            "target": ServiceOrder.Status.DRAFT,
            "style": "",
        },
    ),
}

SAVE_LABELS = {
    ServiceOrder.Status.DRAFT: "Save draft",
    ServiceOrder.Status.IN_PROGRESS: "Save changes",
    ServiceOrder.Status.COMPLETE: "Save changes",
    ServiceOrder.Status.CANCELLED: "Save notes",
}
