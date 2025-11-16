from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.conf import settings

from cases.models import (
    Case,
    CaseWork,
    CaseDocument,
    CaseUpdate,
    Remark,
    AdHocFee,
)


class Command(BaseCommand):
    help = (
        "Permanently delete ALL case data (cases, works, documents, updates, remarks, ad-hoc fees, charges). "
        "Only configuration (banks, branches, case types, fees) is kept."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Do not prompt for confirmation",
        )

    def handle(self, *args, **options):
        confirm = options.get("yes", False)
        if not confirm:
            self.stdout.write(self.style.WARNING("This will permanently DELETE all case data."))
            self.stdout.write(self.style.WARNING("Configuration like banks, branches, and case types will remain."))
            resp = input("Type 'DELETE' to proceed: ")
            if resp.strip().upper() != "DELETE":
                self.stdout.write("Aborted.")
                return

        with transaction.atomic():
            # Gather counts for summary
            counts_before = {
                'cases': Case.objects.count(),
                'works': CaseWork.objects.count(),
                'docs': CaseDocument.objects.count(),
                'updates': CaseUpdate.objects.count(),
                'remarks': Remark.objects.count(),
                'adhoc': AdHocFee.objects.count(),
            }

            # Delete files for CaseDocument and CaseWork first
            self.stdout.write("Deleting files for case documents…")
            for doc in CaseDocument.objects.all().only('id', 'file'):
                try:
                    if doc.file and hasattr(doc.file, 'delete'):
                        doc.file.delete(save=False)
                except Exception:
                    # Best-effort file deletion; continue
                    pass
            self.stdout.write("Deleting files for case works…")
            for work in CaseWork.objects.all().only('id', 'document'):
                try:
                    if work.document and hasattr(work.document, 'delete'):
                        work.document.delete(save=False)
                except Exception:
                    pass

            # Now delete DB rows (cascade will clear dependents). We delete Cases last to ensure cascades fire.
            self.stdout.write("Deleting dependent objects…")
            AdHocFee.objects.all().delete()
            CaseUpdate.objects.all().delete()
            Remark.objects.all().delete()
            CaseDocument.objects.all().delete()
            CaseWork.objects.all().delete()

            self.stdout.write("Deleting cases…")
            Case.objects.all().delete()

        self.stdout.write(self.style.SUCCESS("All case data deleted."))
        self.stdout.write("Summary (before deletion):")
        for k, v in counts_before.items():
            self.stdout.write(f"  {k}: {v}")
