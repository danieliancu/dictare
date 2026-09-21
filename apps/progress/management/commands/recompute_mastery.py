"""Rebuild PatternMastery from verified exposures only.

    python manage.py recompute_mastery               # every user with attempts
    python manage.py recompute_mastery --user a@b.ro

Run after QA marks speech patterns as present/absent in recordings.
"""

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User
from apps.progress.services import mastery


class Command(BaseCommand):
    help = "Recompute pattern mastery (only phenomena verified as audible count)."

    def add_arguments(self, parser):
        parser.add_argument("--user", help="Email of a single user.")

    def handle(self, *args, **opts):
        users = User.objects.filter(attempts__completed=True).distinct()
        if opts["user"]:
            users = User.objects.filter(email=opts["user"].lower())
            if not users.exists():
                raise CommandError("User not found.")
        count = 0
        for user in users:
            mastery.recompute(user)
            count += 1
        self.stdout.write(self.style.SUCCESS(f"Mastery recomputed for {count} user(s)."))
