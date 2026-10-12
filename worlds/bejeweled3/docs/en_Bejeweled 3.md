# Bejeweled 3

## Where is the options page?

The [player options page for this game](../player-options) contains all the options you need to configure and export
a config file.

## What does randomization do to this game?

Bejeweled 3's modes, and the progress inside them, are locked behind items from the multiworld:

- **Game modes.** You start with Classic or Quest (your choice). Zen, Lightning, Quest/Classic, and the four secret
  modes (Poker, Butterflies, Diamond Mine, Ice Storm) are items.
- **Relic Keys** (progressive). Relic 1's quests always count; relic *n* needs *n − 1* keys.
- **Progressive Level Caps.** Classic levels 2–5 count from the start; each cap opens three more.
- **Progressive Badge Tiers.** Bronze badges count from the start; each tier opens the next (Silver, Gold, Platinum).
- **Jewel Shards** for the Shard Hunt goal.

Checks are things you already do in the game: reaching a Classic level, earning a badge tier, and completing a quest.

You can play any mode in the game at any time. A badge or quest earned in a mode you haven't unlocked yet
**isn't lost**: the client holds it and sends it the moment the item arrives. Classic levels are the exception: a level
only counts while that Classic game is still running.

## How long is a seed?

The **Seed Length** option sets everything: which checks exist, how many gating items there are and how many
Jewel Shards you need.

| Length | Rough time | Checks | What's in it |
|---|---|---|---|
| Short (default) | ~3 hours | 30 | 7 modes, Classic levels 2–5, relics 1–2 (16 quests), quick Bronze badges |
| Medium | ~8 hours | 49 | + levels 6–8, relic 3, every Bronze, quick Silvers, Annihilator, Superstar |
| Long | ~20 hours | 87 | + levels 9–10, all 40 quests, Ice Storm, every Silver, reachable Golds, Heroes Welcome, Levelord |
| Marathon | 100+ hours | 114 | + every Gold and Platinum, Top Secret |

Hard, expert and luck-based badges only ever hold filler, so nobody else in the multiworld waits on your skill or luck.
Archipelago logic still only knows about items: "in logic" means nothing is item-locked, not that it's easy.

## What is the goal?

- **Shard Hunt** (default): collect enough Jewel Shards (5 of 6 on Short, up to 16 of 20 on Marathon). Needs no
  in-game skill.
- **Levelord:** reach level 10 in a single Classic game.
- **Heroes Welcome:** complete Quest mode. Takes several hours, even on a Short seed.

## Which items can be in another player's world?

All of them. The one exception is the other base mode (Quest Mode if you start in Classic, Classic Mode if you start
in Quest): it's always in one of your own early checks, so you're never stuck waiting in the first hour.

## What does another world's item look like in Bejeweled 3?

Nothing changes in the game. The Bejeweled 3 Client window lists every check you send and every item you receive,
and its **Bejeweled 3** tab shows what to do next.

## When the player receives an item, what happens?

The client logs it. If the item unlocks checks you've already done (for example a quest finished before Quest Mode
arrived), those checks send right away.

## How does this work, and what should I expect?

The client reads Bejeweled 3's memory from outside, like a trainer that only looks. It never modifies the game, its
files or your save. It supports the current Steam version only (1.1.12.4196).

This world is in **beta**. The hour estimates come from a single Short playtest (2 h 19 min in a four-player
multiworld) and are guesses for the longer lengths. Bug reports and timing reports are very welcome.
