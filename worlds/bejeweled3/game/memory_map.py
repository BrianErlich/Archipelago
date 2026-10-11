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
    board_score: int  # Board + : i32                                     verified (Classic)
    board_level: int  # Board + : i32, 0-based                            verified (Classic)
    board_classes: frozenset[str]  # RTTI names accepted as a board; mode mapping verified in Phase 2


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
    board_score=0xD24,
    board_level=0xE04,
    # Only ClassicBoard has been observed; the others are RTTI classes present in the exe (UNVERIFIED mapping).
    board_classes=frozenset({
        ".?AVClassicBoard@Sexy@@", ".?AVZenBoard@Sexy@@", ".?AVSpeedBoard@Sexy@@", ".?AVQuestBoard@Sexy@@",
        ".?AVPokerBoard@Sexy@@", ".?AVButterflyBoard@Sexy@@", ".?AVInfernoBoard@Sexy@@", ".?AVDigBoard@Sexy@@",
    }),
)

MEMORY_MAPS: dict[str, MemoryMap] = {
    "1.1.12.4196": STEAM_1_1_12_4196,
}
