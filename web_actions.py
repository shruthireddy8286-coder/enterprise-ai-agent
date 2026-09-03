"""
web_actions.py

Local "open / redirect to a website" command support.

Handles two kinds of requests, both without ever calling the LLM:

1. Literal commands -- "open youtube", "go to github", "launch netflix".
2. Task-style requests -- "book a cab", "book bus tickets", "book a train",
   "play some games", "order food", "book a flight", "book movie tickets" --
   which get routed to a sensible real-world site for that task.

Everything here runs entirely on the user's own machine: it only ever
launches the OS's already-configured default browser via Python's built-in
`webbrowser` module, in direct response to the current user's own typed
message. Nothing is downloaded, installed, or executed on their behalf.
"""

from __future__ import annotations

import re
import webbrowser
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Direct "open <name>" shortcuts
# ---------------------------------------------------------------------------
KNOWN_SITES = {
    # everyday sites
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "github": "https://www.github.com",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "twitter": "https://www.twitter.com",
    "x": "https://www.x.com",
    "linkedin": "https://www.linkedin.com",
    "amazon": "https://www.amazon.com",
    "wikipedia": "https://www.wikipedia.org",
    "netflix": "https://www.netflix.com",
    "spotify": "https://open.spotify.com",
    "whatsapp": "https://web.whatsapp.com",
    "maps": "https://maps.google.com",
    "google maps": "https://maps.google.com",
    "chatgpt": "https://chat.openai.com",
    "claude": "https://claude.ai",
    "reddit": "https://www.reddit.com",
    "twitch": "https://www.twitch.tv",
    "outlook": "https://outlook.live.com",
    "drive": "https://drive.google.com",
    "google drive": "https://drive.google.com",
    "yahoo": "https://www.yahoo.com",
    "bing": "https://www.bing.com",
    "stackoverflow": "https://stackoverflow.com",
    "stack overflow": "https://stackoverflow.com",
    # transport / booking brands, so naming the brand directly also works
    "uber": "https://www.uber.com",
    "ola": "https://www.olacabs.com",
    "redbus": "https://www.redbus.in",
    "irctc": "https://www.irctc.co.in",
    "makemytrip": "https://www.makemytrip.com",
    "goibibo": "https://www.goibibo.com",
    "skyscanner": "https://www.skyscanner.net",
    "bookmyshow": "https://in.bookmyshow.com",
    "swiggy": "https://www.swiggy.com",
    "zomato": "https://www.zomato.com",
    "airbnb": "https://www.airbnb.com",
    "booking.com": "https://www.booking.com",
    "ixigo": "https://www.ixigo.com",
    # games
    "crazygames": "https://www.crazygames.com",
    "poki": "https://poki.com",
}

# ---------------------------------------------------------------------------
# Task-style intents: phrases matched anywhere in the sentence, routed to a
# sensible real-world site for that task. Checked in order; first match wins.
# ---------------------------------------------------------------------------
INTENT_ROUTES: List[Tuple[List[str], str, str]] = [
    (
        ["book a cab", "book cab", "need a cab", "book a taxi", "book taxi",
         "call a cab", "call a taxi", "book uber", "get an uber", "need a ride"],
        "https://www.uber.com",
        "Uber (cab booking)",
    ),
    (
        ["book bus", "bus ticket", "bus booking", "book a bus", "bus tickets"],
        "https://www.redbus.in",
        "RedBus (bus ticket booking)",
    ),
    (
        ["book train", "train ticket", "train booking", "book a train",
         "railway ticket", "training ticket", "training booking"],
        "https://www.irctc.co.in",
        "IRCTC (train ticket booking)",
    ),
    (
        ["book flight", "flight ticket", "flight booking", "book a flight",
         "book a plane ticket", "airline ticket"],
        "https://www.makemytrip.com",
        "MakeMyTrip (flight booking)",
    ),
    (
        ["book movie", "movie ticket", "movie booking", "book a movie",
         "cinema ticket"],
        "https://in.bookmyshow.com",
        "BookMyShow (movie ticket booking)",
    ),
    (
        ["order food", "food delivery", "order a meal", "get food delivered"],
        "https://www.swiggy.com",
        "Swiggy (food delivery)",
    ),
    (
        ["book a hotel", "hotel booking", "book hotel", "book a room"],
        "https://www.booking.com",
        "Booking.com (hotel booking)",
    ),
    (
        ["play a game", "play games", "play online game", "play some games",
         "open a game", "open games", "online games", "open online games"],
        "https://www.crazygames.com",
        "CrazyGames (free online games)",
    ),
]

OPEN_PATTERN = re.compile(
    r"^\s*(?:open|launch|go\s*to|start|show\s*me)\s+(.+?)\s*"
    r"(?:\s+website|\s+site|\s+app|\s+page)?\s*[\.!]?\s*$",
    re.IGNORECASE,
)


def _normalize_target(raw_target: str) -> str:
    return raw_target.strip().strip(".").lower()


def _build_url(target: str) -> str:
    if target in KNOWN_SITES:
        return KNOWN_SITES[target]
    if target.startswith("http://") or target.startswith("https://"):
        return target
    if "." in target and " " not in target:
        # Looks like it's already a domain, e.g. "example.com"
        return f"https://{target}"
    cleaned = target.replace(" ", "")
    return f"https://www.{cleaned}.com"


def _match_intent(text: str) -> Optional[Tuple[str, str]]:
    lowered = text.lower()
    for phrases, url, display_name in INTENT_ROUTES:
        for phrase in phrases:
            if phrase in lowered:
                return display_name, url
    return None


def parse_action_command(user_text: str) -> Optional[Tuple[str, str]]:
    """
    Returns (display_name, url) if `user_text` should trigger opening or
    redirecting to an external site -- either a literal "open <site>"
    command, or a task-style request like "book a cab" / "play some games".
    Returns None otherwise so the caller falls back to normal chat handling.
    """
    if not user_text or not user_text.strip():
        return None

    # 1. Task-style intents take priority -- e.g. "open online games" should
    #    route to a real games portal, not a fabricated "onlinegames.com".
    intent_match = _match_intent(user_text)
    if intent_match:
        return intent_match

    # 2. Literal "open X" / "go to X" style commands.
    match = OPEN_PATTERN.match(user_text)
    if match:
        target_raw = match.group(1).strip()
        if target_raw:
            target = _normalize_target(target_raw)
            return target_raw, _build_url(target)

    return None


def open_in_browser(url: str) -> bool:
    """Open `url` in the user's default local browser. Returns True on apparent success."""
    try:
        return bool(webbrowser.open(url, new=2))
    except Exception:
        return False
