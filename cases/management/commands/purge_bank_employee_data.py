from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth.models import User

from cases.models import (
    Employee,
    EmployeeDocument,
)
from Bank.models import Bank, BankBranch, BankStateCaseType


class Command(BaseCommand):
    help = (
        "Permanently delete ALL bank and employee data, including branches, bank case types, bank documents, "
        "extra fees, employees, and employee documents. Case data is not touched by this command."
    )

    def add_arguments(self, parser):
        parser.add_argument("--yes", action="store_true", help="Do not prompt for confirmation")
        parser.add_argument(
            "--delete-users",
            action="store_true",
            help="Also delete linked auth.User accounts for employees (except superusers)",
        )
        parser.add_argument(
            "--include-superusers",
            action="store_true",
            help="Also delete superuser accounts when --delete-users is provided (USE WITH EXTREME CAUTION)",
        )

    def handle(self, *args, **options):
        confirm = options.get("yes", False)
        delete_users = options.get("delete_users", False)
        include_supers = options.get("include_superusers", False)

        if not confirm:
            self.stdout.write(self.style.WARNING("This will permanently DELETE all bank and employee data."))
            self.stdout.write(self.style.WARNING("Cases will not be deleted by this command."))
            resp = input("Type 'DELETE' to proceed: ")
            if resp.strip().upper() != "DELETE":
                self.stdout.write("Aborted.")
                return

        with transaction.atomic():
            # Delete files first
            # Legacy BankDocument model removed; if you had a replacement, delete files there instead.
            self.stdout.write("No bank documents model to purge (skipped).")
            self.stdout.write("Deleting employee documents files…")
            for ed in EmployeeDocument.objects.all().only('id', 'file'):
                try:
                    if ed.file and hasattr(ed.file, 'delete'):
                        ed.file.delete(save=False)
                except Exception:
                    pass

            counts_before = {
                'banks': Bank.objects.count(),
                'branches': BankBranch.objects.count(),
                'bank_case_types': BankStateCaseType.objects.count(),
                'bank_documents': 0,
                'employees': Employee.objects.count(),
                'employee_documents': EmployeeDocument.objects.count(),
            }

            # Delete dependent objects
            # No bank documents to delete in new structure
            BankStateCaseType.objects.all().delete()
            BankBranch.objects.all().delete()
            # Employees depend on User; remove docs first
            EmployeeDocument.objects.all().delete()

            # Capture users to delete if requested
            users_to_delete = []
            if delete_users:
                q = User.objects.filter(employee__isnull=False).distinct()
                if not include_supers:
                    q = q.filter(is_superuser=False)
                users_to_delete = list(q.values_list('id', flat=True))

            Employee.objects.all().delete()
            Bank.objects.all().delete()

            if users_to_delete:
                User.objects.filter(id__in=users_to_delete).delete()

        self.stdout.write(self.style.SUCCESS("All bank and employee data deleted."))
        self.stdout.write("Summary (before deletion):")
        for k, v in counts_before.items():
            self.stdout.write(f"  {k}: {v}")
