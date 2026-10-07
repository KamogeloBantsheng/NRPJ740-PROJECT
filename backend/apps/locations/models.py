from django.db import models


class LocationKind(models.TextChoices):
    ROOM = "ROOM", "Room"
    COMMON_AREA = "COMMON_AREA", "Common Area"


class Residence(models.Model):
    """Residence building domain model (Table 5.7)."""

    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "residences"
        ordering = ("name",)

    def __str__(self):
        return self.name


class Location(models.Model):
    """Specific room or common area within a residence (Table 5.7)."""

    id = models.BigAutoField(primary_key=True)
    residence = models.ForeignKey(
        Residence,
        on_delete=models.RESTRICT,
        related_name="locations",
    )
    block = models.CharField(max_length=30)
    floor = models.SmallIntegerField()  # Ground floor is 0
    label = models.CharField(max_length=60)
    kind = models.CharField(max_length=12, choices=LocationKind.choices)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "locations"
        constraints = (
            models.UniqueConstraint(
                fields=["residence", "block", "floor", "label"],
                name="unique_residence_block_floor_label",
            ),
            models.CheckConstraint(
                condition=models.Q(kind__in=LocationKind.values),
                name="check_location_kind",
            ),
        )
        ordering = ("residence", "block", "floor", "label")

    def __str__(self):
        return f"{self.residence.name} - Block {self.block} Fl {self.floor} ({self.label})"


class FaultCategory(models.Model):
    """Classification of maintenance fault (Table 5.7)."""

    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=60, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "fault_categories"
        verbose_name_plural = "fault categories"
        ordering = ("name",)

    def __str__(self):
        return self.name
