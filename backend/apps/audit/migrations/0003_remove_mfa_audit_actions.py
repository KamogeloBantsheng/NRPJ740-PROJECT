"""Remove the MFA audit actions now that two-factor sign-in is out of scope (Section 3.3).

audit_logs is append-only, so any MFA_ENABLED or MFA_DISABLED rows already written must stay.
The replacement CHECK is therefore added NOT VALID: PostgreSQL applies it to every new row
without rewriting history.
"""

from django.db import migrations, models

ACTIONS = [
    ("REQUEST_SUBMITTED", "Request Submitted"),
    ("CLARIFICATION_REQUESTED", "Clarification Requested"),
    ("CLARIFICATION_PROVIDED", "Clarification Provided"),
    ("REQUEST_APPROVED", "Request Approved"),
    ("REQUEST_REJECTED", "Request Rejected"),
    ("WORK_ASSIGNED", "Work Assigned"),
    ("WORK_REASSIGNED", "Work Reassigned"),
    ("WORK_STARTED", "Work Started"),
    ("WORK_COMPLETED", "Work Completed"),
    ("REQUEST_VERIFIED_CLOSED", "Request Verified Closed"),
    ("REQUEST_REOPENED", "Request Reopened"),
    ("USER_CREATED", "User Created"),
    ("USER_IMPORTED", "User Imported"),
    ("USER_ROLE_CHANGED", "User Role Changed"),
    ("USER_DEACTIVATED", "User Deactivated"),
    ("USER_REACTIVATED", "User Reactivated"),
    ("PASSWORD_RESET", "Password Reset"),
    ("PASSWORD_CHANGED", "Password Changed"),
    ("LOGIN_FAILED", "Login Failed"),
]
ACTION_VALUES = [value for value, _ in ACTIONS]
QUOTED_VALUES = ", ".join(f"'{value}'" for value in ACTION_VALUES)
OLD_QUOTED_VALUES = f"{QUOTED_VALUES}, 'MFA_ENABLED', 'MFA_DISABLED'"


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0002_remove_auditevent_check_audit_action_and_more"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=f"""
                    ALTER TABLE audit_logs DROP CONSTRAINT check_audit_action;
                    ALTER TABLE audit_logs ADD CONSTRAINT check_audit_action
                        CHECK (action IN ({QUOTED_VALUES})) NOT VALID;
                    """,
                    reverse_sql=f"""
                    ALTER TABLE audit_logs DROP CONSTRAINT check_audit_action;
                    ALTER TABLE audit_logs ADD CONSTRAINT check_audit_action
                        CHECK (action IN ({OLD_QUOTED_VALUES}));
                    """,
                ),
            ],
            state_operations=[
                migrations.RemoveConstraint(model_name="auditevent", name="check_audit_action"),
                migrations.AlterField(
                    model_name="auditevent",
                    name="action",
                    field=models.CharField(choices=ACTIONS, max_length=30),
                ),
                migrations.AddConstraint(
                    model_name="auditevent",
                    constraint=models.CheckConstraint(
                        condition=models.Q(("action__in", ACTION_VALUES)),
                        name="check_audit_action",
                    ),
                ),
            ],
        ),
    ]
