

from django.contrib import admin
from .models import CaseType, Bank, Branch, BranchCaseType, Employee, Case, CaseUpdate, Remark

admin.site.register(CaseType)
admin.site.register(Bank)
admin.site.register(Branch)
admin.site.register(BranchCaseType)
admin.site.register(Employee)
admin.site.register(Case)
admin.site.register(CaseUpdate)
admin.site.register(Remark)
