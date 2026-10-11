"""
The "Bejeweled 3" guide shown in the client: goal progress, what to do next, banked checks and what's still locked.
Pure functions over a Tracker (no I/O), so the guide is unit-tested like the rest of the client logic.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from .locations import (
    BUTTERFLIES,
    DIAMOND_MINE,
    EASY,
    EXPERT,
    HARD,
    ICE_STORM,
    MEDIUM,
    POKER,
    QUEST_NAMES,
    QUESTS_PER_RELIC,
    LocationData,
)
from .tracker import GOAL_HEROES_WELCOME, GOAL_LEVELORD, GOAL_SHARD_HUNT, LOCATIONS_BY_ID, Tracker

# Badge requirements, from the game's own thresholds (properties\badges.txt). {n} is the tier's threshold.
BADGE_THRESHOLDS: dict[int, tuple[int, ...]] = {
    0: (50, 400, 1400, 3400), 1: (25, 150, 550, 1300), 2: (25, 150, 550, 1300), 3: (30, 40, 50, 60),
    4: (50_000, 150_000, 300_000, 500_000), 5: (20_000, 30_000, 40_000, 60_000),
    6: (100_000, 300_000, 500_000, 750_000), 7: (100_000, 300_000, 500_000, 750_000), 8: (10, 30, 60, 100),
    9: (100_000, 300_000, 500_000, 750_000), 10: (5, 8, 12, 15), 11: (100_000, 300_000, 500_000, 750_000),
    12: (5, 8, 12, 15), 13: (100_000, 300_000, 500_000, 750_000), 14: (4, 6, 8, 10),
}
BADGE_TEXT: dict[int, str] = {
    0: "clear {n:,} Flame Gems (total, any mode)",
    1: "clear {n:,} Star Gems (total, any mode)",
    2: "clear {n:,} Hypercubes (total, any mode)",
    3: "destroy {n} gems in one move (any mode)",
    4: "finish a Classic game with {n:,} points",
    5: "score {n:,} during a Lightning game's Last Hurrah",
    6: "score {n:,} in one Lightning game",
    7: "score {n:,} in one Poker game",
    8: "get {n} Flushes in Poker (total)",
    9: "score {n:,} in one Ice Storm game",
    10: "get a x{n} column combo in Ice Storm",
    11: "score {n:,} in one Diamond Mine game",
    12: "collect {n} artifacts in one Diamond Mine game",
    13: "score {n:,} in one Butterflies game",
    14: "collect {n} butterflies in one move",
    15: "complete Quest mode",
    16: "swap two Hypercubes together (any mode)",
    17: "line up 6 gems in a row (any mode)",
    18: "reach level 10 in one Classic game",
    19: "score 300,000 in each secret mode",
}
# The game's own unlock for each secret mode (the Archipelago item is needed as well).
IN_GAME_UNLOCK = {
    POKER: "reach level 5 in Classic",
    BUTTERFLIES: "reach level 5 in Zen",
    DIAMOND_MINE: "finish 4 quests of relic 1",
    ICE_STORM: "score 100,000 in one Lightning game",
}
RATING_ORDER = {EASY: 0, MEDIUM: 1, HARD: 2, EXPERT: 3}
QUESTS_TO_RESTORE_RELIC = 4


@dataclass(frozen=True)
class Line:
    style: str  # "title" | "heading" | "item" | "note"
    text: str


def requirement(data: LocationData) -> str:
    if data.kind == "level":
        return f"reach level {data.level} in one Classic game"
    if data.kind == "quest":
        return f"complete the {QUEST_NAMES[data.quest_index]} quest"
    assert data.badge is not None
    template = BADGE_TEXT[data.badge.badge_id]
    if data.badge.elite:
        return template
    return template.format(n=BADGE_THRESHOLDS[data.badge.badge_id][data.tier - 1])


def build_guide(tracker: Tracker, checked: Iterable[int]) -> list[Line]:
    done = set(checked)
    lines: list[Line] = [Line("title", _goal_text(tracker)),
                         Line("note", f"Checks sent: {len(done & tracker.slot_locations)} of "
                                      f"{len(tracker.slot_locations)}")]
    paused = tracker.paused_reason
    if paused is not None:
        lines.append(Line("note", f"Paused: {paused}."))
        return lines

    available: list[LocationData] = []
    banked: list[tuple[LocationData, str]] = []
    locked: dict[str, list[LocationData]] = defaultdict(list)
    for location_id in sorted(tracker.slot_locations - done):
        data = LOCATIONS_BY_ID.get(location_id)
        if data is None:
            continue
        missing = tracker.missing_item(data)
        if tracker.stable is not None and tracker.baseline is not None and tracker.achieved(data):
            if missing is not None:
                banked.append((data, missing))
            continue
        if missing is None:
            available.append(data)
        else:
            locked[missing].append(data)

    lines.append(Line("heading", "Do next"))
    lines += _do_next(tracker, available) or [Line("note", "Nothing open right now: you're waiting on items "
                                                           "(see below).")]
    if banked:
        lines.append(Line("heading", "Banked (sends when the item arrives)"))
        lines += [Line("item", f"{data.name}: waiting for {missing}") for data, missing in banked]
    if locked:
        lines.append(Line("heading", "Waiting on items"))
        for item, waiting in sorted(locked.items(), key=lambda pair: -len(pair[1])):
            hint_name = item.split(" (")[0]
            lines.append(Line("item", f"{item}: {len(waiting)} check{'s' if len(waiting) != 1 else ''}"
                                      f"   (type !hint {hint_name} to find it)"))
    return lines


def _goal_text(tracker: Tracker) -> str:
    if tracker.goal == GOAL_SHARD_HUNT:
        return f"Goal: collect Jewel Shards ({tracker.received['Jewel Shard']}/{tracker.shard_required})"
    if tracker.goal == GOAL_LEVELORD:
        return "Goal: reach level 10 in one Classic game (Levelord)"
    if tracker.goal == GOAL_HEROES_WELCOME:
        return "Goal: complete Quest mode (Heroes Welcome)"
    return "Goal: unknown"


def _do_next(tracker: Tracker, available: list[LocationData]) -> list[Line]:
    lines: list[Line] = []
    non_quests = sorted((d for d in available if d.kind != "quest"),
                        key=lambda d: (d.filler_only, RATING_ORDER[d.rating], d.kind != "level", d.address))
    for data in non_quests:
        note = " (bonus: never blocks anyone)" if data.filler_only else ""
        lines.append(Line("item", f"{data.name}: {requirement(data)}{note}"))
        if data.region in IN_GAME_UNLOCK:
            lines.append(Line("note", f"    {data.region} also needs the game's own unlock: "
                                      f"{IN_GAME_UNLOCK[data.region]}."))
    quests_by_relic: dict[int, list[LocationData]] = defaultdict(list)
    for data in available:
        if data.kind == "quest":
            quests_by_relic[data.relic].append(data)
    for relic, quests in sorted(quests_by_relic.items()):
        names = ", ".join(QUEST_NAMES[d.quest_index] for d in quests)
        lines.append(Line("item", f"Relic {relic} quests ({len(quests)} open): {names}"))
        if relic > 1 and tracker.stable is not None:
            first = (relic - 2) * QUESTS_PER_RELIC
            done_previous = sum(tracker.stable.quests[first:first + QUESTS_PER_RELIC])
            if done_previous < QUESTS_TO_RESTORE_RELIC:
                lines.append(Line("note", f"    Relic {relic} opens in game after {QUESTS_TO_RESTORE_RELIC} quests "
                                          f"of relic {relic - 1} (you have {done_previous})."))
    return lines


def render_plain(lines: list[Line]) -> str:
    out = []
    for line in lines:
        if line.style == "heading":
            out.append(f"\n== {line.text} ==")
        elif line.style == "item":
            out.append(f"  - {line.text}")
        else:
            out.append(line.text if line.style == "title" else f"  {line.text}")
    return "\n".join(out)


def render_markup(lines: list[Line]) -> str:
    """Kivy markup for the client tab."""
    from kivy.utils import escape_markup
    out = []
    for line in lines:
        text = escape_markup(line.text)
        if line.style == "title":
            out.append(f"[size=20sp][b]{text}[/b][/size]")
        elif line.style == "heading":
            out.append(f"\n[b]{text}[/b]")
        elif line.style == "item":
            out.append(f"  •  {text}")
        else:
            out.append(f"[i]{text}[/i]")
    return "\n".join(out)

