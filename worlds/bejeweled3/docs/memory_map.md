# Bejeweled 3 — memory & save-data map

Source of truth for every address, offset, enum and file format the client uses.
Anything not marked **VERIFIED** must not be relied on; code using it must fail safe.

Chain notation: `RVA,OFF1,OFF2,…:TYPE` (hex). `addr = module_base + RVA`; for each `OFF`: `addr = read_u32(addr) + OFF`; then read `TYPE` at `addr`.

## Target build

| Property | Value | How established | Status |
|---|---|---|---|
| Store | Steam, app 78000, depot build id 591 | `appmanifest_78000.acf` | VERIFIED |
| Install dir | `C:\SteamInstall2025\steamapps\common\Bejeweled 3\` | filesystem | VERIFIED (Brian's PC) |
| Main exe / process name | `Bejeweled3.exe` (no `popcapgame1.exe` wrapper; `steam_api.dll` alongside) | filesystem, PDB path `c:\p4_managed\Bej3\steam_adapt_engineer\...` in exe | VERIFIED (static) — confirm running name with `bj3_probe.py info` |
| FileVersion | `1.1.12.4196` | PE version resource | VERIFIED (static) |
| Architecture | x86 (PE machine 0x14C) | PE header | VERIFIED |
| ASLR | **off** — `DllCharacteristics = 0x8000` (no DYNAMIC_BASE), preferred base `0x400000` | PE header | VERIFIED (static). Client still computes `module_base + RVA`. |
| Sections (RVA) | `.text 0x1000–0x3BE575`, `.rdata 0x3BF000–0x4BC40A`, `.data 0x4BD000–0x92B1DC` (RW), `.rsrc 0x92C000–…` | PE section table | VERIFIED (static) |
| RTTI | MSVC RTTI present (`.?AV…@Sexy@@` type descriptors) | strings | VERIFIED (static). Lets the probe/client name any object's class from its vtable. |

**Process-name hazard:** other PopCap games also run as `popcapgame1.exe` (Peggle Deluxe was running as `C:\ProgramData\PopCap Games\Peggle\popcapgame1.exe` on Brian's PC on 2026-10-10). The client must identify the game by the exe's **ProductName = "Bejeweled 3"** (and/or path), never by process name alone. `bj3_probe.py` already does this.

## Prior art: redstone59 chains — NOT applicable to Steam build

redstone59 reads `popcapgame1.exe` at absolute `0x887F34` (RVA `0x487F34`) → `+0xBE0` board → `+0x0` type / `+0xD20` score / `+0xE04` level / `+0x322C` quest id.
On Steam 1.1.12.4196, RVA `0x487F34` falls inside **`.rdata` (read-only constants)**, so it cannot hold a live game-object pointer. Treat the whole chain as **from a different executable**. The *offsets* (`+0xBE0`, `+0xD20`, `+0xE04`) may still be informative if the classes are the same — check once the board object is found.

Note: their "board type at `+0x0`" is the object's **vtable pointer**, i.e. the board's C++ class — consistent with the RTTI approach below.

## Values to establish

| # | Value | Pointer path / file field | Type | Verified on build | How verified | Status |
|---|---|---|---|---|---|---|
| 1 | Current board / mode (incl. "no board / menu") | `4E170C,BE8,0:vtable` → RTTI class name. Board pointer `4E170C,BE8:u32` = **0 in main menu** | vtable | 1.1.12.4196 | `objtree`: Bej3App+0xBE8 → `ClassicBoard` in Classic; `walk`: 0 at main menu | VERIFIED for Classic + menu; other modes UNVERIFIED |
| 0a | App object (`Sexy::Bej3App`) | `4E170C,0` (also `4E1728`, `4E1730`, `4E1B44`) | ptr | 1.1.12.4196 | `walk`: RTTI = `.?AVBej3App@Sexy@@`, same object from 4 globals, survived restart | VERIFIED (once) |
| 0b | Live profile (`Sexy::Profile`) | `4E170C,B80,0` (Bej3App+0xB80) | ptr | 1.1.12.4196 | `walk`: RTTI = `.?AVProfile@Sexy@@` | VERIFIED (once) |
| 0c | Profile lifetime points? | `4E170C,B80,C4` (Profile+0xC4) | i32 | 1.1.12.4196 | 850 after game 1; 1300 with 450 on screen in game 2 (850+450). Same number as `profile.dat`@0x10 | LIKELY — is NOT the current score |
| 2a | Current score | **`4E170C,BE8,D24`** (also `+C88`, identical). `+D64` = displayed score (counts up after a match) | i32 | 1.1.12.4196 | `fields --value` at 1200/1730; `watch` 1730→2430: C88/D24 jump instantly, D64 animates | VERIFIED (Classic) |
| 2b | Classic level (0-based) | **`4E170C,BE8,E04`** | i32 | 1.1.12.4196 | `watch`: 0 → 1 on the level 1→2 transition (same offset as redstone). `+E08`=3, `+E0C`=1 constant | VERIFIED (Classic, one level-up). Zen UNVERIFIED |
| 7a | Left the board | board pointer `4E170C,BE8` becomes 0 → every board chain read fails | — | 1.1.12.4196 | `watch` showed `??` the moment Brian quit to menu | VERIFIED |
| 3 | Badge state (persistent) | **memory:** `4E170C,B80,1A0+4*id` (Profile+0x1A0, u32[20]). **file:** `profile.dat` 0xB8+4*id (u32[20]). Value = highest tier earned: 0 none, 2 = Silver (observed), so presumably 1 Bronze, 3 Gold, 4 Platinum. Elite badges: presumably 0/1 — UNVERIFIED | u32 | 1.1.12.4196 | Brian earned Blaster (id 3) in Zen: Profile+0x1AC 0→2, other 19 slots stayed 0; after quitting, file 0xC4 = 2; after a relaunch, memory = 2 again; tooltip then asked for **Gold**, so 2 = Silver (Silver earned directly; tiers can be skipped) | **VERIFIED** (memory + file, Silver). Bronze/Gold/Platinum/elite values inferred |
| 4 | Quest progress (40 quests, persistent) | **memory:** `4E170C,B80,158+k` (Profile+0x158, u8[40]). **file:** `profile.dat` 0x118+k (u8[40]). k = 0-based index in `properties\quest.cfg` order (see quest table); 1 = completed | u8 | 1.1.12.4196 | Brian completed Avalanche (k=5) and Buried Treasure (k=6) → memory +0x15D/+0x15E and file 0x11D/0x11E went 0→1, nothing else in the array changed; the game wrote the file mid-session | **VERIFIED** (2 data points, both adjacent — a 3rd non-adjacent quest would make it airtight) |
| 4b | Second quest array (meaning unknown: "unlocked/seen"?) | Profile+0x2AC+k; file after the variable strings (0x1AF+k on this profile) | u8 | 1.1.12.4196 | same two bytes flipped at the same time | UNKNOWN — not needed |
| 5 | Active profile | **memory:** `4E170C,B80,64:wstr` (Profile+0x64, MSVC `std::wstring`; layout = buffer/ptr, size @+0x10, cap @+0x14 — layout assumed from MSVC, confirm). **File:** first name in `users.dat` = last *written* profile, but the file is NOT rewritten on a profile switch | wstr | 1.1.12.4196 | `fields --text`: Profile+0x64 → UTF-16 "AP1PROBE". 2026-10-11 (fresh launch, new heap addresses): read 'AP2PROBE' while AP2PROBE active; switched in game → 'AP1PROBE'. The Profile object is reused (same address) and reloaded in place on a switch. users.dat was rewritten on one switch but not on another | memory: **VERIFIED**; file: not a reliable live signal |
| 6 | Secret-mode unlock flags | profile file? | — | — | — | UNVERIFIED (stretch only) |
| 7 | Game-over / restart detection | board vtable change, score reset? | — | — | — | UNVERIFIED |
| 8a | Lightning timer | — | — | — | — | UNVERIFIED (stretch only) |
| 8b | Score write | same address as 2a | — | — | — | UNVERIFIED (stretch only; never written in Phases 0–3) |

## Save / profile data

**Location — VERIFIED (2026-10-10, Steam 1.1.12.4196):** `%LOCALAPPDATA%\Steam\Bejeweled3\users\`
(`C:\Users\shall\AppData\Local\Steam\Bejeweled3\users\`). Not ProgramData, unlike Peggle.

```
users\users.dat                 profile list (64 bytes with one profile)
users\<PROFILE NAME>\profile.dat   per-profile stats (432 bytes for a fresh profile)
users\<PROFILE NAME>\classic.sav   saved in-progress Classic game (12 KB)
```

`users.dat` (one profile `AP1PROBE`), all little-endian:

| Offset | Bytes | Meaning | Status |
|---|---|---|---|
| 0x00 | `F5 EE 1B 39` | magic (same as profile.dat) | VERIFIED (observed) |
| 0x04 | u16 = 8 | ? (format version?) | UNVERIFIED |
| 0x06 | u16 len + chars | profile name `AP1PROBE` | VERIFIED |
| 0x26 | u32 = 0x6ACA7873 | unix time 2026-10-10 12:40 — created? | UNVERIFIED |
| 0x2E | u32 = 0x6ACB141B | unix time 2026-10-10 23:44 — last played | UNVERIFIED |
| 0x36 | u16 len + chars | `AP1PROBE` again — **probably the active/last-used profile** | UNVERIFIED — confirm with a 2nd profile |

`profile.dat`: magic `F5EE1B39`, then u32 `0x47` (version?), then a run of u32 fields — mostly **cumulative stats**. 432 bytes for both a fresh and a played profile (fixed layout).

| Offset | Observed (AP1: s1 → s2 → s3) | Meaning | Status |
|---|---|---|---|
| 0x10 | 850 → 2580 → 3280 | lifetime points (mirrors in-memory Profile+0xC4) | LIKELY |
| 0x0C, 0x1C–0x5C, 0x74, 0x78 | monotonic increases | other lifetime counters (moves, gems by colour, specials…) | unidentified, not needed |
| 0x70 | 0 → 100 on AP2 (fresh) only | ? | unknown |
| 0x10C | bitfield `0x20000800` → `0x28000800` | flags (tutorial/hints seen?) — bit 27 set during session 2 | unknown |

**Layout relation to memory:** file 0x0C…0x93 = Profile object +0xC0…+0x147 (delta 0xB4); file 0xB8…0x107 (badge tiers) = Profile +0x1A0…+0x1EF (delta 0xE8). Variable-length strings follow from ~0x174 (Zen ambience / binaural / affirmation file names, e.g. `Coastal.ogg`), so offsets after them shift. Parse only the fixed prefix.

**When is profile.dat written?** NOT immediately when a badge is earned. Observed writes: profile creation, some profile switches, during play (00:39:08, before the badge registered), and **on quitting the game** (00:41:19, contained the badge). → The client reads **live memory** while the game runs and uses the file only for "earned while the client was closed".

Reaching Classic level 2 (s2 → s3) changed only counters — **no "best level" field found**; the in-progress game (incl. level) lives in `classic.sav` while a Classic game is suspended. No badge earned yet → badge fields not located.

Previously hypothesised from exe strings (kept for reference):

| Clue (exe string) | Interpretation |
|---|---|
| `userdata/users.dat`, `userdata/user%d/`, `userdata` | Steam-style layout: one profile list + one folder per profile |
| `users\users.dat`, `users\_temp`, `\profile.dat`, `users\hiscores.dat` | Classic PopCap layout: `users\users.dat` + `users\<id>\profile.dat`, high scores separate |
| `PopCap\Bejeweled3`, `PopCap Games`, `Bejeweled3` | Base folder name candidates |
| Classes `Profile`, `FilesystemProfileDriver`, `FilesystemSaveGameDriver` | Profile saved to plain files (format unknown) |

Strong precedent: Steam **Peggle** on the same PC saves to `C:\ProgramData\Steam\Peggle\userdata\users.dat`. Expected for BJ3: `C:\ProgramData\Steam\Bejeweled3\userdata\` — **to confirm after first launch** (`bj3_probe.py files`).

## RTTI classes of interest (from exe, VERIFIED to exist as types; mapping to modes is UNVERIFIED)

Board classes — `Board` (base), `ClassicBoard`, `ZenBoard`, `SpeedBoard`, `PokerBoard`, `ButterflyBoard`, `DigBoard`, `InfernoBoard`, `QuestBoard`, and quest-variant boards `BadMoveLimitBoard`, `BalanceBoard`, `FillerBoard`, `MoveLimitBoard`, `NoLoseBoard`, `RealTimeBombBoard`, `TimeBombBoard`, `TimeLimitBoard`.
Likely (unverified) mode mapping: Lightning ↔ `SpeedBoard`, Diamond Mine ↔ `DigBoard`, Ice Storm ↔ `InfernoBoard`? (Ice Storm's internal name is unknown — verify).

Badge classes — `Badge` (base), `SingleStateBadge`, `ClassicLevelBadge`, `ClassicScoreBadge`, `LightningScoreBadge`, `PokerScoreBadge`, `PokerFlushesBadge`, `ButterfliesScoreBadge`, `ButterfliesBigMoveBadge`, `IceStormScoreBadge`, `IceStormColComboBadge`, `DiamondMineScoreBadge`, `DiamondMineArtifactsBadge`, `BlasterBadge`, `ChromaticBadge`, `HypercubeAnnihilationBadge`, `FinalFrenzyBadge`, `InfernoBadge`, `StellarBadge`, `SupernovaBadge`, `SecretHighScoreBadge`, `QuestModeFinishedBadge`.
This is the authoritative list of badge *types* in this build; display names, tiers and thresholds still need verification in game.

Other: `Bej3App` (application object — likely root of all pointer chains), `Profile`, `QuestMenu`, `QuestGoal`, `QuestDataParser`, `RecordsScreen`, `StatsTab`, `BadgesTab`, `HighScoresTab`.
Data files referenced: `properties\quest.cfg`, `properties\defaultquest.cfg`, `properties\secret.cfg`, `properties\speed.cfg` (not on disk — probably inside `main.pak`).

## Badge table (VERIFIED 2026-10-11: id from each badge object's +4, names/requirements from in-game tooltips; the Badges screen lists them in id order)

| id | Class | In-game name | Bronze requirement (tooltip) | Other tiers seen |
|---|---|---|---|---|
| 0 | InfernoBadge | Inferno | Clear 50 Flame Gems | |
| 1 | StellarBadge | Stellar | Clear 25 Star Gems | |
| 2 | ChromaticBadge | Chromatic | Clear 25 Hypercubes | |
| 3 | BlasterBadge | Blaster | Destroy 30 gems in a single move | Silver 40, Gold 50 (tier value 3 observed after Brian hit 50) |
| 4 | ClassicScoreBadge | Bejeweler | Finish a Classic game with over 50,000 | |
| 5 | FinalFrenzyBadge | Final Frenzy | Over 20,000 during a Last Hurrah in Lightning | |
| 6 | LightningScoreBadge | High Voltage | 100,000 in Lightning | |
| 7 | PokerScoreBadge | Ante Up | 100,000 in Poker | |
| 8 | PokerFlushesBadge | The Gambler | 10 Flushes in Poker | |
| 9 | IceStormScoreBadge | Glacial Explorer | 100,000 in Ice Storm | |
| 10 | IceStormColComboBadge | Ice Breaker | x5 Column Combo in Ice Storm | |
| 11 | DiamondMineScoreBadge | Diamond, Mine | 100,000 in Diamond Mine | |
| 12 | DiamondMineArtifactsBadge | Relic Hunter | Collect 5 artifacts in Diamond Mine | |
| 13 | ButterfliesScoreBadge | Butterfly Monarch | 100,000 in Butterflies | |
| 14 | ButterfliesBigMoveBadge | Butterfly Bonanza | Collect 4 butterflies in one move | |
| 15 | QuestModeFinishedBadge | Heroes Welcome (elite) | Complete Quest Mode | |
| 16 | HypercubeAnnihilationBadge | Annihilator (elite) | Match two Hypercubes together | |
| 17 | SupernovaBadge | Superstar (elite) | Line up 6 gems in a row | |
| 18 | ClassicLevelBadge | Levelord (elite) | Reach level 10 in Classic | |
| 19 | SecretHighScoreBadge | Top Secret (elite) | 300,000 in all four secret games (progress shown 0/4) | |

**All tier thresholds come from the game data:** `properties\badges.txt` in `main.pak`, format `Name:B/S/G/P`; elite badges have one value. The full table with difficulty ratings is in `docs/BALANCE.md`. Tier values: **2 = Silver, 3 = Gold verified** (Blaster 0→2→3); 1 = Bronze and 4 = Platinum inferred.

Notes vs. SPEC §2: there is **no Zen badge**; Classic's score badge is 50k for bronze (not 100k); 15 common + 5 elite = 20 (spec said ~15 + 4). Higher-tier thresholds are only visible once the previous tier is held.

Badge objects in memory (20, found by vtable; vtables are static in `.rdata`, e.g. BlasterBadge `0x863FC8`) hold definitions only (+4 id, +0x1C → `SteamAchievements`) — their bytes did not change when Blaster was earned.

## Quest table (from `properties\quest.cfg` inside `main.pak`; PopCap pak = XOR 0xF7, magic 0xBAC04AC0)

40 quests in 5 sections ("relics") of 8. On screen each relic shows 8 quests and needs **4** completed to restore it (relic 1 showed 2/4 drops after 2 quests).

| Relic | k = 0…7 / 8…15 / … |
|---|---|
| 1 (k 0–7) | Butterflies, Gold Rush, Alchemy, Stratamax, Balance, Avalanche, Buried Treasure, Time Bomb |
| 2 (k 8–15) | Poker, Ice Storm, Stratamax II, Sandstorm, Butterflies II, Balance II, Time Bomb II, Avalanche II |
| 3 (k 16–23) | Alchemy II, Wall Blast, Poker II, Butterflies III, Avalanche III, Gold Rush II, Stratamax III, Time Bomb III |
| 4 (k 24–31) | Gold Rush III, Butterflies IV, Alchemy III, Avalanche IV, Ice Storm II, Time Bomb IV, Balance III, Stratamax IV |
| 5 (k 32–39) | Balance IV, Sandstorm II, Stratamax V, Wall Blast II, Gold Rush IV, Poker III, Avalanche V, Ice Storm III |

**Blocking check (Phase 1), 2026-10-11:**
- Brian completed Avalanche, Buried Treasure, Balance and Time Bomb. The quest array read `[4, 5, 6, 7]`, matching `quest.cfg` order (k = 4…7), and the second array matched too.
- Relic 1 was restored and the game showed "New Mode Unlocked: Diamond Mine".
- **The 4 unused relic 1 quests are still playable after restoring** (Brian confirmed). → All 40 quest locations are reachable.
- Not yet observed: one of those leftover quests being completed and flipping its byte. Expected, since the array has a byte per quest; confirm in Phase 2.
- **Heroes Welcome trigger:** still unknown (20 vs 40 quests). `badges.txt` gives its threshold as just `1` ("complete Quest mode"). The client reads the badge slot itself (id 15), so this only affects logic/docs, not detection.

## Log

- 2026-10-10 — Static analysis of `Bejeweled3.exe` (Steam 1.1.12.4196): version, PE layout, ASLR off, redstone RVA in `.rdata`, RTTI classes, save-path strings. Probe written; tested on a throwaway 32-bit process and synthetic memory, not yet against the game.
- 2026-10-10 (evening, Brian running the probe) — score scan led to Profile (+0xC4 lifetime points); `objtree` found the board at Bej3App+0xBE8; score `+D24`, level `+E04` verified with `watch`; saves found in `%LOCALAPPDATA%`.
- 2026-10-11 (Claude via computer use + Brian playing) — active-profile name verified across a switch and a restart; badge table read from the game UI; Blaster Silver → badge array at Profile+0x1A0 / file 0xB8; quit forced a profile.dat write; Avalanche + Buried Treasure → quest array at Profile+0x158 / file 0x118; quest order extracted from main.pak.

## Phase 2 verification (2026-10-11, subagent via computer use + read-only probe, profile AP1PROBE)

| Mode / board | RTTI class | Score | Level `+E04` | Board pointer 0 after leaving |
|---|---|---|---|---|
| Classic | `ClassicBoard` | `+D24` = `+C88` = on-screen (6,890) | 1 at on-screen level 2 | yes |
| Zen | `ZenBoard` | `+D24` = on-screen (14,180…14,380) | **3 at on-screen level 4 → 0-based, same offset as Classic** | yes |
| Lightning | `SpeedBoard` | `+D24` = on-screen (1,500) | 0 | yes |
| Quest "Butterflies" (relic 1) | `ButterflyBoard` | 0; this quest shows no score | 0 | yes |
| Quest "Alchemy" (relic 1) | `TimeLimitBoard` | 0 ("0 of 64" on screen) | 0 | yes |
| Diamond Mine | `DigBoard` | **`+D24` stays 0 during play** and is only set at TIME UP. The live score $4,000 was at `+C88`, `+CE8` and `+E00` | 0 | yes |

- **Score offset changed to `+C88`.** It equals the instant score in Classic (verified 2026-10-10) and is live in Diamond Mine. It's assumed for Zen and Lightning, where `+D24` was checked instead. Score is only used for the board-session guard and `/bj3 status`.
- Quest boards use mode-style classes (`ButterflyBoard`, `TimeLimitBoard`), not one `QuestBoard`, so a board class doesn't identify the mode uniquely. That's harmless: only `ClassicBoard` drives checks (levels).
- Poker, Butterflies and Ice Storm are still locked on AP1PROBE, so `PokerBoard`, the Butterflies mode board and `InfernoBoard` (Ice Storm?) remain unverified.
- **Profile name short-string path: still not exercised.** The new profile `AP3` (3 chars) read correctly, but its `std::wstring` reused AP1PROBE's heap buffer (capacity 15). The inline case (capacity 7) probably needs a game restart with a short-named profile active.
- **The Profile object is edited in place on a profile switch** (same address, `0B0CC150`), which confirms the 2026-10-11 note.
- **The Gambler's tooltip shows a counter `(0/10)`, so it's cumulative.** Relic Hunter has no counter and is probably per-game (one Diamond Mine game with 0 artifacts didn't change it).
