"""Client logic tests (SPEC §9, INSTRUCTIONS_phase2 §2): tracker.py against scripted snapshots, plus the reader's
RTTI validation and the client's attach handling, all without the game."""
import asyncio
import struct
import sys
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
