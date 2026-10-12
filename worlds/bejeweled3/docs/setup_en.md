# Bejeweled 3 Setup Guide

## What you need

- **Bejeweled 3 for PC, Steam version** (1.1.12.4196, the current Steam build). Other versions (EA app,
  retail/PopCap discs) aren't supported; the client tells you if yours doesn't match.
- **Archipelago 0.6.7 or newer** ([download](https://github.com/ArchipelagoMW/Archipelago/releases)).
- **`bejeweled3.apworld`** from the
  [Bejeweled 3 releases page](https://github.com/BrianErlich/Archipelago/releases?q=bejeweled3).

## First: make a fresh Bejeweled 3 profile for each seed

This is the one step that costs you checks if you skip it. Bejeweled 3 saves badges and quests **per profile,
forever**, and anything a profile already has can't be sent again.

1. Start Bejeweled 3. On the main menu, click **"Click here to change user"** under your name.
2. Pick **(Add A New User)** and name it for this seed, e.g. `APFriends1`. The game doesn't allow spaces or hyphens.
3. Leave that profile selected.

The first time the client connects to a seed, it **remembers the active profile** and counts only progress made
from then on. If you connect with an old profile, the client lists everything that profile already had as
"will never count for this seed". Nothing breaks, but those checks are gone.

## Installing

1. Double-click `bejeweled3.apworld`. The Archipelago Launcher opens and installs it.
   (Or: Launcher → **Install APWorld** → pick the file.)
2. Restart the Launcher if it was already open. **Bejeweled 3 Client** now appears in its list.

**Whoever generates the multiworld also needs the `.apworld` installed.** Custom worlds can't be generated on
archipelago.gg, so the host generates on their own PC (Launcher → **Generate**) and uploads the result to
archipelago.gg to host it.

## Your options (YAML)

Make one in the Launcher's **Options Creator** (pick Bejeweled 3), or start from this:

```yaml
name: YourName
game: Bejeweled 3
Bejeweled 3:
  seed_length: short      # short (~3 h), medium (~8 h), long (~20 h), marathon (100+ h)
  goal: shard_hunt        # shard_hunt, levelord, heroes_welcome
  starting_mode: classic  # classic or quest
```

**Seed Length** is the main choice: it decides how many checks your slot has and roughly how long it takes.
Short is a relaxed evening; Marathon is for veterans chasing every Platinum. Give the YAML to whoever hosts.

## Connecting

1. Start Bejeweled 3 (with your fresh profile selected) and **Bejeweled 3 Client** from the Launcher, in either order.
   The client finds the game by itself.
2. In the client, type `/connect <server address>`, e.g. `/connect archipelago.gg:51187`, then your slot name
   (the `name` from your YAML).
3. The client log confirms `This seed is bound to Bejeweled 3 profile '...'`, followed by a status line.

Don't run Bejeweled 3 as administrator; if you do, the client can't read it and tells you so.

## How it plays

- **Checks:** reaching Classic levels, earning badge tiers, and completing quests.
- **Items:** game modes (e.g. *Quest Mode*, *Poker Mode*), Relic Keys, Progressive Level Caps,
  Progressive Badge Tiers, and Jewel Shards for the Shard Hunt goal.
- **Your second mode comes early:** if you start in Classic, Quest Mode is in one of your own first checks
  (and the other way round).
- **Locked modes:** you can still play a mode you haven't received; the client warns you when a game starts.
  Badges and quests you earn there are **saved and sent automatically** when the item arrives.
  **Classic levels are the exception**: a level only counts while that same Classic game is running.
- **Secret modes need two unlocks:** the Archipelago item *and* the game's own unlock (Poker: Classic level 5;
  Butterflies: Zen level 5; Diamond Mine: finish 4 quests of the first relic; Ice Storm: 100,000 points in Lightning).
- **Relic Keys** let later relics' quests count. They don't skip the game's own rule that relic *n + 1* opens only
  after 4 quests of relic *n*.
- **Hard checks never block anyone:** expert or luck-based badges only ever hold filler.
- **Skill note:** Archipelago logic only knows about items. "In logic" means nothing is item-locked, not that it's easy.

## The client window

- The **Bejeweled 3** tab is your to-do list: the goal, what to play next, checks you've done that are waiting on an
  item, and which item each one needs.
- The main log shows every check sent and item received, like any Archipelago client.

### Commands

| Command | What it does |
|---|---|
| `/bj3 status` | What the client sees (game, profile, current mode), your unlocks and any held checks. |
| `/bj3 guide` | The same to-do list as the Bejeweled 3 tab, printed in the log. |
| `/bj3 hint <item>` | Hints an item (like `!hint`, same hint cost) and posts where it is to the room chat, tagged `[Bejeweled 3 Client]`, so whoever holds it knows you're waiting. Example: `/bj3 hint Quest Mode`. |
| `/bj3 rescan` | Re-reads everything from the game from scratch. |

## Known limitations

- **Steam build only** (1.1.12.4196).
- **Classic levels are live-only.** The game doesn't save your best level, so a level counts only while you're in
  that game, with the client running.
- **Badges earned inside quests** (e.g. Butterfly Bonanza during a Butterflies quest) belong to that badge's mode,
  so they're held until you have that mode's item. They aren't lost, but it can be surprising.
- **Heroes Welcome:** it's not yet confirmed whether the game awards it after 20 or after all 40 quests.
- **Steam achievements** pop as you earn badges on your Archipelago profile.

## Troubleshooting

| Message | What to do |
|---|---|
| `Waiting for Bejeweled 3 to start.` | Start the game; the client attaches within a second or two. |
| `Windows refused access to Bejeweled 3...` | The game runs as administrator and the client doesn't. Run both normally. |
| `Bejeweled 3 version ... isn't supported` | Only the current Steam build works for now. |
| `Not sending checks: this seed is bound to profile 'X'...` | Switch to profile X in game; the client resumes by itself. |
| `... is held until you receive ...` | That check waits for an item; it sends automatically when the item arrives. |

Found a bug? Open an issue on [GitHub](https://github.com/BrianErlich/Archipelago/issues) and attach the client log
(`logs\Bejeweled3Client_*.txt` in your Archipelago folder).
