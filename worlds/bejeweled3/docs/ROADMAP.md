# Bejeweled 3 APWorld — Roadmap

v1 ships narrow (SPEC §6.5). Everything below is **not implemented in Phases 1–3**. It is collected here so the v1 design leaves room for it: ID blocks have gaps, and options are grouped.

## v1.1 — veteran options (from `CHECKIN_phase0.md` §5.4)

- **Per-tier badge inclusion:** choose which tiers (Bronze/Silver/Gold/Platinum) become locations, per badge or globally, instead of only `include_platinum_badges`.
- **Per-badge pool:** include or exclude individual badges (e.g. drop Butterfly Bonanza, keep Inferno).
- **Per-mode location toggles:** remove all locations tied to a mode (e.g. no Poker checks at all).
- **Goal variety:**
  - restore all relics;
  - earn N badges (any tier) / N badge tiers;
  - Top Secret;
  - reach a score in every mode;
  - combinations ("any K of these goals").
- **Level-check range:** configurable Classic levels up to 10 (and possibly Zen), independent of `include_skill_gates`.
- **Score-threshold checks:** optional per-mode score milestones (e.g. 25k/50k/100k/250k in Lightning), live-only like levels.

## Later / ideas

- Traps (SPEC Phase 4): Score Reset, Time Drain — need memory writes; opt-in only.
- Hard mode lock (SPEC Phase 4): needs unlock flags or forced return to menu.
- DeathLink (board game-over → send; receive → end the current board). Needs game-over detection (Phase 0 item 7, currently a stretch note).
- Other builds: EA app / retail `popcapgame1.exe` — separate `memory_map.py` version keys.
- Lifetime-stat checks (Flame/Star Gems cleared, etc.) from the Profile stat block.
