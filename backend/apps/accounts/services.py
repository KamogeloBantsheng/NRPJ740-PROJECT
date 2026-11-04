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
from django.conf import settings
from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.db.models.functions import Lower
from django.http import HttpRequest
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.audit.models import AuditAction
from apps.audit.services import AuditService
from apps.locations.models import Location, LocationKind, Residence

DANGEROUS_CSV_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_csv_cell(value: str | None) -> str:
    """Neutralize spreadsheet formula injection (CWE-1236) by prefixing dangerous characters with an apostrophe."""
    if not value:
        return ""
    trimmed = value.strip()
    if trimmed.startswith(DANGEROUS_CSV_PREFIXES):
        return f"'{trimmed}"
    return trimmed


def get_client_ip(request: HttpRequest) -> str:
    """Return the client IP that the sign-in throttle should count.

    X-Forwarded-For entries to the left of our own proxy are supplied by the client and can
    be forged, so only the entry appended by a trusted proxy is used. With no trusted proxy
    configured (local development) the header is ignored completely.
    """
    trusted_hops = settings.TRUSTED_PROXY_COUNT
    forwarded = [ip.strip() for ip in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if ip.strip()]
    if trusted_hops > 0 and len(forwarded) >= trusted_hops:
        return forwarded[-trusted_hops]
    return request.META.get("REMOTE_ADDR", "127.0.0.1")


class AuthService:
    """Handles authentication, session rotation, password policy, and login throttling."""

    MAX_FAILED_ATTEMPTS = 5
    THROTTLE_WINDOW_SECONDS = 60

    @classmethod
    def _enforce_throttle(cls, *, email: str, ip_address: str) -> None:
        """Refuse sign-in after 5 failures in one minute for the account or for the IP (NFR-02, AC-01.3)."""
        for scope in ({"email": email}, {"ip_address": ip_address}):
            failures = AuditService.count_failed_logins(**scope, window_seconds=cls.THROTTLE_WINDOW_SECONDS)
            if failures >= cls.MAX_FAILED_ATTEMPTS:
                raise ThrottledException("Too many failed login attempts. Please try again in a minute.")

    @classmethod
    def authenticate(
        cls,
        *,
        email: str,
        password: str,
        request: HttpRequest,
    ) -> User:
        """Authenticate by email and password and start a rotated session (FR-01)."""
        normalized_email = email.strip().lower()
        ip_address = get_client_ip(request)

        cls._enforce_throttle(email=normalized_email, ip_address=ip_address)

        user = User.objects.filter(email__iexact=normalized_email).first()

        # One generic message whichever value was wrong, so accounts cannot be enumerated (AC-01.2)
        generic_error = "Invalid email or password."

        if user is None:
            # Hash anyway so an unknown email takes as long as a wrong password
            User().set_password(password)

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

        # Active accounts only (BR-07)
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

        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])

        # Rotates the session identifier to prevent session fixation (ADR-03)
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
        with transaction.atomic():
            user.set_password(new_password)
            user.must_change_password = False
            user.save(update_fields=["password", "must_change_password"])

            AuditService.record(
                action=AuditAction.PASSWORD_CHANGED,
                actor=user,
                target_user=user,
                details={"forced": was_forced},
            )

        if request is not None:
            update_session_auth_hash(request, user)


def terminate_user_sessions(user_id: int) -> None:
    """Delete every active session belonging to a user (BR-07)."""
    for session in Session.objects.filter(expire_date__gte=timezone.now()):
        if session.get_decoded().get("_auth_user_id") == str(user_id):
            session.delete()


def generate_temp_password(length: int = 12) -> str:
    """Generate a high-entropy temporary password meeting security requirements."""
    # No "@": a password starting with it reads as a formula when the credentials file opens in Excel
    alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!#$%&*"
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

        with transaction.atomic():
            user = User(
                email=normalized_email,
                full_name=sanitize_csv_cell(trimmed_name),
                role=role,
                residence=residence,
                assigned_location=assigned_location,
                student_number=sanitize_csv_cell(trimmed_student) if trimmed_student else None,
                must_change_password=True,
                is_active=True,
            )
            user.set_password(temp_password)
            user.save()

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
        """Update a user in one transaction, enforcing the BR-07 guards (FR-03, TC-06).

        Audit events and session removal are part of the transaction, so a refused update
        leaves no trace. The row lock is the same one TransitionService takes on a Technician,
        so a Technician cannot be deactivated and given work at the same instant (ADR-02).
        """
        with transaction.atomic():
            # Admins are locked in id order first, so the last-Admin guard is safe when two
            # Admins change each other at the same moment.
            if user.role == Role.ADMIN:
                list(User.objects.select_for_update().filter(role=Role.ADMIN, is_active=True).order_by("id"))
            user = User.objects.select_for_update().get(id=user.id)

            cls._apply_active_change(actor, user, is_active)
            cls._apply_role_change(actor, user, role, residence_id, student_number)
            cls._apply_residence_change(user, residence_id)
            cls._apply_student_number_change(user, student_number)
            cls._apply_room_change(user, assigned_location_id)

            if full_name is not None and full_name.strip():
                user.full_name = sanitize_csv_cell(full_name.strip())

            user.save()
            return user

    @staticmethod
    def _has_active_work_orders(user: User) -> bool:
        from apps.workflow.models import WorkOrder

        return WorkOrder.objects.filter(technician=user, ended_at__isnull=True).exists()

    @staticmethod
    def _is_last_active_admin(user: User) -> bool:
        return not User.objects.filter(role=Role.ADMIN, is_active=True).exclude(id=user.id).exists()

    @classmethod
    def _apply_active_change(cls, actor: User, user: User, is_active: bool | None) -> None:
        if is_active is None or is_active == user.is_active:
            return

        if is_active:
            user.is_active = True
            AuditService.record(
                action=AuditAction.USER_REACTIVATED,
                actor=actor,
                target_user=user,
                details={"email": user.email},
            )
            return

        if user.role == Role.ADMIN and cls._is_last_active_admin(user):
            raise ConflictException("Cannot deactivate the last active administrator.")
        if user.role == Role.TECHNICIAN and cls._has_active_work_orders(user):
            raise ConflictException("Cannot deactivate a technician with active work orders.")

        user.is_active = False
        terminate_user_sessions(user.id)
        AuditService.record(
            action=AuditAction.USER_DEACTIVATED,
            actor=actor,
            target_user=user,
            details={"email": user.email},
        )

    @classmethod
    def _apply_role_change(
        cls,
        actor: User,
        user: User,
        role: str | None,
        residence_id: int | None,
        student_number: str | None,
    ) -> None:
        if role is None or role == user.role:
            return

        if user.role == Role.ADMIN and user.is_active and cls._is_last_active_admin(user):
            raise ConflictException("Cannot demote the last active administrator.")
        if user.role == Role.TECHNICIAN and cls._has_active_work_orders(user):
            raise ConflictException("Cannot change role of a technician with active work orders.")

        old_role = user.role
        user.role = role

        if role in (Role.RESIDENT, Role.WARDEN):
            if not residence_id and not user.residence_id:
                user.residence = Residence.objects.filter(is_active=True).first()
        else:
            user.residence = None

        if role != Role.RESIDENT:
            user.student_number = None
        elif not (student_number or "").strip() and not user.student_number:
            raise ValidationException(
                "Student number required for resident.",
                fields={"student_number": ["Student number is required for residents."]},
            )

        AuditService.record(
            action=AuditAction.USER_ROLE_CHANGED,
            actor=actor,
            target_user=user,
            details={"from_role": old_role, "to_role": role},
        )

    @staticmethod
    def _apply_residence_change(user: User, residence_id: int | None) -> None:
        if residence_id is None or residence_id == user.residence_id:
            return

        if user.role not in (Role.RESIDENT, Role.WARDEN):
            raise ValidationException(
                "Residence can only be set for residents and wardens.",
                fields={"residence": ["Residence can only be set for residents and wardens."]},
            )

        residence = Residence.objects.filter(id=residence_id).first()
        if not residence:
            raise ValidationException("Invalid residence.", fields={"residence": ["Residence not found."]})

        user.residence = residence
        # A room belongs to one residence, so it cannot follow the user to another
        if user.assigned_location and user.assigned_location.residence_id != residence.id:
            user.assigned_location = None

    @staticmethod
    def _apply_student_number_change(user: User, student_number: str | None) -> None:
        trimmed = (student_number or "").strip()
        if user.role != Role.RESIDENT or not trimmed or trimmed == user.student_number:
            return

        if User.objects.filter(student_number__iexact=trimmed).exclude(id=user.id).exists():
            raise ValidationException(
                "A user with this student number already exists.",
                fields={"student_number": ["A user with this student number already exists."]},
            )
        user.student_number = sanitize_csv_cell(trimmed)

    @staticmethod
    def _apply_room_change(user: User, assigned_location_id: int | None) -> None:
        if user.role != Role.RESIDENT:
            if assigned_location_id:
                raise ValidationException(
                    "Assigned location can only be set for residents.",
                    fields={"assigned_location_id": ["Assigned location can only be set for residents."]},
                )
            user.assigned_location = None
            return

        if assigned_location_id is None:
            return
        if assigned_location_id in (0, -1):
            user.assigned_location = None
            return

        room = Location.objects.filter(
            id=assigned_location_id,
            residence=user.residence,
            is_active=True,
            kind=LocationKind.ROOM,
        ).first()
        if not room:
            raise ValidationException(
                "Invalid room selection.",
                fields={"assigned_location_id": ["Selected room does not exist or is not a room in this residence."]},
            )
        user.assigned_location = room

    @classmethod
    def reset_password(cls, *, actor: User, user: User) -> str:
        """Reset user password to a newly generated temporary password (FR-03)."""
        temp_password = generate_temp_password(12)
        with transaction.atomic():
            user.set_password(temp_password)
            user.must_change_password = True
            user.save(update_fields=["password", "must_change_password"])

            terminate_user_sessions(user.id)

            AuditService.record(
                action=AuditAction.PASSWORD_RESET,
                actor=actor,
                target_user=user,
                details={"email": user.email, "forced": True},
            )

        return temp_password


class UserImportService:
    """All-or-nothing batch CSV import of user accounts (FR-04, NFR-03, TC-07, TC-08, TC-09).

    Columns: email, full_name, student_number, and optionally role, residence and room.
    A blank role means RESIDENT; a blank residence means the active residence (Moroka Hall).
    """

    MAX_FILE_BYTES = 2 * 1024 * 1024  # 2 MB limit
    MAX_ROWS = 2000

    EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    @classmethod
    def import_users_csv(
        cls,
        *,
        actor: User,
        csv_file_bytes: bytes,
    ) -> dict:
        """Validate the whole file, then create every account or none."""
        if actor.role != Role.ADMIN:
            raise ForbiddenException("Only administrators can import user accounts.")

        reader = cls._open_reader(csv_file_bytes)
        header_map = {col.strip().lower(): col for col in reader.fieldnames}
        for required_column in ("email", "full_name", "student_number"):
            if required_column not in header_map:
                raise ValidationException(
                    f"CSV missing mandatory column: '{required_column}'. "
                    "Required headers: email, full_name, student_number",
                    fields={"headers": [f"Missing '{required_column}' column."]},
                )

        residences = {r.name.lower(): r for r in Residence.objects.filter(is_active=True)}
        default_residence = Residence.objects.filter(is_active=True).first()
        if not default_residence:
            raise ValidationException("No active residence found in the system to assign users to.")

        rows_data, errors = cls._validate_rows(reader, header_map, residences, default_residence)
        errors.extend(cls._find_existing_collisions(rows_data))

        if errors:
            errors.sort(key=lambda item: item["row"])
            raise ValidationException(
                "CSV validation failed. No accounts were created.",
                fields={"bad_rows": errors},
            )

        created_records = cls._create_all(actor, rows_data)
        return {
            "created_count": len(created_records),
            "credentials": created_records,
        }

    @classmethod
    def _open_reader(cls, csv_file_bytes: bytes) -> csv.DictReader:
        if len(csv_file_bytes) > cls.MAX_FILE_BYTES:
            raise ValidationException(
                f"File size exceeds the 2 MB maximum limit ({len(csv_file_bytes)} bytes).",
                fields={"file": ["File size exceeds 2 MB limit."]},
            )

        try:
            content = csv_file_bytes.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValidationException(
                "CSV file must be valid UTF-8 encoded text.",
                fields={"file": ["File is not valid UTF-8 encoded."]},
            ) from exc

        reader = csv.DictReader(io.StringIO(content))
        try:
            has_headers = bool(reader.fieldnames)
        except csv.Error as exc:
            raise cls._unreadable_file() from exc
        if not has_headers:
            raise ValidationException(
                "CSV file is empty or missing a header row.",
                fields={"file": ["CSV file contains no headers."]},
            )
        return reader

    @staticmethod
    def _unreadable_file() -> ValidationException:
        return ValidationException(
            "CSV file could not be read.",
            fields={"file": ["File is not a valid CSV document."]},
        )

    @classmethod
    def _validate_rows(cls, reader, header_map, residences, default_residence) -> tuple[list[dict], list[dict]]:
        rows_data = []
        errors = []
        seen_emails = set()
        seen_students = set()
        rooms_by_residence = {}
        row_count = 0

        try:
            for row_number, row in enumerate(reader, start=2):  # row 1 is the header
                row_count += 1
                if row_count > cls.MAX_ROWS:
                    raise ValidationException(
                        f"CSV file exceeds the maximum allowed row count of {cls.MAX_ROWS}.",
                        fields={"file": [f"Maximum row limit is {cls.MAX_ROWS}."]},
                    )

                parsed, row_errors = cls._validate_row(
                    row, header_map, residences, default_residence, seen_emails, seen_students, rooms_by_residence
                )
                if row_errors:
                    errors.append({"row": row_number, "errors": row_errors})
                else:
                    rows_data.append({"row": row_number, **parsed})
        except csv.Error as exc:
            raise cls._unreadable_file() from exc

        if row_count == 0:
            raise ValidationException(
                "CSV file contains no data rows.",
                fields={"file": ["File contains no data rows."]},
            )
        return rows_data, errors

    @classmethod
    def _validate_row(
        cls, row, header_map, residences, default_residence, seen_emails, seen_students, rooms_by_residence
    ) -> tuple[dict, list[str]]:
        def cell(*names: str) -> str:
            """Read a trimmed cell; a short row leaves missing cells as None."""
            for name in names:
                if name in header_map:
                    value = (row.get(header_map[name]) or "").strip()
                    if value:
                        return value
            return ""

        row_errors = []

        raw_email = cell("email")
        email_lower = raw_email.lower()
        if not raw_email:
            row_errors.append("Email is required.")
        elif not cls.EMAIL_REGEX.match(raw_email):
            row_errors.append(f"Invalid email format: '{raw_email}'.")
        elif email_lower in seen_emails:
            row_errors.append(f"Duplicate email '{raw_email}' within CSV file.")
        else:
            seen_emails.add(email_lower)

        raw_name = cell("full_name")
        if not raw_name:
            row_errors.append("Full name is required.")
        elif len(raw_name) > 150:
            row_errors.append("Full name exceeds 150 characters.")

        role = cell("role").upper() or Role.RESIDENT
        if role not in Role.values:
            row_errors.append(f"Invalid role '{role}'. Must be one of: {', '.join(Role.values)}.")

        raw_residence = cell("residence")
        residence = None
        if role in (Role.RESIDENT, Role.WARDEN):
            residence = residences.get(raw_residence.lower()) if raw_residence else default_residence
            if residence is None:
                row_errors.append(f"Unknown or inactive residence '{raw_residence}'.")
        elif raw_residence:
            row_errors.append("Only residents and wardens can have a residence.")

        raw_student = cell("student_number")
        if role == Role.RESIDENT:
            if not raw_student:
                row_errors.append("Student number is required.")
            elif len(raw_student) > 20:
                row_errors.append("Student number exceeds 20 characters.")
            elif raw_student in seen_students:
                row_errors.append(f"Duplicate student number '{raw_student}' within CSV file.")
            else:
                seen_students.add(raw_student)
        elif raw_student:
            row_errors.append("Only residents can have a student number.")

        raw_room = cell("room", "room_number")
        room = None
        if raw_room:
            if role != Role.RESIDENT:
                row_errors.append("Only residents can be assigned a room.")
            elif residence is not None:
                room = cls._room_lookup(rooms_by_residence, residence).get(raw_room.lower())
                if room is None:
                    row_errors.append(f"Room '{raw_room}' was not found in {residence.name}.")

        return (
            {
                "email": email_lower,
                "full_name": sanitize_csv_cell(raw_name),
                "student_number": sanitize_csv_cell(raw_student) if raw_student else None,
                "role": role,
                "residence": residence,
                "room": room,
            },
            row_errors,
        )

    @staticmethod
    def _room_lookup(rooms_by_residence: dict, residence: Residence) -> dict:
        if residence.id not in rooms_by_residence:
            rooms = Location.objects.filter(residence=residence, kind=LocationKind.ROOM, is_active=True)
            rooms_by_residence[residence.id] = {room.label.lower(): room for room in rooms}
        return rooms_by_residence[residence.id]

    @staticmethod
    def _find_existing_collisions(rows_data: list[dict]) -> list[dict]:
        """Compare against existing accounts; emails are compared case-insensitively (AC-04.2)."""
        errors = []
        emails = {item["email"] for item in rows_data}
        students = {item["student_number"] for item in rows_data if item["student_number"]}

        existing_emails = set(
            User.objects.annotate(email_lower=Lower("email"))
            .filter(email_lower__in=emails)
            .values_list("email_lower", flat=True)
        )
        existing_students = set(
            User.objects.filter(student_number__in=students).values_list("student_number", flat=True)
        )

        for item in rows_data:
            if item["email"] in existing_emails:
                errors.append({
                    "row": item["row"],
                    "errors": [f"Email '{item['email']}' is already registered in the system."],
                })
            if item["student_number"] in existing_students:
                errors.append({
                    "row": item["row"],
                    "errors": [f"Student number '{item['student_number']}' is already registered in the system."],
                })
        return errors

    @staticmethod
    def _create_all(actor: User, rows_data: list[dict]) -> list[dict]:
        created_records = []
        with transaction.atomic():
            for item in rows_data:
                temp_pwd = generate_temp_password(12)
                user = User(
                    email=item["email"],
                    full_name=item["full_name"],
                    student_number=item["student_number"],
                    role=item["role"],
                    residence=item["residence"],
                    assigned_location=item["room"],
                    must_change_password=True,
                    is_active=True,
                )
                user.set_password(temp_pwd)
                user.save()

                created_records.append({
                    "id": user.id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "student_number": user.student_number or "",
                    "role": user.role,
                    "temporary_password": temp_pwd,
                })

            AuditService.record(
                action=AuditAction.USER_IMPORTED,
                actor=actor,
                details={"total_imported": len(created_records)},
            )
        return created_records
