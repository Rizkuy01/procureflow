from django import forms
from django.forms import inlineformset_factory

from .models import PurchaseRequest, PurchaseRequestItem, Supplier, SupplierEvaluation


class PurchaseRequestForm(forms.ModelForm):
    class Meta:
        model = PurchaseRequest
        fields = ("title", "department", "purpose", "needed_by")
        widgets = {"needed_by": forms.DateInput(attrs={"type": "date"})}


class PurchaseRequestItemForm(forms.ModelForm):
    class Meta:
        model = PurchaseRequestItem
        fields = ("description", "item_type", "quantity", "unit", "estimated_unit_price", "proposed_supplier_name")


PurchaseRequestItemFormSet = inlineformset_factory(
    PurchaseRequest,
    PurchaseRequestItem,
    form=PurchaseRequestItemForm,
    extra=0,
    min_num=1,
    validate_min=True,
    can_delete=True,
)


class DecisionForm(forms.Form):
    decision = forms.ChoiceField(
        choices=(
            ("approved", "Setujui"),
            ("rejected", "Tolak"),
            ("returned", "Kembalikan untuk koreksi"),
        )
    )
    comment = forms.CharField(widget=forms.Textarea, required=False)


class SupplierEvaluationForm(forms.ModelForm):
    class Meta:
        model = SupplierEvaluation
        fields = (
            "supplier",
            "price_score",
            "quality_score",
            "lead_time_score",
            "compliance_score",
            "notes",
        )
        widgets = {
            "notes": forms.Textarea,
        }

    def __init__(self, *args, request_obj=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supplier"].queryset = Supplier.objects.filter(is_active=True)
        self.request_obj = request_obj


class SupplierSelectionForm(forms.Form):
    final_supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.none(),
        empty_label="Pilih supplier final",
    )

    def __init__(self, *args, request_obj=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["final_supplier"].queryset = Supplier.objects.filter(
            is_active=True,
            evaluations__request=request_obj,
        ).distinct()


class ReceiptForm(forms.Form):
    purchase_order_item = forms.IntegerField(widget=forms.HiddenInput())
    received_quantity = forms.DecimalField(min_value=0.01, decimal_places=2, max_digits=12)
    notes = forms.CharField(widget=forms.Textarea, required=False)


class CancellationForm(forms.Form):
    reason = forms.CharField(
        label="Alasan pembatalan",
        widget=forms.Textarea,
        min_length=5,
    )


class DiscrepancyForm(forms.Form):
    description = forms.CharField(widget=forms.Textarea, min_length=5)


class ResolutionForm(forms.Form):
    resolution_notes = forms.CharField(
        label="Catatan penyelesaian",
        widget=forms.Textarea,
        min_length=5,
    )
