"""Idempotent seed command for role demo users (FR-01, Section 4.8, AGENT_BRIEF item 8)."""

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Role, User
from apps.locations.models import Location, LocationKind, Residence

DEMO_USERS = [
    {
        "email": "resident@example.test",
        "full_name": "Demo Resident",
        "role": Role.RESIDENT,
        "student_number": "20240001",
        "requires_residence": True,
        "room_label": "A.203",
    },
    {
        "email": "technician@example.test",
        "full_name": "Demo Technician",
        "role": Role.TECHNICIAN,
        "student_number": None,
        "requires_residence": False,
    },
    {
        "email": "technician2@example.test",
        "full_name": "Demo Technician 2",
        "role": Role.TECHNICIAN,
        "student_number": None,
        "requires_residence": False,
    },
    {
        "email": "supervisor@example.test",
        "full_name": "Demo Supervisor",
        "role": Role.SUPERVISOR,
        "student_number": None,
        "requires_residence": False,
    },
    {
        "email": "warden@example.test",
        "full_name": "Demo Warden",
        "role": Role.WARDEN,
        "student_number": None,
        "requires_residence": True,
    },
    {
        "email": "admin@example.test",
        "full_name": "Demo Administrator",
        "role": Role.ADMIN,
        "student_number": None,
        "requires_residence": False,
    },
]


class Command(BaseCommand):
    """Seed demo accounts for each of the 5 roles using DEMO_PASSWORD."""

    help = "Seed one demo account per role (FR-01) with password from DEMO_PASSWORD setting."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            type=str,
            default=None,
            help="Custom password for demo accounts (defaults to DEMO_PASSWORD setting).",
        )

    def handle(self, *args, **options):
        password = options.get("password") or getattr(settings, "DEMO_PASSWORD", "DemoPass#2026")

        self.stdout.write("Seeding demo accounts for all 5 roles...")

        with transaction.atomic():
            moroka, _ = Residence.objects.get_or_create(
                name="Moroka Hall of Residence",
                defaults={"is_active": True},
            )

            created_count = 0
            updated_count = 0

            for user_def in DEMO_USERS:
                email = user_def["email"]
                residence = moroka if user_def["requires_residence"] else None
                assigned_loc = None
                if user_def.get("room_label") and moroka:
                    assigned_loc = Location.objects.filter(
                        residence=moroka,
                        label=user_def["room_label"],
                        kind=LocationKind.ROOM,
                    ).first() or Location.objects.filter(
                        residence=moroka,
                        kind=LocationKind.ROOM,
                    ).first()

                user = User.objects.filter(email__iexact=email).first()

                if user:
                    user.full_name = user_def["full_name"]
                    user.role = user_def["role"]
                    user.student_number = user_def["student_number"]
                    user.residence = residence
                    user.assigned_location = assigned_loc
                    user.is_active = True
                    user.must_change_password = False
                    user.set_password(password)
                    user.save()
                    updated_count += 1
                    loc_info = f", Room: {assigned_loc.label}" if assigned_loc else ""
                    self.stdout.write(f"Updated demo user: {email} ({user_def['role']}{loc_info})")
                else:
                    User.objects.create_user(
                        email=email,
                        full_name=user_def["full_name"],
                        role=user_def["role"],
                        password=password,
                        residence=residence,
                        student_number=user_def["student_number"],
                        assigned_location=assigned_loc,
                        is_active=True,
                        must_change_password=False,
                    )
                    created_count += 1
                    loc_info = f", Room: {assigned_loc.label}" if assigned_loc else ""
                    self.stdout.write(f"Created demo user: {email} ({user_def['role']}{loc_info})")

            self.stdout.write(
                self.style.SUCCESS(f"Demo users seeding complete: {created_count} created, {updated_count} updated.")
            )

        call_command("seed_sample_requests")
