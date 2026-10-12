# Bejeweled 3 changelog

## 0.2.0 (beta) — first public release

Generation (needs a new seed):
- The other base mode (Quest Mode on a Classic start, Classic Mode on a Quest start) is always placed in one of
  your own early checks. In the first playtest it sat in another player's world and stalled the slot for an hour.

Client:
- Fixed: elite badges (Superstar, Annihilator...) are stored as 5 in memory; the client rejected that and stopped
  reading the game until restarted.
- New **Bejeweled 3** tab: the goal, what to play next, held checks and the items they wait for.
- New `/bj3 guide` (the same list in the log) and `/bj3 hint <item>` (hints an item and tells the room where it is,
  tagged `[Bejeweled 3 Client]`; only the hint you asked for is announced).
- A heads-up when a game starts in a mode you haven't received yet, or in a quest whose relic needs more Relic Keys.
- Secret modes are told apart from quests that use the same board (e.g. Butterflies mode vs. a Butterflies quest).
- A single garbled read while switching profiles no longer resets the client's state.

## 0.1.0 — private playtest

- First version: four Seed Lengths, three goals, Classic or Quest start; memory-reading client.
