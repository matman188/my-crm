from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Q
from django.forms import BaseInlineFormSet, inlineformset_factory

from crm.forms.customers import CustomerForm
from crm.models import (
    Customer,
    OrderItem,
    OrderServiceCharge,
    Service,
    ServiceOrder,
    SystemSettings,
)


class CustomerChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, customer):
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
        return f"{customer} — {details}" if details else str(customer)


class AssigneeChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, user):
        return (
            f"{user.get_full_name()} ({user.username})"
            if user.get_full_name()
            else user.username
        )


class ServiceOrderForm(forms.ModelForm):
    customer_mode = forms.ChoiceField(
        choices=[
            ("existing", "Choose an existing customer"),
            ("new", "Create a new customer"),
        ],
        widget=forms.HiddenInput,
        initial="existing",
    )
    customer = CustomerChoiceField(
        queryset=Customer.objects.none(), required=False, widget=forms.HiddenInput
    )
    assigned_to = AssigneeChoiceField(
        queryset=get_user_model().objects.none(), required=False
    )
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].queryset = Customer.objects.order_by(
            "first_name", "last_name", "pk"
        )
        assignees = get_user_model().objects.filter(is_active=True)
        if self.instance.assigned_to_id:
            assignees = get_user_model().objects.filter(
                Q(is_active=True) | Q(pk=self.instance.assigned_to_id)
            )
        self.fields["assigned_to"].queryset = assignees.order_by(
            "first_name", "last_name", "username"
        )
        self.fields["assigned_to"].empty_label = "Unassigned"
        self.fields["assigned_to"].label = "Assignee"
        self.fields["notes"].label = "Order notes"
        if self.instance.pk:
            self.fields["revision"].required = True
            self.initial["revision"] = self.instance.revision

    def clean(self):
        data = super().clean()
        if data.get("customer_mode") == "existing" and not data.get("customer"):
            self.add_error("customer", "Choose a customer or create a new one.")
        return data

    class Meta:
        model = ServiceOrder
        fields = ("customer", "assigned_to", "notes")
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}


class OrderItemForm(forms.ModelForm):
    class Meta:
        model = OrderItem
        fields = ("product", "due_date", "due_time", "notes")
        widgets = {
            "due_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "due_time": forms.TimeInput(format="%H:%M", attrs={"type": "time"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }
        labels = {
            "due_date": "Due date",
            "due_time": "Time (optional)",
            "notes": "Item notes",
        }


class OrderServiceChargeForm(forms.ModelForm):
    quantity = forms.IntegerField(min_value=1, max_value=100000000, initial=1)

    def __init__(self, *args, product_id=None, general=False, **kwargs):
        super().__init__(*args, **kwargs)
        services = Service.objects.filter(products__isnull=True)
        if product_id and not general:
            services = Service.objects.filter(
                Q(products=product_id) | Q(products__isnull=True)
            )
        elif not general:
            services = Service.objects.none()
        self.fields["service"].queryset = services.distinct().order_by("name", "pk")
        self.fields["quantity"].label = "Quantity"
        self.fields["notes"].label = "Note (optional)"
        self.original_service_id = self.instance.service_id or ""
        self.original_price = self.instance.unit_price if self.instance.pk else ""

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
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}


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


class DraftConflict(Exception):
    pass


class DraftOrderEditor:
    """Compose the order, inline customer, and nested item/service forms."""

    def __init__(self, *, user, instance=None, data=None):
        self.user = user
        self.instance = instance or ServiceOrder(
            currency=SystemSettings.get_solo().default_currency
        )
        self.form = ServiceOrderForm(data, instance=self.instance)
        self.new_customer = bool(data and data.get("customer_mode") == "new")
        self.customer_form = CustomerForm(
            data if self.new_customer else None, prefix="customer"
        )
        self.items = ItemFormSet(data, instance=self.instance, prefix="items")
        for item_form in self.items:
            self._attach_services(item_form, data)
        self.empty_item = self.items.empty_form
        self._attach_services(self.empty_item, None)
        self.general = GeneralChargeFormSet(
            data,
            instance=self.instance,
            prefix="general",
            queryset=(
                self.instance.charges.filter(item__isnull=True)
                if self.instance.pk
                else OrderServiceCharge.objects.none()
            ),
            form_kwargs={"general": True},
        )
        self.general.empty_charge = self.general.empty_form
        self.general.empty_charge.prefix = "general-__charge__"

    def _attach_services(self, item_form, data):
        try:
            product_id = int(item_form["product"].value())
        except (TypeError, ValueError):
            product_id = None
        item_form.services = ItemChargeFormSet(
            data,
            instance=item_form.instance,
            prefix=f"{item_form.prefix}-services",
            form_kwargs={"product_id": product_id},
        )
        item_form.services.empty_charge = item_form.services.empty_form
        item_form.services.empty_charge.prefix = (
            f"{item_form.services.prefix}-__charge__"
        )

    def is_valid(self):
        valid = self.form.is_valid()
        if self.new_customer:
            if not self.user.has_perm("crm.add_customer"):
                self.form.add_error(
                    "customer_mode", "You do not have permission to create customers."
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
        if order.pk:
            revision = self.form.cleaned_data["revision"]
            updated = ServiceOrder.objects.filter(
                pk=order.pk, revision=revision, status=ServiceOrder.Status.DRAFT
            ).update(revision=F("revision") + 1)
            if not updated:
                raise DraftConflict(
                    "This order changed while you were editing. Reload it before saving again."
                )
            order.revision = revision + 1
        else:
            order.created_by = self.user
        if self.new_customer:
            customer = self.customer_form.save(commit=False)
            customer.owner = self.user
            customer.save()
            order.customer = customer
        order.save()

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
            if not charge.pk or charge.service_id != form.original_service_id:
                charge.unit_price = charge.service.price
            charge.order = order
            charge.item = item
            charge.save()
