# Bejeweled 3 for Archipelago

An [Archipelago](https://archipelago.gg) multiworld randomizer world for **Bejeweled 3 (PC, Steam)**.
Game modes, Relic Keys, Level Caps and Badge Tiers come from the multiworld; Classic levels, badges and quests
send checks. A client reads the game's memory from outside: nothing in the game or your save is modified.

**Status: beta (0.2.0).** Tested in one live four-player multiworld. Expect rough edges and please report them.

## Requirements

- Bejeweled 3, Steam version 1.1.12.4196 (the current Steam build). Other versions aren't supported.
- Archipelago 0.6.7 or newer, on Windows.

## Getting started

1. Download `bejeweled3.apworld` from the release and double-click it.
2. Follow the [setup guide](docs/setup_en.md). Its first step, a fresh in-game profile per seed, matters.
3. Read the [game page](docs/en_Bejeweled%203.md) for what's randomized, the Seed Length table and the goals.

A sample YAML is attached to the release.

## Reporting bugs

Open an issue on [GitHub](https://github.com/BrianErlich/Archipelago/issues). Include your Seed Length, what
happened, and the client log (`logs\Bejeweled3Client_*.txt` in your Archipelago folder).

## Credits

- Made by BrianErlich, built with Claude Code.
- [redstone59's Bejeweled3WorldChampionships](https://github.com/redstone59/Bejeweled3WorldChampionships) showed
  that an outside program reading the game's memory works for Bejeweled 3. No code was taken from it.
- [Bejeweled3PlusExtender](https://github.com/bognarit80/Bejeweled3PlusExtender) (MIT) was a reference for the
  game's class layout and naming.
- Archipelago and this world are MIT licensed.
