from django.db import models
from django.contrib.auth.models import User

class CaseType(models.Model):
	name = models.CharField(max_length=100, unique=True)
	description = models.TextField(blank=True, null=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return self.name

class Bank(models.Model):
	name = models.CharField(max_length=100, unique=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return self.name

class Branch(models.Model):
	bank = models.ForeignKey(Bank, on_delete=models.CASCADE, related_name='branches')
	name = models.CharField(max_length=100)
	branch_code = models.CharField(max_length=20, unique=True)
	address = models.TextField(blank=True, null=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return f"{self.name} ({self.bank.name})"

class BranchCaseType(models.Model):
	branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='branch_case_types')
	case_type = models.ForeignKey(CaseType, on_delete=models.CASCADE, related_name='branch_case_types')
	fee = models.DecimalField(max_digits=10, decimal_places=2)

	class Meta:
		unique_together = ('branch', 'case_type')

	def __str__(self):
		return f"{self.branch.name} - {self.case_type.name}: {self.fee}"



class Employee(models.Model):
	ADVOCATE = 'advocate'
	SRO = 'sro'
	ADMIN = 'admin'
	EMPLOYEE_TYPE_CHOICES = [
		(ADVOCATE, 'Advocate'),
		(SRO, 'SRO'),
		(ADMIN, 'Admin'),
	]

	user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee')
	name = models.CharField(max_length=100)
	employee_id = models.CharField(max_length=20, unique=True)
	aadhar = models.CharField(max_length=12, blank=True, null=True)
	mobile = models.CharField(max_length=15)
	email = models.EmailField()
	employee_type = models.CharField(max_length=10, choices=EMPLOYEE_TYPE_CHOICES)
	is_active = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return f"{self.name} ({self.employee_id}) - {self.get_employee_type_display()}"
		
	class Meta:
		verbose_name = "Employee"
		verbose_name_plural = "Employees"


class Case(models.Model):
	STATUS_CHOICES = [
		('positive', 'Positive'),
		('negative', 'Negative'),
		('on_hold', 'On Hold'),
		('on_query', 'On Query'),
		('document_pending', 'Document Pending'),
		('positive_subject_tosearch', 'Positive Subject to Search'),
		('pending_assignment', 'Pending Assignment'),
		('pending', 'Pending'),
	]

	# Basic Case Information
	applicant_name = models.CharField(max_length=200)
	case_number = models.CharField(max_length=100, unique=True)
	bank = models.ForeignKey(Bank, on_delete=models.PROTECT, related_name='cases')
	case_type = models.ForeignKey(CaseType, on_delete=models.PROTECT, related_name='cases')
	
	# Document Status
	documents_present = models.BooleanField(default=False)
	
	# Assignment Information
	assigned_advocate = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name='assigned_cases', blank=True, null=True, limit_choices_to={'employee_type': 'advocate'})
	
	# Status and Tracking
	status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)
	
	# Additional Case Details (existing fields)
	property_address = models.TextField(blank=True, null=True)
	state = models.CharField(max_length=100, blank=True, null=True)
	tehsil = models.CharField(max_length=100, blank=True, null=True)
	district = models.CharField(max_length=100, blank=True, null=True)
	branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='meta_data_cases', blank=True, null=True)
	receipt_number = models.CharField(max_length=50, blank=True, null=True)
	receipt_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
	total_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
	case_name = models.CharField(max_length=200, blank=True, null=True)
	reference_name = models.CharField(max_length=200, blank=True, null=True)
	employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name='meta_data_cases', blank=True, null=True)
	legal_reference_number = models.CharField(max_length=100, blank=True, null=True)

	# Workflow tracking
	forwarded_to_sro = models.BooleanField(default=False)
	completed_at = models.DateTimeField(blank=True, null=True)
	# Relationship to original (parent) case when created as an additional property case
	parent_case = models.ForeignKey('self', on_delete=models.CASCADE, related_name='child_cases', blank=True, null=True)

	def has_complete_details(self):
		"""Return True if all key working details have been filled out so advocate can finalize.
		Required: property_address, state, district, tehsil, branch, reference_name, case_name.
		"""
		return all([
			self.property_address,
			self.state,
			self.district,
			self.tehsil,
			self.branch,  # ForeignKey object presence
			self.reference_name,
			self.case_name,
		])

	def generate_legal_reference_number(self):
		"""Generate and assign a LRN number if not already present.
		Format: LRN-ST-XXXX where ST is state abbreviation and XXXX is zero padded incremental count per state."""
		if self.legal_reference_number or not self.state:
			return self.legal_reference_number
		state_abbr = self._get_state_abbreviation(self.state)
		count = Case.objects.filter(state__iexact=self.state, legal_reference_number__isnull=False).count() + 1
		self.legal_reference_number = f"LRN-{state_abbr}-{count:04d}"
		return self.legal_reference_number

	@staticmethod
	def _get_state_abbreviation(state_name: str) -> str:
		mapping = {
			'Delhi': 'DL', 'Uttar Pradesh': 'UP', 'Maharashtra': 'MH', 'Karnataka': 'KA', 'Tamil Nadu': 'TN',
			'Telangana': 'TS', 'Gujarat': 'GJ', 'Rajasthan': 'RJ', 'Haryana': 'HR', 'Punjab': 'PB',
			'West Bengal': 'WB', 'Bihar': 'BR', 'Madhya Pradesh': 'MP', 'Odisha': 'OD', 'Kerala': 'KL',
			'Andhra Pradesh': 'AP', 'Assam': 'AS', 'Chhattisgarh': 'CG', 'Goa': 'GA', 'Jammu and Kashmir': 'JK',
			'Jharkhand': 'JH', 'Himachal Pradesh': 'HP', 'Uttarakhand': 'UK', 'Puducherry': 'PY'
		}
		return mapping.get(state_name, ''.join([w[0] for w in state_name.split()][:2]).upper()) if state_name else 'NA'

	def __str__(self):
		return f"{self.case_number} - {self.applicant_name}"
		
	class Meta:
		verbose_name = "Case"
		verbose_name_plural = "Cases"




class CaseUpdate(models.Model):
	case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='updates')
	update_date = models.DateTimeField(auto_now_add=True)
	action = models.CharField(max_length=30, blank=True, null=True)
	remark = models.TextField(blank=True, null=True)

	def __str__(self):
		return f"Update for {self.case.case_name} on {self.update_date.date()}"


class Remark(models.Model):
	case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='remarks')
	remark = models.TextField()
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return f"Remark for {self.case.case_name} on {self.created_at.date()}"

