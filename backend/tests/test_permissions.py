"""Unit checks on the permission module that don't require a DB.

Full grant/effective-perm DB tests land with the integration test harness in M5.
"""
from metamart.permissions import (
    PERM_ADMIN,
    PERM_DELETE,
    PERM_MANAGE_PERMS,
    PERM_MANAGE_RULES,
    PERM_READ,
    PERM_WAIVE_FINDINGS,
    PERM_WRITE,
    effective_perms,
    grant,
    require_permission,
)


def test_perm_constants_are_distinct_single_bits() -> None:
    bits = [
        PERM_READ,
        PERM_WRITE,
        PERM_DELETE,
        PERM_ADMIN,
        PERM_MANAGE_PERMS,
        PERM_MANAGE_RULES,
        PERM_WAIVE_FINDINGS,
    ]
    assert len(set(bits)) == len(bits), "permission bits must be unique"
    for b in bits:
        assert b > 0 and (b & (b - 1)) == 0, f"perm bit {b} must be a single bit"


def test_require_permission_returns_a_dependency_callable() -> None:
    dep = require_permission(PERM_READ)
    assert callable(dep)


def test_helper_apis_are_callable() -> None:
    # Smoke: the functions exist with the expected names. Full DB-backed
    # behavior is exercised in the M5 integration suite.
    assert callable(effective_perms)
    assert callable(grant)
