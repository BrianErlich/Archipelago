from __future__ import annotations

from typing import TYPE_CHECKING

from rule_builder.rules import CanReachRegion, Has, Rule

from .items import BADGE_TIER, JEWEL_SHARD, LEVEL_CAP, RELIC_KEY, caps_needed_for_level
from .locations import CLASSIC, MAX_LEVEL, QUEST, RELIC_COUNT, SECRET_MODES, LocationData, enabled_locations

if TYPE_CHECKING:
    from .world import Bejeweled3World


def location_rule(world: Bejeweled3World, data: LocationData) -> Rule | None:
    """Gating-item rule on top of the location's region (mode) rule, or None if ungated."""
    options = world.options
    if data.kind == "level":
        caps = caps_needed_for_level(data.level)
        if options.level_cap_items and caps:
            return Has(LEVEL_CAP, caps)
        return None
    if data.kind == "quest":
        return Has(RELIC_KEY, data.relic) if options.relic_keys else None
    assert data.badge is not None
    name = data.badge.name
    if name == "Heroes Welcome":
        return Has(RELIC_KEY, RELIC_COUNT) if options.relic_keys else None
    if name == "Levelord":
        return Has(LEVEL_CAP, caps_needed_for_level(MAX_LEVEL)) if options.level_cap_items else None
    if name == "Top Secret":
        rule: Rule = CanReachRegion(SECRET_MODES[0])
        for mode in SECRET_MODES[1:]:
            rule = rule & CanReachRegion(mode)
        return rule
    if not data.badge.elite and data.tier > 1 and options.badge_tier_items:
        return Has(BADGE_TIER, data.tier - 1)
    return None


def set_all_rules(world: Bejeweled3World) -> None:
    for data in enabled_locations(world):
        rule = location_rule(world, data)
        if rule is not None:
            world.set_rule(world.get_location(data.name), rule)
    set_completion_condition(world)


def set_completion_condition(world: Bejeweled3World) -> None:
    options = world.options
    if options.goal == options.goal.option_shard_hunt:
        world.set_completion_rule(Has(JEWEL_SHARD, world.shard_required))
    elif options.goal == options.goal.option_levelord:
        rule: Rule = CanReachRegion(CLASSIC)
        if options.level_cap_items:
            rule = rule & Has(LEVEL_CAP, caps_needed_for_level(MAX_LEVEL))
        world.set_completion_rule(rule)
    else:
        rule = CanReachRegion(QUEST)
        if options.relic_keys:
            rule = rule & Has(RELIC_KEY, RELIC_COUNT)
        world.set_completion_rule(rule)
