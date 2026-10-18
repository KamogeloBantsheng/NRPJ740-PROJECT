import csv
import io
import re
import secrets

from config.exceptions import (
    ConflictException,
    ForbiddenException,
    ThrottledException,
    UnauthenticatedException,
    ValidationException,
)
from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpRequest
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.audit.models import AuditAction
from apps.audit.services import AuditService
from apps.locations.models import Location, LocationKind, Residence


def get_client_ip(request: HttpRequest) -> str:
    """Extract client IP address handling reverse proxy X-Forwarded-For headers."""
    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded:
        return x_forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "127.0.0.1")


class AuthService:
    """Handles authentication, session rotation, password policy, and login throttling."""

    MAX_FAILED_ATTEMPTS = 5
    THROTTLE_WINDOW_SECONDS = 60

    @classmethod
    def authenticate(
        cls,
        *,
        email: str,
        password: str,
        request: HttpRequest,
    ) -> User:
        """Authenticate user by email and password, enforcing sliding window throttling."""
        normalized_email = email.strip().lower()
        ip_address = get_client_ip(request)

        # 1. Check sliding window throttle (Section 4.4, NFR-02)
        failed_count = AuditService.count_failed_logins(
            email=normalized_email,
            ip_address=ip_address,
            window_seconds=cls.THROTTLE_WINDOW_SECONDS,
        )
        if failed_count >= cls.MAX_FAILED_ATTEMPTS:
            raise ThrottledException("Too many failed login attempts. Please try again in a minute.")

        # 2. Look up user
        user = User.objects.filter(email__iexact=normalized_email).first()

        # Generic error message per NFR-02 to prevent account enumeration
        generic_error = "Invalid email or password."

        if user is None or not user.check_password(password):
            AuditService.record(
                action=AuditAction.LOGIN_FAILED,
                target_user=user,
                details={
                    "email": normalized_email,
                    "ip_address": ip_address,
                    "reason": "invalid_credentials",
                },
            )
            raise UnauthenticatedException(generic_error)

        # 3. Check active status (BR-07)
        if not user.is_active:
            AuditService.record(
                action=AuditAction.LOGIN_FAILED,
                actor=user,
                target_user=user,
                details={
                    "email": normalized_email,
                    "ip_address": ip_address,
                    "reason": "account_deactivated",
                },
            )
            raise UnauthenticatedException(generic_error)

        # 4. Successful login: update last_login and cycle session (ADR-03)
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])

        # Cycle session to prevent session fixation and attach authenticated user
        django_login(request, user)

        return user

    @classmethod
    def logout(cls, request: HttpRequest) -> None:
        """Terminate the current user session and flush cookies."""
        django_logout(request)

    @classmethod
    def change_password(
        cls,
        *,
        user: User,
        current_password: str | None,
        new_password: str,
        request: HttpRequest | None = None,
    ) -> None:
        """Validate and apply a password change with Argon2id hashing (FR-02)."""
        # If password change is forced by temp password, current_password can be optional if already validated
        if user.must_change_password:
            if current_password and not user.check_password(current_password):
                raise ValidationException(
                    "Current temporary password is incorrect.",
                    fields={"current_password": ["Incorrect temporary password."]},
                )
        else:
            if not current_password or not user.check_password(current_password):
                raise ValidationException(
                    "Current password is incorrect.",
                    fields={"current_password": ["Incorrect password."]},
                )

        # Length validation (>= 10 chars per Section 2 / Security)
        if len(new_password) < 10:
            raise ValidationException(
                "Password must be at least 10 characters long.",
                fields={"new_password": ["Password must be at least 10 characters long."]},
            )

        # Django built-in validators check
        try:
            validate_password(new_password, user=user)
        except DjangoValidationError as exc:
            raise ValidationException(
                "Password does not meet complexity requirements.",
                fields={"new_password": list(exc.messages)},
            ) from exc

        # Update password hash and clear mandatory change flag
        was_forced = user.must_change_password
        user.set_password(new_password)
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])

        if request is not None:
            update_session_auth_hash(request, user)

        # Audit event
        AuditService.record(
            action=AuditAction.PASSWORD_CHANGED,
            actor=user,
            target_user=user,
            details={"forced": was_forced},
        )


def terminate_user_sessions(user_id: int) -> None:
    """Terminate and delete all active sessions for a given user (BR-07)."""
    try:
        from django.contrib.sessions.models import Session

        for session in Session.objects.filter(expire_date__gte=timezone.now()):
            try:
                data = session.get_decoded()
                if data.get("_auth_user_id") == str(user_id):
                    session.delete()
            except Exception:  # noqa: BLE001
                pass
    except Exception:  # noqa: BLE001
        pass


def generate_temp_password(length: int = 12) -> str:
    """Generate a high-entropy temporary password meeting security requirements."""
    alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


class UserAdminService:
    """Handles user administration, role assignment, active status guards, and password resets (FR-03, BR-07)."""

    @classmethod
    def list_users(
        cls,
        *,
        search: str = "",
        role: str = "",
        is_active: bool | None = None,
        residence_id: int | None = None,
    ):
        """List users with optional filtering and active work-order counts for technicians."""
        qs = User.objects.select_related("residence").annotate(
            active_work_orders_count=Count(
                "work_orders",
                filter=Q(work_orders__ended_at__isnull=True),
            )
        )

        if search.strip():
            q = search.strip().lower()
            qs = qs.filter(
                Q(email__icontains=q)
                | Q(full_name__icontains=q)
                | Q(student_number__icontains=q)
            )

        if role and role in Role.values:
            qs = qs.filter(role=role)

        if is_active is not None:
            qs = qs.filter(is_active=is_active)

        if residence_id:
            qs = qs.filter(residence_id=residence_id)

        return qs.order_by("-created_at")

    @classmethod
    def create_user(
        cls,
        *,
        actor: User,
        email: str,
        full_name: str,
        role: str,
        residence_id: int | None = None,
        assigned_location_id: int | None = None,
        student_number: str | None = None,
    ) -> tuple[User, str]:
        """Create a new user with temporary password and enforced constraint checks (FR-03, BR-07)."""
        normalized_email = email.strip().lower()
        trimmed_name = full_name.strip()
        trimmed_student = student_number.strip() if student_number else None

        field_errors = {}

        if not normalized_email:
            field_errors["email"] = ["Email is required."]
        elif User.objects.filter(email__iexact=normalized_email).exists():
            field_errors["email"] = ["A user with this email address already exists."]

        if not trimmed_name:
            field_errors["full_name"] = ["Full name is required."]

        if not role or role not in Role.values:
            field_errors["role"] = [f"Invalid role '{role}'. Must be one of: {', '.join(Role.values)}."]

        residence = None
        if role in (Role.RESIDENT, Role.WARDEN):
            if not residence_id:
                residence = Residence.objects.filter(is_active=True).first()
                if not residence:
                    field_errors["residence"] = ["Residence is required for residents and wardens."]
            else:
                residence = Residence.objects.filter(id=residence_id).first()
                if not residence:
                    field_errors["residence"] = ["Specified residence does not exist."]
        else:
            if residence_id:
                field_errors["residence"] = [
                    "Residence cannot be assigned to supervisors, technicians, or administrators."
                ]

        assigned_location = None
        if role == Role.RESIDENT:
            if not trimmed_student:
                field_errors["student_number"] = ["Student number is required for residents."]
            elif User.objects.filter(student_number__iexact=trimmed_student).exists():
                field_errors["student_number"] = ["A user with this student number already exists."]

            if assigned_location_id:
                assigned_location = Location.objects.filter(
                    id=assigned_location_id,
                    residence=residence,
                    is_active=True,
                    kind=LocationKind.ROOM,
                ).first()
                if not assigned_location:
                    field_errors["assigned_location_id"] = [
                        "Selected room does not exist, is inactive, or is not in the assigned residence."
                    ]
        else:
            if trimmed_student:
                field_errors["student_number"] = ["Student number can only be assigned to residents."]
            if assigned_location_id:
                field_errors["assigned_location_id"] = ["A room can only be assigned to residents."]

        if field_errors:
            raise ValidationException("Validation failed while creating user.", fields=field_errors)

        temp_password = generate_temp_password(12)

        user = User.objects.create(
            email=normalized_email,
            full_name=trimmed_name,
            role=role,
            residence=residence,
            assigned_location=assigned_location,
            student_number=trimmed_student,
            must_change_password=True,
            is_active=True,
        )
        user.set_password(temp_password)
        user.save(update_fields=["password"])

        AuditService.record(
            action=AuditAction.USER_CREATED,
            actor=actor,
            target_user=user,
            details={
                "email": user.email,
                "role": user.role,
                "full_name": user.full_name,
            },
        )

        return user, temp_password

    @classmethod
    def update_user(
        cls,
        *,
        actor: User,
        user: User,
        full_name: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
        residence_id: int | None = None,
        assigned_location_id: int | None = None,
        student_number: str | None = None,
    ) -> User:
        """Update user profile, role, or active status enforcing BR-07 guards (TC-06)."""
        from apps.workflow.models import WorkOrder

        # 1. Active status guard check (BR-07, TC-06)
        if is_active is not None and is_active != user.is_active:
            if is_active is False:
                # Cannot deactivate the last active Admin
                if user.role == Role.ADMIN:
                    active_admins = User.objects.filter(role=Role.ADMIN, is_active=True).exclude(id=user.id).count()
                    if active_admins < 1:
                        raise ConflictException("Cannot deactivate the last active administrator.")

                # Cannot deactivate a Technician with active work orders
                if user.role == Role.TECHNICIAN:
                    has_active_orders = WorkOrder.objects.filter(technician=user, ended_at__isnull=True).exists()
                    if has_active_orders:
                        raise ConflictException("Cannot deactivate a technician with active work orders.")

                user.is_active = False
                terminate_user_sessions(user.id)
                AuditService.record(
                    action=AuditAction.USER_DEACTIVATED,
                    actor=actor,
                    target_user=user,
                    details={"email": user.email},
                )
            else:
                user.is_active = True
                AuditService.record(
                    action=AuditAction.USER_REACTIVATED,
                    actor=actor,
                    target_user=user,
                    details={"email": user.email},
                )

        # 2. Role change guard check (BR-07, TC-06)
        if role is not None and role != user.role:
            if role not in Role.values:
                raise ValidationException(f"Invalid role '{role}'.", fields={"role": ["Invalid role."]})

            # Cannot demote last active Admin
            if user.role == Role.ADMIN and role != Role.ADMIN and user.is_active:
                active_admins = User.objects.filter(role=Role.ADMIN, is_active=True).exclude(id=user.id).count()
                if active_admins < 1:
                    raise ConflictException("Cannot demote the last active administrator.")

            # Cannot change role of Technician with active work orders
            if user.role == Role.TECHNICIAN and role != Role.TECHNICIAN:
                has_active_orders = WorkOrder.objects.filter(technician=user, ended_at__isnull=True).exists()
                if has_active_orders:
                    raise ConflictException("Cannot change role of a technician with active work orders.")

            old_role = user.role
            user.role = role

            # Adjust residence / student_number according to new role constraints
            if role in (Role.RESIDENT, Role.WARDEN):
                if residence_id:
                    res = Residence.objects.filter(id=residence_id).first()
                    if not res:
                        raise ValidationException("Invalid residence.", fields={"residence": ["Residence not found."]})
                    user.residence = res
                elif not user.residence:
                    user.residence = Residence.objects.filter(is_active=True).first()
            else:
                user.residence = None

            if role == Role.RESIDENT:
                if student_number:
                    user.student_number = student_number.strip()
                elif not user.student_number:
                    raise ValidationException(
                        "Student number required for resident.",
                        fields={"student_number": ["Required."]},
                    )
            else:
                user.student_number = None

            AuditService.record(
                action=AuditAction.USER_ROLE_CHANGED,
                actor=actor,
                target_user=user,
                details={"from_role": old_role, "to_role": role},
            )

        # 3. Room assignment update
        target_role = role if role is not None else user.role
        if target_role == Role.RESIDENT:
            if assigned_location_id is not None:
                if assigned_location_id in (0, -1):
                    user.assigned_location = None
                else:
                    assigned_loc = Location.objects.filter(
                        id=assigned_location_id,
                        residence=user.residence,
                        is_active=True,
                        kind=LocationKind.ROOM,
                    ).first()
                    if not assigned_loc:
                        raise ValidationException(
                            "Invalid room selection.",
                            fields={
                                "assigned_location_id": [
                                    "Selected room does not exist or is not a room in this residence."
                                ]
                            },
                        )
                    user.assigned_location = assigned_loc
        else:
            if assigned_location_id:
                raise ValidationException(
                    "Assigned location can only be set for residents.",
                    fields={"assigned_location_id": ["Assigned location can only be set for residents."]},
                )
            user.assigned_location = None

        # 4. Other fields
        if full_name is not None and full_name.strip():
            user.full_name = full_name.strip()

        user.save()
        return user

    @classmethod
    def reset_password(cls, *, actor: User, user: User) -> str:
        """Reset user password to a newly generated temporary password (FR-03)."""
        temp_password = generate_temp_password(12)
        user.set_password(temp_password)
        user.must_change_password = True
        user.save(update_fields=["password", "must_change_password"])

        # Flush active sessions
        terminate_user_sessions(user.id)

        AuditService.record(
            action=AuditAction.PASSWORD_RESET,
            actor=actor,
            target_user=user,
            details={"email": user.email, "forced": True},
        )

        return temp_password


class UserImportService:
    """All-or-nothing batch CSV import service for resident accounts (FR-04, NFR-03, TC-07, TC-08, TC-09)."""

    MAX_FILE_BYTES = 2 * 1024 * 1024  # 2 MB limit
    MAX_ROWS = 2000

    EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    @classmethod
    def import_residents_csv(
        cls,
        *,
        actor: User,
        csv_file_bytes: bytes,
    ) -> dict:
        """Validate and atomically import resident accounts from CSV file (all-or-nothing)."""
        # 1. Authorize caller
        if actor.role != Role.ADMIN:
            raise ForbiddenException("Only administrators can import user accounts.")

        # 2. File size constraint (TC-09)
        if len(csv_file_bytes) > cls.MAX_FILE_BYTES:
            raise ValidationException(
                f"File size exceeds the 2 MB maximum limit ({len(csv_file_bytes)} bytes).",
                fields={"file": ["File size exceeds 2 MB limit."]},
            )

        # 3. UTF-8 decode check (TC-09)
        try:
            content = csv_file_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise ValidationException(
                "CSV file must be valid UTF-8 encoded text.",
                fields={"file": ["File is not valid UTF-8 encoded."]},
            )

        # 4. Parse CSV
        reader = csv.DictReader(io.StringIO(content))
        if not reader.fieldnames:
            raise ValidationException(
                "CSV file is empty or missing a header row.",
                fields={"file": ["CSV file contains no headers."]},
            )

        # Normalize header keys
        header_map = {col.strip().lower(): col for col in reader.fieldnames}
        for req_col in ("email", "full_name", "student_number"):
            if req_col not in header_map:
                raise ValidationException(
                    f"CSV missing mandatory column: '{req_col}'. Required headers: email, full_name, student_number",
                    fields={"headers": [f"Missing '{req_col}' column."]},
                )

        default_residence = Residence.objects.filter(is_active=True).first()
        if not default_residence:
            raise ValidationException("No active residence found in the system to assign residents to.")

        rows_data = []
        errors = []
        seen_emails = set()
        seen_students = set()

        # Row limit check (TC-09)
        row_count = 0

        for idx, row in enumerate(reader, start=2):  # row 1 is header
            row_count += 1
            if row_count > cls.MAX_ROWS:
                raise ValidationException(
                    f"CSV file exceeds the maximum allowed row count of {cls.MAX_ROWS}.",
                    fields={"file": [f"Maximum row limit is {cls.MAX_ROWS}."]},
                )

            raw_email = row.get(header_map["email"], "").strip()
            raw_name = row.get(header_map["full_name"], "").strip()
            raw_student = row.get(header_map["student_number"], "").strip()

            email_lower = raw_email.lower()

            row_errors = []

            # Email validation
            if not raw_email:
                row_errors.append("Email is required.")
            elif not cls.EMAIL_REGEX.match(raw_email):
                row_errors.append(f"Invalid email format: '{raw_email}'.")
            elif email_lower in seen_emails:
                row_errors.append(f"Duplicate email '{raw_email}' within CSV file.")
            else:
                seen_emails.add(email_lower)

            # Name validation
            if not raw_name:
                row_errors.append("Full name is required.")
            elif len(raw_name) > 150:
                row_errors.append("Full name exceeds 150 characters.")

            # Student number validation
            if not raw_student:
                row_errors.append("Student number is required.")
            elif len(raw_student) > 20:
                row_errors.append("Student number exceeds 20 characters.")
            elif raw_student in seen_students:
                row_errors.append(f"Duplicate student number '{raw_student}' within CSV file.")
            else:
                seen_students.add(raw_student)

            if row_errors:
                errors.append({"row": idx, "errors": row_errors})
            else:
                rows_data.append({
                    "row": idx,
                    "email": email_lower,
                    "full_name": raw_name,
                    "student_number": raw_student,
                })

        if row_count == 0:
            raise ValidationException(
                "CSV file contains no data rows.",
                fields={"file": ["File contains no data rows."]},
            )

        # Database collision check against existing records
        if seen_emails:
            existing_emails = set(User.objects.filter(email__in=seen_emails).values_list("email", flat=True))
            for item in rows_data:
                if item["email"] in existing_emails:
                    errors.append({
                        "row": item["row"],
                        "errors": [f"Email '{item['email']}' is already registered in the system."],
                    })

        if seen_students:
            existing_students = set(
                User.objects.filter(student_number__in=seen_students).values_list("student_number", flat=True)
            )
            for item in rows_data:
                if item["student_number"] in existing_students:
                    errors.append({
                        "row": item["row"],
                        "errors": [f"Student number '{item['student_number']}' is already registered in the system."],
                    })

        # All-or-nothing check (TC-08)
        if errors:
            errors.sort(key=lambda x: x["row"])
            raise ValidationException(
                "CSV validation failed. No accounts were created.",
                fields={"bad_rows": errors},
            )

        # Atomic insertion of all records (TC-07)
        created_records = []
        with transaction.atomic():
            for item in rows_data:
                temp_pwd = generate_temp_password(12)
                user = User.objects.create(
                    email=item["email"],
                    full_name=item["full_name"],
                    student_number=item["student_number"],
                    role=Role.RESIDENT,
                    residence=default_residence,
                    must_change_password=True,
                    is_active=True,
                )
                user.set_password(temp_pwd)
                user.save(update_fields=["password"])

                created_records.append({
                    "id": user.id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "student_number": user.student_number,
                    "temporary_password": temp_pwd,
                })

            AuditService.record(
                action=AuditAction.USER_IMPORTED,
                actor=actor,
                details={
                    "total_imported": len(created_records),
                    "residence_id": default_residence.id,
                },
            )

        return {
            "created_count": len(created_records),
            "credentials": created_records,
        }

