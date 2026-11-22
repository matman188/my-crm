from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Q
from django.forms import BaseInlineFormSet, inlineformset_factory

from crm.forms.customers import CustomerForm
from crm.models import (
    Customer,
    Invoice,
    OrderComplaint,
    OrderItem,
    Product,
    OrderServiceCharge,
    Service,
    ServiceOrder,
    SystemSettings,
)
from crm.order_workflow import (
    MANUAL_PAYMENT_CHOICES,
    ORDER_ACTIONS,
    SAVE_LABELS,
    WORKFLOW_FIELD_STAGES,
)
from crm.order_queries import WORK_VIEWS


ORDER_NOTES_ATTRS = {"rows": 2, "data-order-notes": ""}


class CustomerChoiceField(forms.ModelChoiceField):
    @staticmethod
    def label_from_instance(customer):
        details = " · ".join(
            filter(
                None,
                [
                    customer.company,
                    customer.email,
                    customer.primary_phone,
                    customer.secondary_phone,
                ],
            )
        )
        name = f"{customer} (Archived)" if customer.is_archived else str(customer)
        return f"{name} — {details}" if details else name


class AssignedToChoiceField(forms.ModelChoiceField):
    @staticmethod
    def label_from_instance(user):
        return (
            f"{user.get_full_name()} ({user.username})"
            if user.get_full_name()
            else user.username
        )


def order_assignees(current_id=None):
    return (
        get_user_model()
        .objects.filter(Q(is_active=True) | Q(pk=current_id))
        .order_by("first_name", "last_name", "username")
    )


class OrderWorkflowForm(forms.ModelForm):
    assigned_to = AssignedToChoiceField(
        queryset=get_user_model().objects.none(),
        required=False,
        empty_label="Unassigned",
        label="Assigned To",
    )
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_status = self.instance.status
        self.fields["assigned_to"].queryset = order_assignees(
            self.instance.assigned_to_id
        )
        for name, stages in WORKFLOW_FIELD_STAGES.items():
            self.fields[name].disabled = self.instance.status not in stages
        if self.instance.payment_status_managed_by_refunds:
            self.fields["payment_status"].disabled = True
        else:
            self.fields["payment_status"].choices = MANUAL_PAYMENT_CHOICES
        if self.instance.pk:
            self.fields["revision"].required = True
            self.initial["revision"] = self.instance.revision

    def clean(self):
        data = super().clean()
        if self.target_status == ServiceOrder.Status.COMPLETE and not data.get(
            "assigned_to"
        ):
            self.add_error(
                "assigned_to", "Assign a user before marking the order Complete."
            )
        return data

    class Meta:
        model = ServiceOrder
        fields = ("assigned_to", "collected", "payment_status")
        labels = {"payment_status": "Payment status"}


class ServiceOrderForm(OrderWorkflowForm):
    customer_mode = forms.ChoiceField(
        choices=[
            ("existing", "Choose an existing customer"),
            ("new", "Create a new customer"),
            ("edit", "Edit the selected customer"),
        ],
        widget=forms.HiddenInput,
        initial="existing",
    )
    customer = CustomerChoiceField(
        queryset=Customer.objects.none(), required=False, widget=forms.HiddenInput
    )

    def __init__(self, *args, active_invoice=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.locked = bool(
            self.instance.pk and self.instance.status != ServiceOrder.Status.DRAFT
        )
        self.original_status = self.instance.status
        self.actions = ORDER_ACTIONS[self.original_status]
        if active_invoice:
            self.actions = tuple(
                action
                for action in self.actions
                if action["name"] != "cancel"
                and (
                    action["name"] != "return_to_draft"
                    or self.instance.invoice_revision_reason
                )
            )
        self.action = self.data.get("action", "save") if self.is_bound else "save"
        selected_action = next(
            (action for action in self.actions if action["name"] == self.action), None
        )
        self.target_status = (
            selected_action["target"] if selected_action else self.original_status
        )
        self.invalid_action = self.action != "save" and selected_action is None
        available_customers = Q(is_archived=False)
        if self.instance.pk and self.instance.customer_id:
            available_customers |= Q(pk=self.instance.customer_id)
        self.fields["customer"].queryset = Customer.objects.filter(
            available_customers
        ).order_by("first_name", "last_name", "pk")
        self.fields["notes"].label = "Order notes"
        if self.locked:
            for name in ("customer_mode", "customer"):
                self.fields[name].disabled = True
            if self.is_bound and "notes" not in self.data:
                self.data = self.data.copy()
                self.data["notes"] = self.instance.notes
        if self.original_status == ServiceOrder.Status.CANCELLED:
            self.fields["notes"].help_text = (
                "Add a cancellation reason or other internal notes."
            )

    def clean(self):
        data = super().clean()
        if self.invalid_action:
            self.add_error(
                None,
                "This action is not available for the current order status. Reload the order and use its action buttons.",
            )
        if "transition" in self.data or (
            "status" in self.data and self.data["status"] != self.original_status
        ):
            self.add_error(None, "Use the order action buttons to change the status.")
        if data.get("customer_mode") in ("existing", "edit") and not data.get(
            "customer"
        ):
            self.add_error("customer", "Choose a customer or create a new one.")
        return data

    class Meta(OrderWorkflowForm.Meta):
        fields = (
            "customer",
            "assigned_to",
            "collected",
            "payment_status",
            "notes",
        )
        widgets = {
            "notes": forms.Textarea(attrs=ORDER_NOTES_ATTRS),
        }


class OrderFilterForm(forms.Form):
    view = forms.ChoiceField(
        choices=WORK_VIEWS, required=False, widget=forms.HiddenInput
    )
    sort = forms.ChoiceField(
        label="Sort by",
        choices=(
            ("newest", "Newest first"),
            ("deadline", "Nearest deadline"),
            ("oldest", "Oldest first"),
        ),
        required=False,
    )
    customer = CustomerChoiceField(
        queryset=Customer.objects.order_by("first_name", "last_name", "pk"),
        required=False,
        empty_label="All customers",
        widget=forms.HiddenInput,
    )
    q = forms.CharField(
        label="Search",
        required=False,
        max_length=200,
        widget=forms.TextInput(
            attrs={
                "type": "search",
                "placeholder": "Reference, customer, assigned user, or notes",
            }
        ),
    )
    status = forms.ChoiceField(
        choices=[("", "All statuses"), *ServiceOrder.Status.choices],
        required=False,
    )
    collected = forms.ChoiceField(
        choices=[
            ("", "All collections"),
            ("yes", "Collected"),
            ("no", "Not collected"),
        ],
        required=False,
    )
    payment_status = forms.ChoiceField(
        label="Payment status",
        choices=[("", "All payments"), *ServiceOrder.PaymentStatus.choices],
        required=False,
    )
    complaint = forms.ChoiceField(
        choices=[
            ("", "Any complaint status"),
            ("yes", "Complaint logged"),
            ("no", "No complaint"),
            *OrderComplaint.Outcome.choices,
        ],
        required=False,
    )


class DeleteDraftForm(forms.Form):
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)


class OrderItemForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_product_id = self.instance.product_id
        self.fields["product"].queryset = Product.objects.filter(
            Q(is_archived=False) | Q(pk=self.original_product_id)
        ).order_by("name", "pk")

    class Meta:
        model = OrderItem
        fields = ("product", "due_date", "due_time", "notes")
        widgets = {
            "due_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "due_time": forms.TimeInput(format="%H:%M", attrs={"type": "time"}),
            "notes": forms.Textarea(attrs=ORDER_NOTES_ATTRS),
        }
        labels = {
            "due_date": "Due date",
            "due_time": "Time (optional)",
            "notes": "Item notes",
        }


class OrderServiceChargeForm(forms.ModelForm):
    quantity = forms.IntegerField(min_value=1, max_value=100000000, initial=1)

    def __init__(
        self,
        *args,
        product_id=None,
        original_product_id=None,
        general=False,
        locked=False,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        services = Service.objects.filter(products__isnull=True)
        if product_id and not general:
            services = Service.objects.filter(
                Q(products=product_id) | Q(products__isnull=True)
            )
        elif not general:
            services = Service.objects.none()
        services = services.filter(is_archived=False)
        if self.instance.service_id and (
            locked or general or product_id == original_product_id
        ):
            services = Service.objects.filter(
                Q(pk__in=services.values("pk")) | Q(pk=self.instance.service_id)
            )
        self.fields["service"].queryset = services.distinct().order_by("name", "pk")
        self.fields["quantity"].label = "Quantity"
        self.fields["notes"].label = "Note (optional)"
        self.original_service_id = self.instance.service_id or ""
        self.original_price = self.instance.unit_price if self.instance.pk else ""
        self.product_changed = not general and product_id != original_product_id

    def clean_service(self):
        service = self.cleaned_data["service"]
        if service.price < 0:
            raise ValidationError(
                "This service has a negative price. Ask an administrator to correct it."
            )
        return service

    class Meta:
        model = OrderServiceCharge
        fields = ("service", "quantity", "notes")
        widgets = {"notes": forms.Textarea(attrs=ORDER_NOTES_ATTRS)}


class OrderItemDetailsForm(forms.ModelForm):
    class Meta(OrderItemForm.Meta):
        fields = ("due_date", "due_time", "notes")


class OrderChargeNotesForm(forms.ModelForm):
    class Meta(OrderServiceChargeForm.Meta):
        fields = ("notes",)


class OwnedInlineFormSet(BaseInlineFormSet):
    """Reject forged or repeated IDs, including IDs from another order/item."""

    def clean(self):
        super().clean()
        allowed_ids = set(self.get_queryset().values_list("pk", flat=True))
        seen = set()
        for form in self.forms:
            record = form.cleaned_data.get("id")
            if record:
                if record.pk not in allowed_ids or record.pk in seen:
                    raise ValidationError(
                        "An entry does not belong to this order or was submitted twice. Reload and try again."
                    )
                seen.add(record.pk)


ItemFormSet = inlineformset_factory(
    ServiceOrder,
    OrderItem,
    form=OrderItemForm,
    formset=OwnedInlineFormSet,
    extra=0,
    min_num=1,
    validate_min=True,
    max_num=50,
    validate_max=True,
    absolute_max=60,
)
ItemChargeFormSet = inlineformset_factory(
    OrderItem,
    OrderServiceCharge,
    form=OrderServiceChargeForm,
    formset=OwnedInlineFormSet,
    extra=0,
    min_num=1,
    validate_min=True,
    max_num=50,
    validate_max=True,
    absolute_max=60,
)
GeneralChargeFormSet = inlineformset_factory(
    ServiceOrder,
    OrderServiceCharge,
    fk_name="order",
    form=OrderServiceChargeForm,
    formset=OwnedInlineFormSet,
    extra=0,
    max_num=50,
    validate_max=True,
    absolute_max=60,
)


class OrderConflict(Exception):
    pass


class OrderEditor:
    """Compose the order, inline customer, and nested item/service forms."""

    def __init__(self, *, user, instance=None, data=None):
        self.user = user
        self.instance = instance or ServiceOrder(
            currency=SystemSettings.get_solo().default_currency
        )
        self.locked = bool(
            self.instance.pk and self.instance.status != ServiceOrder.Status.DRAFT
        )
        self.original_status = self.instance.status
        self.original_customer_id = self.instance.customer_id
        self.details_editable = bool(
            self.instance.pk and self.original_status == ServiceOrder.Status.IN_PROGRESS
        )
        self.detail_forms = []
        self.invoices = (
            list(
                self.instance.invoices.select_related(
                    "issued_by", "closed_by", "replaces", "replacement"
                ).defer("snapshot", "replaces__snapshot", "replacement__snapshot")
            )
            if self.instance.pk
            else []
        )
        self.active_invoice = next(
            (
                invoice
                for invoice in self.invoices
                if invoice.status == Invoice.Status.ISSUED
            ),
            None,
        )
        self.form = ServiceOrderForm(
            data, instance=self.instance, active_invoice=self.active_invoice
        )
        self.actions = self.form.actions
        self.save_label = SAVE_LABELS[self.original_status]
        self.new_customer = bool(
            not self.locked and data and data.get("customer_mode") == "new"
        )
        self.editing_customer = bool(
            not self.locked and data and data.get("customer_mode") == "edit"
        )
        customer_instance = None
        if self.editing_customer:
            try:
                customer_instance = self.form.fields["customer"].clean(
                    self.form["customer"].value()
                )
            except ValidationError:
                pass  # The order form reports an invalid customer selection.
        self.customer_form = CustomerForm(
            data if self.new_customer or self.editing_customer else None,
            instance=customer_instance,
            prefix="customer",
        )
        item_data = None if self.locked else data
        self.items = ItemFormSet(item_data, instance=self.instance, prefix="items")
        for item_form in self.items:
            self._attach_services(item_form, item_data)
        self.empty_item = self.items.empty_form
        self._attach_services(self.empty_item, None)
        self.general = GeneralChargeFormSet(
            item_data,
            instance=self.instance,
            prefix="general",
            queryset=(
                self.instance.charges.filter(item__isnull=True)
                if self.instance.pk
                else OrderServiceCharge.objects.none()
            ),
            form_kwargs={"general": True, "locked": self.locked},
        )
        self.general.empty_charge = self.general.empty_form
        self.general.empty_charge.prefix = "general-__charge__"
        if self.locked:
            for item_form in self.items:
                self._attach_details(item_form, OrderItemDetailsForm, data)
                for charge_form in item_form.services:
                    self._attach_details(charge_form, OrderChargeNotesForm, data)
            for charge_form in self.general:
                self._attach_details(charge_form, OrderChargeNotesForm, data)

    def _attach_details(self, form, detail_form_class, data):
        for field in form.fields.values():
            field.disabled = True
        if not self.details_editable:
            return
        # Bind only non-commercial fields on rows loaded from this order. Posted
        # IDs, management counts, add/delete flags, and prices are never consumed.
        detail_data = None
        if data is not None:
            detail_data = {
                form.add_prefix(name): data.get(
                    form.add_prefix(name), getattr(form.instance, name)
                )
                for name in detail_form_class.Meta.fields
            }
        form.detail_form = detail_form_class(
            detail_data, instance=form.instance, prefix=form.prefix
        )
        self.detail_forms.append(form.detail_form)

    @property
    def detail_errors(self):
        return any(form.errors for form in self.detail_forms)

    def _attach_services(self, item_form, data):
        try:
            product_id = int(item_form["product"].value())
        except (TypeError, ValueError):
            product_id = None
        item_form.services = ItemChargeFormSet(
            data,
            instance=item_form.instance,
            prefix=f"{item_form.prefix}-services",
            form_kwargs={
                "product_id": product_id,
                "original_product_id": item_form.original_product_id,
                "locked": self.locked,
            },
        )
        item_form.services.empty_charge = item_form.services.empty_form
        item_form.services.empty_charge.prefix = (
            f"{item_form.services.prefix}-__charge__"
        )

    def is_valid(self):
        valid = self.form.is_valid()
        if self.locked:
            for detail_form in self.detail_forms:
                valid = detail_form.is_valid() and valid
            return valid
        if self.new_customer or self.editing_customer:
            permission = (
                "crm.add_customer" if self.new_customer else "crm.change_customer"
            )
            if not self.user.has_perm(permission):
                self.form.add_error(
                    "customer_mode",
                    (
                        "You do not have permission to create customers."
                        if self.new_customer
                        else "You do not have permission to edit customers."
                    ),
                )
                valid = False
            valid = self.customer_form.is_valid() and valid
        valid = self.items.is_valid() and valid
        for item_form in self.items:
            if not item_form.cleaned_data.get("DELETE"):
                valid = item_form.services.is_valid() and valid
        return self.general.is_valid() and valid

    @transaction.atomic
    def save(self):
        order = self.form.save(commit=False)
        if not self.new_customer and (
            not order.pk or order.customer_id != self.original_customer_id
        ):
            available = Customer.objects.filter(
                pk=order.customer_id, is_archived=False
            ).update(updated_at=F("updated_at"))
            if not available:
                raise OrderConflict(
                    "This customer was archived or removed. Choose an active customer before saving."
                )
        if order.pk:
            revision = self.form.cleaned_data["revision"]
            if revision != order.revision:
                raise OrderConflict(
                    "This order changed while you were editing. Reload it before saving again."
                )
            updated = ServiceOrder.objects.filter(
                pk=order.pk, revision=revision, status=self.original_status
            ).update(revision=F("revision") + 1)
            if not updated:
                raise OrderConflict(
                    "This order changed while you were editing. Reload it before saving again."
                )
            order.revision = revision + 1
        else:
            order.created_by = self.user
        order.status = self.form.target_status
        if self.new_customer or self.editing_customer:
            customer = self.customer_form.save(commit=False)
            if self.new_customer:
                customer.owner = self.user
                customer.save()
            else:
                customer.save(update_fields=[*CustomerForm.Meta.fields, "updated_at"])
            order.customer = customer
        order.save()

        if self.locked:
            for detail_form in self.detail_forms:
                if detail_form.has_changed():
                    record = detail_form.save(commit=False)
                    record.save(update_fields=detail_form.Meta.fields)
            return order

        for item_form in self.items:
            if item_form.cleaned_data.get("DELETE"):
                if item_form.instance.pk:
                    item_form.instance.delete()
                continue
            if (
                not item_form.cleaned_data
                or not item_form.has_changed()
                and not item_form.instance.pk
            ):
                continue
            item = item_form.save(commit=False)
            if not item.pk or item.product_id != item_form.original_product_id:
                if not Product.objects.filter(
                    pk=item.product_id, is_archived=False
                ).update(updated_at=F("updated_at")):
                    raise OrderConflict(
                        "This product was archived or removed. Choose an active product before saving."
                    )
            item.order = order
            item.save()
            self._save_charges(item_form.services, order, item)
        self._save_charges(self.general, order)
        return order

    @staticmethod
    def _save_charges(formset, order, item=None):
        for form in formset:
            if form.cleaned_data.get("DELETE"):
                if form.instance.pk:
                    form.instance.delete()
                continue
            if not form.cleaned_data or not form.has_changed() and not form.instance.pk:
                continue
            charge = form.save(commit=False)
            if (
                not charge.pk
                or charge.service_id != form.original_service_id
                or form.product_changed
            ):
                if not Service.objects.filter(
                    pk=charge.service_id, is_archived=False
                ).update(updated_at=F("updated_at")):
                    raise OrderConflict(
                        "This service was archived or removed. Choose an active service before saving."
                    )
            if not charge.pk or charge.service_id != form.original_service_id:
                charge.unit_price = charge.service.price
            charge.order = order
            charge.item = item
            charge.save()
