from __future__ import annotations

from typing import TYPE_CHECKING

from rule_builder.rules import CanReachRegion, Has, Rule

from .items import BADGE_TIER, JEWEL_SHARD, LEVEL_CAP, RELIC_KEY, caps_needed_for_level, keys_needed_for_relic
from .locations import CLASSIC, MAX_LEVEL, QUEST, RELIC_COUNT, SECRET_MODES, LocationData, enabled_locations

if TYPE_CHECKING:
    from .world import Bejeweled3World


def needs(item: str, count: int) -> Rule | None:
    return Has(item, count) if count > 0 else None


def location_rule(data: LocationData) -> Rule | None:
    """Gating-item rule on top of the location's region (mode) rule, or None if ungated."""
    if data.kind == "level":
        return needs(LEVEL_CAP, caps_needed_for_level(data.level))
    if data.kind == "quest":
        return needs(RELIC_KEY, keys_needed_for_relic(data.relic))
    assert data.badge is not None
    name = data.badge.name
    if name == "Heroes Welcome":
        return needs(RELIC_KEY, keys_needed_for_relic(RELIC_COUNT))
    if name == "Levelord":
        return needs(LEVEL_CAP, caps_needed_for_level(MAX_LEVEL))
    if name == "Top Secret":
        rule: Rule = CanReachRegion(SECRET_MODES[0])
        for mode in SECRET_MODES[1:]:
            rule = rule & CanReachRegion(mode)
        return rule
    if not data.badge.elite:
        return needs(BADGE_TIER, data.tier - 1)
    return None


def set_all_rules(world: Bejeweled3World) -> None:
    for data in enabled_locations(world):
        rule = location_rule(data)
        if rule is not None:
            world.set_rule(world.get_location(data.name), rule)
    set_completion_condition(world)


def set_completion_condition(world: Bejeweled3World) -> None:
    goal = world.options.goal
    if goal == goal.option_shard_hunt:
        world.set_completion_rule(Has(JEWEL_SHARD, world.shard_required))
    elif goal == goal.option_levelord:
        world.set_completion_rule(CanReachRegion(CLASSIC) & Has(LEVEL_CAP, caps_needed_for_level(MAX_LEVEL)))
    else:
        world.set_completion_rule(CanReachRegion(QUEST) & Has(RELIC_KEY, keys_needed_for_relic(RELIC_COUNT)))
