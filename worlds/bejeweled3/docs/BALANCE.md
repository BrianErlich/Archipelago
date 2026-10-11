# Bejeweled 3 APWorld — progression & difficulty notes

Dev notes for balancing; not shipped (`.apignore`). Thresholds are **from the game data** (`properties\badges.txt` in `main.pak`). Difficulty ratings are **judgements** to be refined by playtesting; data points are logged at the bottom.

## 1. Vanilla progression (what the game itself gates)

| Unlock | Vanilla condition | Effort | Status |
|---|---|---|---|
| Classic, Zen, Lightning, Quest | available from the start | — | observed |
| **Diamond Mine** | restore relic 1 = complete any 4 of its 8 quests | ~20–30 min | **verified 2026-10-11** (Brian: Avalanche, Buried Treasure, Balance, Time Bomb → "New Mode Unlocked: Diamond Mine") |
| Poker | reach Classic level 5 | ~20–40 min in one Classic game | wiki, unverified |
| Butterflies | reach Zen level 5 | easy, Zen can't be lost | wiki, unverified |
| **Ice Storm** | 100,000 in one Lightning game | **hard** for casual players | wiki, unverified |
| Relic *n+1* | restore relic *n* (4 of its 8 quests) | ~20–40 min per relic, harder each relic | observed for relic 1 |
| Remaining quests of a restored relic | **stay playable** | — | verified (Brian, after restoring relic 1) |

Consequences for logic: Butterflies is reachable for everyone; Poker needs moderate Classic play; Diamond Mine needs Quest Mode in practice (already in the region rule); **Ice Storm is the only real skill gate**, which is why `include_skill_gates` exists.

## 2. Badge thresholds (game data) and difficulty

Ratings: **E** easy — comes with normal play in the first hour or two · **M** medium — needs a focused session or decent play · **H** hard — skilled play or many hours · **X** expert/grind — top players or tens of hours. "Cum." = counter accumulates across games (time-gated rather than skill-gated); "1 game" = must happen within a single game or move (skill/luck-gated).

| id | Badge | Kind | Bronze | Silver | Gold | Platinum | Rating B / S / G / P |
|---|---|---|---|---|---|---|---|
| 0 | Inferno (Flame Gems) | cum. | 50 | 400 | 1,400 | 3,400 | E / M / H / X |
| 1 | Stellar (Star Gems) | cum. | 25 | 150 | 550 | 1,300 | M / H / X / X |
| 2 | Chromatic (Hypercubes) | cum. | 25 | 150 | 550 | 1,300 | M / H / X / X |
| 3 | Blaster (gems in one move) | 1 move, luck | 30 | 40 | 50 | 60 | E / E / M / H |
| 4 | Bejeweler (Classic score) | 1 game | 50k | 150k | 300k | 500k | M / H / X / X |
| 5 | Final Frenzy (Last Hurrah, Lightning) | 1 game | 20k | 30k | 40k | 60k | M / M / H / X |
| 6 | High Voltage (Lightning score) | 1 game | 100k | 300k | 500k | 750k | H / X / X / X |
| 7 | Ante Up (Poker score) | 1 game | 100k | 300k | 500k | 750k | M / H / X / X |
| 8 | The Gambler (Poker flushes) | cum.? | 10 | 30 | 60 | 100 | M / M / H / H |
| 9 | Glacial Explorer (Ice Storm score) | 1 game | 100k | 300k | 500k | 750k | H / X / X / X |
| 10 | Ice Breaker (Ice Storm column combo) | 1 game | x5 | x8 | x12 | x15 | M / H / X / X |
| 11 | Diamond, Mine (DM score) | 1 game | 100k | 300k | 500k | 750k | M / H / X / X |
| 12 | Relic Hunter (DM artifacts) | 1 game? | 5 | 8 | 12 | 15 | M / H / X / X |
| 13 | Butterfly Monarch (Butterflies score) | 1 game | 100k | 300k | 500k | 750k | M / H / X / X |
| 14 | Butterfly Bonanza (butterflies in one move) | 1 move, luck | 4 | 6 | 8 | 10 | M / H / X / X |
| 15 | Heroes Welcome | quest | complete Quest mode | — | — | — | H (long) |
| 16 | Annihilator (swap two Hypercubes) | luck | 1 | — | — | — | H (needs two adjacent Hypercubes) |
| 17 | Superstar (6 in a row) | luck | 1 | — | — | — | H (rare board state) |
| 18 | Levelord | 1 game | Classic level 10 | — | — | — | H (long Classic game) |
| 19 | Top Secret | 4 modes | 300k in all 4 secret modes | — | — | — | X |

Notes:
- `badges.txt` lists elite thresholds as Heroes Welcome 1, Annihilator 1, Superstar 1, **Levelord 10**, **Top Secret 4**. The stored *tier value* for elites is still unverified (likely 1 = earned).
- "Cum.?" / "1 game?" = the tooltip wording is ambiguous; confirm in Phase 2 by watching the badge progress counter across two games.
- Tier values: 2 = Silver and 3 = Gold verified (Blaster), 1 = Bronze, 4 = Platinum inferred.

### Rating counts (default-ish pool, Bronze–Gold, 15 common + elite)

- **E/M (fun, reachable):** 22 of 45 common tiers — mostly Bronze/Silver, plus Blaster Gold, Final Frenzy Silver and The Gambler Silver.
- **H:** ~11 of 45 common tiers, plus the 4 default elites.
- **X:** ~12 of 45 common tiers — mostly Gold score tiers (500k) and Gold cumulative tiers. **Platinum is almost all X** (correctly off by default).

## 3. Balancing problems this exposes (for the Phase 1 decision)

1. **The default pool contains many X locations.** Gold is on by default (only Platinum is off). Gold tiers of the 100k-family score badges (500k in one game) and Stellar/Chromatic Gold (550 cumulative) are expert-level. In logic they are "in logic" as soon as the items arrive (SPEC §6.3 skill note), so **other players' progression could sit behind a 500k Poker game**. That is the single biggest fun risk.
2. **Luck badges** (Annihilator, Superstar, Butterfly Bonanza Silver+) can't be forced by skill; a progression item there can stall a multiworld.
3. **Cumulative badges are time sinks, not skill sinks.** They feel fine as filler-holding checks that pop "for free" during normal play, but holding progression they turn into grinds.
4. **Ice Storm** is double-gated by skill: its unlock (100k Lightning) and its own badges (100k Ice Storm). `include_skill_gates` already removes it by default. Good.
5. **Tier skipping creates bursts:** a strong player who receives a Badge Tier item can clear Bronze + Silver + Gold of several badges at once. That's fun and fine, but it means tier items shouldn't be the very last progression items.

## 4. Proposed fixes (decisions for Brian — none implemented yet)

- **A. Difficulty tags in the location table.** Each location row carries its rating (E/M/H/X) as data. No new option needed.
- **B. Use AP's progress types.** X locations, plus the luck elites, get `LocationProgressType.EXCLUDED`: they can only ever hold filler/junk, so nobody waits on them. H locations stay DEFAULT. This is standard AP practice and doesn't change the option set.
- **C. Default badge tiers.** Either keep Gold in by default and rely on B, or replace `include_platinum_badges` with a `max_badge_tier` choice (Bronze / Silver / Gold / Platinum, default Silver or Gold). The second option is cleaner for players but changes the v1 option set, so it needs approval.
- **D. Levels.** Level checks 2–8 (9–10 under `include_skill_gates`) are E→H and live-only. Fine as is. Levelord stays an elite location (H) and an alternative goal.
- **E. Quests.** All 40 quest locations are valid: a relic's leftover quests stay playable. Later relics' quests are harder, but quests are mostly M with a time limit, and failing one has no cost. Keep all 40 as DEFAULT. Relic *n* quests require `Relic Key × n` (logic) **and** 4 quests of relic *n−1* done in game, which the keys model.
- **F. Progression share target.** With defaults (7 modes + 5 keys + 4 caps + 3 tiers + 10 shards = 29 progression) against ~90 locations, that's ≈ 32%. Keep it above ~25% (test threshold).

## 5. Playtest data log

| Date | Who | Observation |
|---|---|---|
| 2026-10-11 | Brian, profile AP1PROBE | Blaster Silver (≥40 gems in one move) in the first Zen session (~30 min); **Gold (50)** during the next quest session. → Blaster B/S are E, Gold is M. |
| 2026-10-11 | Brian | Relic 1 restored after 4 quests in roughly 30–40 min total including Zen play; Diamond Mine unlocked. |
| 2026-10-10 | Brian | Classic level 2 reached within a few minutes; level 4 in a later session (game mode not recorded). |
