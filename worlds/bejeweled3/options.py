from dataclasses import dataclass

from Options import Choice, OptionGroup, PerGameCommonOptions


class SeedLength(Choice):
    """
    How long your Bejeweled 3 slot takes, like ordering fries in a size. Everything scales with it:
    which checks exist, the gating items, and the Jewel Shards for the Shard Hunt goal.

    Short (default): about 3 hours. Seven modes, Classic levels 2-5, relics 1-2 (16 quests), quick Bronze badges.
    Medium: about 8 hours. Adds levels 6-8, relic 3, every Bronze badge, quick Silvers, Annihilator and Superstar.
    Long: about 20 hours. Adds levels 9-10, all 40 quests, Ice Storm, every Silver, reachable Golds,
          Heroes Welcome and Levelord.
    Marathon: 100+ hours, for veterans. Every badge tier including Platinum, plus Top Secret.

    Hard and expert checks only ever hold filler, so nobody else in the multiworld waits on them.
    The hours are estimates for an experienced casual player.
    """
    display_name = "Seed Length"
    option_short = 1
    option_medium = 2
    option_long = 3
    option_marathon = 4
    default = option_short


class Goal(Choice):
    """
    What you need to do to finish your slot.

    Shard Hunt: collect Jewel Shards from the multiworld (how many depends on Seed Length). Needs no in-game skill.
    Levelord: reach level 10 in a single Classic game.
    Heroes Welcome: complete Quest mode. This takes several hours, even on a Short seed.

    The goal adds whatever gating items it needs (Level Caps for Levelord, Relic Keys for Heroes Welcome).
    """
    display_name = "Goal"
    option_shard_hunt = 0
    option_levelord = 1
    option_heroes_welcome = 2
    default = option_shard_hunt


class StartingMode(Choice):
    """
    The game mode you can send checks from at the start. The other modes become items.

    Classic: start with Classic levels and badges.
    Quest: start with the first relic's eight quests.

    Zen and Lightning have too few checks of their own to start a seed with.
    """
    display_name = "Starting Mode"
    option_classic = 0  # values index BASE_MODES (Classic, Zen, Lightning, Quest)
    option_quest = 3
    default = option_classic


@dataclass
class Bejeweled3Options(PerGameCommonOptions):
    seed_length: SeedLength
    goal: Goal
    starting_mode: StartingMode


option_groups = [
    OptionGroup("Bejeweled 3", [SeedLength, Goal, StartingMode]),
]
