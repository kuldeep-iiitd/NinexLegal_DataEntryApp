
from django import forms
from django.contrib.auth.models import User
from .models import CaseType, Branch, BranchCaseType, Bank, Employee, Case, CaseUpdate

class CaseCreationForm(forms.ModelForm):
    documents_present = forms.BooleanField(
        required=False,
        label="Are documents present?",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    assigned_advocate = forms.ModelChoiceField(
        queryset=Employee.objects.filter(employee_type='advocate', is_active=True),
        required=False,
        empty_label="Select an Advocate",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = Case
        fields = ['applicant_name', 'case_number', 'bank', 'case_type', 'documents_present', 'assigned_advocate']
        widgets = {
            'applicant_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter applicant name'}),
            'case_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter case number'}),
            'bank': forms.Select(attrs={'class': 'form-control'}),
            'case_type': forms.Select(attrs={'class': 'form-control'}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['bank'].queryset = Bank.objects.all()
        self.fields['case_type'].queryset = CaseType.objects.all()
        
        # Make advocate field conditional
        if self.data.get('documents_present'):
            self.fields['assigned_advocate'].required = True
        else:
            self.fields['assigned_advocate'].required = False
            
    def clean(self):
        cleaned_data = super().clean()
        documents_present = cleaned_data.get('documents_present')
        assigned_advocate = cleaned_data.get('assigned_advocate')
        
        if documents_present and not assigned_advocate:
            raise forms.ValidationError("Please select an advocate when documents are present.")
            
        return cleaned_data

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

class BankForm(forms.ModelForm):
    class Meta:
        model = Bank
        fields = ['name']

class CaseTypeForm(forms.ModelForm):
    class Meta:
        model = CaseType
        fields = ['name']

class BranchForm(forms.ModelForm):
    class Meta:
        model = Branch
        fields = ['bank', 'name', 'branch_code', 'address']

class BranchCaseTypeForm(forms.ModelForm):
    class Meta:
        model = BranchCaseType
        fields = ['case_type', 'fee']
        
class EmployeeForm(forms.ModelForm):
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
        fields = ['name', 'employee_id', 'aadhar', 'mobile', 'email', 'employee_type']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter full name'}),
            'employee_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter unique employee ID'}),
            'aadhar': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Aadhar number'}),
            'mobile': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter mobile number'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter email address'}),
            'employee_type': forms.Select(attrs={'class': 'form-control'}),
        }
        
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError(f"Username '{username}' is already taken. Please choose a different username.")
        return username
        
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
        
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if password and confirm_password:
            if password != confirm_password:
                raise forms.ValidationError("Passwords do not match. Please ensure both password fields are identical.")
        
        return cleaned_data
        
class EmployeeEditForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ['name', 'aadhar', 'mobile', 'email', 'employee_type', 'is_active']


class AdditionalCaseAddressForm(forms.Form):
    property_address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'w-full border rounded p-2',
            'rows': 3
        })
    )

class CaseWorkForm(forms.ModelForm):
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
    state = forms.ChoiceField(
        choices=STATE_CHOICES, 
        widget=forms.Select(attrs={
            'class': 'w-full border rounded p-2',
        })
    )
    
    class Meta:
        model = Case
        fields = ['property_address','state','district','tehsil','branch','reference_name','case_name']
        widgets = {
            'property_address': forms.Textarea(attrs={
                'class': 'w-full border rounded p-2',
                'rows': 3
            }),
            # state uses select via field declaration above
            'district': forms.TextInput(attrs={
                'class': 'w-full border rounded p-2'
            }),
            'tehsil': forms.TextInput(attrs={
                'class': 'w-full border rounded p-2'
            }),
            'branch': forms.Select(attrs={
                'class': 'w-full border rounded p-2'
            }),
            'reference_name': forms.TextInput(attrs={
                'class': 'w-full border rounded p-2'
            }),
            'case_name': forms.TextInput(attrs={
                'class': 'w-full border rounded p-2'
            }),
        }

class CaseActionForm(forms.Form):
    action = forms.ChoiceField(choices=[
        ('query','Query'),
        ('hold','Hold'),
        ('document_hold','Document Hold'),
        ('positive','Positive'),
        ('negative','Negative')
    ], widget=forms.Select(attrs={
        'class': 'w-full border rounded p-2',
    }))
    remark = forms.CharField(
        required=False, 
        widget=forms.Textarea(attrs={
            'class': 'w-full border rounded p-2',
            'rows': 3,
            'placeholder': 'Enter your remarks here (required for Hold/Query/Document Hold)'
        })
    )
    forward_to_sro = forms.BooleanField(
        required=False, 
        label="Forward to SRO (for Negative)",
        widget=forms.CheckboxInput(attrs={
            'class': 'mr-2 border rounded'
        })
    )

    def clean(self):
        cd = super().clean()
        if cd.get('action') in ['hold', 'query', 'document_hold'] and not cd.get('remark', '').strip():
            self.add_error('remark', 'Remark is required when selecting Hold, Query, or Document Hold actions.')
        return cd
