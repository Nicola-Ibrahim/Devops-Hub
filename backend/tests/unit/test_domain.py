import unittest
from datetime import UTC, datetime, timedelta, timezone

from developer_platform.domain import (
    DeletionReason,
    DesiredState,
    DomainError,
    LeasePolicy,
    LeaseViolation,
    ResourceStatus,
    TransitionViolation,
    transition_status,
)

UTC = UTC


class LeasePolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = LeasePolicy()
        self.accepted_at = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)

    def test_defaults_and_acceptance_based_expiry(self) -> None:
        self.assertEqual(self.policy.default_ttl_seconds, 3600)
        self.assertEqual(self.policy.max_lifetime_seconds, 86400)
        self.assertEqual(
            self.policy.initial_expiry(self.accepted_at),
            self.accepted_at + timedelta(hours=1),
        )

    def test_initial_expiry_accepts_utc_offset_zero_and_returns_utc(self) -> None:
        from datetime import timezone as tz

        offset_utc = tz(timedelta(0))
        accepted = self.accepted_at.astimezone(offset_utc)
        expiry = self.policy.initial_expiry(accepted, 90)
        self.assertEqual(expiry, accepted + timedelta(seconds=90))
        self.assertEqual(expiry.utcoffset(), timedelta(0))

    def test_initial_expiry_rejects_naive_or_non_utc_datetime(self) -> None:
        with self.assertRaises(LeaseViolation):
            self.policy.initial_expiry(self.accepted_at.replace(tzinfo=None))
        with self.assertRaises(LeaseViolation):
            self.policy.initial_expiry(self.accepted_at.astimezone(timezone(timedelta(hours=1))))

    def test_initial_expiry_rejects_invalid_ttl(self) -> None:
        for ttl in (0, -1, True, 1.5, "60"):
            with self.subTest(ttl=ttl), self.assertRaises(LeaseViolation):
                self.policy.initial_expiry(self.accepted_at, ttl)  # type: ignore[arg-type]

    def test_policy_rejects_invalid_default_and_maximum(self) -> None:
        for values in (
            {"default_ttl_seconds": 0},
            {"default_ttl_seconds": True},
            {"default_ttl_seconds": 2.5},
            {"max_lifetime_seconds": 0},
            {"max_lifetime_seconds": False},
            {"max_lifetime_seconds": "86400"},
            {"default_ttl_seconds": 100, "max_lifetime_seconds": 99},
        ):
            with self.subTest(values=values), self.assertRaises(LeaseViolation):
                LeasePolicy(**values)  # type: ignore[arg-type]

    def test_initial_ttl_cannot_exceed_maximum_lifetime(self) -> None:
        with self.assertRaises(LeaseViolation):
            self.policy.initial_expiry(self.accepted_at, 86401)

    def _renew(self, **overrides: object) -> datetime:
        values: dict[str, object] = {
            "created_at": self.accepted_at,
            "current_expiry": self.accepted_at + timedelta(hours=1),
            "requested_expiry": self.accepted_at + timedelta(hours=2),
            "now": self.accepted_at + timedelta(minutes=30),
            "desired_state": DesiredState.RUNNING,
            "status": ResourceStatus.READY,
        }
        values.update(overrides)
        return self.policy.renewal_expiry(**values)  # type: ignore[arg-type]

    def test_renewal_extends_active_lease(self) -> None:
        self.assertEqual(self._renew(), self.accepted_at + timedelta(hours=2))

    def test_renewal_rejects_expired_lease(self) -> None:
        with self.assertRaises(LeaseViolation):
            self._renew(now=self.accepted_at + timedelta(hours=1))

    def test_renewal_rejects_current_time_before_resource_creation(self) -> None:
        with self.assertRaises(LeaseViolation):
            self._renew(now=self.accepted_at - timedelta(seconds=1))

    def test_renewal_rejects_inconsistent_stored_expiry(self) -> None:
        for expiry in (
            self.accepted_at,
            self.accepted_at + timedelta(hours=24, seconds=1),
        ):
            with self.subTest(expiry=expiry), self.assertRaises(LeaseViolation):
                self._renew(current_expiry=expiry)

    def test_renewal_rejects_non_extending_expiry(self) -> None:
        for expiry in (
            self.accepted_at,
            self.accepted_at + timedelta(minutes=59),
            self.accepted_at + timedelta(hours=1),
        ):
            with self.subTest(expiry=expiry), self.assertRaises(LeaseViolation):
                self._renew(requested_expiry=expiry)

    def test_renewal_rejects_beyond_total_lifetime(self) -> None:
        with self.assertRaises(LeaseViolation):
            self._renew(requested_expiry=self.accepted_at + timedelta(hours=24, seconds=1))

    def test_renewal_allows_exact_maximum_lifetime(self) -> None:
        self.assertEqual(
            self._renew(requested_expiry=self.accepted_at + timedelta(hours=24)),
            self.accepted_at + timedelta(hours=24),
        )

    def test_renewal_rejects_deleted_or_terminal_resources(self) -> None:
        with self.assertRaises(LeaseViolation):
            self._renew(desired_state=DesiredState.DELETED)
        for status in (
            ResourceStatus.FAILED,
            ResourceStatus.DELETING,
            ResourceStatus.CLEANUP_FAILED,
            ResourceStatus.DELETED,
        ):
            with self.subTest(status=status), self.assertRaises(LeaseViolation):
                self._renew(status=status)

    def test_domain_errors_have_safe_stable_codes(self) -> None:
        self.assertIsInstance(LeaseViolation("safe message"), DomainError)
        self.assertEqual(LeaseViolation.code, "lease_violation")
        self.assertEqual(TransitionViolation.code, "invalid_resource_transition")


class ResourceTransitionTests(unittest.TestCase):
    def test_lifecycle_enums_match_contract(self) -> None:
        self.assertEqual(
            {status.value for status in ResourceStatus},
            {"pending", "provisioning", "ready", "failed", "deleting", "cleanup_failed", "deleted"},
        )
        self.assertEqual({state.value for state in DesiredState}, {"running", "deleted"})
        self.assertEqual(
            {reason.value for reason in DeletionReason},
            {"requested", "expired", "cancelled", "pr_closed", "provision_failed"},
        )

    def test_happy_path_and_cleanup_retry(self) -> None:
        self.assertEqual(
            transition_status(
                ResourceStatus.PENDING,
                ResourceStatus.PROVISIONING,
                desired_state=DesiredState.RUNNING,
            ),
            ResourceStatus.PROVISIONING,
        )
        self.assertEqual(
            transition_status(
                ResourceStatus.PROVISIONING,
                ResourceStatus.READY,
                desired_state=DesiredState.RUNNING,
            ),
            ResourceStatus.READY,
        )
        self.assertEqual(
            transition_status(
                ResourceStatus.READY, ResourceStatus.DELETING, desired_state=DesiredState.DELETED
            ),
            ResourceStatus.DELETING,
        )
        self.assertEqual(
            transition_status(
                ResourceStatus.DELETING,
                ResourceStatus.CLEANUP_FAILED,
                desired_state=DesiredState.DELETED,
            ),
            ResourceStatus.CLEANUP_FAILED,
        )
        self.assertEqual(
            transition_status(
                ResourceStatus.CLEANUP_FAILED,
                ResourceStatus.DELETING,
                desired_state=DesiredState.DELETED,
            ),
            ResourceStatus.DELETING,
        )

    def test_deleted_requires_provider_confirmation(self) -> None:
        for kwargs in (
            {"deletion_confirmed": False, "outstanding_provider_operations": False},
            {"deletion_confirmed": True, "outstanding_provider_operations": True},
            {"deletion_confirmed": True},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(TransitionViolation):
                transition_status(
                    ResourceStatus.DELETING,
                    ResourceStatus.DELETED,
                    desired_state=DesiredState.DELETED,
                    **kwargs,
                )
        self.assertEqual(
            transition_status(
                ResourceStatus.DELETING,
                ResourceStatus.DELETED,
                desired_state=DesiredState.DELETED,
                deletion_confirmed=True,
                outstanding_provider_operations=False,
            ),
            ResourceStatus.DELETED,
        )

    def test_deleted_requires_deleted_desired_state_even_if_already_deleted(self) -> None:
        for current in (ResourceStatus.DELETING, ResourceStatus.DELETED):
            with self.subTest(current=current), self.assertRaises(TransitionViolation):
                transition_status(
                    current,
                    ResourceStatus.DELETED,
                    desired_state=DesiredState.RUNNING,
                    deletion_confirmed=True,
                    outstanding_provider_operations=False,
                )

    def test_same_state_does_not_bypass_deletion_intent(self) -> None:
        with self.assertRaises(TransitionViolation):
            transition_status(
                ResourceStatus.READY,
                ResourceStatus.READY,
                desired_state=DesiredState.DELETED,
            )

    def test_repeated_deleted_status_still_requires_external_resolution(self) -> None:
        with self.assertRaises(TransitionViolation):
            transition_status(
                ResourceStatus.DELETED,
                ResourceStatus.DELETED,
                desired_state=DesiredState.DELETED,
                deletion_confirmed=True,
            )

    def test_deleted_tombstone_can_reopen_cleanup_only(self) -> None:
        self.assertEqual(
            transition_status(
                ResourceStatus.DELETED, ResourceStatus.DELETING, desired_state=DesiredState.DELETED
            ),
            ResourceStatus.DELETING,
        )
        for target in (
            ResourceStatus.PROVISIONING,
            ResourceStatus.READY,
            ResourceStatus.PENDING,
            ResourceStatus.FAILED,
        ):
            with self.subTest(target=target), self.assertRaises(TransitionViolation):
                transition_status(
                    ResourceStatus.DELETED, target, desired_state=DesiredState.DELETED
                )

    def test_desired_deleted_resource_cannot_become_ready(self) -> None:
        with self.assertRaises(TransitionViolation):
            transition_status(
                ResourceStatus.PROVISIONING,
                ResourceStatus.READY,
                desired_state=DesiredState.DELETED,
            )

    def test_desired_deleted_resource_only_advances_through_cleanup(self) -> None:
        with self.assertRaises(TransitionViolation):
            transition_status(
                ResourceStatus.PENDING,
                ResourceStatus.FAILED,
                desired_state=DesiredState.DELETED,
            )

    def test_invalid_transitions_are_rejected(self) -> None:
        for current, target in (
            (ResourceStatus.PENDING, ResourceStatus.READY),
            (ResourceStatus.FAILED, ResourceStatus.READY),
            (ResourceStatus.CLEANUP_FAILED, ResourceStatus.DELETED),
        ):
            with (
                self.subTest(current=current, target=target),
                self.assertRaises(TransitionViolation),
            ):
                transition_status(current, target, desired_state=DesiredState.RUNNING)

    def test_repeating_current_status_is_idempotent(self) -> None:
        self.assertEqual(
            transition_status(
                ResourceStatus.READY, ResourceStatus.READY, desired_state=DesiredState.RUNNING
            ),
            ResourceStatus.READY,
        )
