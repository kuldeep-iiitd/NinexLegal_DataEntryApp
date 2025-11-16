from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import connection, transaction

class Command(BaseCommand):
    help = "Mirror Bank app tables into legacy cases_bank / cases_branch for existing foreign keys. Safe to run multiple times."

    def handle(self, *args, **options):
        now = timezone.now()
        with transaction.atomic():
            with connection.cursor() as cur:
                now_str = now.strftime('%Y-%m-%d %H:%M:%S')
                # ---- Phase 0: Import legacy -> new (repair path) ----
                # Some existing Case rows still reference legacy cases_bank / cases_branch ids.
                # To allow FK migrations and current saves to work, ensure corresponding rows
                # exist in the new Bank tables with the SAME primary keys.
                self.stdout.write('Importing legacy cases_bank into Bank_bank (if missing, renaming duplicates)...')
                # Insert with conflict handling on unique name: append legacy id if name already taken.
                cur.execute("""
                    INSERT INTO Bank_bank (id, name)
                    SELECT cb.id,
                           CASE
                               WHEN EXISTS (SELECT 1 FROM Bank_bank b2 WHERE b2.name = cb.name) THEN cb.name || ' (legacy-' || cb.id || ')'
                               ELSE cb.name
                           END AS name
                    FROM cases_bank cb
                    WHERE NOT EXISTS (
                        SELECT 1 FROM Bank_bank b WHERE b.id = cb.id
                    )
                """)

                self.stdout.write('Importing legacy cases_branch into Bank_bankbranch (if missing, preserving ids)...')
                cur.execute(f"""
                    INSERT INTO Bank_bankbranch (id, bank_id, state_id, name, branch_code, address)
                    SELECT cbr.id, cbr.bank_id, NULL, cbr.name,
                           COALESCE(NULLIF(cbr.branch_code, ''), 'AUTO' || cbr.id) AS branch_code,
                           COALESCE(cbr.address, '')
                    FROM cases_branch cbr
                    WHERE NOT EXISTS (
                        SELECT 1 FROM Bank_bankbranch bb WHERE bb.id = cbr.id
                    )
                """)
                # Ensure legacy bank rows exist matching Bank_bank ids
                self.stdout.write('Syncing legacy cases_bank with Bank_bank...')
                cur.execute(f"""
                    INSERT INTO cases_bank (id, created_at, updated_at, state, name)
                    SELECT b.id, '{now_str}', '{now_str}', COALESCE(bs.state_name, ''), b.name
                    FROM Bank_bank b
                    LEFT JOIN (
                        SELECT bb.bank_id AS bank_id, s.name AS state_name
                        FROM Bank_bankbranch bb
                        LEFT JOIN cases_state s ON s.id = bb.state_id
                        GROUP BY bb.bank_id
                    ) bs ON bs.bank_id = b.id
                    WHERE NOT EXISTS (
                        SELECT 1 FROM cases_bank cb WHERE cb.id = b.id
                    )
                """)

                # Sync branches: ensure branch ids exist in legacy table pointing to corresponding legacy bank ids
                self.stdout.write('Syncing legacy cases_branch with Bank_bankbranch...')
                # Generate a unique branch_code if missing/null to satisfy NOT NULL UNIQUE constraint in legacy table
                # Use 'AUTO' || id as fallback
                cur.execute(f"""
                    INSERT INTO cases_branch (id, name, branch_code, address, created_at, updated_at, bank_id, gst_number, pan_number)
                    SELECT bb.id, bb.name,
                           COALESCE(NULLIF(bb.branch_code, ''), 'AUTO' || bb.id) AS branch_code,
                           COALESCE(bb.address, ''),
                           '{now_str}', '{now_str}',
                           bb.bank_id,
                           NULL, NULL
                    FROM Bank_bankbranch bb
                    WHERE NOT EXISTS (
                        SELECT 1 FROM cases_branch cb WHERE cb.id = bb.id
                    )
                """)

        self.stdout.write(self.style.SUCCESS('Legacy bank tables synchronized.'))
