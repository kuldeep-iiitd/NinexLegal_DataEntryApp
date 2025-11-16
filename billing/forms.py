from django import forms
from cases.models import CaseType, Case
from Bank.models import Bank, BankBranch


class BillingFilterForm(forms.Form):
    scope = forms.ChoiceField(
        choices=[
            ('bank', 'Bank'),
            ('branch', 'Branch'),
            ('date', 'Date Range'),
            ('month', 'Month'),
            ('day', 'Day'),
            ('financial_year', 'Financial Year'),
            ('custom', 'Custom selection'),
        ],
        initial='bank',
        required=True,
        label='How do you want to generate the bill?'
    )
    bank = forms.ModelChoiceField(queryset=Bank.objects.all(), required=False, label='Bank')
    branch = forms.ModelChoiceField(queryset=BankBranch.objects.all(), required=False, label='Branch')
    case_type = forms.ModelChoiceField(
        queryset=CaseType.objects.all(),
        required=False,
        label='Case type (optional)',
        help_text='Only case types configured for selected bank/branch will be used'
    )
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}), label='Date from')
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}), label='Date to')
    # Optional date range filter (always optional, applies in addition to scope)
    optional_date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}), label='Optional date from')
    optional_date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}), label='Optional date to')
    month = forms.IntegerField(min_value=1, max_value=12, required=False, label='Month')
    year = forms.IntegerField(min_value=2000, max_value=2100, required=False, label='Year')
    cases = forms.ModelMultipleChoiceField(
        queryset=Case.objects.all(),
        required=False,
        label='Pick cases',
        help_text='Select one or more cases to bill now',
        widget=forms.SelectMultiple(attrs={'class': 'w-full border rounded p-2 h-48'})
    )

    def clean(self):
        cleaned = super().clean()
        scope = cleaned.get('scope')
        # Validate only the relevant fields for the chosen scope
        if scope == 'bank':
            if not cleaned.get('bank'):
                self.add_error('bank', 'Select a bank')
        elif scope == 'branch':
            if not cleaned.get('branch'):
                self.add_error('branch', 'Select a branch')
        elif scope == 'date':
            if not cleaned.get('date_from') or not cleaned.get('date_to'):
                self.add_error('date_from', 'Select a start date')
                self.add_error('date_to', 'Select an end date')
        elif scope == 'month':
            if not cleaned.get('month') or not cleaned.get('year'):
                self.add_error('month', 'Provide month and year')
                self.add_error('year', 'Provide month and year')
        elif scope == 'day':
            if not cleaned.get('date_from'):
                self.add_error('date_from', 'Select a date')
        elif scope == 'financial_year':
            if not cleaned.get('year'):
                self.add_error('year', 'Provide starting financial year (e.g., 2025 for FY 25-26)')
        elif scope == 'custom':
            if not cleaned.get('cases'):
                self.add_error('cases', 'Pick at least one case')
        # If optional range both provided, ensure order
        of = cleaned.get('optional_date_from')
        ot = cleaned.get('optional_date_to')
        if of and ot and of > ot:
            self.add_error('optional_date_from', 'From date must be before To date')
            self.add_error('optional_date_to', 'To date must be after From date')
        return cleaned
