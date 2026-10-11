from dataclasses import dataclass

from Options import Choice, DefaultOnToggle, OptionGroup, OptionSet, PerGameCommonOptions, Range, Toggle

from .locations import ELITE_BADGE_NAMES


class Goal(Choice):
    """
    What you need to do to finish your slot.

    Shard Hunt: collect a number of Jewel Shards from the multiworld. Doesn't depend on in-game skill.
    Levelord: reach level 10 in a single Classic game (requires all Progressive Level Caps if those are on).
    Heroes Welcome: complete Quest mode (requires all five Relic Keys if those are on). This takes several hours.
    """
    display_name = "Goal"
    option_shard_hunt = 0
    option_levelord = 1
    option_heroes_welcome = 2
    default = option_shard_hunt


class ShardCount(Range):
    """
    Shard Hunt only: how many Jewel Shards are in the item pool.
    Lowered automatically if your slot doesn't have enough locations to hold them.
    """
    display_name = "Jewel Shard Count"
    range_start = 1
    range_end = 30
    default = 10


class ShardRequired(Range):
    """
    Shard Hunt only: how many Jewel Shards you need to finish. Capped at the Jewel Shard Count.
    """
    display_name = "Jewel Shards Required"
    range_start = 1
    range_end = 30
    default = 7


class StartingMode(Choice):
    """
    The game mode you can send checks from at the start. The other base modes become items.
    Secret modes (Poker, Butterflies, Ice Storm, Diamond Mine) can't be the starting mode,
    because each one also has to be unlocked in game first.
    """
    display_name = "Starting Mode"
    option_classic = 0
    option_zen = 1
    option_lightning = 2
    option_quest = 3
    default = option_classic


class RelicKeys(DefaultOnToggle):
    """
    Adds progressive Relic Keys. Quest checks in relic N only count once you hold N Relic Keys.
    Keys don't skip anything in game: relic N+1 still opens only after you finish 4 quests of relic N.
    """
    display_name = "Relic Keys"


class LevelCapItems(DefaultOnToggle):
    """
    Adds Progressive Level Caps. "Reach Level N" checks above the cap don't count.
    The cap starts at level 2 and each Progressive Level Cap raises it by 2.
    """
    display_name = "Progressive Level Caps"


class BadgeTierItems(DefaultOnToggle):
    """
    Adds Progressive Badge Tiers. Bronze badge checks always count;
    each Progressive Badge Tier enables the next tier (Silver, then Gold, then Platinum).
    """
    display_name = "Progressive Badge Tiers"


class MaxBadgeTier(Choice):
    """
    The highest tier of the 15 common badges that becomes a check.
    Gold and especially Platinum need expert play or a lot of grinding;
    expert-level checks only ever hold filler, so nobody else waits on them.
    """
    display_name = "Max Badge Tier"
    option_bronze = 1
    option_silver = 2
    option_gold = 3
    option_platinum = 4
    default = option_silver


class IncludeEliteBadges(OptionSet):
    """
    Which elite badges become checks.
    Annihilator, Superstar and Top Secret depend on luck or expert play, so they only ever hold filler.
    Levelord and Top Secret also need Include Skill Gates.
    """
    display_name = "Include Elite Badges"
    valid_keys = frozenset(ELITE_BADGE_NAMES)
    default = frozenset({"Heroes Welcome", "Levelord", "Annihilator", "Superstar"})


class IncludeSkillGates(Toggle):
    """
    Includes content that needs real skill to unlock or reach:
    the Ice Storm mode (unlocked in game by scoring 100,000 in Lightning) with its badges,
    "Reach Level 9" and "Reach Level 10", the Levelord badge, and the Top Secret badge.
    """
    display_name = "Include Skill Gates"


class QuestLocations(Range):
    """
    How many relics' quests are checks (8 quests per relic). 5 = all 40 quests, 0 = no quest checks.
    """
    display_name = "Quest Locations (Relics)"
    range_start = 0
    range_end = 5
    default = 5


@dataclass
class Bejeweled3Options(PerGameCommonOptions):
    goal: Goal
    shard_count: ShardCount
    shard_required: ShardRequired
    starting_mode: StartingMode
    relic_keys: RelicKeys
    level_cap_items: LevelCapItems
    badge_tier_items: BadgeTierItems
    max_badge_tier: MaxBadgeTier
    include_elite_badges: IncludeEliteBadges
    include_skill_gates: IncludeSkillGates
    quest_locations: QuestLocations


option_groups = [
    OptionGroup("Goal", [Goal, ShardCount, ShardRequired]),
    OptionGroup("Progression", [StartingMode, RelicKeys, LevelCapItems, BadgeTierItems]),
    OptionGroup("Locations", [MaxBadgeTier, IncludeEliteBadges, IncludeSkillGates, QuestLocations]),
]
