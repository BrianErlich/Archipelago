from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, ClassVar

from Options import OptionError
from worlds.AutoWorld import World

from . import items, locations, regions, rules, web_world
from . import options as bj3_options

logger = logging.getLogger("Bejeweled 3")


class Bejeweled3World(World):
    """
    Bejeweled 3 (PC). Match gems across eight modes, earn badges and restore the Lost Relics of Bejeweled.
    Modes and gating items come from the multiworld; reaching Classic levels, earning badges and completing
    quests send checks.
    """

    game = locations.GAME_NAME
    web = web_world.Bejeweled3WebWorld()
    options_dataclass = bj3_options.Bejeweled3Options
    options: bj3_options.Bejeweled3Options

    location_name_to_id: ClassVar[dict[str, int]] = locations.LOCATION_NAME_TO_ID
    item_name_to_id: ClassVar[dict[str, int]] = items.ITEM_NAME_TO_ID
    location_name_groups = locations.LOCATION_NAME_GROUPS
    item_name_groups = items.ITEM_NAME_GROUPS
    origin_region_name = locations.MENU

    shard_count: int = 0
    shard_required: int = 0

    def generate_early(self) -> None:
        location_count = len(locations.enabled_locations(self))
        other_progression = (len(items.mode_items(self)) + items.relic_key_count(self)
                             + items.level_cap_count(self) + items.badge_tier_count(self))
        room = location_count - other_progression
        if room < 0:
            raise OptionError(f"Bejeweled 3 ({self.player_name}): these options leave {location_count} locations for "
                              f"{other_progression} progression items. Enable more locations "
                              f"(quest_locations, max_badge_tier, include_elite_badges).")

        if self.options.goal != self.options.goal.option_shard_hunt:
            return
        self.shard_count = min(self.options.shard_count.value, room)
        if self.shard_count < 1:
            raise OptionError(f"Bejeweled 3 ({self.player_name}): no room for Jewel Shards. Enable more locations.")
        if self.shard_count < self.options.shard_count.value:
            logger.warning(f"Bejeweled 3 ({self.player_name}): only room for {self.shard_count} Jewel Shards "
                           f"(asked for {self.options.shard_count.value}).")
        self.shard_required = min(self.options.shard_required.value, self.shard_count)
        if self.shard_required < self.options.shard_required.value:
            logger.warning(f"Bejeweled 3 ({self.player_name}): Jewel Shards Required lowered to "
                           f"{self.shard_required} to match the shard count.")

    def create_regions(self) -> None:
        regions.create_and_connect_regions(self)
        locations.create_all_locations(self)

    def set_rules(self) -> None:
        rules.set_all_rules(self)

    def create_items(self) -> None:
        items.create_all_items(self)

    def create_item(self, name: str) -> items.Bejeweled3Item:
        return items.create_item_with_classification(self, name)

    def get_filler_item_name(self) -> str:
        return items.SPARKLE

    def fill_slot_data(self) -> Mapping[str, Any]:
        return {
            **self.options.as_dict(
                "goal", "starting_mode", "relic_keys", "level_cap_items", "badge_tier_items", "max_badge_tier",
                "include_skill_gates", "quest_locations",
            ),
            "include_elite_badges": sorted(self.options.include_elite_badges.value),
            "shard_count": self.shard_count,
            "shard_required": self.shard_required,
        }
