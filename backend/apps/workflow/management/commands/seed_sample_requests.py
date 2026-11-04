"""Sample requests for the evaluation profile (Section 8), so a fresh system has data to show.

They go through TransitionService like real work, so each has a true audit history. The command
does nothing once any request exists, which keeps a repeated start from adding more.
"""

from django.core.management.base import BaseCommand

from apps.accounts.models import Role, User
from apps.locations.models import FaultCategory, Location, LocationKind
from apps.workflow.models import MaintenanceRequest, Priority
from apps.workflow.services import TransitionService

# (category, description, the steps to walk the request through)
SAMPLES = (
    ("Plumbing", "Hot water tap in the second floor bathroom will not close fully.", ()),
    ("Electrical", "The corridor light outside the laundry flickers and then goes off.", ("approve",)),
    ("Locks and doors", "Fire door on the stairwell does not latch when it swings shut.", ("approve", "assign")),
    (
        "Carpentry",
        "Study desk drawer runner has come off and the drawer will not open.",
        ("approve", "assign", "start"),
    ),
    (
        "Plumbing",
        "Basin in the common bathroom drains very slowly and water stands in it.",
        ("approve", "assign", "start", "complete"),
    ),
    (
        "Electrical",
        "Plug point next to the kitchen counter sparks when anything is plugged in.",
        ("approve", "assign", "start", "complete", "close"),
    ),
)


class Command(BaseCommand):
    help = "Seed sample maintenance requests in different lifecycle states."

    def handle(self, *args, **options):
        if MaintenanceRequest.objects.exists():
            self.stdout.write("Sample requests skipped: requests already exist.")
            return

        resident = User.objects.filter(role=Role.RESIDENT, assigned_location__isnull=False).first()
        supervisor = User.objects.filter(role=Role.SUPERVISOR, is_active=True).first()
        technician = User.objects.filter(role=Role.TECHNICIAN, is_active=True).first()
        common_area = Location.objects.filter(residence=resident.residence, kind=LocationKind.COMMON_AREA).first()

        steps = {
            "approve": (supervisor, "APPROVE", {"priority": Priority.MEDIUM}),
            "assign": (supervisor, "ASSIGN", {"technician_id": technician.id}),
            "start": (technician, "START_WORK", {}),
            "complete": (technician, "COMPLETE_WORK", {"note": "Fault found, repaired and tested before leaving."}),
            "close": (supervisor, "VERIFY_CLOSE", {}),
        }

        for category_name, description, walk in SAMPLES:
            req, _ = TransitionService.submit_request(
                resident=resident,
                location=common_area,
                category=FaultCategory.objects.get(name=category_name),
                description=description,
            )
            for step in walk:
                actor, action, payload = steps[step]
                req = TransitionService.execute(
                    request_id=req.id,
                    action=action,
                    actor=actor,
                    expected_status=req.status,
                    payload=payload,
                )

        self.stdout.write(self.style.SUCCESS(f"Seeded {len(SAMPLES)} sample requests."))
