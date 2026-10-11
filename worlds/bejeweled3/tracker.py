"""
Pure client logic for Bejeweled 3: game snapshots + received items + slot data -> checks to send, held checks,
goal state and status text. No I/O, so every rule here is unit-tested against scripted snapshots.

Rules (SPEC §6.3, §6.6, §7, revision 4):
- A snapshot only counts after two consecutive identical reads (debounce), and only if it validates:
  badge tiers 0-4, quest bytes 0/1, and no tier/quest going backwards within a profile session.
- Only progress beyond the profile's baseline (recorded when the seed was bound) ever sends.
- A badge read at tier t sends every tier above the baseline up to t (tiers can be skipped in game).
- Runtime gating is per item: a check waits only for its own mode's item and its gating item counts.
- Levels are live-only: each Classic board is a session; the best level of the current session counts.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from .game.reader import Snapshot
from .items import (
    BADGE_TIER,
    FREE_LEVEL,
    ITEM_NAME_TO_ID,
    JEWEL_SHARD,
    LEVEL_CAP,
    LEVELS_PER_CAP,
    RELIC_KEY,
    caps_needed_for_level,
    keys_needed_for_relic,
    mode_item_name,
)
from .locations import (
    ALL_MODES,
    BASE_MODES,
    CLASSIC,
    LOCATION_TABLE,
    MAX_LEVEL,
    QUEST,
    RELIC_COUNT,
    SECRET_MODES,
    TIER_NAMES,
    LocationData,
)

BADGE_COUNT = 20
QUEST_COUNT = 40
MAX_TIER = 4  # common badges: 0 none, 1 Bronze ... 4 Platinum (2, 3, 4 verified)
FIRST_ELITE_ID = 15
MAX_ELITE_VALUE = 5  # elite badges store 5 when earned (Superstar, verified 2026-10-11 in Brian's live seed)
HEROES_WELCOME_ID = 15
LEVELORD_ID = 18
LEVELORD_LEVEL_INDEX = MAX_LEVEL - 1  # board level is 0-based
CLASSIC_BOARD = ".?AVClassicBoard@Sexy@@"

ITEM_ID_TO_NAME = {item_id: name for name, item_id in ITEM_NAME_TO_ID.items()}
LOCATIONS_BY_ID = {data.address: data for data in LOCATION_TABLE.values()}

GOAL_SHARD_HUNT, GOAL_LEVELORD, GOAL_HEROES_WELCOME = 0, 1, 2


@dataclass(frozen=True)
class Baseline:
    badges: tuple[int, ...]
    quests: tuple[int, ...]

    def to_json(self) -> dict[str, list[int]]:
        return {"badges": list(self.badges), "quests": list(self.quests)}

    @classmethod
    def from_json(cls, data: dict) -> Baseline:
        return cls(tuple(int(v) for v in data["badges"]), tuple(int(v) for v in data["quests"]))


def snapshot_is_valid(snapshot: Snapshot) -> bool:
    return (len(snapshot.badges) == BADGE_COUNT and len(snapshot.quests) == QUEST_COUNT
            and all(0 <= tier <= (MAX_TIER if badge_id < FIRST_ELITE_ID else MAX_ELITE_VALUE)
                    for badge_id, tier in enumerate(snapshot.badges))
            and all(value in (0, 1) for value in snapshot.quests))


class Tracker:
    def __init__(self, slot_locations: Iterable[int], starting_mode: int, goal: int, shard_required: int) -> None:
        self.slot_locations = set(slot_locations)
        self.starting_mode = BASE_MODES[starting_mode]
        self.goal = goal
        self.shard_required = shard_required
        self.received: Counter[str] = Counter()
        self.bound_profile: str | None = None
        self.baseline: Baseline | None = None
        self.messages: list[str] = []
        self.held: dict[int, str] = {}
        self.reset_game_state()

    # ------------------------------------------------------------------ state

    def reset_game_state(self) -> None:
        """Forget everything read from the game (new attach, or the active profile changed)."""
        self.stable: Snapshot | None = None
        self._last_raw: Snapshot | None = None
        self.session_board: int | None = None
        self.session_best_level = -1  # 0-based level index; -1 = no Classic board this session
        self.levelord_live = False
        self._paused_warned_for: str | None = None

    def set_received(self, item_ids: Iterable[int]) -> None:
        """Replace the received-item counts. Idempotent: duplicates of any item are harmless."""
        self.received = Counter(ITEM_ID_TO_NAME[i] for i in item_ids if i in ITEM_ID_TO_NAME)

    def apply_binding(self, profile_name: str, baseline: Baseline) -> None:
        """Called with the binding the server holds (ours if we were first, otherwise the stored one)."""
        self.bound_profile = profile_name
        self.baseline = baseline
        self._paused_warned_for = None
        lost = self.baseline_losses()
        if lost:
            self.messages.append(f"Profile '{profile_name}' already had progress when this seed was bound. "
                                 f"These checks will never count for this seed: {', '.join(lost)}.")

    def baseline_losses(self) -> list[str]:
        if self.baseline is None:
            return []
        lost = []
        for location_id in sorted(self.slot_locations):
            data = LOCATIONS_BY_ID.get(location_id)
            if data is not None and self._in_baseline(data):
                lost.append(data.name)
        return lost

    def _in_baseline(self, data: LocationData) -> bool:
        assert self.baseline is not None
        if data.kind == "quest":
            return self.baseline.quests[data.quest_index] == 1
        if data.kind == "badge":
            assert data.badge is not None
            return self.baseline.badges[data.badge.badge_id] >= data.tier
        return False

    # ------------------------------------------------------------------ snapshots

    def update(self, snapshot: Snapshot | None) -> None:
        """Feed one raw read. Only two consecutive identical, valid reads change state."""
        if snapshot is None or not snapshot_is_valid(snapshot):
            self._last_raw = None
            return
        if self.stable is not None and snapshot.profile_name != self.stable.profile_name:
            self.messages.append(f"Active profile changed to '{snapshot.profile_name}'. Re-checking the binding.")
            self.reset_game_state()
        previous, self._last_raw = self._last_raw, snapshot
        if previous is None or not _same_reading(previous, snapshot):
            return
        if self.stable is not None and _went_backwards(self.stable, snapshot):
            return  # garbage read: tiers and quests never decrease within a profile session
        self.stable = snapshot
        self._update_board_session(snapshot)

    def _update_board_session(self, snapshot: Snapshot) -> None:
        board = snapshot.board
        if board is None:
            self.session_board, self.session_best_level = None, -1
            return
        if board.address != self.session_board:
            self.session_board, self.session_best_level = board.address, -1
            self._hint_locked_mode(board.mode)
        elif board.score == 0 and board.level == 0:
            self.session_best_level = -1  # same address reused for a new game
        if board.rtti == CLASSIC_BOARD:
            self.session_best_level = max(self.session_best_level, board.level)
            if board.level >= LEVELORD_LEVEL_INDEX:
                self.levelord_live = True

    def _hint_locked_mode(self, mode: str | None) -> None:
        """Say so when a game starts in a mode whose item hasn't arrived, if that mode has checks in this seed."""
        if mode is None or self.has_mode(mode):
            return
        held_here = [LOCATIONS_BY_ID[i] for i in self.slot_locations
                     if i in LOCATIONS_BY_ID and LOCATIONS_BY_ID[i].region == mode]
        if not held_here:
            return
        item = mode_item_name(mode)
        if mode == CLASSIC:
            after = "Levels reached now won't count, but badges you earn are saved and count when it arrives."
        elif mode == QUEST:
            after = "Quests you finish now are saved and will count when it arrives."
        else:
            after = "Badges you earn now are saved and will count when it arrives."
        self.messages.append(f"You're playing {mode}, but you haven't received {item} yet. {after}")

    @property
    def needs_binding(self) -> bool:
        return self.bound_profile is None and self.stable is not None

    def proposed_binding(self) -> tuple[str, Baseline]:
        assert self.stable is not None
        return self.stable.profile_name, Baseline(self.stable.badges, self.stable.quests)

    @property
    def paused_reason(self) -> str | None:
        if self.stable is None:
            return "waiting for a stable read of the game"
        if self.bound_profile is None or self.baseline is None:
            return "waiting for the profile binding from the server"
        if self.stable.profile_name != self.bound_profile:
            return (f"this seed is bound to profile '{self.bound_profile}', but '{self.stable.profile_name}' is "
                    f"active. Switch to '{self.bound_profile}' in game; nothing is sent until then")
        return None

    # ------------------------------------------------------------------ checks

    def evaluate(self, already_checked: Iterable[int]) -> list[int]:
        """Locations to send now. Updates `held` and queues a message for each newly held check."""
        reason = self.paused_reason
        if reason is not None:
            if self.stable is not None and self.bound_profile is not None and self._paused_warned_for != reason:
                self.messages.append(f"Not sending checks: {reason}.")
                self._paused_warned_for = reason
            return []
        self._paused_warned_for = None
        done = set(already_checked)
        to_send = []
        held: dict[int, str] = {}
        for location_id in sorted(self.slot_locations - done):
            data = LOCATIONS_BY_ID.get(location_id)
            if data is None or not self._achieved(data):
                continue
            missing = self.missing_item(data)
            if missing is None:
                to_send.append(location_id)
            else:
                held[location_id] = missing
                if self.held.get(location_id) != missing:
                    live_note = " (levels only count while you're still in that game)" if data.kind == "level" else ""
                    self.messages.append(f"{data.name} is held until you receive {missing}{live_note}.")
        self.held = held
        return to_send

    def _achieved(self, data: LocationData) -> bool:
        assert self.stable is not None and self.baseline is not None
        if data.kind == "level":
            return self.session_best_level + 1 >= data.level
        if data.kind == "quest":
            return self.stable.quests[data.quest_index] == 1 and self.baseline.quests[data.quest_index] == 0
        assert data.badge is not None
        badge_id = data.badge.badge_id
        return self.stable.badges[badge_id] >= data.tier > self.baseline.badges[badge_id]

    def has_mode(self, mode: str) -> bool:
        return mode == self.starting_mode or self.received[mode_item_name(mode)] > 0

    def missing_item(self, data: LocationData) -> str | None:
        """The single item this check is waiting for, or None if it can be sent."""
        if data.region in ALL_MODES and not self.has_mode(data.region):
            return mode_item_name(data.region)
        if data.kind == "level":
            return self._need(LEVEL_CAP, caps_needed_for_level(data.level))
        if data.kind == "quest":
            return self._need(RELIC_KEY, keys_needed_for_relic(data.relic))
        assert data.badge is not None
        if data.badge.name == "Top Secret":
            for mode in SECRET_MODES:
                if not self.has_mode(mode):
                    return mode_item_name(mode)
            return None
        if data.badge.name == "Heroes Welcome":
            return self._need(RELIC_KEY, keys_needed_for_relic(RELIC_COUNT))
        if data.badge.name == "Levelord":
            return self._need(LEVEL_CAP, caps_needed_for_level(MAX_LEVEL))
        if data.badge.elite:
            return None
        return self._need(BADGE_TIER, data.tier - 1)

    def _need(self, item: str, count: int) -> str | None:
        have = self.received[item]
        if have >= count:
            return None
        return f"{item} ({count} needed, you have {have})" if count > 1 else item

    # ------------------------------------------------------------------ goal and status

    def goal_reached(self) -> bool:
        if self.goal == GOAL_SHARD_HUNT:
            return self.received[JEWEL_SHARD] >= self.shard_required > 0
        if self.paused_reason is not None:
            return False
        assert self.stable is not None and self.baseline is not None
        if self.goal == GOAL_LEVELORD:
            earned = self.stable.badges[LEVELORD_ID] > 0 and self.baseline.badges[LEVELORD_ID] == 0
            return earned or self.levelord_live
        return self.stable.badges[HEROES_WELCOME_ID] > 0 and self.baseline.badges[HEROES_WELCOME_ID] == 0

    def level_cap(self) -> int:
        return min(MAX_LEVEL, FREE_LEVEL + LEVELS_PER_CAP * self.received[LEVEL_CAP])

    def status_line(self) -> str:
        modes = [mode for mode in ALL_MODES if self.has_mode(mode)]
        tier = TIER_NAMES[min(MAX_TIER, 1 + self.received[BADGE_TIER])]
        parts = [
            f"Modes: {', '.join(modes)}",
            f"Relic Keys: {self.received[RELIC_KEY]}",
            f"Level cap: {self.level_cap()}",
            f"Badge tier: {tier}",
        ]
        if self.goal == GOAL_SHARD_HUNT:
            parts.append(f"Jewel Shards: {self.received[JEWEL_SHARD]}/{self.shard_required}")
        if self.held:
            parts.append(f"Held checks: {len(self.held)}")
        return " | ".join(parts)

    def drain_messages(self) -> list[str]:
        messages, self.messages = self.messages, []
        return messages


def _same_reading(a: Snapshot, b: Snapshot) -> bool:
    """Equal for debounce purposes: everything except the (fast-changing) score."""
    board_a = (a.board.address, a.board.rtti, a.board.level) if a.board else None
    board_b = (b.board.address, b.board.rtti, b.board.level) if b.board else None
    return (a.profile_name, a.badges, a.quests, board_a) == (b.profile_name, b.badges, b.quests, board_b)


def _went_backwards(old: Snapshot, new: Snapshot) -> bool:
    return (any(n < o for o, n in zip(old.badges, new.badges, strict=True))
            or any(n < o for o, n in zip(old.quests, new.quests, strict=True)))

