import itertools
import json
from pathlib import Path
from typing import Any, ClassVar

from BaseClasses import CollectionState, ItemClassification, LocationProgressType
from Fill import distribute_items_restrictive
from test.general import gen_steps, setup_multiworld

from ..items import BADGE_TIER, JEWEL_SHARD, LEVEL_CAP, RELIC_KEY
from ..locations import LOCATION_TABLE, badge_location_name, level_location_name, quest_location_name
from ..world import Bejeweled3World
from . import Bejeweled3TestBase

# With default options, at least this share of the item pool must be progression (SPEC §9).
MIN_PROGRESSION_SHARE = 0.25
# Non-filler-only locations reachable with just the starting mode: guards against a narrow, slow start.
MIN_SPHERE_ZERO = 7
# Pool sizes are part of the design (BALANCE.md): change them on purpose, not by accident.
LOCATION_COUNTS = {"short": 30, "medium": 49, "long": 87, "marathon": 114}

ID_SNAPSHOT = Path(__file__).parent / "ids_snapshot.json"


def badge(name: str, tier: str | None = None) -> str:
    return f"Badge: {name}" + (f" - {tier}" if tier else "")


class LengthTestBase(Bejeweled3TestBase):
    """Checks shared by every seed length; subclasses set `length` and the matching option."""
    length: ClassVar[str] = "short"

    def location_names(self) -> set[str]:
        return {location.name for location in self.multiworld.get_locations(self.player)}

    def test_location_count(self) -> None:
        self.assertEqual(len(self.multiworld.get_locations()), LOCATION_COUNTS[self.length])
        self.assertEqual(len(self.multiworld.get_items()), len(self.multiworld.get_locations()))

    def test_sphere_zero_is_wide(self) -> None:
        state = CollectionState(self.multiworld)
        open_checks = [location.name for location in self.multiworld.get_locations()
                       if location.progress_type != LocationProgressType.EXCLUDED and location.can_reach(state)]
        self.assertGreaterEqual(len(open_checks), MIN_SPHERE_ZERO, open_checks)

    def test_filler_only_flags(self) -> None:
        for location in self.multiworld.get_locations(self.player):
            data = LOCATION_TABLE[location.name]
            expected = LocationProgressType.EXCLUDED if data.filler_only else LocationProgressType.DEFAULT
            with self.subTest(location=location.name):
                self.assertEqual(location.progress_type, expected)

    def test_relic_keys_gate_quests(self) -> None:
        self.collect_all_but(RELIC_KEY)
        keys = self.get_items_by_name(RELIC_KEY)
        names = self.location_names()
        first_quests = [quest_location_name(k) for k in range(0, 40, 8) if quest_location_name(k) in names]
        for held in range(len(keys) + 1):
            for name in first_quests:
                relic = LOCATION_TABLE[name].relic
                with self.subTest(keys=held, relic=relic):
                    self.assertEqual(self.can_reach_location(name), relic <= held + 1)
            if held < len(keys):
                self.collect(keys[held])


class TestShort(LengthTestBase):
    length = "short"

    def test_progression_share(self) -> None:
        pool = self.multiworld.itempool
        progression = [item for item in pool if item.classification & ItemClassification.progression]
        self.assertGreaterEqual(len(progression) / len(pool), MIN_PROGRESSION_SHARE,
                                f"{len(progression)}/{len(pool)} progression")

    def test_short_contents(self) -> None:
        self.assertNotIn("Ice Storm", {region.name for region in self.multiworld.get_regions()})
        self.assertFalse(self.get_items_by_name("Ice Storm Mode"))
        self.assertFalse(self.get_items_by_name(LEVEL_CAP))
        self.assertFalse(self.get_items_by_name(BADGE_TIER))
        self.assertEqual(len(self.get_items_by_name(RELIC_KEY)), 1)
        self.assertEqual(len(self.get_items_by_name(JEWEL_SHARD)), 6)
        names = self.location_names()
        self.assertIn(level_location_name(5), names)
        self.assertNotIn(level_location_name(6), names)
        self.assertIn(quest_location_name(15), names)  # relic 2
        self.assertNotIn(quest_location_name(16), names)  # relic 3
        self.assertNotIn(badge("Stellar", "Bronze"), names)  # slow cumulative badge
        self.assertNotIn(badge("Blaster", "Silver"), names)

    def test_levels_2_to_5_need_nothing(self) -> None:
        for level in range(2, 6):
            self.assertTrue(self.can_reach_location(level_location_name(level)))

    def test_secret_modes_need_both_items(self) -> None:
        for secret, prerequisite, location in (("Butterflies Mode", "Zen Mode", badge("Butterfly Monarch", "Bronze")),
                                               ("Diamond Mine Mode", "Quest Mode", badge("Relic Hunter", "Bronze"))):
            for missing in (secret, prerequisite):
                with self.subTest(location=location, missing=missing):
                    self.multiworld.state = CollectionState(self.multiworld)
                    self.collect_all_but(missing)
                    self.assertFalse(self.can_reach_location(location))
                    self.collect_by_name(missing)
                    self.assertTrue(self.can_reach_location(location))

    def test_shard_goal(self) -> None:
        self.collect_all_but(JEWEL_SHARD)
        shards = self.get_items_by_name(JEWEL_SHARD)
        self.collect(shards[:4])
        self.assertBeatable(False)
        self.collect(shards[4])
        self.assertBeatable(True)


class TestMedium(LengthTestBase):
    length = "medium"
    options: ClassVar[dict[str, Any]] = {"seed_length": "medium"}

    def test_one_level_cap_opens_levels_6_to_8(self) -> None:
        self.collect_all_but(LEVEL_CAP)
        self.assertFalse(self.can_reach_location(level_location_name(6)))
        self.collect_by_name(LEVEL_CAP)
        self.assertTrue(self.can_reach_location(level_location_name(8)))

    def test_one_badge_tier_opens_silver(self) -> None:
        self.collect_all_but(BADGE_TIER)
        self.assertTrue(self.can_reach_location(badge("Blaster", "Bronze")))
        self.assertFalse(self.can_reach_location(badge("Blaster", "Silver")))
        self.collect_by_name(BADGE_TIER)
        self.assertTrue(self.can_reach_location(badge("Blaster", "Silver")))

    def test_luck_elites_are_filler_only(self) -> None:
        for name in ("Annihilator", "Superstar"):
            self.assertEqual(self.world.get_location(badge(name)).progress_type, LocationProgressType.EXCLUDED)


class TestLong(LengthTestBase):
    length = "long"
    options: ClassVar[dict[str, Any]] = {"seed_length": "long"}

    def test_ice_storm_needs_lightning_and_its_item(self) -> None:
        location = badge("Ice Breaker", "Bronze")
        for missing in ("Ice Storm Mode", "Lightning Mode"):
            with self.subTest(missing=missing):
                self.multiworld.state = CollectionState(self.multiworld)
                self.collect_all_but(missing)
                self.assertFalse(self.can_reach_location(location))

    def test_levels_9_10_and_levelord_need_two_caps(self) -> None:
        self.collect_all_but(LEVEL_CAP)
        caps = self.get_items_by_name(LEVEL_CAP)
        self.assertEqual(len(caps), 2)
        self.collect(caps[0])
        self.assertTrue(self.can_reach_location(level_location_name(8)))
        self.assertFalse(self.can_reach_location(level_location_name(9)))
        self.assertFalse(self.can_reach_location(badge("Levelord")))
        self.collect(caps[1])
        self.assertTrue(self.can_reach_location(level_location_name(10)))
        self.assertTrue(self.can_reach_location(badge("Levelord")))

    def test_gold_needs_two_tiers(self) -> None:
        self.collect_all_but(BADGE_TIER)
        tiers = self.get_items_by_name(BADGE_TIER)
        self.assertEqual(len(tiers), 2)
        self.collect(tiers[0])
        self.assertFalse(self.can_reach_location(badge("Blaster", "Gold")))
        self.collect(tiers[1])
        self.assertTrue(self.can_reach_location(badge("Blaster", "Gold")))

    def test_hard_checks_are_filler_only(self) -> None:
        for name in (level_location_name(9), badge("High Voltage", "Bronze"), badge("Heroes Welcome")):
            self.assertEqual(self.world.get_location(name).progress_type, LocationProgressType.EXCLUDED)


class TestMarathon(LengthTestBase):
    length = "marathon"
    options: ClassVar[dict[str, Any]] = {"seed_length": "marathon", "starting_mode": "quest"}

    def test_everything_present(self) -> None:
        self.assertEqual(len(self.get_items_by_name(BADGE_TIER)), 3)
        self.assertEqual(len(self.get_items_by_name(RELIC_KEY)), 4)
        self.assertTrue(self.get_items_by_name("Classic Mode"))
        self.assertFalse(self.get_items_by_name("Quest Mode"))

    def test_top_secret_needs_all_secret_modes(self) -> None:
        for missing in ("Poker Mode", "Butterflies Mode", "Ice Storm Mode", "Diamond Mine Mode"):
            with self.subTest(missing=missing):
                self.multiworld.state = CollectionState(self.multiworld)
                self.collect_all_but(missing)
                self.assertFalse(self.can_reach_location(badge("Top Secret")))

    def test_poker_needs_classic(self) -> None:
        self.collect_all_but("Classic Mode")
        self.assertFalse(self.can_reach_location(badge("Ante Up", "Bronze")))


class TestHeroesWelcomeOnShort(Bejeweled3TestBase):
    options: ClassVar[dict[str, Any]] = {"goal": "heroes_welcome"}

    def test_goal_adds_and_needs_all_keys(self) -> None:
        self.assertFalse(self.get_items_by_name(JEWEL_SHARD))
        self.collect_all_but(RELIC_KEY)
        keys = self.get_items_by_name(RELIC_KEY)
        self.assertEqual(len(keys), 4)
        self.collect(keys[:3])
        self.assertBeatable(False)
        self.collect(keys[3])
        self.assertBeatable(True)


class TestLevelordOnShort(Bejeweled3TestBase):
    options: ClassVar[dict[str, Any]] = {"goal": "levelord"}

    def test_goal_adds_and_needs_two_caps(self) -> None:
        self.collect_all_but(LEVEL_CAP)
        caps = self.get_items_by_name(LEVEL_CAP)
        self.assertEqual(len(caps), 2)
        self.collect(caps[0])
        self.assertBeatable(False)
        self.collect(caps[1])
        self.assertBeatable(True)


class TestOptionSweep(Bejeweled3TestBase):
    """Every option combination generates, balances, starts wide and is beatable with all items (3 seeds each)."""
    run_default_tests = False

    def test_combinations(self) -> None:
        grid = {
            "seed_length": ["short", "medium", "long", "marathon"],
            "goal": ["shard_hunt", "levelord", "heroes_welcome"],
            "starting_mode": ["classic", "quest"],
        }
        for values in itertools.product(*grid.values()):
            options = dict(zip(grid, values, strict=True))
            for seed in range(3):
                with self.subTest(**options, seed=seed):
                    multiworld = setup_multiworld(Bejeweled3World, gen_steps, seed=seed, options=options)
                    self.assertEqual(len(multiworld.itempool), len(multiworld.get_locations()))
                    self.assertTrue(multiworld.can_beat_game(multiworld.get_all_state()))
                    start = CollectionState(multiworld)
                    open_checks = [location for location in multiworld.get_locations()
                                   if location.progress_type != LocationProgressType.EXCLUDED
                                   and location.can_reach(start)]
                    self.assertGreaterEqual(len(open_checks), MIN_SPHERE_ZERO)


class TestEarlyLocalMode(Bejeweled3TestBase):
    """The other base mode lands in this slot's own sphere-1 checks (the live seed's item-starvation fix)."""
    run_default_tests = False

    def test_other_base_mode_is_local_and_early(self) -> None:
        other = {"classic": "Quest Mode", "quest": "Classic Mode"}
        for length, start in itertools.product(["short", "medium", "long", "marathon"], other):
            for seed in range(3):
                with self.subTest(seed_length=length, starting_mode=start, seed=seed):
                    options = {"seed_length": length, "starting_mode": start}
                    # Two slots, so "local" means something: the item could otherwise land in player 2's world.
                    multiworld = setup_multiworld([Bejeweled3World, Bejeweled3World], gen_steps, seed=seed,
                                                  options=[options, {}])
                    distribute_items_restrictive(multiworld)
                    placed = [location for location in multiworld.get_locations()
                              if location.item and location.item.player == 1 and location.item.name == other[start]]
                    self.assertEqual(len(placed), 1)
                    self.assertEqual(placed[0].player, 1)
                    self.assertTrue(placed[0].can_reach(CollectionState(multiworld)))


class TestIdsStable(Bejeweled3TestBase):
    """IDs are part of the datapackage. If this fails, you renumbered something that may already be released."""
    run_default_tests = False

    def test_ids_match_snapshot(self) -> None:
        snapshot = json.loads(ID_SNAPSHOT.read_text(encoding="utf-8"))
        self.assertEqual(snapshot["items"], Bejeweled3World.item_name_to_id)
        self.assertEqual(snapshot["locations"], Bejeweled3World.location_name_to_id)

    def test_ids_unique(self) -> None:
        self.assertEqual(len(set(Bejeweled3World.item_name_to_id.values())), len(Bejeweled3World.item_name_to_id))
        self.assertEqual(len(set(Bejeweled3World.location_name_to_id.values())),
                         len(Bejeweled3World.location_name_to_id))

    def test_names(self) -> None:
        self.assertIn("Quest: Relic 1 - Butterflies", Bejeweled3World.location_name_to_id)
        self.assertIn("Badge: Blaster - Silver", Bejeweled3World.location_name_to_id)
        self.assertEqual(badge_location_name(LOCATION_TABLE["Badge: Superstar"].badge, 1), "Badge: Superstar")
