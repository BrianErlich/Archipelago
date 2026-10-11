# Bejeweled 3 Setup Guide

*First draft (Phase 2), written from the first live playtest. Phase 3 polishes it.*

## What you need

- **Bejeweled 3 for PC, Steam version** (version 1.1.12.4196, the current Steam build). Other versions (EA app,
  retail/PopCap discs) aren't supported yet; the client will tell you if your version doesn't match.
- **Archipelago 0.6.7 or newer** ([download](https://github.com/ArchipelagoMW/Archipelago/releases)).
- **`bejeweled3.apworld`** from this world's release page.

## Installing

1. Double-click `bejeweled3.apworld`. The Archipelago Launcher opens and installs it.
   (Or: Launcher → **Install APWorld** → pick the file.)
2. Restart the Launcher if it was already open. You should now see **Bejeweled 3 Client** in it.

Only players playing Bejeweled 3 need the client. **Whoever generates the multiworld needs the `.apworld`
installed too.** archipelago.gg can't generate seeds with custom worlds, so the host generates locally and
uploads the result to the website to host it.

## Your settings (YAML)

Make one in the Launcher's **Options Creator** (pick Bejeweled 3), or copy this:

```yaml
name: YourName
game: Bejeweled 3
Bejeweled 3:
  seed_length: short      # short (~3 h), medium (~8 h), long (~20 h), marathon (100+ h)
  goal: shard_hunt        # shard_hunt, levelord, heroes_welcome
  starting_mode: classic  # classic or quest
```

**Seed Length** is the main choice: it decides how many checks your slot has and roughly how long it takes.
Short is a relaxed evening. Marathon is for veterans who want every Platinum badge.

## Before you connect: make a fresh profile

Bejeweled 3 saves badges and quest progress **per profile**, permanently. So:

1. Start Bejeweled 3. On the main menu, click **"Click here to change user"** under your name.
2. Pick **(Add A New User)** and give it a name for this seed, e.g. `APFriends1`. (The game doesn't allow
   hyphens or spaces.)
3. Make sure that profile is selected, then connect.

The first time the client connects to a seed, it **remembers the active profile** and only counts progress made
from then on. If you connect with an old profile, everything that profile had already done is listed as "will never
count for this seed". Nothing breaks, but you lose those checks.

## Connecting

1. Start Bejeweled 3 (with your profile selected) and the **Bejeweled 3 Client** from the Launcher, in either order.
   The client finds the game by itself.
2. In the client, type `/connect <server address>`, e.g. `/connect archipelago.gg:51187`, and enter your slot name.
3. The client log confirms: `This seed is bound to Bejeweled 3 profile '...'`, followed by your status line.

Don't run Bejeweled 3 as administrator. If you do, the client can't read it and will tell you so.

## How it plays

- **Checks:** reaching Classic levels, earning badge tiers, and completing quests.
- **Items:** game modes (e.g. *Quest Mode*, *Poker Mode*), Relic Keys, Progressive Level Caps,
  Progressive Badge Tiers, and Jewel Shards for the Shard Hunt goal.
- **Locked modes:** you can still play a mode you haven't received; the client says so when you start. Badges and quests
  you earn there are **saved and sent automatically** when the item arrives. **Classic levels are the exception**:
  a level only counts while you're still in that same Classic game.
- **Secret modes need two unlocks:** the Archipelago item *and* the game's own unlock (Poker: Classic level 5;
  Butterflies: Zen level 5; Diamond Mine: finish 4 quests of the first relic; Ice Storm: 100,000 in Lightning).
- **Relic Keys** let quests of later relics count. They don't skip the game's own rule that relic *n+1* opens only
  after 4 quests of relic *n*.
- **Hard checks never block anyone:** expert-level or luck-based badges only ever hold filler.
- **Skill note:** Archipelago logic only knows about items, not skill. "In logic" means nothing is item-locked,
  not that it's easy.
- Earning badges on your AP profile also unlocks the matching **Steam achievements**.

## Commands

- `/bj3 status`: what the client sees (game, profile, current mode) plus your unlocks and any held checks.
- `/bj3 rescan`: re-read everything from the game.

## Troubleshooting

| Message | What to do |
|---|---|
| `Waiting for Bejeweled 3 to start.` | Start the game; the client attaches within a second or two. |
| `Windows refused access to Bejeweled 3...` | The game runs as administrator and the client doesn't. Run both normally. |
| `Bejeweled 3 version ... isn't supported` | Only the current Steam build works for now. |
| `Not sending checks: this seed is bound to profile 'X'...` | Switch to profile X in game; the client resumes by itself. |
| `... is held until you receive ...` | That check waits for an item; it sends automatically when it arrives. |
