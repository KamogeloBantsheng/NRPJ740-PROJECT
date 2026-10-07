"""Idempotent seed command for residences, locations, and fault categories (Table 5.7, FR-05, BR-09)."""

import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.locations.models import FaultCategory, Location, LocationKind, Residence

PREAPPROVED_FAULT_CATEGORIES = (
    "Plumbing",
    "Electrical",
    "Carpentry",
    "Locks and doors",
    "Other",
)


class Command(BaseCommand):
    """Seed reference data including Moroka Hall residence, locations, and fault categories."""

    help = "Seed residences, real rooms and common areas, and approved fault categories."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            default=None,
            help="Path to custom locations CSV file (defaults to data/seed/locations.csv).",
        )

    def handle(self, *args, **options):
        csv_arg = options.get("file")
        if csv_arg:
            csv_path = Path(csv_arg)
        else:
            # Default to repo root data/seed/locations.csv
            csv_path = Path(settings.BASE_DIR).parent / "data" / "seed" / "locations.csv"

        if not csv_path.exists():
            raise CommandError(f"Locations seed file not found: {csv_path}")

        self.stdout.write(f"Starting seed process using {csv_path}...")

        with transaction.atomic():
            # 1. Seed Moroka Hall Residence
            residence, res_created = Residence.objects.get_or_create(
                name="Moroka Hall of Residence",
                defaults={"is_active": True},
            )
            res_status = "created" if res_created else "already exists"
            self.stdout.write(f"Residence: '{residence.name}' ({res_status})")

            # 2. Seed Fault Categories
            cat_created_count = 0
            cat_existing_count = 0
            for cat_name in PREAPPROVED_FAULT_CATEGORIES:
                _, created = FaultCategory.objects.get_or_create(
                    name=cat_name,
                    defaults={"is_active": True},
                )
                if created:
                    cat_created_count += 1
                else:
                    cat_existing_count += 1
            self.stdout.write(
                f"Fault Categories: {cat_created_count} created, {cat_existing_count} existing."
            )

            # 3. Seed Locations from CSV
            loc_created_count = 0
            loc_existing_count = 0

            with open(csv_path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row_num, row in enumerate(reader, start=2):
                    res_name = row["residence_name"].strip()
                    block = row["block"].strip()
                    floor = int(row["floor"].strip())
                    label = row["label"].strip()
                    kind = row["kind"].strip()

                    if kind not in LocationKind.values:
                        raise CommandError(f"Invalid kind '{kind}' at line {row_num}")

                    # Ensure residence matches or fetch it
                    if res_name == residence.name:
                        target_res = residence
                    else:
                        target_res, _ = Residence.objects.get_or_create(
                            name=res_name,
                            defaults={"is_active": True},
                        )

                    _, created = Location.objects.get_or_create(
                        residence=target_res,
                        block=block,
                        floor=floor,
                        label=label,
                        defaults={
                            "kind": kind,
                            "is_active": True,
                        },
                    )
                    if created:
                        loc_created_count += 1
                    else:
                        loc_existing_count += 1

            self.stdout.write(
                f"Locations: {loc_created_count} created, {loc_existing_count} existing."
            )

        self.stdout.write(self.style.SUCCESS("Seed process completed successfully."))
