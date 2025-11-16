from django.db import models

class Bank(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class BankState(models.Model):
    bank = models.ForeignKey(Bank, on_delete=models.CASCADE, related_name='bank_states')
    state = models.ForeignKey('cases.State', on_delete=models.CASCADE, related_name='state_banks')

    class Meta:
        unique_together = ('bank', 'state')
        verbose_name = 'Bank State'
        verbose_name_plural = 'Bank States'

    def __str__(self):
        return f"{self.bank.name} - {self.state.name}"

class BankStateCaseType(models.Model):
    
    bank = models.ForeignKey(Bank, on_delete=models.CASCADE, related_name='state_case_type_fees')
    state = models.ForeignKey('cases.State', on_delete=models.CASCADE, related_name='bank_case_type_fees')
    casetype = models.ForeignKey('cases.CaseType', on_delete=models.CASCADE, related_name='bank_state_fees')
    fees = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        unique_together = ('bank', 'state', 'casetype')
        verbose_name = 'Bank State Case Type Fee'
        verbose_name_plural = 'Bank State Case Type Fees'

    def __str__(self):
        return f"{self.bank.name} / {self.state.name} / {self.casetype.name}: {self.fees}"


class BankBranch(models.Model):
    bank = models.ForeignKey(Bank, on_delete=models.CASCADE, related_name='branches')
    state = models.ForeignKey('cases.State', on_delete=models.SET_NULL, null=True, blank=True, related_name='bank_branches')
    name = models.CharField(max_length=100)
    branch_code = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Bank Branch'
        verbose_name_plural = 'Bank Branches'

    def __str__(self):
        state_part = f", {self.state.name}" if self.state else ""
        return f"{self.name} ({self.bank.name}{state_part})"


class BankDocument(models.Model):
    bank = models.ForeignKey(Bank, on_delete=models.CASCADE, related_name='documents')
    name = models.CharField(max_length=150)
    file = models.FileField(upload_to='bank_documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at', 'id']
        verbose_name = 'Bank Document'
        verbose_name_plural = 'Bank Documents'

    def __str__(self):
        return f"{self.bank.name} — {self.name}"


