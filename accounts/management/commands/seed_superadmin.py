import os

from django.core.management.base import BaseCommand, CommandError

from accounts.models import Role, User


class Command(BaseCommand):
    help = 'Creates (or updates) a single Super Admin user for initial access to /admin/ and the API.'

    def add_arguments(self, parser):
        parser.add_argument('--email', default=os.environ.get('SUPERADMIN_EMAIL'))
        parser.add_argument('--password', default=os.environ.get('SUPERADMIN_PASSWORD'))
        parser.add_argument('--first-name', default=os.environ.get('SUPERADMIN_FIRST_NAME', 'Super'))
        parser.add_argument('--last-name', default=os.environ.get('SUPERADMIN_LAST_NAME', 'Admin'))

    def handle(self, *args, **options):
        email = options['email']
        password = options['password']

        if not email or not password:
            raise CommandError(
                'Both --email and --password are required '
                '(or set SUPERADMIN_EMAIL / SUPERADMIN_PASSWORD env vars).'
            )

        user, created = User.objects.get_or_create(
            email=email.lower(),
            defaults={
                'role': Role.SUPER_ADMIN,
                'first_name': options['first_name'],
                'last_name': options['last_name'],
                'is_staff': True,
                'is_superuser': True,
            },
        )

        if not created:
            user.role = Role.SUPER_ADMIN
            user.is_staff = True
            user.is_superuser = True

        user.set_password(password)
        user.full_clean(exclude=['password'])
        user.save()

        verb = 'Created' if created else 'Updated'
        self.stdout.write(self.style.SUCCESS(f'{verb} Super Admin: {user.email}'))
