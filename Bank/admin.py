from django.contrib import admin
from .models import Bank, BankState, BankStateCaseType, BankBranch, BankDocument

@admin.register(Bank)
class BankAdmin(admin.ModelAdmin):
	list_display = ('name',)
	search_fields = ('name',)

@admin.register(BankState)
class BankStateAdmin(admin.ModelAdmin):
	list_display = ('bank', 'state')
	list_filter = ('state', 'bank')

@admin.register(BankStateCaseType)
class BankStateCaseTypeAdmin(admin.ModelAdmin):
	list_display = ('bank', 'state', 'casetype', 'fees')
	list_filter = ('bank', 'state', 'casetype')
	search_fields = ('bank__name', 'state__name', 'casetype__name')

@admin.register(BankBranch)
class BankBranchAdmin(admin.ModelAdmin):
	list_display = ('name', 'bank', 'state', 'branch_code')
	list_filter = ('bank', 'state')
	search_fields = ('name', 'branch_code', 'bank__name')

@admin.register(BankDocument)
class BankDocumentAdmin(admin.ModelAdmin):
	list_display = ('name', 'bank', 'uploaded_at')
	list_filter = ('bank',)
	search_fields = ('name', 'bank__name')
