"""Serializers for Location and FaultCategory reference data (Table 5.7, FR-05)."""

from rest_framework import serializers

from apps.locations.models import FaultCategory, Location, Residence


class ResidenceSerializer(serializers.ModelSerializer):
    """Serializer for residence reference data."""

    class Meta:
        model = Residence
        fields = ("id", "name")


class LocationSerializer(serializers.ModelSerializer):
    """Serializer for room and common area locations within a residence."""

    display_name = serializers.SerializerMethodField()

    class Meta:
        model = Location
        fields = (
            "id",
            "residence_id",
            "block",
            "floor",
            "label",
            "kind",
            "display_name",
        )

    def get_display_name(self, obj: Location) -> str:
        kind_label = "Room" if obj.kind == "ROOM" else "Common Area"
        return f"Block {obj.block}, Fl {obj.floor} - {obj.label} ({kind_label})"


class FaultCategorySerializer(serializers.ModelSerializer):
    """Serializer for approved maintenance fault categories."""

    class Meta:
        model = FaultCategory
        fields = ("id", "name")
