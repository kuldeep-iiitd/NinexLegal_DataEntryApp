
from django import forms
from django.contrib.auth.models import User
from .models import CaseType, Employee, Case, CaseUpdate, State, District, Tehsil, CaseWork
from Bank.models import Bank as ExternalBank, BankBranch

class CaseCreationForm(forms.ModelForm):
    documents_present = forms.BooleanField(
        required=False,
        label="Are documents present?",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    is_quotation = forms.BooleanField(
        required=False,
        label="Is this only a quotation (no documents yet)?",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'hx-change': 'toggleQuotation(this)'})
    )

    quotation_price = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        label="Quoted Price",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter quoted price'})
    )
    
    assigned_advocate = forms.ModelChoiceField(
        queryset=Employee.objects.filter(employee_type='advocate', is_active=True),
        required=False,
        empty_label="Select an Advocate",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    assign_to_admin = forms.BooleanField(
        required=False,
        label="Assign to Admin (AD)",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    class Meta:
        model = Case
        fields = ['applicant_name', 'case_number', 'bank', 'case_type', 'is_quotation', 'quotation_price', 'documents_present', 'assigned_advocate']
        widgets = {
            'applicant_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter applicant name'}),
            'case_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter case number'}),
            'bank': forms.Select(attrs={'class': 'form-control'}),
            'case_type': forms.Select(attrs={'class': 'form-control'}),
        }
    
class CaseWorkCreateForm(forms.ModelForm):
    class Meta:
        model = CaseWork
        fields = ['case_type', 'document', 'notes']
        widgets = {
            'notes': forms.TextInput(attrs={'placeholder': 'Optional notes'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure the document is mandatory
        self.fields['document'].required = True
        # Limit case_type choices to all defined case types; can be narrowed in view if needed
        self.fields['case_type'].queryset = CaseType.objects.all().order_by('name')

class CaseAssignmentForm(forms.ModelForm):
    """Form for assigning cases to advocates when documents become available"""
    assigned_advocate = forms.ModelChoiceField(
        queryset=Employee.objects.filter(employee_type='advocate', is_active=True),
        empty_label="Select an Advocate",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = Case
        fields = ['assigned_advocate']
        
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.documents_present = True
        # Change status to 'pending' when an advocate is assigned
        # This moves it from 'pending_assignment' to 'pending'
        instance.status = 'pending'
        if commit:
            instance.save()
        return instance

class ReassignCaseAdvocateForm(forms.ModelForm):
    """Admin-only form to reassign a case to the same or a different advocate.
    Options:
    - apply_to_children: also reassign all child cases
    - set_pending: if checked and case is in a finalized state, move back to 'pending' for new work
    """
    assigned_advocate = forms.ModelChoiceField(
        queryset=Employee.objects.filter(employee_type='advocate', is_active=True),
        empty_label="Select an Advocate",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    # Simplified: only select a new advocate; reassignment always cascades to children and preserves status.

    class Meta:
        model = Case
        fields = ['assigned_advocate']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Preselect current advocate in the dropdown
        if getattr(self.instance, 'assigned_advocate_id', None):
            self.fields['assigned_advocate'].initial = self.instance.assigned_advocate_id

class QuotationFinalizeForm(forms.ModelForm):
    quotation_price = forms.DecimalField(
        required=True,
        max_digits=10,
        decimal_places=2,
        label="Final Quotation Price",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter final agreed price'})
    )
    documents_present = forms.BooleanField(
        required=True,
        label="All required documents are now present",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    assigned_advocate = forms.ModelChoiceField(
        queryset=Employee.objects.filter(employee_type='advocate', is_active=True),
        required=True,
        empty_label="Select Advocate",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    confirm = forms.BooleanField(
        required=True,
        label="I confirm quotation is final and documents are verified",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = Case
        fields = ['quotation_price', 'documents_present', 'assigned_advocate']

    def clean(self):
        cd = super().clean()
        if not cd.get('confirm'):
            raise forms.ValidationError('You must confirm the quotation is final and documents are present.')
        return cd

STATE_CHOICES = [
    ('Andhra Pradesh','Andhra Pradesh'),
    ('Arunachal Pradesh','Arunachal Pradesh'),
    ('Assam','Assam'),
    ('Bihar','Bihar'),
    ('Chhattisgarh','Chhattisgarh'),
    ('Goa','Goa'),
    ('Gujarat','Gujarat'),
    ('Haryana','Haryana'),
    ('Himachal Pradesh','Himachal Pradesh'),
    ('Jharkhand','Jharkhand'),
    ('Karnataka','Karnataka'),
    ('Kerala','Kerala'),
    ('Madhya Pradesh','Madhya Pradesh'),
    ('Maharashtra','Maharashtra'),
    ('Manipur','Manipur'),
    ('Meghalaya','Meghalaya'),
    ('Mizoram','Mizoram'),
    ('Nagaland','Nagaland'),
    ('Odisha','Odisha'),
    ('Punjab','Punjab'),
    ('Rajasthan','Rajasthan'),
    ('Sikkim','Sikkim'),
    ('Tamil Nadu','Tamil Nadu'),
    ('Telangana','Telangana'),
    ('Tripura','Tripura'),
    ('Uttar Pradesh','Uttar Pradesh'),
    ('Uttarakhand','Uttarakhand'),
    ('West Bengal','West Bengal'),
    ('Andaman and Nicobar Islands','Andaman and Nicobar Islands'),
    ('Chandigarh','Chandigarh'),
    ('Dadra and Nagar Haveli and Daman and Diu','Dadra and Nagar Haveli and Daman and Diu'),
    ('Delhi','Delhi'),
    ('Jammu and Kashmir','Jammu and Kashmir'),
    ('Ladakh','Ladakh'),
    ('Lakshadweep','Lakshadweep'),
    ('Puducherry','Puducherry'),
]

"""Deprecated legacy bank forms removed; Bank app forms should be used instead."""

from django.forms import modelformset_factory
"""Legacy BankDocument formset removed; use Bank app for document handling."""

# BankExtraFee and related forms removed (deprecated extra charges feature)

class BankCaseTypeForm(forms.Form):
    """Placeholder removed; use Bank app fee management."""
    pass

class CaseTypeForm(forms.ModelForm):
    class Meta:
        model = CaseType
        fields = ['name']

class BranchForm(forms.ModelForm):
    class Meta:
        model = BankBranch
        fields = ['bank', 'state', 'name', 'branch_code', 'address']

        
class EmployeeForm(forms.ModelForm):
    initials = forms.CharField(
        max_length=2,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., AB'
        }),
        help_text="Two-letter initials (optional, letters only)"
    )
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter unique username'
        }),
        help_text="Username must be unique and cannot be changed later."
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter password'
        })
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm password'
        }),
        label="Confirm Password"
    )
    
    class Meta:
        model = Employee
        fields = ['name', 'employee_id', 'mobile', 'email', 'initials', 'employee_type', 'aadhaar_number', 'pan_number']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter full name'}),
            'employee_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter unique employee ID'}),
            'mobile': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter mobile number'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter email address'}),
            'employee_type': forms.Select(attrs={'class': 'form-control'}),
            'aadhaar_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '12-digit Aadhaar number'}),
            'pan_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'PAN (AAAAA9999A)'}),
        }

    def clean_gst_number(self):
        gst = (self.cleaned_data.get('gst_number') or '').strip().upper()
        if not gst:
            return gst
        import re
        # Basic GSTIN pattern: 2 digits(state) + 10 PAN + 1 entity + 1 Z + 1 checksum
        if not re.match(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$', gst):
            raise forms.ValidationError('Enter a valid GSTIN (15 characters).')
        return gst
        
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError(f"Username '{username}' is already taken. Please choose a different username.")
        return username
    
    def clean_initials(self):
        ini = (self.cleaned_data.get('initials') or '').strip()
        if not ini:
            return ini
        if len(ini) != 2 or not ini.isalpha():
            raise forms.ValidationError('Enter exactly two letters for initials (A-Z).')
        ini = ini.upper()
        if Employee.objects.filter(initials__iexact=ini).exists():
            raise forms.ValidationError(f"Initials '{ini}' are already assigned to another employee.")
        return ini
        
    def clean_employee_id(self):
        employee_id = self.cleaned_data.get('employee_id')
        if Employee.objects.filter(employee_id=employee_id).exists():
            raise forms.ValidationError(f"Employee ID '{employee_id}' already exists. Please use a unique Employee ID.")
        return employee_id
        
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError(f"Email '{email}' is already registered. Please use a different email.")
        return email

    def clean_aadhaar_number(self):
        aadhaar = (self.cleaned_data.get('aadhaar_number') or '').strip()
        if not aadhaar:
            return aadhaar
        if not aadhaar.isdigit() or len(aadhaar) != 12:
            raise forms.ValidationError('Enter a valid 12-digit Aadhaar number (digits only).')
        return aadhaar

    def clean_pan_number(self):
        pan = (self.cleaned_data.get('pan_number') or '').strip().upper()
        if not pan:
            return pan
        import re
        if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]$', pan):
            raise forms.ValidationError('Enter a valid PAN in format AAAAA9999A.')
        return pan
        
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if password and confirm_password:
            if password != confirm_password:
                raise forms.ValidationError("Passwords do not match. Please ensure both password fields are identical.")
        
        return cleaned_data
        
from .models import EmployeeDocument
EmployeeDocumentFormSet = modelformset_factory(
    EmployeeDocument,
    fields=('name', 'file'),
    extra=1,
    can_delete=True,
    widgets={
        'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Document Name'}),
        'file': forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf,.doc,.docx,.jpg,.jpeg,.png,.gif,.webp,.xls,.xlsx,.txt'}),
    }
)

class EmployeeEditForm(forms.ModelForm):
    initials = forms.CharField(
        max_length=2,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., AB'
        }),
        help_text="Two-letter initials (optional, letters only)"
    )
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter username'
        }),
        help_text="Username for login access."
    )
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Leave blank to keep current password'
        }),
        help_text="Leave blank to keep current password."
    )
    confirm_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm new password'
        }),
        label="Confirm Password"
    )
    
    class Meta:
        model = Employee
        fields = ['name', 'employee_id', 'mobile', 'email', 'initials', 'employee_type', 'is_active', 'aadhaar_number', 'pan_number']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter full name'}),
            'employee_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter employee ID'}),
            'mobile': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter mobile number'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter email address'}),
            'employee_type': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'aadhaar_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '12-digit Aadhaar number'}),
            'pan_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'PAN (AAAAA9999A)'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self.instance, 'user') and self.instance.user:
            self.fields['username'].initial = self.instance.user.username
        # Pre-fill initials
        if hasattr(self.instance, 'initials'):
            self.fields['initials'].initial = self.instance.initials
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if hasattr(self.instance, 'user') and self.instance.user:
            # Check if username is changed and if new username already exists
            if username != self.instance.user.username and User.objects.filter(username=username).exists():
                raise forms.ValidationError(f"Username '{username}' is already taken.")
        return username
        
    def clean_employee_id(self):
        employee_id = self.cleaned_data.get('employee_id')
        # Check if employee_id is changed and if new employee_id already exists
        if employee_id != self.instance.employee_id and Employee.objects.filter(employee_id=employee_id).exists():
            raise forms.ValidationError(f"Employee ID '{employee_id}' already exists.")
        return employee_id
        
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if hasattr(self.instance, 'user') and self.instance.user:
            # Check if email is changed and if new email already exists
            if email != self.instance.user.email and User.objects.filter(email=email).exists():
                raise forms.ValidationError(f"Email '{email}' is already registered.")
        return email
    
    def clean_initials(self):
        ini = (self.cleaned_data.get('initials') or '').strip()
        if not ini:
            return ini
        if len(ini) != 2 or not ini.isalpha():
            raise forms.ValidationError('Enter exactly two letters for initials (A-Z).')
        ini = ini.upper()
        # Allow same initials if unchanged for this employee
        if self.instance and self.instance.initials and self.instance.initials.upper() == ini:
            return ini
        if Employee.objects.filter(initials__iexact=ini).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(f"Initials '{ini}' are already assigned to another employee.")
        return ini
        
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if password and confirm_password:
            if password != confirm_password:
                raise forms.ValidationError("Passwords do not match.")
        elif password and not confirm_password:
            raise forms.ValidationError("Please confirm the new password.")
        elif confirm_password and not password:
            raise forms.ValidationError("Please enter the new password.")
        
        return cleaned_data

    def clean_aadhaar_number(self):
        aadhaar = (self.cleaned_data.get('aadhaar_number') or '').strip()
        if not aadhaar:
            return aadhaar
        if not aadhaar.isdigit() or len(aadhaar) != 12:
            raise forms.ValidationError('Enter a valid 12-digit Aadhaar number (digits only).')
        return aadhaar

    def clean_pan_number(self):
        pan = (self.cleaned_data.get('pan_number') or '').strip().upper()
        if not pan:
            return pan
        import re
        if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]$', pan):
            raise forms.ValidationError('Enter a valid PAN in format AAAAA9999A.')
        return pan


class AdditionalCaseAddressForm(forms.Form):
    property_address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'w-full border rounded p-2',
            'rows': 3
        })
    )

class CaseDetailsForm(forms.ModelForm):
    # Flag to trigger duplicate check for school cases
    is_school_case = forms.BooleanField(
        required=False,
        label="This is a school case (check duplicates)",
        widget=forms.CheckboxInput(attrs={'class': 'mr-2'})
    )
    state = forms.ChoiceField(
        choices=[],
        widget=forms.Select(attrs={'class': 'w-full border rounded p-2'})
    )
    
    class Meta:
        model = Case
        fields = ['property_address','state','district','tehsil','branch']
        widgets = {
            'property_address': forms.Textarea(attrs={
                'class': 'w-full border rounded p-2',
                'rows': 3
            }),
            # state uses select via field declaration above
            'district': forms.Select(attrs={'class': 'w-full border rounded p-2'}),
            'tehsil': forms.Select(attrs={'class': 'w-full border rounded p-2'}),
            'branch': forms.Select(attrs={
                'class': 'w-full border rounded p-2'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate dynamic state choices from master State; fallback to static if empty
        state_choices = [(s.name, s.name) for s in State.objects.order_by('name')]
        if not state_choices:
            # Fallback to global STATE_CHOICES declared earlier in this module
            try:
                from .forms import STATE_CHOICES as GLOBAL_STATE_CHOICES  # circular guard; safe due to same module
            except Exception:
                GLOBAL_STATE_CHOICES = []
            state_choices = GLOBAL_STATE_CHOICES
        # Ensure current instance state appears in list even if not in master
        inst = kwargs.get('instance') or getattr(self, 'instance', None)
        if inst and inst.state and (inst.state, inst.state) not in state_choices:
            state_choices = [(inst.state, inst.state)] + state_choices
        self.fields['state'].choices = [('', 'Select State')] + state_choices

        # Limit branch choices to the branches of the case's bank
        instance = kwargs.get('instance') or getattr(self, 'instance', None)
        case_bank = getattr(instance, 'bank', None) if instance else None
        if case_bank is not None:
            # Determine chosen state from POST data (preferred) or instance
            selected_state_name = None
            if self.is_bound:
                selected_state_name = (self.data.get('state') or '').strip() or None
            if not selected_state_name and getattr(instance, 'state', None):
                selected_state_name = instance.state
            if selected_state_name:
                sel = (selected_state_name or '').strip()
                self.fields['branch'].queryset = BankBranch.objects.filter(bank=case_bank, state__name__iexact=sel)
            else:
                self.fields['branch'].queryset = BankBranch.objects.filter(bank=case_bank)
        else:
            self.fields['branch'].queryset = BankBranch.objects.none()
    def save(self, commit=True):
        instance = super().save(commit=False)
        # Persist school case flag
        instance.is_school_case = bool(self.cleaned_data.get('is_school_case'))
        # Safety: ensure branch selected matches chosen state
        sel_branch = self.cleaned_data.get('branch')
        sel_state = self.cleaned_data.get('state')
        if sel_branch and sel_state and sel_branch.state and sel_branch.state.name != sel_state:
            # Invalidate branch selection if mismatch
            self.add_error('branch', 'Selected branch does not belong to the chosen state.')
            raise forms.ValidationError('Branch/state mismatch.')
        if commit:
            instance.save()
        return instance

class CaseActionForm(forms.Form):
    action = forms.ChoiceField(choices=[
        ('draft','Draft'),
        ('query','Query'),
        ('positive_subject_tosearch','Positive Subject to Search'),
        ('draft_positive_subject_tosearch','Draft Positive Subject to Search'),
        ('positive','Positive'),
        ('negative','Negative')
    ], widget=forms.Select(attrs={'class': 'w-full border rounded p-2'}))
    remark = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'w-full border rounded p-2',
            'rows': 3,
            'placeholder': 'Enter your remarks here (required for On Hold)'
        })
    )
    forward_to_sro = forms.BooleanField(
        required=False,
        label="Forward to SRO now (auto for Positive Subject to Search)",
        widget=forms.CheckboxInput(attrs={'class': 'mr-2 border rounded'})
    )
    # forward_to_sro removed; forwarding handled automatically in the view logic
    # Document upload is handled in a dedicated step after finalization

    def clean(self):
        cd = super().clean()
        return cd

    def __init__(self, *args, **kwargs):
        # Allow passing a case for context
        self_case = kwargs.pop('case', None)
        super().__init__(*args, **kwargs)
        # Keep case for LRN validation
        self._case = self_case


class ChildCaseForm(forms.Form):
    property_address = forms.CharField(required=False, widget=forms.Textarea(attrs={'class':'w-full border rounded p-2','rows':2}))
    # choices will be set dynamically in __init__ from DB (fallback to static)
    state = forms.ChoiceField(required=False, choices=[], widget=forms.Select(attrs={'class':'w-full border rounded p-2'}))
    district = forms.CharField(required=False, widget=forms.Select(attrs={'class':'w-full border rounded p-2'}))
    tehsil = forms.CharField(required=False, widget=forms.Select(attrs={'class':'w-full border rounded p-2'}))
    branch = forms.ModelChoiceField(required=False, queryset=BankBranch.objects.all(), widget=forms.Select(attrs={'class':'w-full border rounded p-2'}))
    # Allow setting initial child status and uploading a document at creation
    initial_status = forms.ChoiceField(required=False, choices=[], widget=forms.Select(attrs={'class':'w-full border rounded p-2'}))
    supporting_document = forms.FileField(required=False, label="Upload Document (PDF/DOC/Image)", widget=forms.ClearableFileInput(attrs={'accept':'.pdf,.doc,.docx,image/*','class':'w-full border rounded p-2'}))
    document_description = forms.CharField(required=False, max_length=255, widget=forms.TextInput(attrs={'class':'w-full border rounded p-2','placeholder':'Optional description'}))

    def __init__(self, *args, **kwargs):
        parent_case = kwargs.pop('parent_case', None)
        super().__init__(*args, **kwargs)
        # Build state choices from DB; fallback to static if empty
        state_choices = [(s.name, s.name) for s in State.objects.order_by('name')]
        if not state_choices:
            try:
                from .forms import STATE_CHOICES as GLOBAL_STATE_CHOICES  # same module; safe
            except Exception:
                GLOBAL_STATE_CHOICES = []
            state_choices = GLOBAL_STATE_CHOICES
        # Ensure parent's state appears in choices even if not in DB/static
        if parent_case and parent_case.state and (parent_case.state, parent_case.state) not in state_choices:
            state_choices = [(parent_case.state, parent_case.state)] + state_choices
        self.fields['state'].choices = [('', 'Select State')] + state_choices

        if parent_case and parent_case.bank_id:
            # Determine selected state (POST preferred, else parent state)
            selected_state = None
            if self.is_bound:
                selected_state = (self.data.get('state') or '').strip() or None
            if not selected_state and getattr(parent_case, 'state', None):
                selected_state = parent_case.state
            if selected_state:
                self.fields['branch'].queryset = BankBranch.objects.filter(bank=parent_case.bank, state__name__iexact=selected_state)
            else:
                self.fields['branch'].queryset = BankBranch.objects.filter(bank=parent_case.bank)
        # Preselect parent's values for convenience
        if parent_case:
            if parent_case.state:
                self.fields['state'].initial = parent_case.state
            if parent_case.district:
                self.fields['district'].initial = parent_case.district
                self.fields['district'].widget.attrs['data-initial'] = parent_case.district
            if parent_case.tehsil:
                self.fields['tehsil'].initial = parent_case.tehsil
                self.fields['tehsil'].widget.attrs['data-initial'] = parent_case.tehsil
        # Populate status choices from Case model
        try:
            allowed = {'draft','query','positive','negative','positive_subject_tosearch'}
            filtered = [c for c in Case.STATUS_CHOICES if c[0] in allowed]
            self.fields['initial_status'].choices = [('', 'Select Status')] + filtered
        except Exception:
            self.fields['initial_status'].choices = [
                ('', 'Select Status'),
                ('draft','Draft'),
                ('query','Query'),
                ('positive','Positive'),
                ('negative','Negative'),
                ('positive_subject_to_search','Positive Subject to Search'),
            ]

    def clean(self):
        cd = super().clean()
        branch = cd.get('branch')
        state = cd.get('state') or None
        # If a state is chosen, ensure branch belongs to that state
        if branch and state and branch.state and branch.state.name.lower() != state.lower():
            self.add_error('branch', 'Selected branch does not belong to the chosen state.')
        # Validate document if provided (optional for all statuses)
        f = self.files.get('supporting_document')
        if f:
            if hasattr(f, 'size') and f.size > 5 * 1024 * 1024:
                self.add_error('supporting_document', 'File too large (max 5MB).')
            allowed = [
                'application/pdf',
                'image/jpeg','image/png','image/gif','image/webp',
                'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            ]
            if hasattr(f, 'content_type') and f.content_type not in allowed:
                self.add_error('supporting_document', 'Unsupported file type. Upload PDF, DOC/DOCX, or image.')
        return cd


class CaseDocumentUploadForm(forms.Form):
    supporting_document = forms.FileField(
        required=True,
        label="Upload Supporting Document (PDF/DOC/Image)",
        widget=forms.ClearableFileInput(attrs={'accept':'.pdf,.doc,.docx,image/*','class':'w-full border rounded p-2'})
    )
    document_description = forms.CharField(
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={'class':'w-full border rounded p-2','placeholder':'Optional description'})
    )

    def clean(self):
        cd = super().clean()
        f = self.files.get('supporting_document')
        if not f:
            self.add_error('supporting_document', 'Supporting document is required.')
        else:
            if f.size > 5 * 1024 * 1024:
                self.add_error('supporting_document', 'File too large (max 5MB).')
            allowed = [
                'application/pdf',
                'image/jpeg','image/png','image/gif','image/webp',
                'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            ]
            if hasattr(f, 'content_type') and f.content_type not in allowed:
                self.add_error('supporting_document', 'Unsupported file type. Upload PDF, DOC/DOCX, or image.')
        return cd


class FinalizeWithDocumentForm(forms.Form):
    supporting_document = forms.FileField(
        required=True,
        label="Final Document (PDF/DOC/Image)",
        widget=forms.ClearableFileInput(attrs={'accept':'.pdf,.doc,.docx,image/*','class':'w-full border rounded p-2'})
    )
    document_description = forms.CharField(
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={'class':'w-full border rounded p-2','placeholder':'Optional description'})
    )
    # Optional status selector; views may override or hide via force_status
    status = forms.ChoiceField(
        required=False,
        choices=[('positive','Positive'),('negative','Negative'),('positive_subject_tosearch','Positive Subject to Search'),('query','Query'),('draft','Draft')],
        widget=forms.Select(attrs={'class':'w-full border rounded p-2'})
    )
    remark = forms.CharField(
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={'class':'w-full border rounded p-2','placeholder':'Optional remark'})
    )

    def clean(self):
        cd = super().clean()
        f = self.files.get('supporting_document')
        if not f:
            self.add_error('supporting_document', 'Supporting document is required.')
        else:
            if hasattr(f, 'size') and f.size > 5 * 1024 * 1024:
                self.add_error('supporting_document', 'File too large (max 5MB).')
            allowed = [
                'application/pdf',
                'image/jpeg','image/png','image/gif','image/webp',
                'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            ]
            if hasattr(f, 'content_type') and f.content_type not in allowed:
                self.add_error('supporting_document', 'Unsupported file type. Upload PDF, DOC/DOCX, or image.')
        return cd


class StateForm(forms.ModelForm):
    class Meta:
        model = State
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full border rounded p-2', 'placeholder': 'State name'}),
        }

    def clean_name(self):
        name = (self.cleaned_data.get('name') or '').strip()
        if not name:
            raise forms.ValidationError('State name is required.')
        qs = State.objects.filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('A state with this name already exists.')
        return name


class DistrictForm(forms.ModelForm):
    class Meta:
        model = District
        fields = ['state', 'name']
        widgets = {
            'state': forms.Select(attrs={'class': 'w-full border rounded p-2'}),
            'name': forms.TextInput(attrs={'class': 'w-full border rounded p-2', 'placeholder': 'District name'}),
        }

    def clean(self):
        cd = super().clean()
        state = cd.get('state')
        name = (cd.get('name') or '').strip()
        if not state or not name:
            return cd
        qs = District.objects.filter(state=state, name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            self.add_error('name', 'This district already exists in the selected state.')
        cd['name'] = name
        return cd


class TehsilForm(forms.ModelForm):
    # Non-model helper field to drive district filtering
    state = forms.ModelChoiceField(
        required=False,
        queryset=State.objects.none(),
        widget=forms.Select(attrs={'class': 'w-full border rounded p-2'})
    )
    class Meta:
        model = Tehsil
        fields = ['district', 'name']
        widgets = {
            'district': forms.Select(attrs={'class': 'w-full border rounded p-2'}),
            'name': forms.TextInput(attrs={'class': 'w-full border rounded p-2', 'placeholder': 'Tehsil/Taluk/Mandal name'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate state choices
        self.fields['state'].queryset = State.objects.order_by('name')
        selected_state = None
        # Derive selected state from POST data first
        if self.is_bound:
            try:
                state_id = self.data.get('state')
                if state_id:
                    selected_state = State.objects.filter(pk=int(state_id)).first()
            except (TypeError, ValueError):
                selected_state = None
        # If not bound or not provided, infer from instance
        if not selected_state and getattr(self.instance, 'pk', None) and getattr(self.instance, 'district_id', None):
            try:
                selected_state = self.instance.district.state
            except Exception:
                selected_state = None
        # Set initial for state if inferred
        if selected_state:
            self.fields['state'].initial = selected_state.pk
            self.fields['district'].queryset = District.objects.filter(state=selected_state).order_by('name')
        else:
            self.fields['district'].queryset = District.objects.select_related('state').order_by('state__name', 'name')

    def clean(self):
        cd = super().clean()
        district = cd.get('district')
        state = cd.get('state')
        name = (cd.get('name') or '').strip()
        if not district or not name:
            return cd
        qs = Tehsil.objects.filter(district=district, name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            self.add_error('name', 'This tehsil already exists under the selected district.')
        cd['name'] = name
        # Validate district belongs to selected state if state provided
        if state and district and district.state_id != state.id:
            self.add_error('district', 'Selected district does not belong to the chosen state.')
        return cd

class SROUpdateForm(forms.Form):
    receipt_number = forms.CharField(required=False, max_length=50, widget=forms.TextInput(attrs={'class':'w-full border rounded p-2','placeholder':'Receipt number (optional)'}))
    receipt_amount = forms.DecimalField(required=True, max_digits=10, decimal_places=2, widget=forms.NumberInput(attrs={'class':'w-full border rounded p-2','placeholder':'Amount received'}))
    receipt_expense = forms.DecimalField(required=False, max_digits=10, decimal_places=2, widget=forms.NumberInput(attrs={'class':'w-full border rounded p-2','placeholder':'Receipt expense (optional)'}))
    supporting_document = forms.FileField(required=True, label="Upload Receipt (PDF/DOC/Image)", widget=forms.ClearableFileInput(attrs={'accept':'.pdf,.doc,.docx,image/*','class':'w-full border rounded p-2'}))
    document_description = forms.CharField(required=False, max_length=255, widget=forms.TextInput(attrs={'class':'w-full border rounded p-2','placeholder':'Optional description'}))

    def clean(self):
        cd = super().clean()
        f = self.files.get('supporting_document')
        if not f:
            self.add_error('supporting_document', 'Receipt document is required.')
        else:
            if f.size > 5 * 1024 * 1024:
                self.add_error('supporting_document', 'File too large (max 5MB).')
            allowed = [
                'application/pdf',
                'image/jpeg','image/png','image/gif','image/webp',
                'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            ]
            if hasattr(f, 'content_type') and f.content_type not in allowed:
                self.add_error('supporting_document', 'Unsupported file type. Upload PDF, DOC/DOCX, or image.')
        amt = cd.get('receipt_amount')
        if amt is not None and amt <= 0:
            self.add_error('receipt_amount', 'Amount must be greater than zero.')
        exp = cd.get('receipt_expense')
        if exp is not None and exp < 0:
            self.add_error('receipt_expense', 'Expense cannot be negative.')
        return cd


class SROScopeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ['is_super_sro', 'allowed_states', 'allowed_districts', 'allowed_tehsils']
        widgets = {
            'is_super_sro': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'allowed_states': forms.SelectMultiple(attrs={'class': 'form-control h-48'}),
            'allowed_districts': forms.SelectMultiple(attrs={'class': 'form-control h-48'}),
            'allowed_tehsils': forms.SelectMultiple(attrs={'class': 'form-control h-48'}),
        }
        help_texts = {
            'is_super_sro': 'If checked, this SRO can access all SRO cases in all locations.',
            'allowed_states': 'Limit access to selected States (leave empty for none).',
            'allowed_districts': 'Further restrict within picked States (optional).',
            'allowed_tehsils': 'Most specific restriction (optional).',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Order options for usability
        self.fields['allowed_states'].queryset = State.objects.order_by('name')
        self.fields['allowed_districts'].queryset = District.objects.select_related('state').order_by('state__name', 'name')
        self.fields['allowed_tehsils'].queryset = Tehsil.objects.select_related('district', 'district__state').order_by('district__state__name', 'district__name', 'name')
