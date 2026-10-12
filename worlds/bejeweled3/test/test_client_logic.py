"""Client logic tests (SPEC §9, INSTRUCTIONS_phase2 §2): tracker.py against scripted snapshots, plus the reader's
RTTI validation and the client's attach handling, all without the game."""
import asyncio
import struct
import sys
import time
import unittest

from ..game.memory_map import STEAM_1_1_12_4196
from ..game.reader import (
    ELEVATION_MESSAGE,
    AttachResult,
    AttachStatus,
    BoardState,
    FakeReader,
    ReadError,
    Snapshot,
)
from ..items import BADGE_TIER, ITEM_NAME_TO_ID, JEWEL_SHARD, LEVEL_CAP, RELIC_KEY
from ..locations import LOCATION_TABLE, level_location_name, quest_location_name
from ..tracker import GOAL_HEROES_WELCOME, GOAL_LEVELORD, GOAL_SHARD_HUNT, Baseline, Tracker

ALL_LOCATIONS = {data.address for data in LOCATION_TABLE.values()}
CLASSIC_BOARD = ".?AVClassicBoard@Sexy@@"
ZEN_BOARD = ".?AVZenBoard@Sexy@@"
EMPTY = Baseline((0,) * 20, (0,) * 40)


def loc(name: str) -> int:
    return LOCATION_TABLE[name].address


def badge(name: str, tier: str | None = None) -> int:
    return loc(f"Badge: {name}" + (f" - {tier}" if tier else ""))


def item_ids(*names: str) -> list[int]:
    return [ITEM_NAME_TO_ID[name] for name in names]


def snap(profile: str = "AP-Test", badges: dict[int, int] | None = None, quests: set[int] | None = None,
         board: BoardState | None = None) -> Snapshot:
    tiers = [0] * 20
    for badge_id, tier in (badges or {}).items():
        tiers[badge_id] = tier
    done = [1 if k in (quests or set()) else 0 for k in range(40)]
    return Snapshot(profile, tuple(tiers), tuple(done), board)


def classic(level: int, address: int = 0x1000, score: int = 1000) -> BoardState:
    return BoardState(address, CLASSIC_BOARD, "Classic", score, level)


class TrackerTestCase(unittest.TestCase):
    def make(self, goal: int = GOAL_SHARD_HUNT, starting_mode: int = 0, shard_required: int = 5,
             baseline: Baseline = EMPTY, profile: str = "AP-Test", items: tuple[str, ...] = ()) -> Tracker:
        tracker = Tracker(ALL_LOCATIONS, starting_mode, goal, shard_required)
        tracker.apply_binding(profile, baseline)
        tracker.set_received(item_ids(*items))
        return tracker

    @staticmethod
    def feed(tracker: Tracker, snapshot: Snapshot | None, times: int = 2) -> None:
        for _ in range(times):
            tracker.update(snapshot)


class TestPersistentStateAndBaseline(TrackerTestCase):
    def test_state_present_at_connect_sends(self) -> None:
        tracker = self.make(items=("Quest Mode",))
        self.feed(tracker, snap(badges={3: 1}, quests={0}))
        self.assertEqual(set(tracker.evaluate(set())), {badge("Blaster", "Bronze"), loc(quest_location_name(0))})

    def test_baseline_suppresses_old_progress(self) -> None:
        baseline = Baseline(tuple(2 if i == 3 else 0 for i in range(20)), tuple(1 if k == 0 else 0 for k in range(40)))
        tracker = self.make(baseline=baseline, items=("Quest Mode", BADGE_TIER, BADGE_TIER))
        self.feed(tracker, snap(badges={3: 3}, quests={0, 1}))
        sent = set(tracker.evaluate(set()))
        self.assertEqual(sent, {badge("Blaster", "Gold"), loc(quest_location_name(1))})
        self.assertNotIn(badge("Blaster", "Silver"), sent)
        self.assertNotIn(loc(quest_location_name(0)), sent)

    def test_baseline_warning_lists_lost_checks(self) -> None:
        baseline = Baseline(tuple(1 if i == 0 else 0 for i in range(20)), (0,) * 40)
        tracker = Tracker(ALL_LOCATIONS, 0, GOAL_SHARD_HUNT, 5)
        tracker.apply_binding("Old", baseline)
        self.assertTrue(any("Badge: Inferno - Bronze" in message for message in tracker.drain_messages()))

    def test_tier_skipping_sends_every_tier(self) -> None:
        tracker = self.make(items=(BADGE_TIER, BADGE_TIER))
        self.feed(tracker, snap(badges={3: 3}))
        self.assertEqual(set(tracker.evaluate(set())),
                         {badge("Blaster", "Bronze"), badge("Blaster", "Silver"), badge("Blaster", "Gold")})

    def test_already_checked_not_resent(self) -> None:
        tracker = self.make()
        self.feed(tracker, snap(badges={3: 1}))
        self.assertEqual(tracker.evaluate({badge("Blaster", "Bronze")}), [])


class TestHeldChecks(TrackerTestCase):
    def test_locked_mode_then_item(self) -> None:
        tracker = self.make()
        self.feed(tracker, snap(badges={11: 1}))  # Diamond, Mine Bronze
        self.assertEqual(tracker.evaluate(set()), [])
        self.assertEqual(tracker.held[badge("Diamond, Mine", "Bronze")], "Diamond Mine Mode")
        self.assertTrue(any("held until you receive Diamond Mine Mode" in m for m in tracker.drain_messages()))
        tracker.set_received(item_ids("Diamond Mine Mode"))  # per-item: Quest Mode is NOT needed at runtime
        self.assertEqual(tracker.evaluate(set()), [badge("Diamond, Mine", "Bronze")])

    def test_relic_key(self) -> None:
        tracker = self.make(items=("Quest Mode",))
        self.feed(tracker, snap(quests={8}))  # relic 2
        self.assertEqual(tracker.evaluate(set()), [])
        self.assertEqual(tracker.held[loc(quest_location_name(8))], RELIC_KEY)
        tracker.set_received(item_ids("Quest Mode", RELIC_KEY))
        self.assertEqual(tracker.evaluate(set()), [loc(quest_location_name(8))])

    def test_relic_one_is_free(self) -> None:
        tracker = self.make(items=("Quest Mode",))
        self.feed(tracker, snap(quests={7}))
        self.assertEqual(tracker.evaluate(set()), [loc(quest_location_name(7))])

    def test_level_cap(self) -> None:
        tracker = self.make()
        self.feed(tracker, snap(board=classic(level=6)))  # 0-based 6 = level 7 reached
        sent = set(tracker.evaluate(set()))
        self.assertEqual(sent, {loc(level_location_name(n)) for n in range(2, 6)})
        self.assertIn(loc(level_location_name(7)), tracker.held)
        tracker.set_received(item_ids(LEVEL_CAP))  # same board session still active
        self.assertEqual(set(tracker.evaluate(sent)), {loc(level_location_name(6)), loc(level_location_name(7))})

    def test_badge_tier(self) -> None:
        tracker = self.make()
        self.feed(tracker, snap(badges={0: 2}))
        self.assertEqual(tracker.evaluate(set()), [badge("Inferno", "Bronze")])
        self.assertEqual(tracker.held[badge("Inferno", "Silver")], BADGE_TIER)
        tracker.set_received(item_ids(BADGE_TIER))
        self.assertEqual(tracker.evaluate({badge("Inferno", "Bronze")}), [badge("Inferno", "Silver")])

    def test_top_secret_needs_all_secret_mode_items(self) -> None:
        tracker = self.make(items=("Poker Mode", "Butterflies Mode", "Ice Storm Mode"))
        self.feed(tracker, snap(badges={19: 1}))
        tracker.evaluate(set())
        self.assertEqual(tracker.held[badge("Top Secret")], "Diamond Mine Mode")

    def test_duplicate_items_harmless(self) -> None:
        tracker = self.make(items=("Quest Mode", "Quest Mode", RELIC_KEY, RELIC_KEY, RELIC_KEY, RELIC_KEY, RELIC_KEY,
                                   RELIC_KEY, LEVEL_CAP, LEVEL_CAP, LEVEL_CAP, BADGE_TIER, BADGE_TIER, BADGE_TIER,
                                   BADGE_TIER))
        self.feed(tracker, snap(quests={39}, badges={0: 4}))
        sent = set(tracker.evaluate(set()))
        self.assertIn(loc(quest_location_name(39)), sent)
        self.assertIn(badge("Inferno", "Platinum"), sent)
        self.assertEqual(tracker.level_cap(), 10)


class TestValidation(TrackerTestCase):
    def test_single_read_is_not_enough(self) -> None:
        tracker = self.make()
        tracker.update(snap(badges={3: 1}))
        self.assertEqual(tracker.evaluate(set()), [])
        tracker.update(snap(badges={3: 1}))
        self.assertEqual(tracker.evaluate(set()), [badge("Blaster", "Bronze")])

    def test_unknown_tick_breaks_debounce(self) -> None:
        tracker = self.make()
        tracker.update(snap(badges={3: 1}))
        tracker.update(None)  # the reader saw an unknown RTTI / failed read
        tracker.update(snap(badges={3: 1}))
        self.assertEqual(tracker.evaluate(set()), [])

    def test_out_of_range_tier_ignored(self) -> None:
        tracker = self.make()
        self.feed(tracker, snap(badges={3: 7}))
        self.assertIsNone(tracker.stable)
        self.feed(tracker, snap(quests=set(), badges={}))
        self.assertIsNotNone(tracker.stable)

    def test_bad_quest_byte_ignored(self) -> None:
        tracker = self.make()
        bad = Snapshot("AP-Test", (0,) * 20, (2,) + (0,) * 39, None)
        self.feed(tracker, bad)
        self.assertIsNone(tracker.stable)

    def test_non_monotonic_tier_ignored(self) -> None:
        tracker = self.make(items=(BADGE_TIER,))
        self.feed(tracker, snap(badges={3: 2}))
        self.feed(tracker, snap(badges={3: 1}))  # tiers never go down: garbage read
        self.assertEqual(tracker.stable.badges[3], 2)


class TestBoardSessions(TrackerTestCase):
    def test_pointer_change_resets(self) -> None:
        tracker = self.make()
        self.feed(tracker, snap(board=classic(level=3, address=0x1000)))
        self.assertEqual(tracker.session_best_level, 3)
        self.feed(tracker, snap(board=classic(level=1, address=0x2000)))
        self.assertEqual(tracker.session_best_level, 1)

    def test_null_pointer_resets(self) -> None:
        tracker = self.make()
        self.feed(tracker, snap(board=classic(level=3)))
        self.feed(tracker, snap(board=None))
        self.assertEqual(tracker.session_best_level, -1)

    def test_score_zero_level_zero_resets(self) -> None:
        tracker = self.make()
        self.feed(tracker, snap(board=classic(level=3, score=5000)))
        self.feed(tracker, snap(board=classic(level=0, score=0)))  # same address reused for a new game
        self.assertEqual(tracker.session_best_level, 0)

    def test_held_level_lost_after_reset_then_counts_again(self) -> None:
        tracker = self.make()
        self.feed(tracker, snap(board=classic(level=6, address=0x1000)))
        checked = set(tracker.evaluate(set()))
        self.assertIn(loc(level_location_name(7)), tracker.held)
        self.feed(tracker, snap(board=None))  # left that game: the held level is lost
        tracker.set_received(item_ids(LEVEL_CAP))
        self.assertEqual(tracker.evaluate(checked), [])
        self.feed(tracker, snap(board=classic(level=6, address=0x3000)))  # reached again in a new game
        self.assertEqual(set(tracker.evaluate(checked)), {loc(level_location_name(6)), loc(level_location_name(7))})

    def test_only_classic_board_counts_levels(self) -> None:
        tracker = self.make(items=("Zen Mode",))
        self.feed(tracker, snap(board=BoardState(0x1000, ZEN_BOARD, None, 9000, 7)))
        self.assertEqual(tracker.evaluate(set()), [])


class TestProfileBinding(TrackerTestCase):
    def test_unbound_tracker_sends_nothing_and_proposes_binding(self) -> None:
        tracker = Tracker(ALL_LOCATIONS, 0, GOAL_SHARD_HUNT, 5)
        self.feed(tracker, snap(profile="Fresh", badges={3: 1}))
        self.assertTrue(tracker.needs_binding)
        self.assertEqual(tracker.evaluate(set()), [])
        name, baseline = tracker.proposed_binding()
        self.assertEqual(name, "Fresh")
        self.assertEqual(baseline.badges[3], 1)

    def test_wrong_profile_pauses(self) -> None:
        tracker = self.make(profile="AP-Seed")
        self.feed(tracker, snap(profile="Other", badges={3: 1}))
        self.assertEqual(tracker.evaluate(set()), [])
        self.assertIn("bound to profile 'AP-Seed'", tracker.paused_reason)
        self.assertTrue(any("Not sending checks" in m for m in tracker.drain_messages()))

    def test_profile_switch_mid_session_resets_then_resumes(self) -> None:
        tracker = self.make(profile="AP-Seed")
        self.feed(tracker, snap(profile="AP-Seed", board=classic(level=3)))
        self.feed(tracker, snap(profile="Other"))
        self.assertEqual(tracker.session_best_level, -1)
        self.assertEqual(tracker.evaluate(set()), [])
        self.feed(tracker, snap(profile="AP-Seed", badges={3: 1}))
        self.assertEqual(tracker.evaluate(set()), [badge("Blaster", "Bronze")])

    def test_one_garbage_name_read_resets_nothing(self) -> None:
        tracker = self.make(profile="AP-Seed")
        self.feed(tracker, snap(profile="AP-Seed", board=classic(level=3)))
        tracker.update(snap(profile="AP-S\x00\x01", board=classic(level=3)))  # torn read during a switch
        self.feed(tracker, snap(profile="AP-Seed", board=classic(level=3)))
        self.assertEqual(tracker.session_best_level, 3)
        self.assertEqual(tracker.drain_messages(), [])


class TestGoals(TrackerTestCase):
    def test_shard_hunt(self) -> None:
        tracker = self.make(shard_required=5, items=(JEWEL_SHARD,) * 4)
        self.assertFalse(tracker.goal_reached())
        tracker.set_received(item_ids(*(JEWEL_SHARD,) * 5))
        self.assertTrue(tracker.goal_reached())

    def test_levelord_badge(self) -> None:
        tracker = self.make(goal=GOAL_LEVELORD)
        self.feed(tracker, snap())
        self.assertFalse(tracker.goal_reached())
        self.feed(tracker, snap(badges={18: 1}))
        self.assertTrue(tracker.goal_reached())  # gating items not required for the goal itself

    def test_levelord_live_fallback_needs_two_reads(self) -> None:
        tracker = self.make(goal=GOAL_LEVELORD)
        tracker.update(snap(board=classic(level=9)))
        self.assertFalse(tracker.goal_reached())
        tracker.update(snap(board=classic(level=9)))
        self.assertTrue(tracker.goal_reached())

    def test_levelord_in_baseline_does_not_count(self) -> None:
        tracker = self.make(goal=GOAL_LEVELORD, baseline=Baseline(tuple(1 if i == 18 else 0 for i in range(20)),
                                                                   (0,) * 40))
        self.feed(tracker, snap(badges={18: 1}))
        self.assertFalse(tracker.goal_reached())

    def test_heroes_welcome(self) -> None:
        tracker = self.make(goal=GOAL_HEROES_WELCOME)
        self.feed(tracker, snap(quests=set(range(40))))
        self.assertFalse(tracker.goal_reached())
        self.feed(tracker, snap(quests=set(range(40)), badges={15: 1}))
        self.assertTrue(tracker.goal_reached())

    def test_goal_not_reached_on_wrong_profile(self) -> None:
        tracker = self.make(goal=GOAL_HEROES_WELCOME, profile="AP-Seed")
        self.feed(tracker, snap(profile="Other", badges={15: 1}))
        self.assertFalse(tracker.goal_reached())


@unittest.skipUnless(sys.platform == "win32", "PymemReader is Windows-only")
class TestReaderValidation(unittest.TestCase):
    """PymemReader.read() over a fake address space: wrong or unknown RTTI means an unknown tick."""

    BASE, APP, PROFILE, BOARD, NAME = 0x400000, 0x10000000, 0x20000000, 0x30000000, 0x40000000

    def build(self, profile_class: str = ".?AVProfile@Sexy@@", board_class: str | None = CLASSIC_BOARD):
        from ..game.reader import PymemReader
        memory: dict[int, bytes] = {}
        vtables: dict[str, int] = {}

        def put(address: int, data: bytes) -> None:
            memory[address] = data

        def add_class(name: str) -> int:
            index = len(vtables)
            vtable, col, type_descriptor = (self.BASE + 0x1000 + index * 0x100, self.BASE + 0x2000 + index * 0x100,
                                            self.BASE + 0x3000 + index * 0x100)
            put(vtable - 4, struct.pack("<I", col))
            put(col + 12, struct.pack("<I", type_descriptor))
            put(type_descriptor + 8, name.encode() + b"\0" * (64 - len(name)))
            vtables[name] = vtable
            return vtable

        m = STEAM_1_1_12_4196
        put(self.BASE + m.app_ptr_rva, struct.pack("<I", self.APP))
        put(self.APP, struct.pack("<I", add_class(m.app_class)))
        put(self.APP + m.profile_offset, struct.pack("<I", self.PROFILE))
        put(self.APP + m.board_offset, struct.pack("<I", self.BOARD if board_class else 0))
        put(self.PROFILE, struct.pack("<I", add_class(profile_class)))
        put(self.PROFILE + m.profile_name, struct.pack("<I12xII", self.NAME, 8, 15))
        put(self.NAME, "AP-Fakes".encode("utf-16-le"))
        put(self.PROFILE + m.badge_tiers, struct.pack("<20I", *([0, 0, 0, 2] + [0] * 16)))
        put(self.PROFILE + m.quests_done, bytes(40))
        if board_class:
            put(self.BOARD, struct.pack("<I", add_class(board_class)))
            put(self.BOARD + m.board_score, struct.pack("<i", 1234))
            put(self.BOARD + m.board_level, struct.pack("<i", 2))

        reader = PymemReader()
        reader.handle, reader.map, reader.base, reader.image_size = 1, m, self.BASE, 0x1000000

        def fake_read(address: int, size: int) -> bytes:
            for start, data in memory.items():
                if start <= address and address + size <= start + len(data):
                    return data[address - start: address - start + size]
            raise ReadError(hex(address))

        reader._read = fake_read  # type: ignore[method-assign]
        return reader

    def test_valid_snapshot(self) -> None:
        snapshot = self.build().read()
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.profile_name, "AP-Fakes")
        self.assertEqual(snapshot.badges[3], 2)
        self.assertEqual(snapshot.board, BoardState(self.BOARD, CLASSIC_BOARD, "Classic", 1234, 2))

    def test_menu_has_no_board(self) -> None:
        snapshot = self.build(board_class=None).read()
        self.assertIsNotNone(snapshot)
        self.assertIsNone(snapshot.board)

    def test_wrong_profile_class_is_unknown_tick(self) -> None:
        self.assertIsNone(self.build(profile_class=".?AVSomethingElse@Sexy@@").read())

    def test_unknown_board_class_is_unknown_tick(self) -> None:
        self.assertIsNone(self.build(board_class=".?AVBadgeWidget@Sexy@@").read())


class TestClientAttach(unittest.TestCase):
    def test_access_denied_reports_elevation_and_keeps_searching(self) -> None:
        from ..client import Bejeweled3Context

        async def run() -> Bejeweled3Context:
            reader = FakeReader(attach_results=[AttachResult(AttachStatus.ACCESS_DENIED, ELEVATION_MESSAGE)])
            ctx = Bejeweled3Context(reader_factory=lambda: reader)
            with self.assertLogs("Client", level="WARNING") as logs:
                await ctx.tick()
                await ctx.tick()
            self.assertEqual(sum(ELEVATION_MESSAGE in line for line in logs.output), 1)  # said once, not spammed
            return ctx

        ctx = asyncio.run(run())
        self.assertFalse(ctx.attached)

    def test_attach_then_game_closes(self) -> None:
        from ..client import Bejeweled3Context

        async def run() -> Bejeweled3Context:
            reader = FakeReader([snap()])
            ctx = Bejeweled3Context(reader_factory=lambda: reader)
            await ctx.tick()
            self.assertTrue(ctx.attached)
            reader.is_alive = False
            await ctx.tick()
            return ctx

        ctx = asyncio.run(run())
        self.assertFalse(ctx.attached)


class TestLockedModeHint(TrackerTestCase):
    QUEST_BOARD = ".?AVTimeLimitBoard@Sexy@@"

    def board(self, rtti: str, mode: str | None, address: int = 0x5000) -> BoardState:
        return BoardState(address, rtti, mode, 0, 0)

    def hints(self, tracker: Tracker) -> list[str]:
        return [m for m in tracker.drain_messages() if m.startswith("You're playing")]

    def test_hint_when_starting_a_locked_quest(self) -> None:
        tracker = self.make()
        tracker.drain_messages()
        self.feed(tracker, snap(board=self.board(self.QUEST_BOARD, "Quest")), times=4)
        hints = self.hints(tracker)
        self.assertEqual(len(hints), 1)  # once per game, not every tick
        self.assertIn("haven't received Quest Mode", hints[0])
        self.assertIn("saved and will count", hints[0])

    def test_no_hint_when_unlocked(self) -> None:
        tracker = self.make(items=("Quest Mode",))
        tracker.drain_messages()
        self.feed(tracker, snap(board=self.board(self.QUEST_BOARD, "Quest")))
        self.assertEqual(self.hints(tracker), [])

    def test_no_hint_for_ambiguous_board(self) -> None:
        tracker = self.make()
        tracker.drain_messages()
        self.feed(tracker, snap(board=self.board(".?AVDigBoard@Sexy@@", None)))  # Diamond Mine or a dig quest
        self.assertEqual(self.hints(tracker), [])

    def test_no_hint_for_mode_without_checks(self) -> None:
        tracker = self.make()
        tracker.drain_messages()
        self.feed(tracker, snap(board=self.board(ZEN_BOARD, "Zen")))  # Zen has no checks of its own
        self.assertEqual(self.hints(tracker), [])

    def test_hint_again_for_the_next_game(self) -> None:
        tracker = self.make()
        tracker.drain_messages()
        self.feed(tracker, snap(board=self.board(self.QUEST_BOARD, "Quest", 0x5000)))
        self.feed(tracker, snap(board=None))
        self.feed(tracker, snap(board=self.board(self.QUEST_BOARD, "Quest", 0x6000)))
        self.assertEqual(len(self.hints(tracker)), 2)


class TestEliteValues(TrackerTestCase):
    """Regression (live seed 2026-10-11): Superstar is stored as 5; that must not invalidate every snapshot."""

    def test_elite_value_five_is_valid_and_earned(self) -> None:
        tracker = self.make(items=(BADGE_TIER, BADGE_TIER, BADGE_TIER))
        self.feed(tracker, snap(badges={3: 4, 17: 5}))
        self.assertIsNotNone(tracker.stable)
        sent = set(tracker.evaluate(set()))
        self.assertIn(badge("Superstar"), sent)
        self.assertIn(badge("Blaster", "Platinum"), sent)

    def test_common_badge_above_four_still_invalid(self) -> None:
        tracker = self.make()
        self.feed(tracker, snap(badges={3: 5}))
        self.assertIsNone(tracker.stable)

    def test_elite_above_five_invalid(self) -> None:
        tracker = self.make()
        self.feed(tracker, snap(badges={17: 6}))
        self.assertIsNone(tracker.stable)


class TestGuide(TrackerTestCase):
    SHORT = frozenset(data.address for data in LOCATION_TABLE.values() if data.length == 1)

    def guide(self, tracker: Tracker, checked: set[int] = frozenset()) -> str:
        from ..guide import build_guide, render_plain
        return render_plain(build_guide(tracker, checked))

    def short_tracker(self, items: tuple[str, ...] = ()) -> Tracker:
        tracker = Tracker(self.SHORT, 0, GOAL_SHARD_HUNT, 5)
        tracker.apply_binding("AP-Test", EMPTY)
        tracker.set_received(item_ids(*items))
        return tracker

    def test_goal_and_do_next(self) -> None:
        tracker = self.short_tracker(items=(JEWEL_SHARD, JEWEL_SHARD))
        self.feed(tracker, snap())
        text = self.guide(tracker)
        self.assertIn("Goal: collect Jewel Shards (2/5)", text)
        self.assertIn("Badge: Inferno - Bronze: clear 50 Flame Gems (total, any mode)", text)
        self.assertIn("Classic: Reach Level 2: reach level 2 in one Classic game", text)
        self.assertIn("Quest Mode: 16 checks", text)  # relic 1 + relic 2 wait for Quest Mode first
        self.assertIn("!hint Quest Mode", text)

    def test_banked_and_done(self) -> None:
        tracker = self.short_tracker()
        self.feed(tracker, snap(badges={3: 1}, quests={6}))
        checked = {badge("Blaster", "Bronze")}
        text = self.guide(tracker, checked)
        self.assertIn("Checks sent: 1 of 30", text)
        self.assertIn("Quest: Relic 1 - Buried Treasure: waiting for Quest Mode", text)
        self.assertNotIn("Badge: Blaster - Bronze:", text)

    def test_relic_gate_reminder(self) -> None:
        tracker = self.short_tracker(items=("Quest Mode", RELIC_KEY))
        self.feed(tracker, snap(quests={0, 1}))
        text = self.guide(tracker)
        self.assertIn("Relic 2 quests (8 open)", text)
        self.assertIn("Relic 2 opens in game after 4 quests of relic 1 (you have 2)", text)

    def test_secret_mode_unlock_reminder(self) -> None:
        tracker = self.short_tracker(items=("Poker Mode",))
        self.feed(tracker, snap())
        self.assertIn("Poker also needs the game's own unlock: reach level 5 in Classic.", self.guide(tracker))

    def test_paused_guide(self) -> None:
        tracker = self.short_tracker()
        self.feed(tracker, snap(profile="Someone Else"))
        self.assertIn("Paused:", self.guide(tracker))


class TestHintAnnouncement(unittest.TestCase):
    @staticmethod
    def with_ctx(check) -> None:
        """Run `check(ctx)` with a client context (which needs a running event loop to exist)."""
        from ..client import Bejeweled3Context

        async def run() -> None:
            ctx = Bejeweled3Context(reader_factory=FakeReader)
            ctx.slot = 1
            ctx.player_names = {0: "Archipelago", 1: "Brian", 2: "Tom"}
            ctx.item_names.lookup_in_slot = lambda code, slot=None: {1: "Quest Mode", 2: "Zen Mode"}.get(code, "?")
            ctx.location_names.lookup_in_slot = lambda code, slot=None: {77: "Shop 12"}.get(code, "?")
            check(ctx)

        asyncio.run(run())

    @staticmethod
    def hint(receiving: int = 1, found: bool = False, item: int = 1) -> dict:
        return {"type": "Hint", "receiving": receiving, "item": [item, 77, 2, 1], "found": found}

    @staticmethod
    def asked(ctx, item: str = "Quest Mode") -> None:
        ctx.announce_item = item
        ctx.announce_hints_until = time.monotonic() + 30

    def test_requested_hint_is_announced_once(self) -> None:
        def check(ctx) -> None:
            self.asked(ctx)
            self.assertEqual(ctx.hint_announcement(self.hint()),
                             "[Bejeweled 3 Client] Waiting on Quest Mode: Shop 12 (Tom's world).")
            self.assertIsNone(ctx.hint_announcement(self.hint()))  # only the first hint after the request
        self.with_ctx(check)

    def test_unrequested_or_foreign_hints_are_not_announced(self) -> None:
        def check(ctx) -> None:
            self.assertIsNone(ctx.hint_announcement(self.hint()))  # nobody asked
            self.asked(ctx)
            self.assertIsNone(ctx.hint_announcement(self.hint(receiving=2)))  # someone else's hint
            self.assertIsNone(ctx.hint_announcement(self.hint(item=2)))  # another of our items, hinted by someone
            self.assertIsNotNone(ctx.hint_announcement(self.hint()))  # ...doesn't use up the request
        self.with_ctx(check)

    def test_found_item(self) -> None:
        def check(ctx) -> None:
            self.asked(ctx)
            self.assertIsNone(ctx.hint_announcement(self.hint(found=True)))  # found already: nothing to ask
        self.with_ctx(check)


    def test_request_resolves_the_name_like_the_server(self) -> None:
        def check(ctx) -> None:
            sent = []

            async def capture(msgs) -> None:
                sent.extend(msgs)
            ctx.send_msgs = capture
            self.assertTrue(ctx.request_announced_hint("quest mode"))
            self.assertEqual(ctx.announce_item, "Quest Mode")
            self.assertFalse(ctx.request_announced_hint("Master Sword"))  # not one of ours: nothing is sent
            self.assertEqual(ctx.announce_item, "Quest Mode")
        self.with_ctx(check)


class TestQuestAwareHints(TrackerTestCase):
    """Shared quest-engine boards: the quest id tells a quest (0-39) from a secret mode (1000 + n)."""

    def hints(self, tracker: Tracker) -> list[str]:
        return [m for m in tracker.drain_messages() if m.startswith("You're playing")]

    def test_dig_quest_is_quest_not_diamond_mine(self) -> None:
        tracker = self.make()
        tracker.drain_messages()
        board = BoardState(0x7000, ".?AVDigBoard@Sexy@@", "Quest", 0, 0, quest_index=1)  # Gold Rush
        self.feed(tracker, snap(board=board))
        hints = self.hints(tracker)
        self.assertEqual(len(hints), 1)
        self.assertIn("haven't received Quest Mode", hints[0])

    def test_secret_mode_hint(self) -> None:
        tracker = self.make()
        tracker.drain_messages()
        self.feed(tracker, snap(board=BoardState(0x7000, ".?AVButterflyBoard@Sexy@@", "Butterflies", 0, 0)))
        self.assertIn("haven't received Butterflies Mode", self.hints(tracker)[0])

    def test_relic_key_hint(self) -> None:
        tracker = self.make(items=("Quest Mode",))
        tracker.drain_messages()
        self.feed(tracker, snap(board=BoardState(0x7000, ".?AVTimeLimitBoard@Sexy@@", "Quest", 0, 0, quest_index=16)))
        hints = self.hints(tracker)
        self.assertEqual(len(hints), 1)
        self.assertIn("Alchemy II (relic 3). It needs 2 Relic Keys to count and you have 0", hints[0])

    def test_no_relic_hint_with_enough_keys(self) -> None:
        tracker = self.make(items=("Quest Mode", RELIC_KEY))
        tracker.drain_messages()
        self.feed(tracker, snap(board=BoardState(0x7000, ".?AVTimeLimitBoard@Sexy@@", "Quest", 0, 0, quest_index=8)))
        self.assertEqual(self.hints(tracker), [])


@unittest.skipUnless(sys.platform == "win32", "PymemReader is Windows-only")
class TestReaderQuestId(TestReaderValidation):
    def with_quest_id(self, board_class: str, quest_id: int):
        reader = self.build(board_class=board_class)
        original = reader._read

        def read(address: int, size: int) -> bytes:
            if address == self.BOARD + STEAM_1_1_12_4196.board_quest_id:
                return struct.pack("<i", quest_id)[:size]
            return original(address, size)

        reader._read = read  # type: ignore[method-assign]
        return reader.read().board

    def test_quest_id_means_quest(self) -> None:
        board = self.with_quest_id(".?AVDigBoard@Sexy@@", 1)
        self.assertEqual((board.mode, board.quest_index), ("Quest", 1))

    def test_secret_id_means_secret_mode(self) -> None:
        board = self.with_quest_id(".?AVButterflyBoard@Sexy@@", 1001)
        self.assertEqual((board.mode, board.quest_index), ("Butterflies", None))

    def test_garbage_id_means_unknown(self) -> None:
        self.assertIsNone(self.with_quest_id(".?AVDigBoard@Sexy@@", 7777).mode)
