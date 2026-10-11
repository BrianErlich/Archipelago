# Bejeweled 3 — manual test (Phase 2 gate)

Brian runs this on his PC. Everything runs **from source** in the project's venv, so nothing needs installing.
Work in a PowerShell window in the `Archipelago` folder. Tick each box and note anything odd next to it.

> Times matter: **start a stopwatch at step 3** and keep a rough log of when things happen. The playtest time goes
> into `BALANCE.md` §5.

## 0. Prepare (once, ~5 min)

1. Generate a Short seed with default options (Claude can do this for you):
   ```
   .venv/Scripts/python Generate.py --player_files_path <folder with your yaml> --outputpath out
   ```
   The YAML only needs `name: Brian`, `game: Bejeweled 3` and `Bejeweled 3: {}`.
2. Start a local server with the generated zip:
   ```
   .venv/Scripts/python MultiServer.py out/AP_<seed>.zip
   ```
   Leave that window open. The server listens on `localhost:38281`.
3. In Bejeweled 3, **create a fresh profile** for this seed, e.g. `AP-Short1`, and select it.

## 1. Attach and bind

- [ ] **Client after game:** with the game running, start the client:
  `.venv/Scripts/python -c "from worlds.bejeweled3.client import launch; launch()"`
  It should log `Attached to Steam 1.1.12.4196`.
- [ ] Connect: type `/connect localhost` and enter the slot name `Brian`. The log should say
  `This seed is bound to Bejeweled 3 profile 'AP-Short1'`, followed by a status line
  (`Modes: Classic | Relic Keys: 0 | Level cap: 5 | Badge tier: Bronze | Jewel Shards: 0/5`).
- [ ] `/bj3 status` prints the game build, profile, where you are, and the status line.
- [ ] **Game after client:** close the game (client stays open). The log says the game was closed. Start the game
  again; the client re-attaches by itself within a few seconds.

## 2. Checks send

- [ ] Play Classic to **level 2**: `Classic: Reach Level 2` appears in the log as sent.
- [ ] Earn a **Bronze badge** (Blaster is the quickest: 30 gems in one move): it sends.
- [ ] Once you've received **Quest Mode**: complete a **relic 1 quest**; it sends. (No Relic Key needed for relic 1.)

## 3. Held checks

- [ ] Earn a check whose item you don't have yet, e.g. reach **level 6** in Classic before you have a Progressive
  Level Cap. The log says `Classic: Reach Level 6 is held until you receive Progressive Level Cap (levels only count
  while you're still in that game)`. If the item arrives while you're still in that game, it sends then.
- [ ] A **badge** or **quest** held for a missing item sends by itself when the item arrives, even much later.

## 4. Disconnect and profile handling

- [ ] Close the **client**, earn a badge in game, reopen the client and connect: the badge sends on connect.
- [ ] Switch to another profile in game: the client warns `Not sending checks: this seed is bound to profile ...`
  and sends nothing. Switch back: it resumes.

## 5. Goal

- [ ] When the **5th Jewel Shard** arrives, the log says `Goal complete!` and the server shows the slot as finished.
  No `!release` needed.

## 6. Stopwatch playtest

- [ ] Play the whole Short seed to the goal. Total time: ______ h ______ min (from creating the profile to goal).
- [ ] Rough split if you can: Classic ____, quests ____, other modes ____, waiting on items ____.
- [ ] Anything that felt slow, confusing or too easy: ______________________

## Report back to Claude

- the ticked boxes and notes;
- the playtest time;
- the client log: it's in `Archipelago/logs/`, newest `Bejeweled3Client_*.txt`.
