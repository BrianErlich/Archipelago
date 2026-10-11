"""
Location table for Bejeweled 3, generated from data.

Sources (see docs/memory_map.md and docs/BALANCE.md):
- badge ids/names/order: badge objects in memory + the in-game Badges screen (Steam 1.1.12.4196)
- tier thresholds: properties\\badges.txt inside main.pak
- quest names/order: properties\\quest.cfg inside main.pak (5 relics x 8 quests)
- difficulty ratings (E/M/H/X): judgement, refined by playtesting (BALANCE.md)

IDs are part of the datapackage: never renumber a released location.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from BaseClasses import Location, LocationProgressType

if TYPE_CHECKING:
    from .world import Bejeweled3World

GAME_NAME = "Bejeweled 3"
BASE_ID = 0xBE30000

# Location ID blocks (offsets from BASE_ID), with room to grow:
#   0..99      Classic levels (offset = level)
#   100..199   quests (100 + quest index k, 0..39)
#   1000..1199 badges (1000 + badge id * 10 + tier; elite badges use tier 1)
LEVEL_BLOCK = 0
QUEST_BLOCK = 100
BADGE_BLOCK = 1000

MENU = "Menu"
CLASSIC, ZEN, LIGHTNING, QUEST = "Classic", "Zen", "Lightning", "Quest"
POKER, BUTTERFLIES, ICE_STORM, DIAMOND_MINE = "Poker", "Butterflies", "Ice Storm", "Diamond Mine"
BASE_MODES = (CLASSIC, ZEN, LIGHTNING, QUEST)
SECRET_MODES = (POKER, BUTTERFLIES, ICE_STORM, DIAMOND_MINE)
ALL_MODES = BASE_MODES + SECRET_MODES

TIER_NAMES = {1: "Bronze", 2: "Silver", 3: "Gold", 4: "Platinum"}

# Difficulty ratings: E easy, M medium, H hard, X expert/grind (X locations are EXCLUDED: filler only).
EASY, MEDIUM, HARD, EXPERT = "E", "M", "H", "X"


@dataclass(frozen=True)
class Badge:
    badge_id: int
    name: str
    mode: str | None  # region where it's earned; None = any mode (placed in Menu)
    ratings: tuple[str, ...]  # one per tier (common: 4, elite: 1)
    luck: bool = False  # can't be forced by skill -> always EXCLUDED

    @property
    def elite(self) -> bool:
        return len(self.ratings) == 1


COMMON_BADGES = (
    Badge(0, "Inferno", None, (EASY, MEDIUM, HARD, EXPERT)),  # 50/400/1400/3400 Flame Gems, cumulative
    Badge(1, "Stellar", None, (MEDIUM, HARD, EXPERT, EXPERT)),  # 25/150/550/1300 Star Gems, cumulative
    Badge(2, "Chromatic", None, (MEDIUM, HARD, EXPERT, EXPERT)),  # 25/150/550/1300 Hypercubes, cumulative
    Badge(3, "Blaster", None, (EASY, EASY, MEDIUM, HARD)),  # 30/40/50/60 gems in one move
    Badge(4, "Bejeweler", CLASSIC, (MEDIUM, HARD, EXPERT, EXPERT)),  # 50k/150k/300k/500k one Classic game
    Badge(5, "Final Frenzy", LIGHTNING, (MEDIUM, MEDIUM, HARD, EXPERT)),  # 20k/30k/40k/60k in a Last Hurrah
    Badge(6, "High Voltage", LIGHTNING, (HARD, EXPERT, EXPERT, EXPERT)),  # 100k/300k/500k/750k Lightning
    Badge(7, "Ante Up", POKER, (MEDIUM, HARD, EXPERT, EXPERT)),  # 100k/300k/500k/750k Poker
    Badge(8, "The Gambler", POKER, (MEDIUM, MEDIUM, HARD, HARD)),  # 10/30/60/100 flushes
    Badge(9, "Glacial Explorer", ICE_STORM, (HARD, EXPERT, EXPERT, EXPERT)),  # 100k/300k/500k/750k Ice Storm
    Badge(10, "Ice Breaker", ICE_STORM, (MEDIUM, HARD, EXPERT, EXPERT)),  # x5/x8/x12/x15 column combo
    Badge(11, "Diamond, Mine", DIAMOND_MINE, (MEDIUM, HARD, EXPERT, EXPERT)),  # 100k/300k/500k/750k
    Badge(12, "Relic Hunter", DIAMOND_MINE, (MEDIUM, HARD, EXPERT, EXPERT)),  # 5/8/12/15 artifacts
    Badge(13, "Butterfly Monarch", BUTTERFLIES, (MEDIUM, HARD, EXPERT, EXPERT)),  # 100k/300k/500k/750k
    Badge(14, "Butterfly Bonanza", BUTTERFLIES, (MEDIUM, HARD, EXPERT, EXPERT)),  # 4/6/8/10 in one move
)

ELITE_BADGES = (
    Badge(15, "Heroes Welcome", QUEST, (HARD,)),  # complete Quest mode
    Badge(16, "Annihilator", None, (HARD,), luck=True),  # swap two Hypercubes
    Badge(17, "Superstar", None, (HARD,), luck=True),  # line up 6 gems in a row
    Badge(18, "Levelord", CLASSIC, (HARD,)),  # Classic level 10 (a skill gate)
    Badge(19, "Top Secret", None, (EXPERT,)),  # 300k in all four secret modes (a skill gate)
)
ELITE_BADGE_NAMES = tuple(badge.name for badge in ELITE_BADGES)
SKILL_GATED_ELITES = frozenset({"Levelord", "Top Secret"})

QUEST_NAMES = (
    # relic 1
    "Butterflies", "Gold Rush", "Alchemy", "Stratamax", "Balance", "Avalanche", "Buried Treasure", "Time Bomb",
    # relic 2
    "Poker", "Ice Storm", "Stratamax II", "Sandstorm", "Butterflies II", "Balance II", "Time Bomb II", "Avalanche II",
    # relic 3
    "Alchemy II", "Wall Blast", "Poker II", "Butterflies III", "Avalanche III", "Gold Rush II", "Stratamax III",
    "Time Bomb III",
    # relic 4
    "Gold Rush III", "Butterflies IV", "Alchemy III", "Avalanche IV", "Ice Storm II", "Time Bomb IV", "Balance III",
    "Stratamax IV",
    # relic 5
    "Balance IV", "Sandstorm II", "Stratamax V", "Wall Blast II", "Gold Rush IV", "Poker III", "Avalanche V",
    "Ice Storm III",
)
QUESTS_PER_RELIC = 8
RELIC_COUNT = 5
assert len(QUEST_NAMES) == QUESTS_PER_RELIC * RELIC_COUNT

MIN_CHECK_LEVEL = 2
MAX_LEVEL = 10
SKILL_GATED_MIN_LEVEL = 9  # levels 9 and 10 need include_skill_gates
LEVEL_RATINGS = {2: EASY, 3: EASY, 4: EASY, 5: MEDIUM, 6: MEDIUM, 7: MEDIUM, 8: HARD, 9: HARD, 10: HARD}


@dataclass(frozen=True)
class LocationData:
    name: str
    address: int
    region: str
    kind: str  # "level" | "quest" | "badge"
    rating: str
    level: int = 0  # kind == "level"
    quest_index: int = -1  # kind == "quest"
    relic: int = 0  # kind == "quest", 1-based
    badge: Badge | None = None  # kind == "badge"
    tier: int = 0  # kind == "badge", 1-based (elite: 1)

    @property
    def excluded(self) -> bool:
        return self.rating == EXPERT or (self.badge is not None and self.badge.luck)


def level_location_name(level: int) -> str:
    return f"Classic: Reach Level {level}"


def quest_location_name(quest_index: int) -> str:
    return f"Quest: Relic {quest_index // QUESTS_PER_RELIC + 1} - {QUEST_NAMES[quest_index]}"


def badge_location_name(badge: Badge, tier: int) -> str:
    if badge.elite:
        return f"Badge: {badge.name}"
    return f"Badge: {badge.name} - {TIER_NAMES[tier]}"


def _build_table() -> dict[str, LocationData]:
    table = [
        LocationData(level_location_name(level), BASE_ID + LEVEL_BLOCK + level, CLASSIC, "level",
                     LEVEL_RATINGS[level], level=level)
        for level in range(MIN_CHECK_LEVEL, MAX_LEVEL + 1)
    ]
    table += [
        LocationData(quest_location_name(k), BASE_ID + QUEST_BLOCK + k, QUEST, "quest", MEDIUM,
                     quest_index=k, relic=k // QUESTS_PER_RELIC + 1)
        for k in range(len(QUEST_NAMES))
    ]
    table += [
        LocationData(badge_location_name(badge, tier), BASE_ID + BADGE_BLOCK + badge.badge_id * 10 + tier,
                     badge.mode or MENU, "badge", rating, badge=badge, tier=tier)
        for badge in COMMON_BADGES + ELITE_BADGES
        for tier, rating in enumerate(badge.ratings, start=1)
    ]
    return {data.name: data for data in table}


LOCATION_TABLE = _build_table()
LOCATION_NAME_TO_ID = {name: data.address for name, data in LOCATION_TABLE.items()}

LOCATION_NAME_GROUPS = {
    "Levels": {name for name, data in LOCATION_TABLE.items() if data.kind == "level"},
    "Quests": {name for name, data in LOCATION_TABLE.items() if data.kind == "quest"},
    "Badges": {name for name, data in LOCATION_TABLE.items() if data.kind == "badge"},
    "Elite Badges": {name for name, data in LOCATION_TABLE.items() if data.badge and data.badge.elite},
    **{f"Relic {n}": {name for name, data in LOCATION_TABLE.items() if data.relic == n}
       for n in range(1, RELIC_COUNT + 1)},
}


class Bejeweled3Location(Location):
    game = GAME_NAME


def is_location_enabled(world: Bejeweled3World, data: LocationData) -> bool:
    options = world.options
    skill_gates = bool(options.include_skill_gates)
    if data.region == ICE_STORM and not skill_gates:
        return False
    if data.kind == "level":
        return data.level < SKILL_GATED_MIN_LEVEL or skill_gates
    if data.kind == "quest":
        return data.relic <= options.quest_locations.value
    assert data.badge is not None
    if data.badge.elite:
        if data.badge.name not in options.include_elite_badges.value:
            return False
        return data.badge.name not in SKILL_GATED_ELITES or skill_gates
    return data.tier <= options.max_badge_tier.value


def enabled_locations(world: Bejeweled3World) -> list[LocationData]:
    return [data for data in LOCATION_TABLE.values() if is_location_enabled(world, data)]


def create_all_locations(world: Bejeweled3World) -> None:
    for data in enabled_locations(world):
        region = world.get_region(data.region)
        location = Bejeweled3Location(world.player, data.name, data.address, region)
        if data.excluded:
            location.progress_type = LocationProgressType.EXCLUDED
        region.locations.append(location)
