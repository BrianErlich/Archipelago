import itertools
import json
from pathlib import Path
from typing import Any, ClassVar

from BaseClasses import ItemClassification, LocationProgressType
from test.general import gen_steps, setup_multiworld

from ..items import BADGE_TIER, JEWEL_SHARD, LEVEL_CAP, RELIC_KEY
from ..locations import LOCATION_TABLE, badge_location_name, level_location_name, quest_location_name
from ..world import Bejeweled3World
from . import Bejeweled3TestBase

# Default options must give a pool where at least this share of items is progression (SPEC §9).
MIN_PROGRESSION_SHARE = 0.25

ID_SNAPSHOT = Path(__file__).parent / "ids_snapshot.json"


def badge(name: str, tier: str | None = None) -> str:
    return f"Badge: {name}" + (f" - {tier}" if tier else "")


class TestDefaults(Bejeweled3TestBase):
    def test_item_count_equals_location_count(self) -> None:
        self.assertEqual(len(self.multiworld.get_items()), len(self.multiworld.get_locations()))

    def test_progression_share(self) -> None:
        pool = self.multiworld.itempool
        progression = [item for item in pool if item.classification & ItemClassification.progression]
        share = len(progression) / len(pool)
        self.assertGreaterEqual(share, MIN_PROGRESSION_SHARE,
                                f"{len(progression)}/{len(pool)} = {share:.0%} progression")

    def test_skill_gates_off_removes_ice_storm_and_high_levels(self) -> None:
        location_names = {location.name for location in self.multiworld.get_locations()}
        self.assertNotIn("Ice Storm", {region.name for region in self.multiworld.get_regions()})
        self.assertFalse(self.get_items_by_name("Ice Storm Mode"))
        for name in (level_location_name(9), level_location_name(10), badge("Glacial Explorer", "Bronze"),
                     badge("Ice Breaker", "Bronze"), badge("Levelord"), badge("Top Secret")):
            self.assertNotIn(name, location_names)
        self.assertIn(level_location_name(8), location_names)

    def test_secret_modes_need_both_items(self) -> None:
        for secret, prerequisite, location in (("Butterflies Mode", "Zen Mode", badge("Butterfly Monarch", "Bronze")),
                                               ("Diamond Mine Mode", "Quest Mode", badge("Relic Hunter", "Bronze"))):
            for missing in (secret, prerequisite):
                with self.subTest(location=location, missing=missing):
                    self.collect_all_but(missing)
                    self.assertFalse(self.can_reach_location(location))
                    self.collect_by_name(missing)
                    self.assertTrue(self.can_reach_location(location))
                    self.multiworld.state = self.multiworld.state.__class__(self.multiworld)

    def test_relic_keys_gate_quests(self) -> None:
        self.collect_all_but(RELIC_KEY)
        for keys in range(6):
            for k in range(0, 40, 8):
                relic = k // 8 + 1
                with self.subTest(keys=keys, relic=relic):
                    self.assertEqual(self.can_reach_location(quest_location_name(k)), relic <= keys)
            if keys < 5:
                self.collect(self.get_item_by_name(RELIC_KEY))

    def test_level_caps_gate_levels(self) -> None:
        self.collect_all_but(LEVEL_CAP)
        caps = self.get_items_by_name(LEVEL_CAP)
        self.assertEqual(len(caps), 3)  # skill gates off: levels up to 8 -> 3 caps
        for held in range(len(caps) + 1):
            for level in range(2, 9):
                with self.subTest(caps=held, level=level):
                    self.assertEqual(self.can_reach_location(level_location_name(level)), level <= 2 + 2 * held)
            if held < len(caps):
                self.collect(caps[held])

    def test_badge_tiers_gate_badges(self) -> None:
        self.collect_all_but(BADGE_TIER)
        self.assertTrue(self.can_reach_location(badge("Blaster", "Bronze")))
        self.assertFalse(self.can_reach_location(badge("Blaster", "Silver")))
        self.collect_by_name(BADGE_TIER)
        self.assertTrue(self.can_reach_location(badge("Blaster", "Silver")))

    def test_expert_and_luck_locations_are_excluded(self) -> None:
        for location in self.multiworld.get_locations(self.player):
            data = LOCATION_TABLE[location.name]
            expected = LocationProgressType.EXCLUDED if data.excluded else LocationProgressType.DEFAULT
            with self.subTest(location=location.name):
                self.assertEqual(location.progress_type, expected)
        self.assertEqual(self.world.get_location(badge("Annihilator")).progress_type, LocationProgressType.EXCLUDED)
        self.assertEqual(self.world.get_location(badge("High Voltage", "Silver")).progress_type,
                         LocationProgressType.EXCLUDED)


class TestSkillGatesOn(Bejeweled3TestBase):
    options: ClassVar[dict[str, Any]] = {
        "include_skill_gates": True,
        "include_elite_badges": ["Heroes Welcome", "Annihilator", "Superstar", "Levelord", "Top Secret"],
    }

    def test_ice_storm_needs_lightning_and_its_item(self) -> None:
        location = badge("Glacial Explorer", "Bronze")
        self.collect_all_but("Ice Storm Mode")
        self.assertFalse(self.can_reach_location(location))
        self.collect_by_name("Ice Storm Mode")
        self.assertTrue(self.can_reach_location(location))

    def test_top_secret_needs_all_secret_modes(self) -> None:
        for missing in ("Poker Mode", "Butterflies Mode", "Ice Storm Mode", "Diamond Mine Mode"):
            with self.subTest(missing=missing):
                self.multiworld.state = self.multiworld.state.__class__(self.multiworld)
                self.collect_all_but(missing)
                self.assertFalse(self.can_reach_location(badge("Top Secret")))

    def test_levels_9_and_10_need_four_caps(self) -> None:
        self.assertEqual(len(self.get_items_by_name(LEVEL_CAP)), 4)
        self.collect_all_but(LEVEL_CAP)
        caps = self.get_items_by_name(LEVEL_CAP)
        self.collect(caps[:3])
        self.assertTrue(self.can_reach_location(level_location_name(8)))
        self.assertFalse(self.can_reach_location(level_location_name(9)))
        self.assertFalse(self.can_reach_location(badge("Levelord")))
        self.collect(caps[3])
        self.assertTrue(self.can_reach_location(level_location_name(10)))
        self.assertTrue(self.can_reach_location(badge("Levelord")))


class TestEverythingOn(Bejeweled3TestBase):
    options: ClassVar[dict[str, Any]] = {
        "goal": "heroes_welcome",
        "max_badge_tier": "platinum",
        "include_skill_gates": True,
        "include_elite_badges": ["Heroes Welcome", "Annihilator", "Superstar", "Levelord", "Top Secret"],
        "starting_mode": "zen",
    }

    def test_classic_is_an_item(self) -> None:
        self.assertTrue(self.get_items_by_name("Classic Mode"))
        self.assertFalse(self.get_items_by_name("Zen Mode"))
        self.assertEqual(len(self.get_items_by_name(BADGE_TIER)), 3)

    def test_heroes_goal_needs_all_relic_keys(self) -> None:
        self.collect_all_but(RELIC_KEY)
        keys = self.get_items_by_name(RELIC_KEY)
        self.assertEqual(len(keys), 5)
        self.collect(keys[:4])
        self.assertBeatable(False)
        self.collect(keys[4])
        self.assertBeatable(True)

    def test_poker_needs_classic(self) -> None:
        self.collect_all_but("Classic Mode")
        self.assertFalse(self.can_reach_location(badge("Ante Up", "Bronze")))


class TestMinimal(Bejeweled3TestBase):
    options: ClassVar[dict[str, Any]] = {
        "quest_locations": 0,
        "max_badge_tier": "bronze",
        "relic_keys": False,
        "level_cap_items": False,
        "badge_tier_items": False,
        "include_elite_badges": [],
        "shard_count": 30,
        "shard_required": 30,
    }

    def test_shards_clamped_to_room(self) -> None:
        shards = len(self.get_items_by_name(JEWEL_SHARD))
        self.assertEqual(shards, self.world.shard_count)
        self.assertLess(shards, 30)
        self.assertEqual(self.world.shard_required, shards)
        self.assertEqual(len(self.multiworld.get_items()), len(self.multiworld.get_locations()))


class TestShardMath(Bejeweled3TestBase):
    options: ClassVar[dict[str, Any]] = {"shard_count": 10, "shard_required": 12}

    def test_required_capped_and_enforced(self) -> None:
        self.assertEqual(self.world.shard_count, 10)
        self.assertEqual(self.world.shard_required, 10)
        self.collect_all_but(JEWEL_SHARD)
        shards = self.get_items_by_name(JEWEL_SHARD)
        self.collect(shards[:9])
        self.assertBeatable(False)
        self.collect(shards[9])
        self.assertBeatable(True)


class TestLevelordGoalWithoutSkillGates(Bejeweled3TestBase):
    options: ClassVar[dict[str, Any]] = {"goal": "levelord"}

    def test_goal_needs_four_caps(self) -> None:
        self.assertEqual(len(self.get_items_by_name(LEVEL_CAP)), 4)
        self.collect_all_but(LEVEL_CAP)
        caps = self.get_items_by_name(LEVEL_CAP)
        self.collect(caps[:3])
        self.assertBeatable(False)
        self.collect(caps[3])
        self.assertBeatable(True)


class TestOptionSweep(Bejeweled3TestBase):
    """Every combination of the structural options generates, balances and is beatable with all items."""
    run_default_tests = False

    def test_combinations(self) -> None:
        grid = {
            "goal": ["shard_hunt", "levelord", "heroes_welcome"],
            "include_skill_gates": [False, True],
            "max_badge_tier": ["bronze", "silver", "gold", "platinum"],
            "relic_keys": [False, True],
            "level_cap_items": [False, True],
            "badge_tier_items": [False, True],
            "quest_locations": [0, 1, 5],
            "starting_mode": ["classic", "zen", "lightning", "quest"],
        }
        for values in itertools.product(*grid.values()):
            options = dict(zip(grid, values, strict=True))
            with self.subTest(**options):
                multiworld = setup_multiworld(Bejeweled3World, gen_steps, seed=0, options=options)
                self.assertEqual(len(multiworld.itempool), len(multiworld.get_locations()))
                state = multiworld.get_all_state()
                self.assertTrue(multiworld.can_beat_game(state))


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
