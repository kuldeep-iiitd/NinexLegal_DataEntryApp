from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, User
from django.contrib.auth.models import Permission

class Command(BaseCommand):
    help = 'Create ADMIN and CO-ADMIN groups and assign users to them'

    def add_arguments(self, parser):
        parser.add_argument(
            '--add-user',
            type=str,
            help='Add a specific user to ADMIN group (provide username)',
        )

    def handle(self, *args, **options):
        # Create ADMIN group
        admin_group, created = Group.objects.get_or_create(name='ADMIN')
        if created:
            self.stdout.write(
                self.style.SUCCESS('Successfully created ADMIN group')
            )
        else:
            self.stdout.write('ADMIN group already exists')

        # Create CO-ADMIN group
        co_admin_group, created = Group.objects.get_or_create(name='CO-ADMIN')
        if created:
            self.stdout.write(
                self.style.SUCCESS('Successfully created CO-ADMIN group')
            )
        else:
            self.stdout.write('CO-ADMIN group already exists')

        # Add all superusers to ADMIN group
        superusers = User.objects.filter(is_superuser=True)
        for user in superusers:
            admin_group.user_set.add(user)
            self.stdout.write(
                self.style.SUCCESS(f'Added superuser {user.username} to ADMIN group')
            )

        # Add specific user if provided
        if options['add_user']:
            try:
                user = User.objects.get(username=options['add_user'])
                admin_group.user_set.add(user)
                self.stdout.write(
                    self.style.SUCCESS(f'Added user {user.username} to ADMIN group')
                )
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'User {options["add_user"]} does not exist')
                )

        self.stdout.write('\n' + '='*50)
        self.stdout.write('SETUP COMPLETE!')
        self.stdout.write('='*50)
        self.stdout.write(f'ADMIN group members: {list(admin_group.user_set.values_list("username", flat=True))}')
        self.stdout.write(f'CO-ADMIN group members: {list(co_admin_group.user_set.values_list("username", flat=True))}')
        self.stdout.write('\nTo add more users to groups:')
        self.stdout.write('1. Go to Django Admin Panel')
        self.stdout.write('2. Navigate to Authentication and Authorization > Groups')
        self.stdout.write('3. Select ADMIN or CO-ADMIN group')
        self.stdout.write('4. Add users to the group')
        self.stdout.write('\nOr use: python manage.py setup_groups --add-user USERNAME')
