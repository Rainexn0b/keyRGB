from __future__ import annotations

# @quality-exception file-size-analysis: single cohesive chassis profile coordinator class; desired/output/commit paths belong together

from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from threading import RLock

from . import protocol


ReportWriter = Callable[[bytes], None]


@dataclass(frozen=True)
class _DesiredSnapshot:
    primary_groups: tuple[protocol.Ite8258ChassisGroup, ...] | None
    zone_groups: dict[str, tuple[protocol.Ite8258ChassisGroup, ...]]
    output_suspended: bool
    desired_revision: int
    applied_revision: int
    desired_dirty: bool


class ProfileCommitDisposition(str, Enum):
    """Outcome of a coordinator mutation relative to the wire."""

    COMMITTED = "committed"
    STAGED_NO_PRIMARY = "staged_no_primary"
    STAGED_SUSPENDED = "staged_suspended"
    STAGED_IN_TRANSACTION = "staged_in_transaction"


class Ite8258ChassisProfileCoordinator:
    """Serialize complete profile writes for the composite Gen10 controller.

    The keyboard, logo, neon strip, and vents share one hardware profile.  A
    SAVE_PROFILE packet for a virtual child is therefore not a zone-local
    patch: sending it alone replaces group 1 from the parent scene.  This
    coordinator retains the desired scene and makes every production write a
    deterministic full-profile transaction.

    It deliberately retains only protocol data, never a transport proxy.  A
    freshly acquired proxy can therefore replay the desired scene after the
    shared transport has been closed or re-opened.

    Output suspension (global off) is distinct from desired-scene edits: child
    on/off while suspended updates retained state without writing the wire, so
    resume restores the latest intent.  An optional nested ``output_transaction``
    batches several facade calls into one physical full-scene commit.
    """

    _ZONE_ORDER = ("logo", "neon", "vent")
    _ZONE_LED_IDS = {
        "logo": protocol.LOGO_LED_IDS,
        "neon": protocol.NEON_LED_IDS,
        "vent": protocol.VENT_LED_IDS,
    }

    def __init__(self) -> None:
        self._lock = RLock()
        self._primary_groups: tuple[protocol.Ite8258ChassisGroup, ...] | None = None
        self._zone_groups = {
            zone_name: protocol.build_uniform_static_groups_for_leds(led_ids, (0, 0, 0))
            for zone_name, led_ids in self._ZONE_LED_IDS.items()
        }
        # Output suspension affects the wire only; desired scene is retained.
        self._output_suspended = False
        self._desired_revision = 0
        self._applied_revision = 0
        self._desired_dirty = False
        self._transaction_depth = 0
        self._transaction_writer: ReportWriter | None = None
        self._transaction_profile_id: int | None = None
        self._transaction_brightness: int | None = None
        self._transaction_snapshot: _DesiredSnapshot | None = None

    @property
    def output_suspended(self) -> bool:
        with self._lock:
            return bool(self._output_suspended)

    @property
    def desired_dirty(self) -> bool:
        with self._lock:
            return bool(self._desired_dirty)

    @contextmanager
    def output_transaction(self, write_report: ReportWriter, *, profile_id: int) -> Iterator[None]:
        """Batch facade mutations into one outermost full-scene commit.

        Nested entries increment depth and commit only at the outermost
        successful exit.  A staging-time exception restores the pre-transaction
        desired snapshot.  An I/O failure during commit keeps the new desired
        scene as dirty for retry.
        """
        # Hold the coordinator lock across the entire logical transaction.
        # RLock keeps same-thread nesting valid while preventing a second thread
        # from being mistaken for a nested participant in the first transaction.
        with self._lock:
            if self._transaction_depth == 0:
                self._transaction_snapshot = self._snapshot_desired()
                self._transaction_writer = write_report
                self._transaction_profile_id = int(profile_id) & 0xFF
                self._transaction_brightness = None
            self._transaction_depth += 1

            try:
                yield
            except BaseException:  # @quality-exception exception-transparency: rollback must restore coordinator invariants even for cancellation and process-control exceptions
                self._transaction_depth -= 1
                if self._transaction_depth == 0:
                    self._restore_snapshot(self._transaction_snapshot)
                    self._clear_transaction_state()
                raise

            self._transaction_depth -= 1
            if self._transaction_depth != 0:
                return
            writer = self._transaction_writer
            commit_profile_id = (
                self._transaction_profile_id if self._transaction_profile_id is not None else int(profile_id) & 0xFF
            )
            brightness = self._transaction_brightness
            self._clear_transaction_state()
            if writer is None:
                return
            if self._output_suspended or self._primary_groups is None:
                return
            self._commit_scene(
                writer,
                profile_id=commit_profile_id,
                brightness=brightness,
            )

    def apply_primary(
        self,
        write_report: ReportWriter,
        *,
        profile_id: int,
        groups: Sequence[protocol.Ite8258ChassisGroup],
        brightness: int,
    ) -> ProfileCommitDisposition:
        """Store primary groups, clear suspension, and commit the whole scene."""
        primary_groups = tuple(groups)
        if not primary_groups:
            raise ValueError("primary profile groups must not be empty")

        level = protocol.clamp_ui_brightness(brightness)
        with self._lock:
            self._primary_groups = primary_groups
            self._output_suspended = False
            self._bump_desired()
            if self._transaction_depth > 0:
                self._transaction_brightness = level
                self._transaction_writer = write_report
                self._transaction_profile_id = int(profile_id) & 0xFF
                return ProfileCommitDisposition.STAGED_IN_TRANSACTION
            self._commit_scene(
                write_report,
                profile_id=profile_id,
                brightness=level,
            )
            return ProfileCommitDisposition.COMMITTED

    def apply_zone(
        self,
        write_report: ReportWriter,
        *,
        zone_name: str,
        profile_id: int,
        groups: Sequence[protocol.Ite8258ChassisGroup],
    ) -> ProfileCommitDisposition:
        """Store a positive child update; commit once primary and output allow it."""
        normalized_zone = self._normalize_zone(zone_name)
        zone_groups = tuple(groups)
        if not zone_groups:
            raise ValueError(f"{normalized_zone} profile groups must not be empty")

        with self._lock:
            self._zone_groups[normalized_zone] = zone_groups
            self._bump_desired()
            return self._maybe_commit_zone(write_report, profile_id=profile_id)

    def turn_off_zone(
        self,
        write_report: ReportWriter,
        *,
        zone_name: str,
        profile_id: int,
    ) -> ProfileCommitDisposition:
        """Black one child in the desired scene without wiping sibling groups.

        While output is suspended this is a desired-scene edit (no wire write),
        not transient global-power cleanup.  Callers that own composite global
        off should skip child turn_off entirely for parent-shared routes.
        """
        normalized_zone = self._normalize_zone(zone_name)

        with self._lock:
            self._zone_groups[normalized_zone] = protocol.build_uniform_static_groups_for_leds(
                self._ZONE_LED_IDS[normalized_zone],
                (0, 0, 0),
            )
            self._bump_desired()
            return self._maybe_commit_zone(write_report, profile_id=profile_id)

    def turn_off_all(self, write_report: ReportWriter, *, profile_id: int) -> None:
        """Suspend output and issue the controller-wide off transaction.

        Desired primary/zone groups are retained for resume.
        """
        with self._lock:
            self._output_suspended = True
            # Explicit power-off is immediate even inside an output transaction;
            # deferring it until transaction exit would invert caller intent.
            self._prepare_profile_write(write_report, profile_id=profile_id)
            write_report(protocol.build_turn_off_report(profile_id=profile_id))

    def set_primary_brightness(
        self,
        write_report: ReportWriter,
        *,
        profile_id: int,
        brightness: int,
    ) -> None:
        """Apply controller-global brightness under the profile transaction lock."""
        level = protocol.clamp_ui_brightness(brightness)
        if level <= 0:
            self.turn_off_all(write_report, profile_id=profile_id)
            return

        with self._lock:
            was_suspended = self._output_suspended
            self._output_suspended = False
            if self._transaction_depth > 0:
                self._transaction_brightness = level
                self._transaction_writer = write_report
                self._transaction_profile_id = int(profile_id) & 0xFF
                if was_suspended and self._primary_groups is not None:
                    self._bump_desired()
                return
            if was_suspended and self._primary_groups is not None:
                self._commit_scene(
                    write_report,
                    profile_id=profile_id,
                    brightness=level,
                )
                return
            # Cold path: no retained primary scene.  Documented as
            # SWITCH_PROFILE + SET_BRIGHTNESS only (no invented groups).
            write_report(protocol.build_switch_profile_report(profile_id))
            write_report(protocol.build_set_brightness_report(protocol.raw_brightness_from_ui(level)))

    def _maybe_commit_zone(
        self,
        write_report: ReportWriter,
        *,
        profile_id: int,
    ) -> ProfileCommitDisposition:
        if self._transaction_depth > 0:
            if self._transaction_writer is None:
                self._transaction_writer = write_report
            if self._transaction_profile_id is None:
                self._transaction_profile_id = int(profile_id) & 0xFF
            return ProfileCommitDisposition.STAGED_IN_TRANSACTION
        if self._output_suspended:
            return ProfileCommitDisposition.STAGED_SUSPENDED
        if self._primary_groups is None:
            return ProfileCommitDisposition.STAGED_NO_PRIMARY
        self._commit_scene(write_report, profile_id=profile_id)
        return ProfileCommitDisposition.COMMITTED

    def _combined_groups(self) -> tuple[protocol.Ite8258ChassisGroup, ...]:
        primary_groups = self._primary_groups
        if primary_groups is None:
            return ()
        return primary_groups + tuple(group for zone_name in self._ZONE_ORDER for group in self._zone_groups[zone_name])

    def _commit_scene(
        self,
        write_report: ReportWriter,
        *,
        profile_id: int,
        brightness: int | None = None,
    ) -> None:
        groups = self._combined_groups()
        if not groups:
            return
        try:
            self._prepare_profile_write(write_report, profile_id=profile_id)
            for report in protocol.build_save_profile_reports(profile_id, groups):
                write_report(report)
            if brightness is not None:
                write_report(
                    protocol.build_set_brightness_report(
                        protocol.raw_brightness_from_ui(brightness),
                    )
                )
        except Exception:  # @quality-exception exception-transparency: arbitrary report-writer failures must preserve dirty desired state before propagating
            # Desired scene remains the latest intent; applied revision does not
            # advance so the scene stays dirty/retryable.
            self._desired_dirty = True
            raise
        self._applied_revision = self._desired_revision
        self._desired_dirty = False

    def _bump_desired(self) -> None:
        self._desired_revision += 1
        self._desired_dirty = True

    def _snapshot_desired(self) -> _DesiredSnapshot:
        return _DesiredSnapshot(
            primary_groups=self._primary_groups,
            zone_groups=dict(self._zone_groups),
            output_suspended=self._output_suspended,
            desired_revision=self._desired_revision,
            applied_revision=self._applied_revision,
            desired_dirty=self._desired_dirty,
        )

    def _restore_snapshot(self, snapshot: _DesiredSnapshot | None) -> None:
        if snapshot is None:
            return
        self._primary_groups = snapshot.primary_groups
        self._zone_groups = dict(snapshot.zone_groups)
        self._output_suspended = snapshot.output_suspended
        self._desired_revision = snapshot.desired_revision
        self._applied_revision = snapshot.applied_revision
        self._desired_dirty = snapshot.desired_dirty

    def _clear_transaction_state(self) -> None:
        self._transaction_writer = None
        self._transaction_profile_id = None
        self._transaction_brightness = None
        self._transaction_snapshot = None

    @staticmethod
    def _prepare_profile_write(write_report: ReportWriter, *, profile_id: int) -> None:
        write_report(protocol.build_switch_profile_report(profile_id))
        write_report(protocol.build_set_direct_mode_report(enabled=False, profile_id=profile_id))

    @classmethod
    def _normalize_zone(cls, zone_name: str) -> str:
        normalized = str(zone_name).strip().lower()
        if normalized not in cls._ZONE_LED_IDS:
            raise ValueError(f"Unknown ITE 8258 chassis zone: {zone_name}")
        return normalized


__all__ = ["Ite8258ChassisProfileCoordinator", "ProfileCommitDisposition"]
