#!/usr/bin/env python3
"""channels.py — single source of truth for Discord channel name -> ID.

Imported by digest.py, grab_poller.py, and any new module that posts to Discord.
The PLAN mandates that channel IDs must NOT be triplicated across files.

If a channel here doesn't exist on the server, posting to it is a 404 —
add new IDs to the bottom of CHANNELS and keep imports working.
"""
CHANNELS = {
    # Project topic channels (per drone-mrac.md routing map)
    "research-planning": "1479106009384620116",
    "literature":        "1479106224157888754",
    "coursework":        "1479106309365432320",   # D4 weekly learning digest target
    "stm32-firmware":    "1479106472133787689",
    "simulation":        "1479106512596111513",
    "computer-vision":   "1479106569072283860",
    "control-laws":      "1479106625485672478",
    "ros-integration":   "1479106678459863172",
    # Roll-up / meta
    "briefing":          "1479107278538805320",   # daily digest header + crash reports
    "general":           "1479107691216371802",
    "inspiration":       "1522565862622629888",
    # D3: China drone industry feed
    "china-drone-robotics-industry": "1522959199611650159",
}

# Convenience: channel IDs for any caller that wants to enumerate them
WATCH_IDS = list(CHANNELS.values())

# Roll-up / crash target (no need to import digest's BRIEFING_CHANNEL)
BRIEFING_ID = CHANNELS["briefing"]


def id_for(name):
    """Look up a channel ID by name, or return None if unknown."""
    return CHANNELS.get(name)


def name_for(cid):
    """Reverse lookup; returns the first matching name or None."""
    for n, v in CHANNELS.items():
        if v == cid:
            return n
    return None
