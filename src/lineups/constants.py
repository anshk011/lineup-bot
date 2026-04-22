"""
Static data for lineup bot — agents, maps, sides, types.
Used to build inline keyboard buttons.
"""

AGENTS: list[str] = [
    "Astra", "Breach", "Brimstone", "Chamber", "Clove",
    "Cypher", "Deadlock", "Fade", "Gekko", "Harbor",
    "KAYO", "Killjoy", "Neon", "Omen", "Phoenix",
    "Raze", "Sage", "Skye", "Sova", "Tejo",
    "Viper", "Vyse", "Yoru",
]

MAPS: list[str] = [
    "Abyss", "Ascent", "Bind", "Breeze", "Corrode",
    "Fracture", "Haven", "Icebox", "Lotus", "Pearl",
    "Split", "Sunset",
]

SIDES: list[str] = ["Attack", "Defense", "Any"]

LINEUP_TYPES: list[str] = ["Lineup", "Setup", "All"]

# How many lineup results to show per page in Telegram
PAGE_SIZE = 5
