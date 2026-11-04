from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower


class Role(models.TextChoices):
    RESIDENT = "RESIDENT", "Resident"
    TECHNICIAN = "TECHNICIAN", "Technician"
    SUPERVISOR = "SUPERVISOR", "Supervisor"
    WARDEN = "WARDEN", "Warden"
    ADMIN = "ADMIN", "Admin"


class UserManager(BaseUserManager):
    """Custom manager for User model with email as unique identifier."""

    def create_user(
        self,
        email: str,
        full_name: str,
        role: str,
        password: str | None = None,
        residence=None,
        student_number: str | None = None,
        **extra_fields,
    ):
        if not email:
            raise ValueError("The Email field must be set.")
        if not full_name:
            raise ValueError("The full_name field must be set.")
        if not role or role not in Role.values:
            raise ValueError(f"Invalid role: {role}")

        email = self.normalize_email(email)
        user = self.model(
            email=email,
            full_name=full_name,
            role=role,
            residence=residence,
            student_number=student_number,
            **extra_fields,
        )
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user


class User(AbstractBaseUser):
    """Custom user model implementing Table 5.7 specifications."""

    id = models.BigAutoField(primary_key=True)
    email = models.EmailField(max_length=254, unique=True)
    full_name = models.CharField(max_length=150)
    student_number = models.CharField(max_length=20, null=True, blank=True)
    role = models.CharField(max_length=12, choices=Role.choices)
    residence = models.ForeignKey(
        "locations.Residence",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="users",
    )
    assigned_location = models.ForeignKey(
        "locations.Location",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="assigned_residents",
    )
    password = models.CharField(max_length=128)
    must_change_password = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ("full_name", "role")

    class Meta:
        db_table = "users"
        constraints = (
            models.UniqueConstraint(
                Lower("email"),
                name="unique_lower_email",
            ),
            models.UniqueConstraint(
                fields=["student_number"],
                condition=models.Q(student_number__isnull=False),
                name="unique_student_number_not_null",
            ),
            models.CheckConstraint(
                condition=models.Q(role__in=Role.values),
                name="check_user_role",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(role__in=[Role.RESIDENT, Role.WARDEN], residence__isnull=False)
                    | models.Q(~models.Q(role__in=[Role.RESIDENT, Role.WARDEN]), residence__isnull=True)
                ),
                name="check_residence_set_for_resident_or_warden_only",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(role=Role.RESIDENT, student_number__isnull=False)
                    | ~models.Q(role=Role.RESIDENT)
                ),
                name="check_student_number_required_for_resident",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(assigned_location__isnull=True)
                    | models.Q(role=Role.RESIDENT)
                ),
                name="check_assigned_location_for_resident_only",
            ),
        )
        ordering = ("email",)

    def __str__(self):
        return f"{self.email} ({self.role})"
