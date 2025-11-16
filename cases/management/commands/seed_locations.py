from django.core.management.base import BaseCommand
from django.db import transaction
from cases.models import State, District, Tehsil
import csv
from pathlib import Path

STATES = [
    'Andhra Pradesh','Arunachal Pradesh','Assam','Bihar','Chhattisgarh','Goa','Gujarat','Haryana','Himachal Pradesh','Jharkhand',
    'Karnataka','Kerala','Madhya Pradesh','Maharashtra','Manipur','Meghalaya','Mizoram','Nagaland','Odisha','Punjab','Rajasthan',
    'Sikkim','Tamil Nadu','Telangana','Tripura','Uttar Pradesh','Uttarakhand','West Bengal',
    'Andaman and Nicobar Islands','Chandigarh','Dadra and Nagar Haveli and Daman and Diu','Delhi','Jammu and Kashmir','Ladakh','Lakshadweep','Puducherry'
]

class Command(BaseCommand):
    help = "Seed States, Districts, and Tehsils from CSV files in cases/data. Files: districts.csv (state,district), tehsils.csv (state,district,tehsil)"

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Delete existing District/Tehsil and reseed (States preserved)')
        parser.add_argument('--data-dir', type=str, default='cases/data', help='Directory containing CSVs')

    def handle(self, *args, **options):
        data_dir = Path(options['data_dir'])
        districts_csv = data_dir / 'districts.csv'
        tehsils_csv = data_dir / 'tehsils.csv'

        with transaction.atomic():
            # Seed States
            self.stdout.write(self.style.NOTICE('Seeding States...'))
            for name in STATES:
                State.objects.get_or_create(name=name)
            self.stdout.write(self.style.SUCCESS(f'Seeded {State.objects.count()} states.'))

            if options['reset']:
                self.stdout.write(self.style.WARNING('Reset mode: deleting all Districts and Tehsils...'))
                Tehsil.objects.all().delete()
                District.objects.all().delete()

            # Seed Districts
            if districts_csv.exists():
                self.stdout.write(self.style.NOTICE(f'Seeding Districts from {districts_csv}...'))
                count = 0
                with districts_csv.open(newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        state_name = (row.get('state') or '').strip()
                        district_name = (row.get('district') or '').strip()
                        if not state_name or not district_name:
                            continue
                        state = State.objects.filter(name__iexact=state_name).first()
                        if not state:
                            self.stdout.write(self.style.WARNING(f'State not found for district: {state_name} / {district_name}'))
                            continue
                        District.objects.get_or_create(name=district_name, state=state)
                        count += 1
                self.stdout.write(self.style.SUCCESS(f'District seed processed {count} rows. Current Districts: {District.objects.count()}'))
            else:
                self.stdout.write(self.style.WARNING('districts.csv not found; skipping District seed.'))

            # Seed Tehsils
            if tehsils_csv.exists():
                self.stdout.write(self.style.NOTICE(f'Seeding Tehsils from {tehsils_csv}...'))
                count = 0
                with tehsils_csv.open(newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        state_name = (row.get('state') or '').strip()
                        district_name = (row.get('district') or '').strip()
                        tehsil_name = (row.get('tehsil') or '').strip()
                        if not state_name or not district_name or not tehsil_name:
                            continue
                        state = State.objects.filter(name__iexact=state_name).first()
                        if not state:
                            self.stdout.write(self.style.WARNING(f'State not found for tehsil: {state_name} / {district_name} / {tehsil_name}'))
                            continue
                        district = District.objects.filter(name__iexact=district_name, state=state).first()
                        if not district:
                            self.stdout.write(self.style.WARNING(f'District not found for tehsil: {state_name} / {district_name} / {tehsil_name}'))
                            continue
                        Tehsil.objects.get_or_create(name=tehsil_name, district=district)
                        count += 1
                self.stdout.write(self.style.SUCCESS(f'Tehsil seed processed {count} rows. Current Tehsils: {Tehsil.objects.count()}'))
            else:
                self.stdout.write(self.style.WARNING('tehsils.csv not found; skipping Tehsil seed.'))

        self.stdout.write(self.style.SUCCESS('Location seeding complete.'))
