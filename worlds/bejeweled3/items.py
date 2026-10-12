"""
Item table for Bejeweled 3.

Item ID blocks (offsets from BASE_ID), with room to grow:
  0..99     mode unlocks
  100..199  gating items / goal items
  200..299  filler
  300..399  traps (reserved for Phase 4)
IDs are part of the datapackage: never renumber a released item.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

from BaseClasses import Item, ItemClassification

from .locations import (
    ALL_MODES,
    BASE_ID,
    BASE_MODES,
    CLASSIC,
    GAME_NAME,
    ICE_STORM,
    ICE_STORM_LENGTH,
    LONG,
    MARATHON,
    MAX_LEVEL,
    MEDIUM_LENGTH,
    QUEST,
    RELIC_COUNT,
    SHORT,
    max_common_tier,
    max_level,
    max_relic,
)

if TYPE_CHECKING:
    from .world import Bejeweled3World

RELIC_KEY = "Relic Key"
LEVEL_CAP = "Progressive Level Cap"
BADGE_TIER = "Progressive Badge Tier"
JEWEL_SHARD = "Jewel Shard"
SPARKLE = "Sparkle"

# Levels up to FREE_LEVEL always count; each Progressive Level Cap raises the cap by LEVELS_PER_CAP (5 -> 8 -> 10).
FREE_LEVEL = 5
LEVELS_PER_CAP = 3

# Shard Hunt: (Jewel Shards in the pool, Jewel Shards required) per seed length.
SHARDS_BY_LENGTH = {SHORT: (6, 5), MEDIUM_LENGTH: (10, 8), LONG: (15, 12), MARATHON: (20, 16)}


def mode_item_name(mode: str) -> str:
    return f"{mode} Mode"


ITEM_NAME_TO_ID: dict[str, int] = {
    **{mode_item_name(mode): BASE_ID + i for i, mode in enumerate(ALL_MODES)},
    RELIC_KEY: BASE_ID + 100,
    LEVEL_CAP: BASE_ID + 101,
    BADGE_TIER: BASE_ID + 102,
    JEWEL_SHARD: BASE_ID + 103,
    SPARKLE: BASE_ID + 200,
}

ITEM_CLASSIFICATIONS: dict[str, ItemClassification] = {
    **{mode_item_name(mode): ItemClassification.progression for mode in ALL_MODES},
    RELIC_KEY: ItemClassification.progression,
    LEVEL_CAP: ItemClassification.progression,
    BADGE_TIER: ItemClassification.progression,
    # Goal macguffins: progression balancing pulling them early wouldn't help anyone.
    JEWEL_SHARD: ItemClassification.progression_skip_balancing,
    SPARKLE: ItemClassification.filler,
}

ITEM_NAME_GROUPS = {
    "Modes": {mode_item_name(mode) for mode in ALL_MODES},
    "Gating Items": {RELIC_KEY, LEVEL_CAP, BADGE_TIER},
}


class Bejeweled3Item(Item):
    game = GAME_NAME


def caps_needed_for_level(level: int) -> int:
    """Progressive Level Caps needed before "Reach Level <level>" counts."""
    return math.ceil(max(0, level - FREE_LEVEL) / LEVELS_PER_CAP)


def keys_needed_for_relic(relic: int) -> int:
    """Relic Keys needed before relic <relic>'s quests count (relic 1 is free)."""
    return relic - 1


def starting_mode_name(world: Bejeweled3World) -> str:
    return BASE_MODES[world.options.starting_mode.value]


def early_local_mode(world: Bejeweled3World) -> str:
    """The other base mode with plenty of checks: Quest on a Classic start, Classic on a Quest start."""
    return mode_item_name(QUEST if starting_mode_name(world) == CLASSIC else CLASSIC)


def relic_key_count(world: Bejeweled3World) -> int:
    top_relic = max_relic(world.options.seed_length.value)
    if world.options.goal == world.options.goal.option_heroes_welcome:
        top_relic = RELIC_COUNT
    return keys_needed_for_relic(top_relic)


def level_cap_count(world: Bejeweled3World) -> int:
    top_level = max_level(world.options.seed_length.value)
    if world.options.goal == world.options.goal.option_levelord:
        top_level = MAX_LEVEL
    return caps_needed_for_level(top_level)


def badge_tier_count(world: Bejeweled3World) -> int:
    return max_common_tier(world.options.seed_length.value) - 1


def shard_counts(world: Bejeweled3World) -> tuple[int, int]:
    return SHARDS_BY_LENGTH[world.options.seed_length.value]


def mode_items(world: Bejeweled3World) -> list[str]:
    start = starting_mode_name(world)
    has_ice_storm = world.options.seed_length.value >= ICE_STORM_LENGTH
    return [mode_item_name(mode) for mode in ALL_MODES if mode != start and (mode != ICE_STORM or has_ice_storm)]


def create_item_with_classification(world: Bejeweled3World, name: str) -> Bejeweled3Item:
    return Bejeweled3Item(name, ITEM_CLASSIFICATIONS[name], ITEM_NAME_TO_ID[name], world.player)


def create_all_items(world: Bejeweled3World) -> None:
    world.push_precollected(world.create_item(mode_item_name(starting_mode_name(world))))

    names = mode_items(world)
    names += [RELIC_KEY] * relic_key_count(world)
    names += [LEVEL_CAP] * level_cap_count(world)
    names += [BADGE_TIER] * badge_tier_count(world)
    names += [JEWEL_SHARD] * world.shard_count

    pool = [world.create_item(name) for name in names]
    free = len(world.multiworld.get_unfilled_locations(world.player)) - len(pool)
    assert free >= 0, "generate_early must guarantee the pool fits"
    pool += [world.create_filler() for _ in range(free)]
    world.multiworld.itempool += pool
