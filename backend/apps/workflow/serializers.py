"""Serializers for request submission, listing, detail, and timeline history (FR-05, FR-06, FR-18)."""


from rest_framework import serializers

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.audit.services import AuditService
from apps.locations.models import FaultCategory, Location
from apps.workflow.models import MaintenanceRequest, Priority, WorkOrder


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
    technician_id = serializers.IntegerField(
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
        user = self.context.get("request").user if "request" in self.context else None
        if user and user.role in (Role.WARDEN, Role.TECHNICIAN) and obj.actor and obj.actor.role == Role.RESIDENT:
            return "Resident"
        return obj.actor.full_name if obj.actor else "System"


class TechnicianItemSerializer(serializers.ModelSerializer):
    """Active technician listing with current active task workload for dispatch (SCR-07)."""

    active_tasks_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = User
        fields = (
            "id",
            "full_name",
            "email",
            "is_active",
            "active_tasks_count",
        )


class WorkOrderSerializer(serializers.ModelSerializer):
    """Work order assignment detail (Table 5.7)."""

    technician_name = serializers.CharField(source="technician.full_name", read_only=True)
    technician_email = serializers.CharField(source="technician.email", read_only=True)
    assigned_by_name = serializers.CharField(source="assigned_by.full_name", read_only=True)

    class Meta:
        model = WorkOrder
        fields = (
            "id",
            "request_id",
            "technician_id",
            "technician_name",
            "technician_email",
            "assigned_by_id",
            "assigned_by_name",
            "assigned_at",
            "ended_at",
            "end_reason",
            "is_active",
        )

    def to_representation(self, instance: WorkOrder) -> dict:
        data = super().to_representation(instance)
        # Staff email is personal data: Supervisor and Admin only (Section 5.7)
        request = self.context.get("request")
        if not request or request.user.role not in (Role.SUPERVISOR, Role.ADMIN):
            data.pop("technician_email", None)
        return data


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
    assigned_technician_name = serializers.SerializerMethodField()

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
            "assigned_technician_name",
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

    def get_assigned_technician_name(self, obj: MaintenanceRequest) -> str | None:
        active = getattr(obj, "active_work_orders", None)
        if active is None:
            active = obj.work_orders.filter(ended_at__isnull=True).select_related("technician")
        return next((wo.technician.full_name for wo in active), None)


class MaintenanceRequestDetailSerializer(serializers.ModelSerializer):
    """Full detail serializer with nested resident, location, category, work order, and timeline (SCR-05)."""

    tracking_number = serializers.CharField(read_only=True)
    resident = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    active_work_order = serializers.SerializerMethodField()
    work_orders = serializers.SerializerMethodField()
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
            "is_owner",
            "location",
            "category",
            "active_work_order",
            "work_orders",
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

    def get_is_owner(self, obj: MaintenanceRequest) -> bool:
        """True for the person who reported the fault, who answers clarification questions (T3)."""
        request = self.context.get("request")
        return bool(request and obj.resident_id == request.user.id)

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

    def get_active_work_order(self, obj: MaintenanceRequest) -> dict | None:
        wo = obj.work_orders.filter(ended_at__isnull=True).select_related("technician", "assigned_by").first()
        if not wo:
            return None
        return WorkOrderSerializer(wo, context=self.context).data

    def get_work_orders(self, obj: MaintenanceRequest) -> list[dict]:
        wos = obj.work_orders.select_related("technician", "assigned_by").order_by("-assigned_at")
        return WorkOrderSerializer(wos, many=True, context=self.context).data

    def get_timeline(self, obj: MaintenanceRequest) -> list[dict]:
        events = AuditService.get_request_history(obj.id)
        return RequestTimelineEventSerializer(events, many=True, context=self.context).data
