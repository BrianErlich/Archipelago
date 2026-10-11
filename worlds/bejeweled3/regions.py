from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import Region
from rule_builder.rules import Has, Rule

from .items import mode_item_name
from .locations import (
    ALL_MODES,
    BUTTERFLIES,
    CLASSIC,
    DIAMOND_MINE,
    ICE_STORM,
    ICE_STORM_LENGTH,
    LIGHTNING,
    MENU,
    POKER,
    QUEST,
    ZEN,
)

if TYPE_CHECKING:
    from .world import Bejeweled3World

# A secret mode needs its own Mode item AND access to the mode where the game unlocks it:
#   Poker <- Classic level 5, Butterflies <- Zen level 5,
#   Ice Storm <- 100,000 in Lightning, Diamond Mine <- restore relic 1 in Quest (4 quests).
SECRET_MODE_PREREQUISITE = {POKER: CLASSIC, BUTTERFLIES: ZEN, ICE_STORM: LIGHTNING, DIAMOND_MINE: QUEST}


def mode_rule(mode: str) -> Rule:
    rule: Rule = Has(mode_item_name(mode))
    if mode in SECRET_MODE_PREREQUISITE:
        rule = rule & Has(mode_item_name(SECRET_MODE_PREREQUISITE[mode]))
    return rule


def active_modes(world: Bejeweled3World) -> list[str]:
    has_ice_storm = world.options.seed_length.value >= ICE_STORM_LENGTH
    return [mode for mode in ALL_MODES if mode != ICE_STORM or has_ice_storm]


def create_and_connect_regions(world: Bejeweled3World) -> None:
    menu = Region(MENU, world.player, world.multiworld)
    regions = [menu]
    for mode in active_modes(world):
        region = Region(mode, world.player, world.multiworld)
        regions.append(region)
    world.multiworld.regions += regions
    for region in regions[1:]:
        world.create_entrance(menu, region, mode_rule(region.name), f"Play {region.name}")
