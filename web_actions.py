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
# Direct "open <name>" shortcuts, grouped by category for easy editing.
# ---------------------------------------------------------------------------
KNOWN_SITES = {
    # --- everyday / search / productivity ---
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "outlook": "https://outlook.live.com",
    "yahoo mail": "https://mail.yahoo.com",
    "drive": "https://drive.google.com",
    "google drive": "https://drive.google.com",
    "dropbox": "https://www.dropbox.com",
    "onedrive": "https://onedrive.live.com",
    "google docs": "https://docs.google.com",
    "google sheets": "https://sheets.google.com",
    "google calendar": "https://calendar.google.com",
    "maps": "https://maps.google.com",
    "google maps": "https://maps.google.com",
    "notion": "https://www.notion.so",
    "zoom": "https://zoom.us",
    "google meet": "https://meet.google.com",
    "microsoft teams": "https://teams.microsoft.com",
    "translate": "https://translate.google.com",
    "google translate": "https://translate.google.com",
    "weather": "https://weather.com",
    "yahoo": "https://www.yahoo.com",
    "bing": "https://www.bing.com",

    # --- social / messaging ---
    "youtube": "https://www.youtube.com",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "twitter": "https://www.twitter.com",
    "x": "https://www.x.com",
    "linkedin": "https://www.linkedin.com",
    "whatsapp": "https://web.whatsapp.com",
    "telegram": "https://web.telegram.org",
    "snapchat": "https://web.snapchat.com",
    "pinterest": "https://www.pinterest.com",
    "discord": "https://discord.com/app",
    "reddit": "https://www.reddit.com",
    "tumblr": "https://www.tumblr.com",
    "threads": "https://www.threads.net",

    # --- dev / knowledge ---
    "github": "https://www.github.com",
    "gitlab": "https://gitlab.com",
    "stackoverflow": "https://stackoverflow.com",
    "stack overflow": "https://stackoverflow.com",
    "wikipedia": "https://www.wikipedia.org",
    "chatgpt": "https://chat.openai.com",
    "claude": "https://claude.ai",

    # --- shopping ---
    "amazon": "https://www.amazon.com",
    "flipkart": "https://www.flipkart.com",
    "myntra": "https://www.myntra.com",
    "ajio": "https://www.ajio.com",
    "meesho": "https://www.meesho.com",
    "ebay": "https://www.ebay.com",
    "aliexpress": "https://www.aliexpress.com",
    "walmart": "https://www.walmart.com",

    # --- groceries / pharmacy ---
    "bigbasket": "https://www.bigbasket.com",
    "blinkit": "https://blinkit.com",
    "zepto": "https://www.zeptonow.com",
    "instacart": "https://www.instacart.com",
    "1mg": "https://www.1mg.com",
    "pharmeasy": "https://pharmeasy.in",

    # --- cabs / rides ---
    "uber": "https://www.uber.com",
    "ola": "https://www.olacabs.com",
    "rapido": "https://www.rapido.bike",
    "lyft": "https://www.lyft.com",

    # --- bus / train / flight / hotel booking ---
    "redbus": "https://www.redbus.in",
    "abhibus": "https://www.abhibus.com",
    "irctc": "https://www.irctc.co.in",
    "trainline": "https://www.thetrainline.com",
    "makemytrip": "https://www.makemytrip.com",
    "goibibo": "https://www.goibibo.com",
    "cleartrip": "https://www.cleartrip.com",
    "yatra": "https://www.yatra.com",
    "skyscanner": "https://www.skyscanner.net",
    "ixigo": "https://www.ixigo.com",
    "airbnb": "https://www.airbnb.com",
    "booking.com": "https://www.booking.com",
    "oyo": "https://www.oyorooms.com",
    "99acres": "https://www.99acres.com",
    "magicbricks": "https://www.magicbricks.com",

    # --- movies / events / streaming ---
    "bookmyshow": "https://in.bookmyshow.com",
    "netflix": "https://www.netflix.com",
    "prime video": "https://www.primevideo.com",
    "hotstar": "https://www.hotstar.com",
    "disney plus": "https://www.disneyplus.com",
    "hulu": "https://www.hulu.com",
    "twitch": "https://www.twitch.tv",

    # --- music ---
    "spotify": "https://open.spotify.com",
    "youtube music": "https://music.youtube.com",
    "apple music": "https://music.apple.com",
    "gaana": "https://gaana.com",
    "jiosaavn": "https://www.jiosaavn.com",

    # --- food delivery ---
    "swiggy": "https://www.swiggy.com",
    "zomato": "https://www.zomato.com",
    "uber eats": "https://www.ubereats.com",
    "doordash": "https://www.doordash.com",

    # --- games ---
    "crazygames": "https://www.crazygames.com",
    "poki": "https://poki.com",
    "steam": "https://store.steampowered.com",
    "epic games": "https://store.epicgames.com",
    "itch.io": "https://itch.io",

    # --- learning / jobs / news ---
    "coursera": "https://www.coursera.org",
    "udemy": "https://www.udemy.com",
    "khan academy": "https://www.khanacademy.org",
    "indeed": "https://www.indeed.com",
    "naukri": "https://www.naukri.com",
    "google news": "https://news.google.com",

    # --- courier / delivery tracking ---
    "fedex": "https://www.fedex.com",
    "dhl": "https://www.dhl.com",
    "india post": "https://www.indiapost.gov.in",
}

# ---------------------------------------------------------------------------
# Task-style intents: phrases matched anywhere in the sentence, routed to a
# sensible real-world site for that task. Checked in order; first match wins.
# ---------------------------------------------------------------------------
INTENT_ROUTES: List[Tuple[List[str], str, str]] = [
    # --- transport / cabs ---
    (
        ["book a cab", "book cab", "need a cab", "book a taxi", "book taxi",
         "call a cab", "call a taxi", "book uber", "get an uber", "need a ride",
         "book a ride"],
        "https://www.uber.com",
        "Uber (cab booking)",
    ),
    # --- bus ---
    (
        ["book bus", "bus ticket", "bus booking", "book a bus", "bus tickets"],
        "https://www.redbus.in",
        "RedBus (bus ticket booking)",
    ),
    # --- train ---
    (
        ["book train", "train ticket", "train booking", "book a train",
         "railway ticket", "training ticket", "training booking"],
        "https://www.irctc.co.in",
        "IRCTC (train ticket booking)",
    ),
    # --- flight ---
    (
        ["book flight", "flight ticket", "flight booking", "book a flight",
         "book a plane ticket", "airline ticket", "book air ticket"],
        "https://www.makemytrip.com",
        "MakeMyTrip (flight booking)",
    ),
    # --- movies / cinema ---
    (
        ["book movie", "movie ticket", "movie booking", "book a movie",
         "cinema ticket"],
        "https://in.bookmyshow.com",
        "BookMyShow (movie ticket booking)",
    ),
    # --- food delivery ---
    (
        ["order food", "food delivery", "order a meal", "get food delivered",
         "order dinner", "order lunch", "hungry order"],
        "https://www.swiggy.com",
        "Swiggy (food delivery)",
    ),
    # --- groceries ---
    (
        ["order groceries", "grocery delivery", "buy groceries",
         "order vegetables", "grocery shopping online"],
        "https://blinkit.com",
        "Blinkit (grocery delivery)",
    ),
    # --- pharmacy ---
    (
        ["order medicine", "buy medicine online", "medicine delivery",
         "order medicines"],
        "https://pharmeasy.in",
        "PharmEasy (medicine delivery)",
    ),
    # --- hotel ---
    (
        ["book a hotel", "hotel booking", "book hotel", "book a room",
         "book accommodation", "book a stay"],
        "https://www.booking.com",
        "Booking.com (hotel booking)",
    ),
    # --- online shopping ---
    (
        ["buy online", "order online", "shop online", "online shopping"],
        "https://www.amazon.com",
        "Amazon (online shopping)",
    ),
    # --- games ---
    (
        ["play a game", "play games", "play online game", "play some games",
         "open a game", "open games", "online games", "open online games"],
        "https://www.crazygames.com",
        "CrazyGames (free online games)",
    ),
    # --- music ---
    (
        ["listen to music", "play music", "play a song", "play songs"],
        "https://open.spotify.com",
        "Spotify (music streaming)",
    ),
    # --- movie / show streaming ---
    (
        ["watch a movie", "watch movies", "watch something", "watch a show",
         "watch tv shows", "stream a movie"],
        "https://www.netflix.com",
        "Netflix (streaming)",
    ),
    # --- video calls / meetings ---
    (
        ["start a video call", "start a meeting", "join a meeting",
         "video call someone", "schedule a meeting"],
        "https://meet.google.com",
        "Google Meet (video calling)",
    ),
    # --- learning / courses ---
    (
        ["learn something new", "take a course", "learn online",
         "online course", "learn a new skill"],
        "https://www.coursera.org",
        "Coursera (online courses)",
    ),
    # --- job search ---
    (
        ["find a job", "job search", "search for jobs", "look for a job",
         "apply for jobs"],
        "https://www.linkedin.com/jobs",
        "LinkedIn Jobs (job search)",
    ),
    # --- courier / parcel tracking ---
    (
        ["track my parcel", "track my package", "track my order",
         "track shipment", "track courier"],
        "https://www.fedex.com",
        "FedEx (shipment tracking)",
    ),
    # --- news ---
    (
        ["read the news", "check the news", "latest news", "today's news"],
        "https://news.google.com",
        "Google News",
    ),
    # --- weather ---
    (
        ["check the weather", "what's the weather", "weather forecast"],
        "https://weather.com",
        "Weather.com",
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
