"""NT-08: repository rules that lint cannot check."""

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.django_db

BACKEND = Path(__file__).resolve().parent.parent


def _status_assignments(path: Path) -> list[int]:
    """Lines in a Python file that assign to an attribute called status."""
    return [
        node.lineno
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Attribute) and target.attr == "status"
    ]


def test_nt08_request_status_is_assigned_only_by_the_transition_service():
    """NFR-10: no other application code assigns a request status."""
    offenders = []
    for path in (BACKEND / "apps").rglob("*.py"):
        if "migrations" in path.parts or (path.name == "services.py" and path.parent.name == "workflow"):
            continue
        if lines := _status_assignments(path):
            offenders.append((path.name, lines))
    assert offenders == []


def test_nt08_transition_service_assigns_status_in_one_place():
    assert len(_status_assignments(BACKEND / "apps/workflow/services.py")) == 1
