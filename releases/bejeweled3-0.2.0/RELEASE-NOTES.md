# Bejeweled 3 for Archipelago — 0.2.0 beta

Bejeweled 3 joins the multiworld: Classic levels, badge tiers and quests send checks, while game modes, Relic Keys, Level Caps and Badge Tiers arrive as items. Includes four seed lengths, three goals, a guide tab and `/bj3 guide` / `/bj3 hint` commands.

This is a beta. The project README records one live four-player multiworld playtest; expect rough edges and please report issues. This newly packaged artifact has not yet been tested in a Windows Archipelago installation.

## Install

1. Use Bejeweled 3 for Windows, Steam build **1.1.12.4196**, and Archipelago **0.6.7 or newer**.
2. Download and double-click **bejeweled3.apworld**, then restart the Archipelago Launcher if it was open.
3. Create a **fresh Bejeweled 3 profile for each seed**. Start with the attached **Bejeweled3.yaml**, changing `YourName` to your slot name.
4. Follow the [setup guide](https://github.com/BrianErlich/Archipelago/blob/bejeweled3/worlds/bejeweled3/docs/setup_en.md). Whoever generates the multiworld also needs this `.apworld`; generate custom-world seeds locally.

The separate client reads the game's memory. It does not modify the game or its save. Bejeweled 3 is not included.

## Changes since the private playtest

- Place the second base mode in an early local check to reduce opening stalls.
- Handle elite badge values correctly and tolerate a transient bad read during profile changes.
- Add the guide tab, guide/hint commands and warnings for unavailable modes or relics.
- Distinguish secret modes from quests using the same board.

See the [changelog](https://github.com/BrianErlich/Archipelago/blob/bejeweled3/worlds/bejeweled3/CHANGELOG.md) for details. Report bugs through [GitHub issues](https://github.com/BrianErlich/Archipelago/issues), including seed length and relevant client log after removing private information.

MIT licensed. Built by BrianErlich with Claude Code. The source README credits the memory-reading and class-layout references.
