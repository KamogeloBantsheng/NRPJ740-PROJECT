"""Bulk requests for the load test (NT-04, NFR-06). Never part of a normal start.

Requests are inserted directly for speed, so they have no audit history. Use this only on a
database that is thrown away afterwards.
"""

import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import User
from apps.locations.models import FaultCategory, Location
from apps.workflow.models import MaintenanceRequest, Priority, RequestStatus


class Command(BaseCommand):
    help = "Insert requests for load testing (default 5,000)."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=5000)

    def handle(self, *args, **options):
        rng = random.Random(740)
        resident = User.objects.get(email="resident@example.test")
        locations = list(Location.objects.filter(residence=resident.residence))
        categories = list(FaultCategory.objects.all())
        now = timezone.now()

        def build(index: int) -> MaintenanceRequest:
            status = rng.choice([RequestStatus.SUBMITTED, RequestStatus.APPROVED, RequestStatus.VERIFIED_CLOSED])
            return MaintenanceRequest(
                resident=resident,
                location=rng.choice(locations),
                category=rng.choice(categories),
                description=f"Load test fault number {index} in the residence.",
                status=status,
                priority=None if status == RequestStatus.SUBMITTED else rng.choice(Priority.values),
                closed_at=now if status == RequestStatus.VERIFIED_CLOSED else None,
            )

        requests = [build(index) for index in range(options["count"])]
        MaintenanceRequest.objects.bulk_create(requests, batch_size=500)

        # created_at is set on insert, so spread the ages afterwards
        for offset, request in enumerate(requests):
            request.created_at = now - timedelta(hours=offset % 2000)
        MaintenanceRequest.objects.bulk_update(requests, ["created_at"], batch_size=500)

        self.stdout.write(self.style.SUCCESS(f"Inserted {len(requests)} requests."))
