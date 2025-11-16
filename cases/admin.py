from django.contrib import admin
from .models import CaseType, Employee, Case, CaseUpdate, Remark, State, District, Tehsil, CaseWork

admin.site.register(CaseType)
admin.site.register(Employee)
admin.site.register(Case)
admin.site.register(CaseUpdate)
admin.site.register(Remark)

@admin.register(State)
class StateAdmin(admin.ModelAdmin):
	search_fields = ['name']
	list_display = ['name']

@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
	search_fields = ['name', 'state__name']
	list_display = ['name', 'state']
	list_filter = ['state']

@admin.register(Tehsil)
class TehsilAdmin(admin.ModelAdmin):
	search_fields = ['name', 'district__name', 'district__state__name']
	list_display = ['name', 'district']
	list_filter = ['district__state']

# External Bank models are registered in Bank app's admin; avoid duplicate registration here.
@admin.register(CaseWork)
class CaseWorkAdmin(admin.ModelAdmin):
    list_display = ('case', 'case_type', 'created_at')
    search_fields = ('case__case_number', 'case__applicant_name', 'case_type__name')
