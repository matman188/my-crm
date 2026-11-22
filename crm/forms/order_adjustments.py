from decimal import Decimal

from django import forms
from django.utils import timezone

from crm.models import OrderComplaint, OrderRefund, OrderServiceCharge


class AffectedServiceField(forms.ModelChoiceField):
    def label_from_instance(self, charge):
        if charge.item_id:
            item = (
                f"Item {self.item_numbers[charge.item_id]} · {charge.item.product.name}"
            )
        else:
            item = "Order extra"
        return f"{item} · {charge.service.name} (charge {charge.pk})"


class OrderAdjustmentForm(forms.ModelForm):
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    affected_service = AffectedServiceField(
        queryset=OrderServiceCharge.objects.none(),
        required=False,
        label="Affected service",
    )

    def __init__(self, *args, order, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial["revision"] = order.revision
        service = self.fields["affected_service"]
        service.queryset = order.charges.select_related(
            "service", "item__product"
        ).order_by("item_id", "pk")
        service.item_numbers = {
            pk: index
            for index, pk in enumerate(order.items.values_list("pk", flat=True), 1)
        }

    def save(self, commit=True):
        entry = super().save(commit=False)
        if "affected_service" in self.changed_data:
            entry.service_description = (
                self.fields["affected_service"].label_from_instance(
                    entry.affected_service
                )
                if entry.affected_service_id
                else ""
            )
        if commit:
            entry.save()
        return entry


class OrderComplaintForm(OrderAdjustmentForm):
    def clean(self):
        data = super().clean()
        if (
            not self.instance.pk
            and not data.get("logged")
            and any(
                data.get(field) for field in ("details", "outcome", "affected_service")
            )
        ):
            self.add_error("logged", "Check Complaint logged to save these details.")
        return data

    class Meta:
        model = OrderComplaint
        fields = ("logged", "details", "outcome", "affected_service")
        labels = {"logged": "Complaint logged", "details": "Complaint details"}
        widgets = {"details": forms.Textarea(attrs={"rows": 2, "data-order-notes": ""})}


class RefundAmountField(forms.DecimalField):
    def __init__(self):
        super().__init__(
            min_value=Decimal("0.01"),
            max_digits=22,
            decimal_places=2,
            label="Refund amount",
            widget=forms.NumberInput(attrs={"form": "order-refund-form"}),
        )


class OrderRefundAmountForm(forms.Form):
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    amount = RefundAmountField()

    def __init__(self, *args, order, refund, **kwargs):
        super().__init__(
            *args,
            auto_id="id_refund_%s",
            initial={"revision": order.revision, "amount": refund.amount},
            **kwargs,
        )


class OrderRefundForm(OrderAdjustmentForm):
    amount = RefundAmountField()
    amount_received = forms.DecimalField(
        min_value=Decimal("0.01"),
        max_digits=22,
        decimal_places=2,
        label="Amount originally paid",
        help_text="Confirm this amount for the first refund.",
    )
    refunded_on = forms.DateField(
        required=False,
        label="Refund date",
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )

    def __init__(self, *args, order, **kwargs):
        kwargs.setdefault("auto_id", "id_refund_%s")
        super().__init__(*args, order=order, **kwargs)
        self.initial["refunded_on"] = timezone.localdate()
        if order.refund_amount_received is not None:
            del self.fields["amount_received"]
        elif not self.is_bound and order.payment_status == order.PaymentStatus.PAID:
            self.initial["amount_received"] = order.total or None
        for field in self.fields.values():
            field.widget.attrs["form"] = "order-refund-form"

    def clean_refunded_on(self):
        today = timezone.localdate()
        refunded_on = self.cleaned_data["refunded_on"] or today
        if refunded_on > today:
            raise forms.ValidationError("Enter the date the refund was given.")
        return refunded_on

    class Meta:
        model = OrderRefund
        fields = (
            "amount_received",
            "amount",
            "refunded_on",
            "reason",
            "affected_service",
        )
        widgets = {
            "reason": forms.Textarea(attrs={"rows": 2}),
        }
