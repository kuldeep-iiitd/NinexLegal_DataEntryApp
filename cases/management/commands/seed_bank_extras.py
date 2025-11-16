"""Deprecated command: BankExtraFee model has been removed.
This management command now performs no action and exists only to avoid import errors
in environments where it may still be referenced.
"""

from django.core.management.base import BaseCommand
from Bank.models import Bank  # Kept for potential future extension


class Command(BaseCommand):
    help = "(Deprecated) BankExtraFee seeding command. No-op since BankExtraFee model was removed."

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='(No-op) Was previously used to force reseed')

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('seed_bank_extras: BankExtraFee model deprecated; command does nothing.'))
        count_banks = Bank.objects.count()
        self.stdout.write(f"Banks present: {count_banks}. No fees seeded.")
