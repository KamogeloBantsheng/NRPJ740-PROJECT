"""Serializers for audit log domain records (FR-18, SCR-13)."""

from rest_framework import serializers
from apps.audit.models import AuditAction, AuditEvent


class AuditUserMiniSerializer(serializers.Serializer):
    """Compact user representation for actor/target in audit trail."""

    id = serializers.IntegerField()
    email = serializers.EmailField()
    full_name = serializers.CharField()
    role = serializers.CharField()


class AuditEventItemSerializer(serializers.ModelSerializer):
    """Detailed audit event representation for administrative inspection."""

    actor = AuditUserMiniSerializer(read_only=True)
    target_user = AuditUserMiniSerializer(read_only=True)
    action_label = serializers.CharField(source="get_action_display", read_only=True)
    tracking_number = serializers.SerializerMethodField()

    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "occurred_at",
            "action",
            "action_label",
            "actor",
            "target_user",
            "request_id",
            "tracking_number",
            "work_order_id",
            "from_status",
            "to_status",
            "note",
            "details",
        ]

    def get_tracking_number(self, obj: AuditEvent) -> str | None:
        if obj.request_id:
            return f"MR-{obj.request_id:06d}"
        return None
