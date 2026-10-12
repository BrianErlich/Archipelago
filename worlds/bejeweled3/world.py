from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

from worlds.AutoWorld import World

from . import items, locations, regions, rules, web_world
from . import options as bj3_options


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
        if self.options.goal == self.options.goal.option_shard_hunt:
            self.shard_count, self.shard_required = items.shard_counts(self)
        progression = (len(items.mode_items(self)) + items.relic_key_count(self) + items.level_cap_count(self)
                       + items.badge_tier_count(self) + self.shard_count)
        location_count = len(locations.enabled_locations(self))
        if progression > location_count:  # a data bug, not a player mistake: every length/goal combination must fit
            raise RuntimeError(f"Bejeweled 3: {progression} progression items for {location_count} locations")
        # The live seed starved when the other base mode sat deep in another player's world: put it in one of
        # this slot's own sphere-1 checks so the first hour always opens a second mode.
        self.multiworld.local_early_items[self.player][items.early_local_mode(self)] = 1

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
            **self.options.as_dict("seed_length", "goal", "starting_mode"),
            "shard_count": self.shard_count,
            "shard_required": self.shard_required,
        }
