from django.db import models
from django.contrib.auth.models import User
from Bank.models import Bank as ExternalBank, BankBranch

class State(models.Model):
	name = models.CharField(max_length=100, unique=True)

	class Meta:
		ordering = ['name']

	def __str__(self):
		return self.name

class District(models.Model):
	state = models.ForeignKey(State, on_delete=models.CASCADE, related_name='districts')
	name = models.CharField(max_length=150)

	class Meta:
		unique_together = ('state', 'name')
		ordering = ['name']

	def __str__(self):
		return f"{self.name} ({self.state.name})"

class Tehsil(models.Model):
	district = models.ForeignKey(District, on_delete=models.CASCADE, related_name='tehsils')
	name = models.CharField(max_length=150)

	class Meta:
		unique_together = ('district', 'name')
		ordering = ['name']

	def __str__(self):
		return f"{self.name} ({self.district.name})"

class CaseType(models.Model):
	name = models.CharField(max_length=100, unique=True)
	description = models.TextField(blank=True, null=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return self.name


"""Deprecated local bank models removed in favor of Bank app models."""


## BankExtraFee removed (legacy extra charges feature deprecated)


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
	mobile = models.CharField(max_length=15)
	email = models.EmailField()
	initials = models.CharField(max_length=2, blank=True, null=True, help_text="Two-letter initials (e.g., AB)")
	employee_type = models.CharField(max_length=10, choices=EMPLOYEE_TYPE_CHOICES)
	is_active = models.BooleanField(default=True)
	# KYC identifiers
	aadhaar_number = models.CharField(max_length=12, blank=True, null=True, help_text="12-digit Aadhaar number (no spaces)")
	pan_number = models.CharField(max_length=10, blank=True, null=True, help_text="10-character PAN (AAAAA9999A)")
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	# SRO scoping
	is_super_sro = models.BooleanField(default=False, help_text="If true, SRO can see and manage all SRO cases")
	allowed_states = models.ManyToManyField(State, blank=True, related_name='sro_allowed_states')
	allowed_districts = models.ManyToManyField(District, blank=True, related_name='sro_allowed_districts')
	allowed_tehsils = models.ManyToManyField(Tehsil, blank=True, related_name='sro_allowed_tehsils')

	def __str__(self):
		return f"{self.name} ({self.employee_id}) - {self.get_employee_type_display()}"
		
	class Meta:
		verbose_name = "Employee"
		verbose_name_plural = "Employees"


class EmployeeDocument(models.Model):
	employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='documents')
	name = models.CharField(max_length=100)
	file = models.FileField(upload_to='employee_documents/')
	uploaded_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return f"{self.name} for {self.employee.name}"


class Case(models.Model):
	STATUS_CHOICES = [
		('quotation', 'Quotation'),
		('positive', 'Positive'),
		('negative', 'Negative'),
		('on_hold', 'On Hold'),
		('on_query', 'On Query'),
		('document_pending', 'Document Pending'),
		('sro_document_pending', 'SRO Document Pending'),
		('positive_subject_tosearch', 'Positive Subject to Search'),
		('pending_assignment', 'Pending Assignment'),
		('pending', 'Pending'),
	]

	# Basic Case Information
	applicant_name = models.CharField(max_length=200)
	case_number = models.CharField(max_length=100, unique=True)
	bank = models.ForeignKey(ExternalBank, on_delete=models.PROTECT, related_name='cases')
	case_type = models.ForeignKey(CaseType, on_delete=models.PROTECT, related_name='cases')
	
	# Document Status
	documents_present = models.BooleanField(default=False)
	
	# Assignment Information
	assigned_advocate = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name='assigned_cases', blank=True, null=True, limit_choices_to={'employee_type': 'advocate'})
	
	# Status and Tracking
	status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')

	# Quotation Workflow Fields
	is_quotation = models.BooleanField(default=False, help_text="Indicates this case started as a quotation (no documents yet)")
	quotation_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text="Quoted price (can be updated until finalized)")
	quotation_finalized = models.BooleanField(default=False, help_text="Quotation confirmed, ready for assignment and document collection")
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)
	
	# Additional Case Details (existing fields)
	property_address = models.TextField(blank=True, null=True)
	state = models.CharField(max_length=100, blank=True, null=True)
	tehsil = models.CharField(max_length=100, blank=True, null=True)
	district = models.CharField(max_length=100, blank=True, null=True)
	is_school_case = models.BooleanField(default=False, help_text="Mark if this is a school case for duplicate checks")
	branch = models.ForeignKey(BankBranch, on_delete=models.PROTECT, related_name='meta_data_cases', blank=True, null=True)
	receipt_number = models.CharField(max_length=50, blank=True, null=True)
	receipt_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
	receipt_expense = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text="Receipt expense amount (optional)")
	# Allow overriding the original case type fee at billing time
	original_custom_fee = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text="Override fee for original case type (optional)")
	total_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
	case_name = models.CharField(max_length=200, blank=True, null=True)
	reference_name = models.CharField(max_length=200, blank=True, null=True)
	employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name='meta_data_cases', blank=True, null=True)
	legal_reference_number = models.CharField(max_length=100, blank=True, null=True)

	# Workflow tracking
	forwarded_to_sro = models.BooleanField(default=False)
	completed_at = models.DateTimeField(blank=True, null=True)
	# Track when a case was reassigned to surface in advocate tray
	reassigned_at = models.DateTimeField(blank=True, null=True)
	# Relationship to original (parent) case when created as an additional property case
	parent_case = models.ForeignKey('self', on_delete=models.CASCADE, related_name='child_cases', blank=True, null=True)

	def has_complete_details(self):
		"""Return True if all key working details (post-refactor) are present to allow final actions.
		Updated requirement: property_address, state, district, tehsil, branch.
		Reference name and case name no longer required in workflow.
		"""
		return all([
			self.property_address,
			self.state,
			self.district,
			self.tehsil,
			self.branch,
		])

	def is_final_status(self):
		"""Return True if the case is in a finalized state (no further work edits or new works allowed).
		Final statuses: positive, negative, positive_subject_tosearch.
		"""
		return self.status in ['positive', 'negative', 'positive_subject_tosearch']

	def propagate_status_to_children(self):
		"""Ensure all child cases have the same status as this parent case."""
		if self.pk:
			self.child_cases.update(status=self.status)

	def generate_legal_reference_number(self):
		"""Generate and assign LRN if not set.
		Format: NX-<STATE>-<EMP>-<SERIAL>-<FY>
		- STATE: state abbreviation (e.g., UP)
		- EMP: two-letter initials of assigned advocate (fall back to name-derived or 'XX')
		- SERIAL: single, global zero-padded sequential number (no per-state, no per-FY)
		  Baseline starts at 1670, so the first new LRN will use 1671.
		- FY: financial year in 'YY.YY' format, which changes after April 1
		"""
		from django.utils import timezone
		if self.legal_reference_number:
			return self.legal_reference_number
		# Require state for LRN; if missing, set NA
		state_abbr = self._get_state_abbreviation(self.state) if self.state else 'NA'
		# Employee initials
		emp_ini = self._get_employee_initials()
		# Financial year
		now = timezone.now().date()
		start_year = now.year % 100
		if now.month < 4:
			start_year = (start_year - 1) % 100
		end_year = (start_year + 1) % 100
		fy_str = f"{start_year:02d}.{end_year:02d}"
		# Global sequential serial (no per-state or per-FY counters)
		# Determine the current max serial across all existing LRNs, then add 1.
		# Baseline is 1670 if none exist or cannot be parsed.
		# Baseline such that the first new serial generated will be 1688
		max_serial = 1687
		existing_lrns = Case.objects.exclude(legal_reference_number__isnull=True) \
			.exclude(legal_reference_number='') \
			.values_list('legal_reference_number', flat=True)
		for lrn in existing_lrns:
			try:
				# Expected pattern: NX-STATE-EMP-SERIAL-FY
				parts = str(lrn).split('-')
				if len(parts) >= 5:
					serial_part = parts[3]
					if serial_part.isdigit():
						max_serial = max(max_serial, int(serial_part))
			except Exception:
				# Ignore malformed entries
				pass
		serial_num = max_serial + 1
		self.legal_reference_number = f"NX-{state_abbr}-{emp_ini}-{serial_num:06d}-{fy_str}"
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

	def _get_employee_initials(self) -> str:
		"""Return two-letter initials for the assigned advocate, fallback to name or 'XX'."""
		e = self.assigned_advocate
		if e:
			# Prefer explicit initials field if present
			ini = getattr(e, 'initials', None)
			if ini:
				ini = ini.strip().upper()
				if len(ini) == 2 and ini.isalpha():
					return ini
			# Derive from name
			name = (e.name or '').strip()
			if name:
				parts = [p for p in name.split() if p]
				if len(parts) == 1:
					return (parts[0][0:1] * 2).upper()
				else:
					return (parts[0][0] + parts[-1][0]).upper()
		return 'XX'

	def __str__(self):
		return f"{self.case_number} - {self.applicant_name}"
		
	class Meta:
		verbose_name = "Case"
		verbose_name_plural = "Cases"


## CaseCharge removed (legacy extra charges application deprecated)


class CaseDocument(models.Model):
	case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='documents')
	file = models.FileField(upload_to='case_documents/')
	uploaded_at = models.DateTimeField(auto_now_add=True)
	uploaded_by = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name='uploaded_case_documents')
	description = models.CharField(max_length=255, blank=True, null=True)
	# Explicit flag to distinguish SRO receipt vs final document
	is_receipt = models.BooleanField(default=False)

	def __str__(self):
		return f"Document for {self.case.case_number} ({self.file.name.split('/')[-1]})"


class CaseWork(models.Model):
	"""A unit of work performed for a case, identified by a CaseType and backed by a document.
	Additional works beyond the original case.case_type must be created via this model.
	"""
	case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='works')
	case_type = models.ForeignKey(CaseType, on_delete=models.PROTECT, related_name='case_works')
	document = models.FileField(upload_to='case_documents/', help_text='Upload the supporting document for this work')
	# Optional per-work custom fee override for billing
	custom_fee = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
	notes = models.CharField(max_length=255, blank=True, null=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['created_at', 'id']

	def __str__(self):
		return f"{self.case.case_number} - {self.case_type.name} (work)"



class CaseUpdate(models.Model):
	case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='updates')
	update_date = models.DateTimeField(auto_now_add=True)
	action = models.CharField(max_length=30, blank=True, null=True)
	remark = models.TextField(blank=True, null=True)

	def __str__(self):
		try:
			label = self.case.case_number or self.case.case_name or str(self.case_id)
		except Exception:
			label = str(self.case_id)
		return f"Update for {label} on {self.update_date.date()}"


class AdHocFee(models.Model):
	"""Additional custom fee line attached to a Case for billing purposes."""
	case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='adhoc_fees')
	name = models.CharField(max_length=150)
	amount = models.DecimalField(max_digits=10, decimal_places=2)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['created_at', 'id']

	def __str__(self):
		return f"{self.case.case_number} - {self.name}: {self.amount}"


class Remark(models.Model):
	case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='remarks')
	remark = models.TextField()
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return f"Remark for {self.case.case_name} on {self.created_at.date()}"


