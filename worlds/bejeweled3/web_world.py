from typing import ClassVar

from BaseClasses import Tutorial
from worlds.AutoWorld import WebWorld

from .options import option_groups


class Bejeweled3WebWorld(WebWorld):
    game = "Bejeweled 3"
    theme = "partyTime"
    setup_en = Tutorial(
        "Multiworld Setup Guide",
        "A guide to setting up Bejeweled 3 for Archipelago.",
        "English",
        "setup_en.md",
        "setup/en",
        ["BrianErlich"],
    )
    tutorials: ClassVar[list[Tutorial]] = [setup_en]
    option_groups = option_groups
