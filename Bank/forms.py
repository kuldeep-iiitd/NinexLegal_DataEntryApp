from django import forms
from .models import Bank, BankStateCaseType, BankState, BankBranch, BankDocument
from cases.models import State, CaseType

class BankForm(forms.ModelForm):
    class Meta:
        model = Bank
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter bank name'})
        }

class BankStateCaseTypeForm(forms.ModelForm):
    state = forms.ModelChoiceField(queryset=State.objects.order_by('name'))
    casetype = forms.ModelChoiceField(queryset=CaseType.objects.order_by('name'), required=True)

    class Meta:
        model = BankStateCaseType
        fields = ["state", "casetype", "fees"]
        widgets = {
            'fees': forms.NumberInput(attrs={'step': '0.01', 'min': '0'})
        }

from django.forms import BaseInlineFormSet

class BaseBankFeeFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            # If there are already form-level errors, don't add more
            return
        
        seen_pairs = set()
        for i, form in enumerate(self.forms):
            if not hasattr(form, 'cleaned_data'):
                continue
            
            # IMPORTANT: Skip validation for forms marked for deletion
            if form.cleaned_data.get('DELETE'):
                continue
            
            state = form.cleaned_data.get('state')
            casetype = form.cleaned_data.get('casetype')
            fees = form.cleaned_data.get('fees')
            
            # Check if row is entirely empty (all fields blank)
            if not state and not casetype and fees is None:
                # entirely empty row - skip validation
                continue
            
            # If any field is filled, all required fields must be filled
            if not state:
                form.add_error('state', "State is required for each fee row.")
            if not casetype:
                form.add_error('casetype', "Case Type is required for each fee row.")
            if fees is None:
                form.add_error('fees', "Fee amount is required.")
            
            # Check for duplicates only if both state and casetype are present
            if state and casetype:
                key = (state.id, casetype.id)
                if key in seen_pairs:
                    form.add_error(None, f"Duplicate fee row for {state.name} / {casetype.name}.")
                seen_pairs.add(key)

class BankStatesForm(forms.Form):
    states = forms.ModelMultipleChoiceField(
        queryset=State.objects.order_by('name'),
        widget=forms.CheckboxSelectMultiple(
            attrs={'class': 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2'}
        )
    )

class BankBranchForm(forms.ModelForm):
    class Meta:
        model = BankBranch
        fields = ['state', 'name', 'branch_code', 'address']
        widgets = {
            'state': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Branch name'}),
            'branch_code': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Code (optional)'}),
            'address': forms.Textarea(attrs={'rows': 3, 'class': 'form-textarea', 'placeholder': 'Address (optional)'}),
        }

    

    def __init__(self, *args, **kwargs):
        bank = kwargs.pop('bank', None)
        super().__init__(*args, **kwargs)
        if bank is not None:
            state_ids = BankState.objects.filter(bank=bank).values_list('state_id', flat=True)
            self.fields['state'].queryset = State.objects.filter(id__in=state_ids).order_by('name')
        else:
            self.fields['state'].queryset = State.objects.none()
        self.fields['state'].required = True


class BankDocumentForm(forms.ModelForm):
    class Meta:
        model = BankDocument
        fields = ['name', 'file']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Document name'}),
            'file': forms.ClearableFileInput(attrs={'class': 'form-input'}),
        }




