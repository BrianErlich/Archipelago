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

## 3. Balancing problems the first design exposed

1. **The default pool contains many X locations.** Gold is on by default (only Platinum is off). Gold tiers of the 100k-family score badges (500k in one game) and Stellar/Chromatic Gold (550 cumulative) are expert-level. In logic they are "in logic" as soon as the items arrive (SPEC §6.3 skill note), so **other players' progression could sit behind a 500k Poker game**. That is the single biggest fun risk.
2. **Luck badges** (Annihilator, Superstar, Butterfly Bonanza Silver+) can't be forced by skill; a progression item there can stall a multiworld.
3. **Cumulative badges are time sinks, not skill sinks.** They feel fine as filler-holding checks that pop "for free" during normal play, but holding progression they turn into grinds.
4. **Ice Storm** is double-gated by skill: its unlock (100k Lightning) and its own badges (100k Ice Storm). `include_skill_gates` already removes it by default. Good.
5. **Tier skipping creates bursts:** a strong player who receives a Badge Tier item can clear Bronze + Silver + Gold of several badges at once. That's fun and fine, but it means tier items shouldn't be the very last progression items.

## 4. What was decided and built (2026-10-11)

- **Seed Length is the backbone** (Brian: "like an order of fries", sized in hours). Short ~3 h (default, 30 checks) / Medium ~8 h (49) / Long ~20 h (87) / Marathon 100+ h (114). Each location row in `locations.py` carries the **shortest length that includes it**; the per-badge `lengths` tuples are where retuning happens.
- **Difficulty tags in the location table** (E/M/H/X).
- **H and X locations, plus the luck elites (Annihilator, Superstar), are `EXCLUDED`** (filler only). This fixes the "Quest Mode on High Voltage Bronze" problem seen in the first default seed. Short and Medium contain no H/X checks at all.
- **Early game widened:** relic 1 needs no Relic Key, levels 2–5 always count, and the starting mode is Classic or Quest only (a Zen start opened just 2 checks, Lightning 3). Every length/goal/start opens at least 7 non-filler checks at the start; a test enforces it.
- **Progression share** with defaults (Short, Shard Hunt): 13 of 30 = 43%. The test threshold is 25%. Levelord / Heroes Welcome goals on Long/Marathon drop to 14–17% (no shards), which is acceptable because those goals are opt-in and long.

| Length | Checks | Progression (Shard Hunt) | Filler-only (H/X/luck) | Open at start (Classic) |
|---|---|---|---|---|
| Short | 30 | 13 | 0 | 7 |
| Medium | 49 | 20 | 3 | 9 |
| Long | 87 | 30 | 23 | 9 |
| Marathon | 114 | 36 | 50 | 9 |

### Time budget behind each length (estimates — calibrate with a stopwatch playtest)

- **Short (~3 h):**
  - Classic to level 5 (~20 min; also unlocks Poker in game).
  - Relics 1–2 (16 quests at about 5 min each, plus retries: ~1.5 h).
  - Quick Bronzes, which mostly overlap other play: Blaster, Inferno, Bejeweler 50k, Final Frenzy 20k, Ante Up 100k, The Gambler 10, Diamond Mine 100k, Relic Hunter 5, Butterfly Monarch 100k, Butterfly Bonanza 4.
  - One game each of Poker, Diamond Mine and Butterflies.
- **Medium (~8 h):** + levels 6–8 (one long Classic game), relic 3 (~1 h), the slow Bronzes (Stellar and Chromatic at 25 each: hours of overlapping play), Silvers for Inferno 400, Blaster 40, Final Frenzy 30k and The Gambler 30.
- **Long (~20 h):** + relics 4–5 (~3 h, harder), Ice Storm, every Silver (several 300k one-game scores and 150 Hypercubes/Star Gems), reachable Golds, Heroes Welcome, Levelord.
- **Marathon (100+ h):** + every Gold and Platinum (3,400 Flame Gems, 1,300 Hypercubes, 750k scores), Top Secret.

## 5. Playtest data log

| Date | Who | Observation |
|---|---|---|
| 2026-10-11 | Brian, profile AP1PROBE | Blaster Silver (≥40 gems in one move) in the first Zen session (~30 min); **Gold (50)** during the next quest session. → Blaster B/S are E, Gold is M. |
| 2026-10-11 | Brian | Relic 1 restored after 4 quests in roughly 30–40 min total including Zen play; Diamond Mine unlocked. |
| 2026-10-10 | Brian | Classic level 2 reached within a few minutes; level 4 in a later session (game mode not recorded). |
