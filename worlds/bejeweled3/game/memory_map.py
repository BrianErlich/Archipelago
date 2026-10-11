"""
ALL game-specific addresses and offsets for the Bejeweled 3 client, keyed by exe FileVersion.
Every value here is verified; see docs/memory_map.md for how. Unknown exe versions are refused (SPEC §7).

Chain notation: addr = module_base + rva; then for each offset: addr = read_u32(addr) + offset.
"""
from __future__ import annotations

from dataclasses import dataclass

PRODUCT_NAME = "Bejeweled 3"  # identify the game by this, never by process name (Peggle is also popcapgame1.exe)


@dataclass(frozen=True)
class MemoryMap:
    build: str
    exe_name: str
    app_ptr_rva: int  # global Bej3App*                                  verified: RTTI .?AVBej3App@Sexy@@
    app_class: str
    profile_offset: int  # Bej3App -> Profile*                              verified: RTTI .?AVProfile@Sexy@@
    profile_class: str
    profile_name: int  # Profile + : std::wstring (MSVC x86)               verified across a switch + restart
    badge_tiers: int  # Profile + : u32[20], value = tier (2 Silver, 3 Gold verified)
    badge_count: int
    quests_done: int  # Profile + : u8[40], quest.cfg order              verified with quests 4..7
    quest_count: int
    board_offset: int  # Bej3App -> Board* (0 when no board)              verified (Classic + menu)
    board_score: int  # Board + : i32, live score                         verified (Classic, Diamond Mine)
    board_level: int  # Board + : i32, 0-based                            verified (Classic, Zen)
    # Every board class in the exe -> the mode it belongs to (None = ambiguous or unknown). Used for the
    # "you're in a locked mode" hint and for display. A board whose class isn't listed here is an unreadable tick.
    board_modes: dict[str, str | None]


STEAM_1_1_12_4196 = MemoryMap(
    build="Steam 1.1.12.4196",
    exe_name="Bejeweled3.exe",
    app_ptr_rva=0x4E170C,
    app_class=".?AVBej3App@Sexy@@",
    profile_offset=0xB80,
    profile_class=".?AVProfile@Sexy@@",
    profile_name=0x64,
    badge_tiers=0x1A0,
    badge_count=20,
    quests_done=0x158,
    quest_count=40,
    board_offset=0xBE8,
    board_score=0xC88,  # +0xD24 equals it in Classic/Zen/Lightning but lags until game end on DigBoard
    board_level=0xE04,
    board_modes={
        # Own board classes: one mode each.
        ".?AVClassicBoard@Sexy@@": "Classic",  # verified 2026-10-10
        ".?AVZenBoard@Sexy@@": "Zen",  # verified 2026-10-11
        ".?AVSpeedBoard@Sexy@@": "Lightning",  # verified 2026-10-11
        # Quest-only challenge types (quest.cfg); all derive from QuestBoard.
        ".?AVTimeLimitBoard@Sexy@@": "Quest",  # verified 2026-10-11 (Alchemy)
        ".?AVBalanceBoard@Sexy@@": "Quest",
        ".?AVFillerBoard@Sexy@@": "Quest",
        ".?AVMoveLimitBoard@Sexy@@": "Quest",
        ".?AVBadMoveLimitBoard@Sexy@@": "Quest",
        ".?AVNoLoseBoard@Sexy@@": "Quest",
        ".?AVTimeBombBoard@Sexy@@": "Quest",
        ".?AVRealTimeBombBoard@Sexy@@": "Quest",
        ".?AVQuestBoard@Sexy@@": "Quest",
        # Shared: secret.cfg defines each secret mode as a "quest" with the same challenge type as some quests,
        # so these boards are EITHER the secret mode OR a quest of that type (None until a marker is verified).
        ".?AVPokerBoard@Sexy@@": None,  # Poker, or quests Poker / Poker II / Poker III
        ".?AVButterflyBoard@Sexy@@": None,  # Butterflies, or the 4 Butterflies quests (seen in one, 2026-10-11)
        ".?AVInfernoBoard@Sexy@@": None,  # Ice Storm (challenge "Inferno"), or the 3 Ice Storm quests
        ".?AVDigBoard@Sexy@@": None,  # Diamond Mine (verified 2026-10-11), or the dig quests (Gold Rush, ...)
        ".?AVBoard@Sexy@@": None,
    },
)

MEMORY_MAPS: dict[str, MemoryMap] = {
    "1.1.12.4196": STEAM_1_1_12_4196,
}
