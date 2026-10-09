"""Serializers for request submission, listing, detail, and timeline history (FR-05, FR-06, FR-18)."""


from rest_framework import serializers

from apps.accounts.models import Role
from apps.audit.models import AuditEvent
from apps.audit.services import AuditService
from apps.locations.models import FaultCategory, Location
from apps.workflow.models import MaintenanceRequest, Priority


class TransitionExecuteSerializer(serializers.Serializer):
    """Payload for executing a lifecycle state transition (Table 5.1)."""

    action = serializers.CharField(required=True)
    expected_status = serializers.CharField(required=True)
    note = serializers.CharField(required=False, allow_blank=True, default="")
    priority = serializers.ChoiceField(
        choices=Priority.choices,
        required=False,
        allow_null=True,
        default=None,
    )


class SubmitRequestSerializer(serializers.Serializer):
    """Payload for submitting a new maintenance fault report (FR-05, SCR-04)."""

    location_id = serializers.IntegerField(required=True)
    category_id = serializers.IntegerField(required=True)
    description = serializers.CharField(
        required=True,
        min_length=10,
        max_length=2000,
        trim_whitespace=True,
    )
    client_token = serializers.UUIDField(required=False, default=None)

    def validate_location_id(self, value: int) -> int:
        if not Location.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Selected location does not exist or is inactive.")
        return value

    def validate_category_id(self, value: int) -> int:
        if not FaultCategory.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Selected fault category does not exist or is inactive.")
        return value


class RequestTimelineEventSerializer(serializers.ModelSerializer):
    """Chronological lifecycle events for request timeline display (FR-18, SCR-05)."""

    actor_role = serializers.SerializerMethodField()
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = AuditEvent
        fields = (
            "id",
            "occurred_at",
            "action",
            "actor_role",
            "actor_name",
            "from_status",
            "to_status",
            "note",
            "details",
        )

    def get_actor_role(self, obj: AuditEvent) -> str:
        return obj.actor.role if obj.actor else "SYSTEM"

    def get_actor_name(self, obj: AuditEvent) -> str:
        return obj.actor.full_name if obj.actor else "System"


class MaintenanceRequestListSerializer(serializers.ModelSerializer):
    """Compact summary serializer for request queue and list views (SCR-03)."""

    tracking_number = serializers.CharField(read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    location_label = serializers.CharField(source="location.label", read_only=True)
    location_block = serializers.CharField(source="location.block", read_only=True)
    location_floor = serializers.IntegerField(source="location.floor", read_only=True)
    location_kind = serializers.CharField(source="location.kind", read_only=True)
    description_snippet = serializers.SerializerMethodField()
    resident_name = serializers.SerializerMethodField()

    class Meta:
        model = MaintenanceRequest
        fields = (
            "id",
            "tracking_number",
            "status",
            "priority",
            "category_name",
            "location_label",
            "location_block",
            "location_floor",
            "location_kind",
            "description_snippet",
            "resident_name",
            "created_at",
            "closed_at",
        )

    def get_description_snippet(self, obj: MaintenanceRequest) -> str:
        if len(obj.description) > 100:
            return f"{obj.description[:97]}..."
        return obj.description

    def get_resident_name(self, obj: MaintenanceRequest) -> str | None:
        user = self.context.get("request").user if "request" in self.context else None
        if user and user.role in (Role.WARDEN, Role.TECHNICIAN):
            return None
        return obj.resident.full_name


class MaintenanceRequestDetailSerializer(serializers.ModelSerializer):
    """Full detail serializer with nested resident, location, category, and timeline (SCR-05)."""

    tracking_number = serializers.CharField(read_only=True)
    resident = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    timeline = serializers.SerializerMethodField()

    class Meta:
        model = MaintenanceRequest
        fields = (
            "id",
            "tracking_number",
            "status",
            "priority",
            "description",
            "client_token",
            "created_at",
            "updated_at",
            "closed_at",
            "resident",
            "location",
            "category",
            "timeline",
        )

    def get_resident(self, obj: MaintenanceRequest) -> dict | None:
        user = self.context.get("request").user if "request" in self.context else None
        if user and user.role in (Role.WARDEN, Role.TECHNICIAN):
            return None
        return {
            "id": obj.resident_id,
            "full_name": obj.resident.full_name,
            "email": obj.resident.email,
            "student_number": obj.resident.student_number,
        }

    def get_location(self, obj: MaintenanceRequest) -> dict:
        loc = obj.location
        return {
            "id": loc.id,
            "residence_name": loc.residence.name if loc.residence else "Moroka Hall",
            "block": loc.block,
            "floor": loc.floor,
            "label": loc.label,
            "kind": loc.kind,
        }

    def get_category(self, obj: MaintenanceRequest) -> dict:
        return {
            "id": obj.category_id,
            "name": obj.category.name,
        }

    def get_timeline(self, obj: MaintenanceRequest) -> list[dict]:
        events = AuditService.get_request_history(obj.id)
        return RequestTimelineEventSerializer(events, many=True).data
