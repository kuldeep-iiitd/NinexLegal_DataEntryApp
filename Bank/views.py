from django.shortcuts import render, redirect
from django.forms import inlineformset_factory
from django.db import transaction
from django.contrib import messages
from cases import decorators
from django.http import HttpResponse
from .forms import (
    BankForm,
    BankStateCaseTypeForm,
    BaseBankFeeFormSet,
    BankStatesForm,
    BankBranchForm,
    BankDocumentForm,
)
from .models import Bank, BankStateCaseType, BankState, BankBranch, BankDocument
from cases.models import State


@decorators.admin_required
def CreateBankView(request):
    if request.method == "POST":
        bank_form = BankForm(request.POST)
        states_form = BankStatesForm(request.POST)
        if bank_form.is_valid() and states_form.is_valid():
            try:
                with transaction.atomic():
                    bank = bank_form.save()
                    for state in states_form.cleaned_data['states']:
                        BankState.objects.get_or_create(bank=bank, state=state)
                messages.success(request, "Bank created and states assigned. Now add fees.")
                return redirect('Bank:manage_bank_fees', bank_id=bank.id)
            except Exception as e:
                messages.error(request, f"Could not save bank: {e}")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        bank_form = BankForm()
        states_form = BankStatesForm()
    return render(request, 'Bank/create_bank.html', {
        'bank_form': bank_form,
        'states_form': states_form,
    })

@decorators.admin_required
def ManageBankFeesView(request, bank_id):
    bank = Bank.objects.get(pk=bank_id)
    BankFeeFormSet = inlineformset_factory(
        Bank,
        BankStateCaseType,
        form=BankStateCaseTypeForm,
        formset=BaseBankFeeFormSet,
        fields=["state", "casetype", "fees"],
        extra=1,
        can_delete=True,
    )
    if request.method == 'POST':
        formset = BankFeeFormSet(request.POST, instance=bank)
        if formset.is_valid():
            try:
                formset.save()
                messages.success(request, 'Fees updated successfully.')
                return redirect('Bank:manage_bank_fees', bank_id=bank.id)
            except Exception as e:
                messages.error(request, f'Error saving fees: {str(e)}')
        else:
            messages.error(request, 'Please correct errors below.')
    else:
        formset = BankFeeFormSet(instance=bank)
    # Limit state field choices per form to bank's assigned states
    assigned_state_ids = list(
        BankState.objects.filter(bank=bank).values_list('state_id', flat=True)
    )
    limited_states_qs = State.objects.filter(id__in=assigned_state_ids).order_by('name') if assigned_state_ids else State.objects.none()
    for f in formset.forms:
        if 'state' in f.fields:
            f.fields['state'].queryset = limited_states_qs
    if not assigned_state_ids:
        messages.warning(request, 'No states assigned to this bank yet. Go back and add states to enable fee entries.')
    return render(request, 'Bank/manage_bank_fees.html', {
        'bank': bank,
        'formset': formset,
    })


@decorators.admin_required
def ViewBanksView(request):
    banks = Bank.objects.all().order_by('name')
    # Prefetch related states and branch counts
    bank_states = BankState.objects.filter(bank__in=banks).select_related('state')
    states_map = {}
    for bs in bank_states:
        states_map.setdefault(bs.bank_id, []).append(bs.state.name)
    branch_counts = {b.id: b.branches.count() for b in banks}
    return render(request, 'Bank/view_banks.html', {
        'banks': banks,
        'states_map': states_map,
        'branch_counts': branch_counts,
    })

@decorators.admin_required
def BankDetailView(request, bank_id):
    """Comprehensive view of a single bank: states and fee mappings grouped by state."""
    bank = Bank.objects.get(pk=bank_id)
    # States where bank operates
    states = list(BankState.objects.filter(bank=bank).select_related('state').order_by('state__name'))
    state_objs = [bs.state for bs in states]
    # Fee mappings
    fee_rows = (
        BankStateCaseType.objects
        .filter(bank=bank)
        .select_related('state', 'casetype')
        .order_by('state__name', 'casetype__name')
    )
    # Group fees by state id
    grouped = {}
    for fr in fee_rows:
        grouped.setdefault(fr.state_id, []).append(fr)
    return render(request, 'Bank/bank_detail.html', {
        'bank': bank,
        'states': state_objs,
        'fee_grouped': grouped,
    })

@decorators.admin_required
def ManageBankStatesView(request, bank_id):
    """Add or remove the states in which the bank operates.
    Uses a multi-select form to set the complete list in one go.
    """
    bank = Bank.objects.get(pk=bank_id)
    if request.method == 'POST':
        form = BankStatesForm(request.POST)
        if form.is_valid():
            selected_states = set(form.cleaned_data['states'].values_list('id', flat=True))
            current_states = set(BankState.objects.filter(bank=bank).values_list('state_id', flat=True))
            to_add = selected_states - current_states
            to_remove = current_states - selected_states
            # Apply changes atomically
            with transaction.atomic():
                if to_remove:
                    BankState.objects.filter(bank=bank, state_id__in=list(to_remove)).delete()
                for sid in to_add:
                    BankState.objects.get_or_create(bank=bank, state_id=sid)
            messages.success(request, 'Bank states updated.')
            return redirect('Bank:manage_bank_states', bank_id=bank.id)
        else:
            messages.error(request, 'Please correct errors below.')
    else:
        initial_ids = list(BankState.objects.filter(bank=bank).values_list('state_id', flat=True))
        form = BankStatesForm(initial={'states': initial_ids})

    # For sidebar context: current states list
    assigned = BankState.objects.filter(bank=bank).select_related('state').order_by('state__name')
    return render(request, 'Bank/manage_bank_states.html', {
        'bank': bank,
        'form': form,
        'assigned_states': [bs.state for bs in assigned],
    })

@decorators.admin_required
def ManageBankBranchesView(request, bank_id):
    bank = Bank.objects.get(pk=bank_id)
    if request.method == 'POST':
        form = BankBranchForm(request.POST, bank=bank)
        if form.is_valid():
            branch = form.save(commit=False)
            branch.bank = bank
            branch.save()
            messages.success(request, 'Branch added.')
            return redirect('Bank:manage_bank_branches', bank_id=bank.id)
        else:
            messages.error(request, 'Please correct errors below.')
    else:
        form = BankBranchForm(bank=bank)
    branches = bank.branches.all().order_by('name')
    return render(request, 'Bank/manage_bank_branches.html', {
        'bank': bank,
        'form': form,
        'branches': branches,
    })

@decorators.admin_required
def DeleteBankBranchView(request, bank_id, branch_id):
    bank = Bank.objects.get(pk=bank_id)
    branch = BankBranch.objects.get(pk=branch_id, bank=bank)
    branch.delete()
    messages.success(request, 'Branch deleted.')
    return redirect('Bank:manage_bank_branches', bank_id=bank.id)

@decorators.admin_required
def EditBankBranchView(request, bank_id, branch_id):
    bank = Bank.objects.get(pk=bank_id)
    branch = BankBranch.objects.get(pk=branch_id, bank=bank)
    if request.method == 'POST':
        form = BankBranchForm(request.POST, instance=branch, bank=bank)
        if form.is_valid():
            form.save()
            messages.success(request, 'Branch updated.')
            return redirect('Bank:manage_bank_branches', bank_id=bank.id)
        else:
            messages.error(request, 'Please correct errors below.')
    else:
        form = BankBranchForm(instance=branch, bank=bank)
    return render(request, 'Bank/edit_bank_branch.html', {
        'bank': bank,
        'form': form,
        'branch': branch,
    })


@decorators.admin_required
def ManageBankDocumentsView(request, bank_id):
    bank = Bank.objects.get(pk=bank_id)
    if request.method == 'POST':
        form = BankDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.bank = bank
            doc.save()
            messages.success(request, 'Document uploaded.')
            return redirect('Bank:manage_bank_documents', bank_id=bank.id)
        else:
            messages.error(request, 'Please correct errors below.')
    else:
        form = BankDocumentForm()
    docs = bank.documents.all()
    return render(request, 'Bank/manage_bank_documents.html', {
        'bank': bank,
        'form': form,
        'documents': docs,
    })


@decorators.admin_required
def EditBankDocumentView(request, bank_id, doc_id):
    bank = Bank.objects.get(pk=bank_id)
    doc = BankDocument.objects.get(pk=doc_id, bank=bank)
    old_file = doc.file
    if request.method == 'POST':
        form = BankDocumentForm(request.POST, request.FILES, instance=doc)
        if form.is_valid():
            replaced = ('file' in form.changed_data and doc.file)
            instance = form.save()
            # If file replaced, remove old file from storage
            try:
                if replaced and old_file and old_file.name != instance.file.name:
                    old_file.delete(save=False)
            except Exception:
                pass
            messages.success(request, 'Document updated.')
            return redirect('Bank:manage_bank_documents', bank_id=bank.id)
        else:
            messages.error(request, 'Please correct errors below.')
    else:
        form = BankDocumentForm(instance=doc)
    return render(request, 'Bank/edit_bank_document.html', {
        'bank': bank,
        'form': form,
        'document': doc,
    })


@decorators.admin_required
def DeleteBankDocumentView(request, bank_id, doc_id):
    bank = Bank.objects.get(pk=bank_id)
    doc = BankDocument.objects.get(pk=doc_id, bank=bank)
    try:
        if doc.file:
            doc.file.delete(save=False)
    except Exception:
        pass
    doc.delete()
    messages.success(request, 'Document deleted.')
    return redirect('Bank:manage_bank_documents', bank_id=bank.id)


@decorators.admin_required
def DeleteBankView(request, bank_id):
    bank = Bank.objects.get(pk=bank_id)
    if request.method == 'POST':
        bank_name = bank.name
        bank.delete()
        messages.success(request, f'Bank "{bank_name}" has been deleted.')
        return redirect('Bank:viewbanks')
    return render(request, 'Bank/confirm_delete_bank.html', {'bank': bank})

