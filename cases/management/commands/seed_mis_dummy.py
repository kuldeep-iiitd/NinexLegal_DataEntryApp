from django.core.management.base import BaseCommand
from django.utils import timezone
from random import randint, choice, random
from datetime import timedelta

from cases.models import (
    Employee, CaseType, Case, State, District, Tehsil
)
from Bank.models import Bank, BankBranch, BankState, BankStateCaseType
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = "Seed dummy data for MIS testing: banks, branches, employees, case types, and cases."

    def add_arguments(self, parser):
        parser.add_argument('--wipe', action='store_true', help='Delete generated objects first')
        parser.add_argument('--cases', type=int, default=50, help='Number of cases to create (default 50)')

    def handle(self, *args, **options):
        wipe = options['wipe']
        num_cases = options['cases']

        if wipe:
            self.stdout.write('Wiping existing dummy data (non-destructive for real users/banks if names differ)...')
            Case.objects.all().delete()
            BankBranch.objects.all().delete()
            BankStateCaseType.objects.all().delete()
            BankState.objects.all().delete()
            Bank.objects.all().delete()
            CaseType.objects.all().delete()
            Employee.objects.all().delete()
            User.objects.filter(username__startswith='dummy_').delete()
            State.objects.all().delete()
            District.objects.all().delete()
            Tehsil.objects.all().delete()

        # States
        states = ['Delhi', 'Uttar Pradesh', 'Haryana']
        state_objs = {name: State.objects.get_or_create(name=name)[0] for name in states}

        # Districts/Tehsils (minimal for address info)
        for sname, sobj in state_objs.items():
            for d in ['Central', 'North', 'South']:
                dist, _ = District.objects.get_or_create(state=sobj, name=d)
                for t in ['I', 'II']:
                    Tehsil.objects.get_or_create(district=dist, name=f'{d} {t}')

        # Banks and their associated states (BankState records)
        bank_specs = [
            ('HDFC', 'Delhi'), ('HDFC', 'Uttar Pradesh'), ('ICICI', 'Delhi'),
            ('SBI', 'Haryana'),
        ]
        banks = {}
        bank_states = []
        for name, st in bank_specs:
            bank_obj, _ = Bank.objects.get_or_create(name=name)
            banks[name] = bank_obj
            state_obj = state_objs[st]
            bs, _ = BankState.objects.get_or_create(bank=bank_obj, state=state_obj)
            bank_states.append(bs)

        # Branches per bank-state combination
        branches = []
        for bs in bank_states:
            bank_obj = bs.bank
            state_obj = bs.state
            for i in range(1, 3):
                br, _ = BankBranch.objects.get_or_create(
                    bank=bank_obj,
                    state=state_obj,
                    name=f"{bank_obj.name} {state_obj.name} Branch {i}",
                    defaults={'branch_code': f"{bank_obj.name[:3].upper()}{state_obj.name[:2].upper()}{i:02d}"}
                )
                branches.append(br)

        # Employees (SRO)
        employees = []
        for i, nm in enumerate(['Alice Kumar', 'Bharat Singh', 'Charu Rao'], start=1):
            user, _ = User.objects.get_or_create(username=f'dummy_user_{i}', defaults={'email': f'user{i}@example.com'})
            emp, _ = Employee.objects.get_or_create(
                user=user,
                defaults={
                    'name': nm,
                    'employee_id': f'DUM{i:03d}',
                    'mobile': f'99999000{i:02d}',
                    'email': f'user{i}@example.com',
                    'employee_type': Employee.SRO,
                    'is_active': True,
                }
            )
            employees.append(emp)

        # Case types and bank fees
        case_types = []
        for nm in ['Search Report', 'Legal Opinion', 'Valuation']:
            ct, _ = CaseType.objects.get_or_create(name=nm)
            case_types.append(ct)
        # Fees per (bank,state,casetype)
        for bs in bank_states:
            for ct in case_types:
                BankStateCaseType.objects.get_or_create(
                    bank=bs.bank,
                    state=bs.state,
                    casetype=ct,
                    defaults={'fees': 1500 + 500 * randint(0, 3)}
                )

        # Create cases
        now = timezone.now()
        for i in range(1, num_cases + 1):
            bank = choice(list(banks.values()))
            # ensure branch belongs to bank
            bank_branches = [br for br in branches if br.bank_id == bank.id]
            branch = choice(bank_branches)
            emp = choice(employees)
            ct = choice(case_types)
            created = now - timedelta(days=randint(0, 120))

            state_name = branch.state.name if branch.state_id else choice(states)
            c = Case.objects.create(
                applicant_name=f"Applicant {i}",
                case_number=f"FILE-{created.strftime('%y%m')}-{i:04d}",
                bank=bank,
                case_type=ct,
                documents_present=bool(randint(0, 1)),
                assigned_advocate=None,
                status=choice([s[0] for s in Case.STATUS_CHOICES]),
                is_quotation=bool(randint(0, 1)),
                quotation_price=1500 if random() < 0.3 else None,
                quotation_finalized=bool(randint(0, 1)),
                property_address=f"{branch.name}, {state_name}",
                state=state_name,
                tehsil='I',
                district='Central',
                branch=branch,
                receipt_number=f"RCPT-{i:05d}",
                receipt_amount=1000 + 500 * randint(0, 4),
                receipt_expense=None,
                total_amount=None,
                case_name=f"Case {i}",
                reference_name=f"Ref {i}",
                employee=emp,
            )

            # created_at auto_now_add; adjust timestamps via update to simulate past dates
            Case.objects.filter(pk=c.pk).update(created_at=created)

        self.stdout.write(self.style.SUCCESS(f"Seeded {num_cases} dummy cases for MIS testing."))
