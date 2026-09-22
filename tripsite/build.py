"""tripsite v0: build a static, shareable trip website from trip profiles.

Usage:
    uv run tripsite/build.py trips/*.md                 # every live trip, in ONE run
    uv run tripsite/build.py trips/<trip>.md --dry-run  # validate only, write nothing
    uv run tripsite/build.py trips/<trip>.md --out /some/other/dir

The trip file is Markdown with YAML frontmatter; see tripsite/README.md for the schema.
Output: dist/<slug>/index.html per trip (single self-contained page), dist/index.html
(neutral placeholder, no trip listing), dist/404.html (neutral "Not found"; without it
Cloudflare Pages serves index.html with 200 for every missing path), dist/robots.txt
(disallow all) and dist/_headers (X-Robots-Tag). A Cloudflare Pages direct upload replaces
the whole site, so dist/ is kept to exactly the trips passed on this run: any other trip
folder is removed, but only if its index.html carries this tool's generator marker in its
<head>. Outputs are written via a temp file + os.replace. Symlinks are never followed.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import math
import os
import re
import stat
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    import yaml
except ImportError:  # pragma: no cover - depends on the environment
    sys.exit(
        "error: PyYAML is not installed.\n"
        "Run the build with uv (it installs project dependencies):\n"
        "    uv run tripsite/build.py trips/<trip>.md"
    )

REPO_ROOT = Path(__file__).resolve().parent.parent
THEMES_DIR = REPO_ROOT / "themes"
DEFAULT_OUT = REPO_ROOT / "dist"

# Leaflet 1.9.4 from unpkg. SRI hashes computed locally from the unpkg files on
# 2026-09-18; they match the hashes published on leafletjs.com/download.html.
LEAFLET_CSS_URL = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
LEAFLET_CSS_SRI = "sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
LEAFLET_JS_URL = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
LEAFLET_JS_SRI = "sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,79}$")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")
THEME_RE = re.compile(r"^[a-z0-9_]+$")
TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")
HEX_COLOUR_RE = re.compile(r"^#[0-9A-Fa-f]{3,8}$")
# Only #RGB and #RRGGBB reach the page: an OSM colour tag with alpha would make a line
# invisible, and a CSS colour name ("red") isn't safe to drop into a style attribute.
CSS_HEX_RE = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")
IATA_RE = re.compile(r"^[A-Z]{3}$")

HOTEL_DISPLAY_CHOICES = ("exact", "approximate", "hidden")
EVENT_KINDS = ("plan", "city")
STAY_CATEGORY = "stay"
# A place is a "stay" (private, handled per privacy.hotel_display) if its category is
# one of these (case-insensitive) OR it has `private: true`.
STAY_CATEGORIES = frozenset({"stay", "hotel", "lodging", "airbnb", "accommodation", "hostel"})
# approximate: the circle centre is moved OFFSET_MIN_M..OFFSET_MAX_M from the stay, on a
# bearing kept 20-70 degrees off north/south/east/west (so the centre's lat AND lon both
# differ from the stay's at 4 dp). The radius is fixed, so it says nothing about the offset.
OFFSET_MIN_M, OFFSET_MAX_M = 150, 250
APPROX_RADIUS_M = 400  # >= OFFSET_MAX_M + 150: the stay is inside, never near the centre
NEAR_STAY_M = 400      # an event's inline {lat, lon} this close to a stay is treated as the stay
POPULAR_NEAR_STAY_M = 100  # a popular pin this close to a private stay gets a warning (not an error)
APPROX_MAX_ZOOM = 14   # the page never zooms closer than this onto an approximate area

# Fixed, tile-safe marker palette (the theme colours only style the page chrome;
# several themes vanish on OSM tiles, e.g. noir's white/black).
MARKER_COLOURS = {
    "ours": "#C62828",        # strong red, white outline
    "popular": "#1565C0",     # strong blue, white outline
    "event": "#00695C",       # dark teal, white outline
    "stay": "#7B1FA2",        # purple fill, semi-transparent
    "stay-edge": "#2A0A3A",   # dark outline for the stay area
    "airport": "#EF6C00",     # amber disc + white plane glyph: not a circle like the others
    "outline": "#FFFFFF",
}

# --- Overpass (airport lookup + metro lines) ------------------------------- #
# Both are fetched once and cached on disk; a later build does no network call at all.
# Cache lives outside dist/ and outside git (.gitignore already has "cache/*").
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
# Overpass and Nominatim both ask for a named agent that identifies the application.
OVERPASS_UA = "tripsite/0.1 (static trip-site builder; https://worldcities.ca)"
OVERPASS_MIN_INTERVAL_S = 1.1   # same politeness floor as Nominatim: >= 1 request/second
OVERPASS_TIMEOUT_S = 180
OVERPASS_RETRY_STATUS = (429, 504)  # "too many requests" / "gateway timeout": back off, retry
OVERPASS_RETRIES = 3
OVERPASS_BACKOFF_S = (5, 15, 45)
DEFAULT_CACHE_DIR = REPO_ROOT / "cache" / "tripsite"
AIRPORT_CACHE_FILE = "airports.json"
METRO_RADIUS_M = 30000          # bbox half-size around trip.center; covers a metropolitan network
METRO_SIMPLIFY_M = 15.0         # Douglas-Peucker tolerance; endpoints are always kept
METRO_COORD_DP = 5              # ~1 m; matches the rounding used for the approximate stay centre
# Above this many bytes of JSON the metro data is written to dist/<slug>/metro.json and
# fetched when the layer is first switched on, instead of being embedded in the page.
METRO_INLINE_MAX_BYTES = 400_000
METRO_SIDECAR = "metro.json"
# Used in ref order when a route relation carries no usable `colour` tag.
METRO_FALLBACK_COLOURS = ("#E53935", "#1E88E5", "#43A047", "#FB8C00", "#8E24AA",
                          "#00ACC1", "#D81B60", "#6D4C41", "#3949AB", "#7CB342")
FAVICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E"
           "%3Ccircle cx='8' cy='8' r='6' fill='%23C62828' stroke='white' stroke-width='2'/%3E%3C/svg%3E")


# --------------------------------------------------------------------------- #
# YAML loading: duplicate keys are errors; base-60 ints remember their text
# --------------------------------------------------------------------------- #


class Sexagesimal(int):
    """An int YAML 1.1 read from a colon form like 12:00 (= 720). Keeps the source text so
    an unquoted time can be recovered, while a bare 930 stays a plain int and is rejected."""

    text: str = ""


class TripLoader(yaml.SafeLoader):
    def construct_mapping(self, node: Any, deep: bool = False) -> dict:
        if isinstance(node, yaml.MappingNode):
            self.flatten_mapping(node)
            seen: dict[Any, int] = {}
            for key_node, _ in node.value:
                key = self.construct_object(key_node, deep=deep)
                try:
                    first = seen.get(key)
                except TypeError:  # unhashable key: SafeLoader reports it below
                    continue
                if first is not None:
                    raise yaml.constructor.ConstructorError(
                        "while constructing a mapping", node.start_mark,
                        f"found duplicate key {key!r} (first used on line {first + 1})",
                        key_node.start_mark)
                seen[key] = key_node.start_mark.line
        return super().construct_mapping(node, deep=deep)

    def construct_yaml_int(self, node: Any) -> int:
        value = super().construct_yaml_int(node)
        text = str(self.construct_scalar(node)).strip()
        if ":" in text:
            s = Sexagesimal(value)
            s.text = text
            return s
        return value


TripLoader.add_constructor("tag:yaml.org,2002:int", TripLoader.construct_yaml_int)


# --------------------------------------------------------------------------- #
# Validation helpers
# --------------------------------------------------------------------------- #


@dataclass
class Problems:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def err(self, where: str, msg: str) -> None:
        self.errors.append(f"{where}: {msg}")

    def warn(self, where: str, msg: str) -> None:
        self.warnings.append(f"{where}: {msg}")


_MISSING = object()


def get(mapping: Any, key: str, where: str, p: Problems, required: bool = True) -> Any:
    """Return mapping[key]; record an error if it is required and missing/empty."""
    if not isinstance(mapping, dict):
        p.err(where, "expected a mapping (key: value pairs)")
        return None
    value = mapping.get(key, _MISSING)
    if value is _MISSING or value is None or value == "":
        if required:
            p.err(where, f"missing required field '{key}'")
        return None
    return value


def as_text(value: Any, where: str, p: Problems) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        p.err(where, "expected text, got bool (YAML reads unquoted yes/no/on/off/true/false as "
                     "true/false): quote it, e.g. \"NO\"")
        return None
    if not isinstance(value, (str, int, float)):
        p.err(where, f"expected text, got {type(value).__name__}")
        return None
    text = value.text if isinstance(value, Sexagesimal) else str(value).strip()
    return text or None


def as_date(value: Any, where: str, p: Problems) -> dt.date | None:
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        try:
            return dt.date.fromisoformat(value.strip())
        except ValueError:
            pass
    p.err(where, f"bad date {value!r} (use YYYY-MM-DD, e.g. 2026-10-22)")
    return None


def as_time(value: Any, where: str, p: Problems) -> str | None:
    """Accept "HH:MM" strings. Unquoted 12:00 is read by YAML 1.1 as the base-60
    integer 720; TripLoader keeps its source text, so recover it from that. A bare
    integer (930, 12) is ambiguous and rejected."""
    if value is None:
        return None
    text = value.text if isinstance(value, Sexagesimal) else value
    if isinstance(text, str):
        m = TIME_RE.match(text.strip())
        if m and int(m.group(1)) < 24 and int(m.group(2)) < 60:
            return f"{int(m.group(1)):02d}:{m.group(2)}"
    if isinstance(value, int) and not isinstance(value, (bool, Sexagesimal)):
        p.err(where, f"bad time {value!r}: a bare number is ambiguous; write it as a quoted "
                     f"\"HH:MM\", e.g. time: \"09:30\"")
        return None
    p.err(where, f"bad time {text!r} (use quoted \"HH:MM\", e.g. \"12:00\")")
    return None


def as_id(value: Any, where: str, p: Problems) -> str | None:
    """Ids are compared as text, so `id: 1` and `location: 1` match."""
    if isinstance(value, int) and not isinstance(value, (bool, Sexagesimal)):
        return str(value)
    return as_text(value, where, p)


def as_coord(value: Any, where: str, p: Problems, lo: float, hi: float) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        p.err(where, f"expected a number, got {value!r}")
        return None
    if not lo <= float(value) <= hi:
        p.err(where, f"{value} is out of range ({lo}..{hi})")
        return None
    return float(value)


def as_bool(value: Any, where: str, p: Problems) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        p.err(where, f"expected true or false, got {value!r}")
        return None
    return value


def as_url(value: Any, where: str, p: Problems) -> str | None:
    text = as_text(value, where, p)
    if text is None:
        return None
    if not re.match(r"^https?://[^\s\"'<>]+$", text):
        p.err(where, f"URL must start with http:// or https:// and contain no spaces: {text!r}")
        return None
    return text


def as_list(value: Any, where: str, p: Problems) -> list:
    if value is None:
        return []
    if not isinstance(value, list):
        p.err(where, "expected a list (lines starting with '- ')")
        return []
    return value


# --------------------------------------------------------------------------- #
# Loading and validating a trip file
# --------------------------------------------------------------------------- #


def split_frontmatter(text: str, path: Path) -> tuple[str, str]:
    lines = text.lstrip("﻿").splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise SystemExit(f"error: {path}: file must start with a '---' line (YAML frontmatter)")
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "".join(lines[1:i]), "".join(lines[i + 1:])
    raise SystemExit(f"error: {path}: no closing '---' line after the YAML frontmatter")


def load_trip(path: Path) -> tuple[dict, str, Problems]:
    """Parse and validate a trip file. Returns (normalised data, markdown body, problems)."""
    if not path.is_file():
        raise SystemExit(f"error: trip file not found: {path}")
    front, body = split_frontmatter(path.read_text(encoding="utf-8"), path)
    try:
        raw = yaml.load(front, Loader=TripLoader)  # TripLoader subclasses SafeLoader
    except yaml.YAMLError as exc:
        raise SystemExit(f"error: {path}: frontmatter is not valid YAML:\n{exc}")
    except ValueError as exc:  # e.g. 2026-10-32 matches YAML's date pattern but isn't a date
        raise SystemExit(f"error: {path}: bad date in frontmatter ({exc}); use real YYYY-MM-DD dates")
    if not isinstance(raw, dict):
        raise SystemExit(f"error: {path}: frontmatter must be a mapping with 'trip:', 'locations:' etc.")

    p = Problems()
    known_top = {"trip", "privacy", "map", "locations", "popular", "events"}
    for key in raw:
        if key not in known_top:
            p.warn("frontmatter", f"unknown top-level key '{key}' ignored")

    trip = _validate_trip(raw.get("trip"), p)
    privacy = _validate_privacy(raw.get("privacy"), p)
    map_opts = _validate_map(raw.get("map"), p)
    seen_ids: dict[str, str] = {}
    ours = [_validate_place(item, f"locations[{i}]", p, seen_ids, popular=False)
            for i, item in enumerate(as_list(raw.get("locations"), "locations", p))]
    popular = [_validate_place(item, f"popular[{i}]", p, seen_ids, popular=True)
               for i, item in enumerate(as_list(raw.get("popular"), "popular", p))]
    ours = [x for x in ours if x]
    popular = [x for x in popular if x]
    events = [_validate_event(item, f"events[{i}]", p, seen_ids)
              for i, item in enumerate(as_list(raw.get("events"), "events", p))]
    events = [x for x in events if x]

    # "outside" holds events outside start..end that carry `keep: true`; filter_events fills it.
    # "metro" is filled later by resolve_transit (it needs the cache / the network).
    data = {"trip": trip, "privacy": privacy, "map": map_opts, "ours": ours, "popular": popular,
            "events": events, "outside": [], "metro": None}
    return data, body, p


def _validate_trip(raw: Any, p: Problems) -> dict:
    w = "trip"
    if raw is None:
        p.err(w, "missing required section 'trip:'")
        return {}
    t: dict[str, Any] = {}
    for key in ("name", "city", "country"):
        t[key] = as_text(get(raw, key, w, p), f"{w}.{key}", p)

    slug = as_text(get(raw, "slug", w, p), f"{w}.slug", p)
    if slug and not SLUG_RE.match(slug):
        p.err(f"{w}.slug", f"{slug!r} must be 3-80 chars of lowercase letters, digits and hyphens")
        slug = None
    t["slug"] = slug

    t["start"] = as_date(get(raw, "start", w, p), f"{w}.start", p)
    t["end"] = as_date(get(raw, "end", w, p), f"{w}.end", p)
    if t["start"] and t["end"] and t["end"] < t["start"]:
        p.err(w, f"end ({t['end']}) is before start ({t['start']})")

    tz = as_text(get(raw, "timezone", w, p), f"{w}.timezone", p)
    if tz:
        try:
            ZoneInfo(tz)
        except (ZoneInfoNotFoundError, ValueError):
            p.err(f"{w}.timezone", f"unknown timezone {tz!r} (use an IANA name like America/Mexico_City)")
    t["timezone"] = tz

    center = get(raw, "center", w, p)
    if center is not None:
        t["center"] = {
            "lat": as_coord(get(center, "lat", f"{w}.center", p), f"{w}.center.lat", p, -90, 90),
            "lon": as_coord(get(center, "lon", f"{w}.center", p), f"{w}.center.lon", p, -180, 180),
        }

    zoom = get(raw, "zoom", w, p)
    if zoom is not None and (isinstance(zoom, (bool, Sexagesimal)) or not isinstance(zoom, int)
                             or not 1 <= zoom <= 19):
        p.err(f"{w}.zoom", f"expected a whole number 1..19, got {zoom!r}")
        zoom = None
    t["zoom"] = zoom

    theme = as_text(get(raw, "theme", w, p), f"{w}.theme", p)
    if theme and (not THEME_RE.match(theme) or not (THEMES_DIR / f"{theme}.json").is_file()):
        names = ", ".join(sorted(f.stem for f in THEMES_DIR.glob("*.json")))
        p.err(f"{w}.theme", f"no theme {theme!r} in themes/ (available: {names})")
        theme = None
    t["theme"] = theme
    t["airports"] = _validate_airports(raw.get("airport"), p)
    return t


def _validate_airports(raw: Any, p: Problems) -> list[dict]:
    """trip.airport: an IATA code, a {code, name, lat, lon} mapping, or a list of either.

    Coordinates are optional here; resolve_transit fills them from the cache or Overpass.
    An airport is never a place: it is not in `locations`/`popular`, never a stay, and
    takes no part in the privacy rules or the leak scan."""
    if raw is None:
        return []
    items = raw if isinstance(raw, list) else [raw]
    out: list[dict] = []
    seen: dict[str, int] = {}
    for i, item in enumerate(items):
        w = f"trip.airport[{i}]" if isinstance(raw, list) else "trip.airport"
        air = _validate_one_airport(item, w, p)
        if air is None:
            continue
        if air["code"] in seen:
            p.err(w, f"duplicate airport code {air['code']!r}")
            continue
        seen[air["code"]] = i
        out.append(air)
    return out


def _validate_one_airport(raw: Any, w: str, p: Problems) -> dict | None:
    if isinstance(raw, dict):
        code_raw = get(raw, "code", w, p)
        name = as_text(get(raw, "name", w, p, required=False), f"{w}.name", p)
        lat = as_coord(get(raw, "lat", w, p, required=False), f"{w}.lat", p, -90, 90)
        lon = as_coord(get(raw, "lon", w, p, required=False), f"{w}.lon", p, -180, 180)
        if (lat is None) != (lon is None):
            p.err(w, "give both lat and lon, or neither (the code is then looked up on Overpass)")
            lat = lon = None
        for key in raw if isinstance(raw, dict) else ():
            if key not in ("code", "name", "lat", "lon"):
                p.warn(w, f"unknown airport key '{key}' ignored")
    else:
        code_raw, name, lat, lon = raw, None, None, None
    code = as_text(code_raw, f"{w}.code", p)
    if code is None:
        return None
    code = code.strip().upper()
    if not IATA_RE.match(code):
        p.err(f"{w}.code", f"{code!r} is not a 3-letter IATA code (e.g. MEX). Write the short form "
                           "'airport: MEX', or give the full form with lat/lon.")
        return None
    return {"code": code, "name": name, "lat": lat, "lon": lon}


def _validate_map(raw: Any, p: Problems) -> dict:
    """Optional top-level `map:` section. Only `metro: on|off` for now.

    Absent (or `metro` absent) means NO metro layer and no Overpass call at all: a build
    only ever goes to the network for a trip that asked for one."""
    opts = {"metro": None}
    if raw is None:
        return opts
    if not isinstance(raw, dict):
        p.err("map", "expected a mapping, e.g. map: {metro: on}")
        return opts
    for key in raw:
        if key != "metro":
            p.warn("map", f"unknown key '{key}' ignored")
    if "metro" in raw:
        # YAML 1.1 reads on/off/yes/no as booleans, which is exactly what is wanted here.
        if raw.get("metro") is None:
            p.err("map.metro", "expected on or off")
        else:
            opts["metro"] = as_bool(raw.get("metro"), "map.metro", p)
    return opts


def _validate_privacy(raw: Any, p: Problems) -> dict:
    if raw is None:
        p.warn("privacy", "section missing; defaulting to hotel_display: approximate, noindex: true")
        return {"hotel_display": "approximate", "noindex": True}
    display = as_text(get(raw, "hotel_display", "privacy", p), "privacy.hotel_display", p)
    if display and display not in HOTEL_DISPLAY_CHOICES:
        p.err("privacy.hotel_display", f"{display!r} must be one of {', '.join(HOTEL_DISPLAY_CHOICES)}")
    noindex = as_bool(get(raw, "noindex", "privacy", p, required=False), "privacy.noindex", p)
    if noindex is False:
        p.warn("privacy.noindex", "false is ignored: every generated page is always noindex,nofollow")
    return {"hotel_display": display, "noindex": True}


def _validate_place(raw: Any, w: str, p: Problems, seen_ids: dict[str, str],
                    popular: bool) -> dict | None:
    if not isinstance(raw, dict):
        p.err(w, "expected a mapping with id, name, category, lat, lon ...")
        return None
    place: dict[str, Any] = {"group": "popular" if popular else "ours"}
    pid = as_id(get(raw, "id", w, p), f"{w}.id", p)
    if pid:
        if not ID_RE.match(pid):
            p.err(f"{w}.id", f"{pid!r} may only use letters, digits, '-' and '_'")
        elif pid in seen_ids:
            p.err(f"{w}.id", f"duplicate id {pid!r} (also used at {seen_ids[pid]})")
        else:
            seen_ids[pid] = w
    place["id"] = pid
    place["name"] = as_text(get(raw, "name", w, p), f"{w}.name", p)
    category = as_text(get(raw, "category", w, p), f"{w}.category", p)
    place["category"] = category.lower() if category else None
    place["lat"] = as_coord(get(raw, "lat", w, p), f"{w}.lat", p, -90, 90)
    place["lon"] = as_coord(get(raw, "lon", w, p), f"{w}.lon", p, -180, 180)
    private = as_bool(get(raw, "private", w, p, required=False), f"{w}.private", p)
    place["stay"] = bool(private) or (place["category"] or "") in STAY_CATEGORIES
    if popular and place["stay"]:
        why = "private: true" if private else f"category {place['category']!r} is a stay category"
        p.err(w, f"{why}; put stays under locations (only there are they kept private)")
    if popular:
        place["default_on"] = as_bool(get(raw, "default_on", w, p), f"{w}.default_on", p)
        place["address"] = as_text(get(raw, "address", w, p, required=False), f"{w}.address", p)
    else:
        place["address"] = as_text(get(raw, "address", w, p), f"{w}.address", p)
    place["notes"] = as_text(get(raw, "notes", w, p, required=False), f"{w}.notes", p)
    place["url"] = as_url(get(raw, "url", w, p, required=False), f"{w}.url", p)
    return place


def _validate_event(raw: Any, w: str, p: Problems, seen_ids: dict[str, str]) -> dict | None:
    if not isinstance(raw, dict):
        p.err(w, "expected a mapping with date, kind, name ...")
        return None
    ev: dict[str, Any] = {}
    ev["date"] = as_date(get(raw, "date", w, p), f"{w}.date", p)
    ev["time"] = as_time(get(raw, "time", w, p, required=False), f"{w}.time", p)
    kind = as_text(get(raw, "kind", w, p), f"{w}.kind", p)
    if kind and kind not in EVENT_KINDS:
        p.err(f"{w}.kind", f"{kind!r} must be one of {', '.join(EVENT_KINDS)}")
    ev["kind"] = kind
    ev["name"] = as_text(get(raw, "name", w, p), f"{w}.name", p)
    ev["booked"] = as_bool(get(raw, "booked", w, p, required=False), f"{w}.booked", p)
    # keep: an event outside the trip dates is normally dropped; with keep: true it is
    # kept and shown under "Just outside your dates". Inside the dates it does nothing.
    ev["keep"] = bool(as_bool(get(raw, "keep", w, p, required=False), f"{w}.keep", p))
    # url = the thing itself (tickets, the venue, the museum page);
    # source = where the information came from. Both optional, both must be http(s).
    ev["url"] = as_url(get(raw, "url", w, p, required=False), f"{w}.url", p)
    ev["source"] = as_url(get(raw, "source", w, p, required=False), f"{w}.source", p)
    ev["notes"] = as_text(get(raw, "notes", w, p, required=False), f"{w}.notes", p)

    loc = raw.get("location")
    if isinstance(loc, int) and not isinstance(loc, (bool, Sexagesimal)):
        loc = str(loc)
    if loc is None:
        ev["loc"] = None
    elif isinstance(loc, str):
        if loc.strip() not in seen_ids:
            p.err(f"{w}.location", f"unknown place id {loc!r} (must match an id in locations/popular)")
        ev["loc"] = {"ref": loc.strip()}
    elif isinstance(loc, dict):
        lw = f"{w}.location"
        ev["loc"] = {
            "lat": as_coord(get(loc, "lat", lw, p), f"{lw}.lat", p, -90, 90),
            "lon": as_coord(get(loc, "lon", lw, p), f"{lw}.lon", p, -180, 180),
            "label": as_text(get(loc, "label", lw, p, required=False), f"{lw}.label", p) or ev["name"],
        }
    else:
        p.err(f"{w}.location", "expected a place id or {lat, lon, label}")
        ev["loc"] = None
    return ev


# --------------------------------------------------------------------------- #
# Privacy and event filtering
# --------------------------------------------------------------------------- #


def metres_between(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres (haversine)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    h = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * 6371000 * math.asin(math.sqrt(min(1.0, h)))


def offset_centre(slug: str, place: dict) -> tuple[float, float, float]:
    """Deterministic (lat, lon, offset_m) for an approximate stay's circle centre.

    Seeded by the slug, id AND the private fields (name, exact coords): with the id
    alone (often guessable, e.g. "hotel") anyone could recompute the offset from the
    public page and subtract it. Same inputs -> same circle on every rebuild."""
    seed = "|".join([slug, place["id"], place.get("name") or "", repr(place["lat"]), repr(place["lon"])])
    h = hashlib.sha256(seed.encode("utf-8")).digest()
    u1 = int.from_bytes(h[0:4], "big") / 2 ** 32
    u2 = int.from_bytes(h[4:8], "big") / 2 ** 32
    u3 = int.from_bytes(h[8:9], "big") % 4
    bearing = math.radians(u3 * 90 + 20 + u1 * 50)  # 20-70 deg into a random quadrant
    # 1 m inside the band so rounding the centre to 5 dp (< 1 m) can't push it outside
    dist = OFFSET_MIN_M + 1 + u2 * (OFFSET_MAX_M - OFFSET_MIN_M - 2)
    # destination point on a sphere
    r = 6371000.0
    la1, lo1 = math.radians(place["lat"]), math.radians(place["lon"])
    ang = dist / r
    la2 = math.asin(math.sin(la1) * math.cos(ang) + math.cos(la1) * math.sin(ang) * math.cos(bearing))
    lo2 = lo1 + math.atan2(math.sin(bearing) * math.sin(ang) * math.cos(la1),
                           math.cos(ang) - math.sin(la1) * math.sin(la2))
    lat, lon = round(math.degrees(la2), 5), round((math.degrees(lo2) + 540) % 360 - 180, 5)
    return lat, lon, metres_between(lat, lon, place["lat"], place["lon"])


def apply_privacy(data: dict, body: str, p: Problems) -> None:
    """Rewrite stay locations per privacy.hotel_display so exact details never reach the page.

    Stays are places under `locations` whose category is in STAY_CATEGORIES or that have
    `private: true` (stays under `popular` are rejected during validation). The original
    stay records are kept in data["_private_stays"] for the post-render leak scan."""
    display = data["privacy"]["hotel_display"]
    slug = data["trip"]["slug"]
    kept: list[dict] = []
    hidden_ids: set[str] = set()
    renamed: dict[str, str] = {}  # the id often names the hotel, so it is replaced too
    private_stays: list[dict] = []
    # Per-place public label: lodging reads "Where we're staying"; any other private place
    # (e.g. a relative's flat marked private: true) reads "Private place". Numbered if repeated.
    kind_total: dict[str, int] = {}
    if display == "approximate":
        for place in data["ours"]:
            if place.get("stay"):
                kind = _approx_kind(place)
                kind_total[kind] = kind_total.get(kind, 0) + 1
    kind_seen: dict[str, int] = {}
    for place in data["ours"]:
        if not place.get("stay") or display == "exact":
            kept.append(place)
            continue
        private_stays.append(place)
        _warn_if_leaked(place, body, data, p)
        _warn_if_popular_near(place, data, p)
        if display == "hidden":
            hidden_ids.add(place["id"])
            continue
        # approximate: a fixed-radius circle whose centre is offset 150-250 m from the stay.
        # id is made opaque; name, address, notes, url and the real category are dropped.
        opaque_id = f"_stay{len(renamed) + 1}"  # leading '_' can't collide: user ids start alphanumeric
        renamed[place["id"]] = opaque_id
        lat, lon, _ = offset_centre(slug, place)
        kind = _approx_kind(place)
        kind_seen[kind] = kind_seen.get(kind, 0) + 1
        label = APPROX_LABELS[kind]
        if kind_total[kind] > 1:
            label = f"{label} {kind_seen[kind]}"
        kept.append({
            "group": "ours", "id": opaque_id, "category": STAY_CATEGORY, "approx": True,
            "radius": APPROX_RADIUS_M, "lat": lat, "lon": lon, "label": label, "approx_kind": kind,
        })
    data["ours"] = kept
    data["_private_stays"] = private_stays
    # Events kept outside the trip dates are pinned and published like any other, so they
    # go through the same near-stay / hidden / renamed handling.
    for ev in all_events(data):
        loc = ev["loc"]
        ref = loc.get("ref") if loc else None
        if loc and ref is None and loc.get("lat") is not None:
            near = _nearest_stay(loc, private_stays)
            if near is not None:
                stay, dist = near
                p.warn(f"events '{ev['name']}'",
                       f"inline location is {dist:.0f} m from a private stay (< {NEAR_STAY_M} m); "
                       f"its coordinates and label are not published"
                       + ("; it points at the approximate stay area instead" if display == "approximate"
                          else "; the event is kept without a map link")
                       + ". Use a place id if it is really somewhere else.")
                ref = stay["id"]
        if ref in hidden_ids:
            ev["loc"] = None  # keep the event, lose the map link
        elif ref in renamed:
            ev["loc"] = {"ref": renamed[ref]}


APPROX_LABELS = {"stay": "Where we’re staying", "private": "Private place"}


def _approx_kind(place: dict) -> str:
    """'stay' for lodging categories, 'private' for other places marked private: true."""
    return "stay" if (place.get("category") or "") in STAY_CATEGORIES else "private"


def _warn_if_popular_near(place: dict, data: dict, p: Problems) -> None:
    """A popular pin right next to a private stay shows roughly where it is. Warning only."""
    for other in data["popular"]:
        d = metres_between(place["lat"], place["lon"], other["lat"], other["lon"])
        if d < POPULAR_NEAR_STAY_M:
            p.warn(f"popular '{other['id']}'",
                   f"is {d:.0f} m from private place '{place['id']}' (< {POPULAR_NEAR_STAY_M} m), so its "
                   "pin shows roughly where that place is. Remove it if that matters.")


def _nearest_stay(loc: dict, stays: list[dict]) -> tuple[dict, float] | None:
    best = None
    for stay in stays:
        d = metres_between(loc["lat"], loc["lon"], stay["lat"], stay["lon"])
        if d < NEAR_STAY_M and (best is None or d < best[1]):
            best = (stay, d)
    return best


def all_events(data: dict) -> list[dict]:
    """In-range events followed by the ones kept outside the dates, in render order."""
    return list(data["events"]) + list(data.get("outside") or [])


def _warn_if_leaked(place: dict, body: str, data: dict, p: Problems) -> None:
    texts = [body]
    for e in all_events(data):
        loc = e.get("loc") or {}
        texts.append(f"{e.get('name') or ''} {e.get('notes') or ''} {loc.get('label') or ''}")
    for other in data["ours"] + data["popular"]:
        if other is not place:
            texts.append(f"{other.get('name') or ''} {other.get('notes') or ''} {other.get('address') or ''}")
    haystack = " ".join(texts).casefold()
    for label in (place.get("name"), place.get("address")):
        if label and label.casefold() in haystack:
            p.warn(f"locations '{place['id']}'",
                   f"stay is not shown exactly, but {label!r} appears in the body, an event or another "
                   "place's name/notes/address; remove it there (the build fails if it reaches the page)")


_POSTCODE_RES = (
    re.compile(r"\b\d{4,6}\b"),                                    # 99001, 75001, 10115
    re.compile(r"\b[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}\b", re.IGNORECASE),    # UK: SW1A 1AA
    re.compile(r"\b[A-Z]\d[A-Z]\s?\d[A-Z]\d\b", re.IGNORECASE),             # CA: K1A 0B1
)


def _stay_fragments(stay: dict) -> list[str]:
    """Text that must not appear on the page for a non-exact stay."""
    frags = [stay.get("name"), stay.get("address"), stay.get("url")]
    address = stay.get("address") or ""
    parts = [s.strip() for s in address.split(",") if s.strip()]
    if parts:
        street = re.sub(r"\s+", " ", re.sub(r"\b\d+[A-Za-z]?\b", " ", parts[0])).strip(" -#")
        if len(street) >= 5:
            frags.append(street)
    for part in parts[1:]:  # postcodes: after the first comma, so a house number isn't one
        for rx in _POSTCODE_RES:
            frags.extend(m.group(0) for m in rx.finditer(part))
    return [f for f in frags if f]


def _coord_variants(x: float) -> set[str]:
    """4-dp rounded and truncated forms, unsigned. Any longer rendering (5+ dp) of the
    same value starts with one of these."""
    a = abs(x)
    return {f"{a:.4f}", f"{math.floor(a * 10 ** 4) / 10 ** 4:.4f}"}


def scan_for_leaks(page: str, stays: list[dict]) -> list[str]:
    """Final safety net: the rendered page must not contain a private stay's name, address
    fragments (street, postcode), url, or its coordinates at 4+ decimals (as a lat/lon pair)."""
    text = (page.replace("\\u0026", "&").replace("\\u003c", "<").replace("\\u003e", ">"))
    text = html.unescape(text)
    folded = text.casefold()
    hits = []
    for stay in stays:
        for frag in _stay_fragments(stay):
            f = frag.casefold()
            if re.fullmatch(r"[\w ]+", f):
                found = re.search(r"(?<!\w)" + re.escape(f) + r"(?!\w)", folded)
            else:
                found = f in folded
            if found:
                hits.append(f"private stay text {frag!r} appears on the page")
        lats, lons = _coord_variants(stay["lat"]), _coord_variants(stay["lon"])
        for m in re.finditer(r"(?<![\d.])(\d{1,3}\.\d{4,})", text):
            if not any(m.group(1).startswith(v) for v in lats | lons):
                continue
            is_lat = any(m.group(1).startswith(v) for v in lats)
            window = text[max(0, m.start() - 80): m.end() + 80]
            partner = lons if is_lat else lats
            if any(re.search(r"(?<![\d.])" + re.escape(v), window) for v in partner):
                hits.append(f"private stay coordinates (~{m.group(1)}) appear on the page")
                break
    return hits


def filter_events(data: dict, p: Problems) -> int:
    """Split events into in-range (data["events"]) and kept-outside (data["outside"]).

    An event outside start..end is dropped with a warning unless it has `keep: true`,
    in which case it moves to data["outside"] and is rendered in its own section. It is
    still pinned on the map and still subject to every privacy rule (apply_privacy and
    the leak scan see both lists). Returns the number actually dropped."""
    start, end = data["trip"]["start"], data["trip"]["end"]
    kept, outside, dropped = [], [], 0
    for ev in data["events"]:
        if ev["date"] < start or ev["date"] > end:
            if ev.get("keep"):
                outside.append(ev)
            else:
                p.warn("events", f"dropped '{ev['name']}' on {ev['date']}: outside trip dates "
                                 f"{start}..{end} (add 'keep: true' to keep it)")
                dropped += 1
        else:
            kept.append(ev)
    def order(e: dict) -> tuple:
        return (e["date"], e["time"] or "")

    kept.sort(key=order)
    outside.sort(key=order)
    data["events"] = kept
    data["outside"] = outside
    return dropped


# --------------------------------------------------------------------------- #
# Overpass: airport lookup and metro lines (fetched once, then cached on disk)
# --------------------------------------------------------------------------- #


class OverpassError(RuntimeError):
    """A request to Overpass failed (network, HTTP status, or unreadable JSON)."""


def _today() -> str:
    """Today in UTC, for a cache entry's "fetched" stamp. Never used for trip dates."""
    return dt.datetime.now(tz=dt.UTC).date().isoformat()


def cache_dir() -> Path:
    """Where fetched Overpass data is kept. Read from the environment every call so a
    test (or a throwaway build) can point it somewhere else."""
    env = os.environ.get("TRIPSITE_CACHE_DIR")
    return Path(env) if env else DEFAULT_CACHE_DIR


def cache_read(name: str) -> Any:
    """Parsed JSON from cache_dir()/name, or None if it isn't there or isn't readable."""
    path = cache_dir() / name
    if not is_real_file(path):
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def cache_write(name: str, payload: Any) -> Path:
    path = cache_dir() / name
    path.parent.mkdir(parents=True, exist_ok=True)
    write_file(path, json.dumps(payload, ensure_ascii=False))
    return path


_last_overpass_at = 0.0


def overpass_get(ql: str) -> dict:
    """GET one Overpass QL query and return the parsed JSON.

    Politeness, as Overpass (and Nominatim) ask for: a named User-Agent, at least
    OVERPASS_MIN_INTERVAL_S between requests from this process, a patient timeout, and a
    backing-off retry on the two "come back later" statuses (429, 504) only. Every other
    status raises at once. A build makes at most one request per airport code plus one per
    city bounding box, and none at all once the cache is warm."""
    global _last_overpass_at
    url = f"{OVERPASS_URL}?{urllib.parse.urlencode({'data': ql})}"
    headers = {"User-Agent": OVERPASS_UA, "Accept": "application/json",
               "Accept-Encoding": "identity"}
    last = ""
    for attempt in range(OVERPASS_RETRIES):
        wait = OVERPASS_MIN_INTERVAL_S - (time.monotonic() - _last_overpass_at)
        if wait > 0:
            time.sleep(wait)
        _last_overpass_at = time.monotonic()
        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=OVERPASS_TIMEOUT_S) as resp:
                body = resp.read()
            return json.loads(body.decode("utf-8", "replace"))
        except urllib.error.HTTPError as exc:
            last = f"HTTP {exc.code} {exc.reason}"
            if exc.code not in OVERPASS_RETRY_STATUS:
                raise OverpassError(f"{OVERPASS_URL}: {last}") from exc
        except (urllib.error.URLError, OSError) as exc:
            last = f"{type(exc).__name__}: {exc}"
        except ValueError as exc:  # not JSON: usually an Overpass error page
            raise OverpassError(f"{OVERPASS_URL}: response was not JSON ({exc})") from exc
        if attempt + 1 < OVERPASS_RETRIES:
            time.sleep(OVERPASS_BACKOFF_S[min(attempt, len(OVERPASS_BACKOFF_S) - 1)])
    raise OverpassError(f"{OVERPASS_URL}: gave up after {OVERPASS_RETRIES} tries ({last})")


# --- airports -------------------------------------------------------------- #


def airport_query(code: str) -> str:
    return ('[out:json][timeout:60];('
            f'node["aeroway"="aerodrome"]["iata"="{code}"];'
            f'way["aeroway"="aerodrome"]["iata"="{code}"];'
            f'relation["aeroway"="aerodrome"]["iata"="{code}"];'
            ');out center tags 5;')


def airport_from_overpass(code: str) -> dict | None:
    """Look up one IATA code as aeroway=aerodrome + iata=<CODE>. None if nothing matched."""
    raw = overpass_get(airport_query(code))
    for el in raw.get("elements") or []:
        centre = el.get("center") or el
        lat, lon = centre.get("lat"), centre.get("lon")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            continue
        tags = el.get("tags") or {}
        name = tags.get("name:en") or tags.get("name") or code
        return {"code": code, "name": str(name), "lat": round(float(lat), METRO_COORD_DP),
                "lon": round(float(lon), METRO_COORD_DP), "source": "overpass",
                "fetched": _today()}
    return None


def resolve_airports(data: dict, p: Problems, refresh: bool = False) -> None:
    """Fill in each airport's lat/lon/name from the trip file, the cache, or Overpass.

    An airport that can't be resolved and has no hand-entered coordinates is an ERROR:
    a silently missing airport pin is worse than a build that says what to type."""
    airports = data["trip"].get("airports") or []
    if not airports:
        return
    cached = cache_read(AIRPORT_CACHE_FILE)
    store: dict[str, dict] = cached if isinstance(cached, dict) else {}
    dirty = False
    for air in airports:
        code = air["code"]
        if air["lat"] is not None and air["lon"] is not None:
            air["name"] = air["name"] or code
            air["source"] = "trip file"
            continue
        hit = None if refresh else store.get(code)
        if not (isinstance(hit, dict) and isinstance(hit.get("lat"), (int, float))
                and isinstance(hit.get("lon"), (int, float))):
            hit = None
        source = "cache"
        if hit is None:
            source = "overpass"
            try:
                hit = airport_from_overpass(code)
            except OverpassError as exc:
                p.err("trip.airport", f"could not reach Overpass to look up {code!r} ({exc}). "
                                      f"{_airport_hint(code)}")
                continue
            if hit is None:
                p.err("trip.airport", f"no airport with iata={code} in OpenStreetMap "
                                      f"(aeroway=aerodrome + iata={code}). Check the code, or "
                                      f"{_airport_hint(code)}")
                continue
            store[code] = hit
            dirty = True
        air["lat"], air["lon"] = float(hit["lat"]), float(hit["lon"])
        air["name"] = air["name"] or str(hit.get("name") or code)
        air["source"] = source
    if dirty:
        cache_write(AIRPORT_CACHE_FILE, store)


def _airport_hint(code: str) -> str:
    return ("add the coordinates by hand:\n"
            f"      airport: {{code: {code}, name: <airport name>, lat: 19.43629, lon: -99.07213}}")


# --- metro lines ----------------------------------------------------------- #


def bbox_around(lat: float, lon: float, radius_m: float) -> tuple[float, float, float, float]:
    """(south, west, north, east) for a square about 2*radius_m across, centred on lat/lon.
    Rounded to 3 dp (~100 m) so a nudged trip.center still hits the same cache entry."""
    dlat = radius_m / 110540.0
    dlon = radius_m / (111320.0 * max(0.05, math.cos(math.radians(lat))))
    south, north = max(-90.0, lat - dlat), min(90.0, lat + dlat)
    west, east = max(-180.0, lon - dlon), min(180.0, lon + dlon)
    return tuple(round(v, 3) for v in (south, west, north, east))  # type: ignore[return-value]


def metro_query(bbox: tuple[float, float, float, float]) -> str:
    """Subway route relations whose geometry is inside the bbox, with member geometry
    inline (`out geom`), so no second pass over ways and nodes is needed."""
    s, w, n, e = bbox
    return (f'[out:json][timeout:{OVERPASS_TIMEOUT_S}];'
            f'relation["type"="route"]["route"="subway"]({s},{w},{n},{e});'
            'out geom;')


def slugify(text: str) -> str:
    out = re.sub(r"[^a-z0-9]+", "-", (text or "").casefold()).strip("-")
    return out[:40] or "city"


def metro_cache_name(city: str, bbox: tuple[float, float, float, float]) -> str:
    """Cache file name keyed by city AND bbox: moving trip.center far enough to change
    the rounded bbox fetches (and keeps) a separate entry."""
    digest = hashlib.sha256(repr(bbox).encode("utf-8")).hexdigest()[:10]
    return f"metro-{slugify(city)}-{digest}.json"


def _metro_colour(tags: dict) -> str | None:
    for key in ("colour", "color"):
        value = str(tags.get(key) or "").strip()
        if CSS_HEX_RE.match(value):
            return value.lower()
        if CSS_HEX_RE.match("#" + value):  # OSM sometimes has a bare "f04e98"
            return ("#" + value).lower()
    return None


def _ref_sort_key(ref: str) -> tuple:
    m = re.match(r"^(\d+)(.*)$", ref)
    return (0, int(m.group(1)), m.group(2)) if m else (1, 0, ref)


def metro_lines_from_overpass(raw: Any, tolerance_m: float = METRO_SIMPLIFY_M) -> list[dict]:
    """Turn an Overpass `out geom` response into one entry per line, ready for the page.

    Grouped by the relation's `ref` (so the two directions of a line become one entry),
    each member way kept as its own polyline (no stitching: Leaflet draws a list of
    segments just as well), deduplicated (the return relation reuses the same ways),
    simplified with Douglas-Peucker and rounded to 5 dp."""
    groups: dict[str, dict] = {}
    elements = (raw or {}).get("elements") or [] if isinstance(raw, dict) else []
    for el in sorted((e for e in elements if isinstance(e, dict)),
                     key=lambda e: (e.get("type") or "", e.get("id") or 0)):
        if el.get("type") != "relation":
            continue
        tags = el.get("tags") or {}
        ref = str(tags.get("ref") or "").strip()
        name = str(tags.get("name") or "").strip()
        key = ref or name
        if not key:
            continue
        g = groups.setdefault(key, {"ref": ref or name, "names": set(), "colour": None,
                                    "segs": {}})
        if name:
            g["names"].add(name)
        g["colour"] = g["colour"] or _metro_colour(tags)
        for member in el.get("members") or []:
            if not isinstance(member, dict) or member.get("type") != "way":
                continue
            # "" is the route itself; platform/stop members are furniture, not track.
            if str(member.get("role") or "") not in ("", "forward", "backward"):
                continue
            pts = []
            for point in member.get("geometry") or []:
                if not isinstance(point, dict):
                    continue
                lat, lon = point.get("lat"), point.get("lon")
                if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                    pts.append((round(float(lat), METRO_COORD_DP),
                                round(float(lon), METRO_COORD_DP)))
            pts = [pt for i, pt in enumerate(pts) if i == 0 or pt != pts[i - 1]]
            if len(pts) < 2:
                continue
            forward, back = tuple(pts), tuple(reversed(pts))
            g["segs"].setdefault(min(forward, back), pts)

    lines = []
    for i, key in enumerate(sorted(groups, key=_ref_sort_key)):
        g = groups[key]
        segs = [[[lat, lon] for lat, lon in simplify_line(pts, tolerance_m)]
                for _, pts in sorted(g["segs"].items())]
        segs = [s for s in segs if len(s) >= 2]
        if not segs:
            continue
        lines.append({
            "ref": g["ref"],
            "name": min(g["names"]) if g["names"] else g["ref"],
            "colour": g["colour"] or METRO_FALLBACK_COLOURS[i % len(METRO_FALLBACK_COLOURS)],
            "segs": segs,
        })
    return lines


def simplify_line(points: list[tuple[float, float]], tolerance_m: float) -> list[tuple[float, float]]:
    """Douglas-Peucker on (lat, lon) points, tolerance in metres.

    Distances are measured on a local equirectangular projection (good to well under a
    metre over a city). The first and last points are always kept, so a simplified line
    starts and ends exactly where the original did. Iterative: a 10 000-point way would
    blow the recursion limit."""
    if len(points) < 3 or tolerance_m <= 0:
        return list(points)
    k = math.cos(math.radians(points[0][0]))
    xy = [(lon * 111320.0 * k, lat * 110540.0) for lat, lon in points]
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        if b <= a + 1:
            continue
        ax, ay = xy[a]
        dx, dy = xy[b][0] - ax, xy[b][1] - ay
        den = math.hypot(dx, dy)
        worst, at = -1.0, -1
        for i in range(a + 1, b):
            px, py = xy[i]
            d = (math.hypot(px - ax, py - ay) if den == 0
                 else abs(dy * (px - ax) - dx * (py - ay)) / den)
            if d > worst:
                worst, at = d, i
        if worst > tolerance_m:
            keep[at] = True
            stack.append((a, at))
            stack.append((at, b))
    return [pt for pt, k2 in zip(points, keep) if k2]


def metro_point_count(lines: list[dict]) -> int:
    return sum(len(seg) for line in lines for seg in line["segs"])


def resolve_metro(data: dict, p: Problems, refresh: bool = False) -> None:
    """Fetch (or reuse) the city's subway route relations and store them in data["metro"].

    Only runs when the trip asked for a metro layer (`map: {metro: on|off}`). Anything
    that goes wrong here is a WARNING and the page is built without the layer: metro
    lines are a reference overlay, never the point of the page."""
    want = data.get("map", {}).get("metro")
    centre = data["trip"].get("center") or {}
    if want is None or centre.get("lat") is None or centre.get("lon") is None:
        return
    bbox = bbox_around(centre["lat"], centre["lon"], METRO_RADIUS_M)
    name = metro_cache_name(data["trip"].get("city") or "", bbox)
    cached = None if refresh else cache_read(name)
    raw = (cached or {}).get("response") if isinstance(cached, dict) else None
    source = "cache"
    if raw is None:
        try:
            raw = overpass_get(metro_query(bbox))
        except OverpassError as exc:
            p.warn("map.metro", f"no metro layer: {exc}. The page is built without it; run again "
                                "with --refresh-transit when the network is back.")
            return
        source = "overpass"
        cache_write(name, {"meta": {"city": data["trip"].get("city"), "bbox": list(bbox),
                                    "query": metro_query(bbox), "url": OVERPASS_URL,
                                    "fetched": _today()},
                           "response": raw})
    lines = metro_lines_from_overpass(raw)
    if not lines:
        p.warn("map.metro", f"no subway route relations in OpenStreetMap around "
                            f"{centre['lat']}, {centre['lon']} (bbox {bbox}); the page is built "
                            "with no metro layer.")
        return
    data["metro"] = {"lines": lines, "on": bool(want), "source": source, "cache": name,
                     "bbox": list(bbox)}


def resolve_transit(data: dict, p: Problems, refresh: bool = False) -> None:
    """The one network-touching step of a build. Everything it fetches is cached on disk,
    so a second build of the same trip makes no request at all."""
    resolve_airports(data, p, refresh=refresh)
    resolve_metro(data, p, refresh=refresh)


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def load_theme(name: str) -> dict[str, str]:
    raw = json.loads((THEMES_DIR / f"{name}.json").read_text(encoding="utf-8"))
    return {k: v for k, v in raw.items() if isinstance(v, str) and HEX_COLOUR_RE.match(v)}


def theme_css(theme: dict[str, str]) -> str:
    """Every hex colour in the theme becomes --theme-<key> (underscores -> hyphens)."""
    lines = [f"  --theme-{k.replace('_', '-')}: {v};" for k, v in sorted(theme.items())]
    return ":root {\n" + "\n".join(lines) + "\n}"


# Categories whose display name isn't just the capitalised word. Sent to the page script
# too (page_json -> catLabels), so the panel and the map popup always agree.
CATEGORY_LABELS = {"daytrip": "Day trip"}


def pretty_category(cat: str) -> str:
    label = CATEGORY_LABELS.get((cat or "").lower())
    return label if label else cat.replace("_", " ").replace("-", " ").capitalize()


def markdown_to_html(md: str) -> str:
    """Deliberately tiny Markdown subset: headings, paragraphs, - / 1. lists,
    ``` code blocks, `code`, **bold**, *italic*, [text](http-url). Everything is
    HTML-escaped first; anything unsupported shows as plain text."""
    out: list[str] = []
    para: list[str] = []
    list_tag: str | None = None
    in_code = False
    code: list[str] = []

    def flush_para() -> None:
        if para:
            out.append("<p>" + " ".join(_inline(x) for x in para) + "</p>")
            para.clear()

    def close_list() -> None:
        nonlocal list_tag
        if list_tag:
            out.append(f"</{list_tag}>")
            list_tag = None

    for line in md.splitlines():
        if line.strip().startswith("```"):
            if in_code:
                out.append("<pre><code>" + esc("\n".join(code)) + "</code></pre>")
                code.clear()
                in_code = False
            else:
                flush_para(); close_list()
                in_code = True
            continue
        if in_code:
            code.append(line)
            continue
        stripped = line.strip()
        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        bullet = re.match(r"^[-*+]\s+(.*)$", stripped)
        number = re.match(r"^\d+[.)]\s+(.*)$", stripped)
        if not stripped:
            flush_para(); close_list()
        elif heading:
            flush_para(); close_list()
            level = min(len(heading.group(1)) + 2, 6)  # page already uses h1/h2
            out.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
        elif bullet or number:
            flush_para()
            tag = "ul" if bullet else "ol"
            if list_tag != tag:
                close_list()
                out.append(f"<{tag}>")
                list_tag = tag
            out.append("<li>" + _inline((bullet or number).group(1)) + "</li>")
        else:
            close_list()
            para.append(stripped)
    if in_code:
        out.append("<pre><code>" + esc("\n".join(code)) + "</code></pre>")
    flush_para(); close_list()
    return "\n".join(out)


LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
# Italic content can't contain the delimiter, so each attempt stops at the next '*'/'_':
# linear time even on a line made entirely of asterisks.
ITALIC_STAR_RE = re.compile(r"(?<![\w*])\*([^*\s](?:[^*]*[^*\s])?)\*(?![\w*])")
ITALIC_UNDER_RE = re.compile(r"(?<![\w_])_([^_\s](?:[^_]*[^_\s])?)_(?![\w_])")


def _emphasis(s: str) -> str:
    s = BOLD_RE.sub(r"<strong>\1</strong>", s)
    s = ITALIC_STAR_RE.sub(r"<em>\1</em>", s)
    return ITALIC_UNDER_RE.sub(r"<em>\1</em>", s)


def _inline(text: str) -> str:
    parts = re.split(r"(`[^`]+`)", text)
    rendered = []
    for part in parts:
        if len(part) > 2 and part.startswith("`") and part.endswith("`"):
            rendered.append("<code>" + esc(part[1:-1]) + "</code>")
            continue
        s = esc(part)
        # Emphasis applies to the text around links and to link text, never to the URL.
        pos, out = 0, []
        for m in LINK_RE.finditer(s):
            out.append(_emphasis(s[pos:m.start()]))
            out.append(f'<a href="{m.group(2)}" rel="noopener noreferrer" target="_blank">'
                       f'{_emphasis(m.group(1))}</a>')
            pos = m.end()
        out.append(_emphasis(s[pos:]))
        rendered.append("".join(out))
    return "".join(rendered)


def fmt_day(d: dt.date) -> str:
    return f"{d.strftime('%a')} {d.day} {d.strftime('%b')}"


def fmt_day_year(d: dt.date, trip_year: int | None) -> str:
    """fmt_day, plus the year when it isn't the trip's own (a kept event in another year)."""
    return fmt_day(d) if d.year == trip_year else f"{fmt_day(d)} {d.year}"


def fmt_range(start: dt.date, end: dt.date) -> str:
    days = (end - start).days + 1
    if start.year == end.year:
        text = f"{fmt_day(start)} – {fmt_day(end)} {end.year}"
    else:
        text = f"{fmt_day(start)} {start.year} – {fmt_day(end)} {end.year}"
    return f"{text} · {days} day{'s' if days != 1 else ''}"


def ext_link(url: str | None, name: str | None) -> str:
    """A small '↗' link to `url`, opening in a new tab, for the side lists.

    Always rendered OUTSIDE the checkbox <label> and outside the pan-to-map <button>:
    inside a <label> a click would toggle the checkbox, and an <a> inside a <button> is
    invalid HTML. As a plain anchor it stays in the tab order, so it is keyboard
    reachable. Returns "" when there is no url, so callers can concatenate it blindly."""
    if not url:
        return ""
    label = f"Open the {name or 'place'} website in a new tab"
    # The leading space keeps the glyph off the name even with no CSS.
    return (f' <a class="ext" href="{esc(url)}" target="_blank" rel="noopener noreferrer" '
            f'title="{esc(label)}" aria-label="{esc(label)}"><span aria-hidden="true">↗</span></a>')


def render_popular_panel(popular: list[dict]) -> str:
    if not popular:
        return '<p class="muted">No popular places listed.</p>'
    by_cat: dict[str, list[tuple[int, dict]]] = {}
    for i, place in enumerate(popular):
        by_cat.setdefault(place["category"], []).append((i, place))
    blocks = []
    for cat in sorted(by_cat):
        items = "\n".join(
            f'      <li><label><input type="checkbox" class="toggle-place" data-id="{esc(pl["id"])}"'
            f' data-category="{esc(cat)}"{" checked" if pl["default_on"] else ""}> {esc(pl["name"])}</label>'
            f'{ext_link(pl.get("url"), pl["name"])}</li>'
            for _, pl in by_cat[cat]
        )
        blocks.append(
            f'  <fieldset class="cat">\n'
            f'    <legend><label><input type="checkbox" class="toggle-cat" data-category="{esc(cat)}">'
            f' {esc(pretty_category(cat))} <span class="muted">({len(by_cat[cat])})</span></label></legend>\n'
            f'    <ul>\n{items}\n    </ul>\n  </fieldset>'
        )
    return "\n".join(blocks)


def render_ours_list(ours: list[dict]) -> str:
    if not ours:
        return '<p class="muted">None yet.</p>'
    items = []
    for place in ours:
        label = f"{place['label']} (approximate area)" if place.get("approx") else place["name"]
        # A stay under `approximate` has already had its url stripped by apply_privacy, and
        # under `hidden` it is not in this list at all. This guard keeps that true even if a
        # later change starts carrying the field through.
        url = None if place.get("approx") else place.get("url")
        items.append(f'    <li><button type="button" class="linkish focus-place" data-id="{esc(place["id"])}">'
                     f'{esc(label)}</button>{ext_link(url, label)}</li>')
    return "  <ul class=\"ours\">\n" + "\n".join(items) + "\n  </ul>"


def render_events(data: dict) -> str:
    trip, events = data["trip"], data["events"]
    by_day: dict[dt.date, list[tuple[int, dict]]] = {}
    for i, ev in enumerate(events):
        by_day.setdefault(ev["date"], []).append((i, ev))
    days = []
    day = trip["start"]
    while day <= trip["end"]:
        entries = by_day.get(day, [])
        if entries:
            lis = "\n".join(_render_event(i, ev) for i, ev in entries)
            inner = f'      <ul class="events">\n{lis}\n      </ul>'
        else:
            inner = '      <p class="muted">Nothing scheduled.</p>'
        days.append(f'    <li class="day" id="day-{day.isoformat()}">\n'
                    f'      <h3>{esc(fmt_day(day))}</h3>\n{inner}\n    </li>')
        day += dt.timedelta(days=1)
    return '  <ol class="days">\n' + "\n".join(days) + "\n  </ol>"


OUTSIDE_HEADING = "Just outside your dates"


def render_outside(data: dict) -> str:
    """Events kept with `keep: true` though they fall outside start..end.

    Rendered below the day-by-day list, sorted by date, each showing its own date
    (weekday included) since there is no day heading above it. Nothing is emitted when
    no event was kept. The data-event indexes continue the in-range ones, matching the
    order page_json writes (in-range first, then these)."""
    outside = data.get("outside") or []
    if not outside:
        return ""
    trip_year = data["trip"]["start"].year if data["trip"].get("start") else None
    base = len(data["events"])
    lis = "\n".join(_render_event(base + j, ev, show_date=True, trip_year=trip_year)
                    for j, ev in enumerate(outside))
    return ('  <div class="outside">\n'
            f'    <h3 class="outside-h">{esc(OUTSIDE_HEADING)}</h3>\n'
            f'      <ul class="events">\n{lis}\n      </ul>\n'
            '  </div>')


def _render_event(i: int, ev: dict, show_date: bool = False, trip_year: int | None = None) -> str:
    """One event row. `show_date` is set only in the "Just outside your dates" section,
    where the row carries its own date because no day heading precedes it."""
    badge = "Our plan" if ev["kind"] == "plan" else "City event"
    name = esc(ev["name"])
    if ev["loc"]:
        name = (f'<button type="button" class="linkish event-go" data-event="{i}" '
                f'title="Show on map">{name} <span aria-hidden="true">⌖</span></button>')
    bits = [f'<span class="badge">{badge}</span>']
    if show_date:
        bits.append(f'<span class="ev-date">{esc(fmt_day_year(ev["date"], trip_year))}</span>')
    bits += [f'<span class="time">{esc(ev["time"] or "All day")}</span>',
             f'<span class="ev-name">{name}{ext_link(ev.get("url"), ev["name"])}</span>']
    if ev["booked"] is True:
        bits.append('<span class="tag">Booked</span>')
    elif ev["booked"] is False:
        bits.append('<span class="tag tag--todo">Not booked</span>')
    extra = []
    if ev["notes"]:
        extra.append(f'<span class="notes">{esc(ev["notes"])}</span>')
    # `url` is the '↗' beside the name above (one affordance per link, same as the places
    # list); `source` stays here as a worded link. The popup shows both as worded links.
    if ev["source"]:
        extra.append(f'<a class="source" href="{esc(ev["source"])}" rel="noopener noreferrer" '
                     f'target="_blank">Source</a>')
    extra_html = f'<div class="ev-extra">{" ".join(extra)}</div>' if extra else ""
    return (f'        <li class="event event--{esc(ev["kind"])}">'
            f'<div class="ev-main">{" ".join(bits)}</div>{extra_html}</li>')


PLACE_KEYS = ("group", "id", "name", "category", "lat", "lon", "default_on", "address", "notes", "url",
              "approx", "radius", "label")
AIRPORT_KEYS = ("code", "name", "lat", "lon")
# page_json is written with indent=1 for readability, which would be ruinous for thousands
# of metro coordinates (one array element per line). The lines are spliced in compactly.
METRO_PLACEHOLDER = "@@metro-lines@@"


def metro_lines_json(lines: list[dict]) -> str:
    """The metro lines as compact JSON: no spaces, coordinates already at 5 dp."""
    return json.dumps(lines, ensure_ascii=False, separators=(",", ":"))


def metro_sidecar_json(lines: list[dict]) -> str:
    return json.dumps({"lines": lines}, ensure_ascii=False, separators=(",", ":"))


def plan_metro_output(data: dict) -> str | None:
    """Choose inline vs sibling file for the metro geometry, by size.

    Sets data["metro"]["inline"] and ["bytes"]. Returns the text for
    dist/<slug>/metro.json when the data is too big to embed, else None."""
    metro = data.get("metro")
    if not metro:
        return None
    size = len(metro_lines_json(metro["lines"]).encode("utf-8"))
    metro["bytes"] = size
    metro["inline"] = size <= METRO_INLINE_MAX_BYTES
    return None if metro["inline"] else metro_sidecar_json(metro["lines"])


def page_json(data: dict) -> str:
    """Trip data for the page script. Escaped so it can't close the <script> tag."""
    t = data["trip"]
    trip_year = t["start"].year if t.get("start") else None
    payload = {
        "trip": {"name": t["name"], "center": t["center"], "zoom": t["zoom"]},
        "maxApproxZoom": APPROX_MAX_ZOOM,
        "catLabels": CATEGORY_LABELS,
        "places": [{k: pl[k] for k in PLACE_KEYS if pl.get(k) is not None}
                   for pl in data["ours"] + data["popular"]],
        # In-range events first, then the ones kept outside the dates: the same order
        # render_events/render_outside number their data-event indexes in.
        "events": [
            {"name": e["name"], "kind": e["kind"], "date": e["date"].isoformat(),
             "day": fmt_day_year(e["date"], trip_year), "time": e["time"], "loc": e["loc"],
             "url": e["url"], "source": e["source"]}
            for e in all_events(data)
        ],
    }
    airports = t.get("airports") or []
    if airports:
        # Airports are reference points, not places: separate list, never in "places",
        # so nothing that walks places (privacy, category toggles, popups) can pick them up.
        payload["airports"] = [{k: a[k] for k in AIRPORT_KEYS} for a in airports]
    metro = data.get("metro")
    if metro:
        payload["metro"] = {"on": bool(metro["on"]), "count": len(metro["lines"])}
        if metro.get("inline", True):
            payload["metro"]["lines"] = METRO_PLACEHOLDER
        else:
            payload["metro"]["url"] = METRO_SIDECAR
    text = json.dumps(payload, ensure_ascii=False, indent=1)
    if metro and metro.get("inline", True):
        text = text.replace(json.dumps(METRO_PLACEHOLDER), metro_lines_json(metro["lines"]), 1)
    return text.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


# Every page this tool writes carries this marker; only marked trip folders are ever pruned.
GENERATOR_META = '<meta name="generator" content="tripsite">'

HEAD_COMMON = """<meta charset="utf-8">
{GENERATOR_META}
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<meta name="referrer" content="strict-origin-when-cross-origin">
<link rel="icon" href="{FAVICON}">""".replace("{FAVICON}", FAVICON).replace("{GENERATOR_META}", GENERATOR_META)


def marker_css() -> str:
    lines = [f"  --mk-{k}: {v};" for k, v in MARKER_COLOURS.items()]
    return ":root {\n" + "\n".join(lines) + "\n}"


LEGEND_ENTRIES = (  # (css class, text); an entry is shown only if its group is on the page
    ("dot--ours", "Our places"),
    ("dot--popular", "Popular places"),
    ("dot--stay", "Where we’re staying (approximate)"),
    ("dot--stay", "Private place (approx.)"),
    ("dot--airport", "Airport"),
    ("dot--metro", "Metro lines"),
)


def render_legend(data: dict) -> str:
    approx_kinds = {pl.get("approx_kind") for pl in data["ours"] if pl.get("approx")}
    present = (any(not pl.get("approx") for pl in data["ours"]), bool(data["popular"]),
               "stay" in approx_kinds, "private" in approx_kinds,
               bool(data["trip"].get("airports")), bool(data.get("metro")))
    items = [f'<span class="dot {cls}"></span> {esc(text)}'
             for (cls, text), on in zip(LEGEND_ENTRIES, present) if on]
    if not items:
        return ""
    return '      <span class="legend">' + "\n      ".join(items) + "</span>"


def render_transit_panel(data: dict) -> str:
    """The "Getting around" block in the side panel: one Airport checkbox (default ON,
    it is a reference point) and one Metro lines checkbox (default from `map.metro`),
    plus a compact colour-chip legend of the line numbers. Nothing is emitted when the
    trip has neither."""
    airports = data["trip"].get("airports") or []
    metro = data.get("metro")
    if not airports and not metro:
        return ""
    blocks = ["    <h2>Getting around</h2>"]
    if airports:
        items = "\n".join(
            f'      <li><button type="button" class="linkish focus-airport" data-air="{i}">'
            f'{esc(a["code"])} — {esc(a["name"])}</button></li>'
            for i, a in enumerate(airports))
        blocks.append(
            '  <fieldset class="cat">\n'
            '    <legend><label><input type="checkbox" id="toggle-airport" checked> '
            f'Airport <span class="muted">({len(airports)})</span></label></legend>\n'
            f'    <ul>\n{items}\n    </ul>\n  </fieldset>')
    if metro:
        chips = "\n".join(
            f'      <li title="{esc(line["name"])}"><span class="mswatch" aria-hidden="true" '
            f'style="background:{esc(line["colour"])}"></span>{esc(line["ref"])}</li>'
            for line in metro["lines"])
        checked = " checked" if metro["on"] else ""
        blocks.append(
            '  <fieldset class="cat">\n'
            f'    <legend><label><input type="checkbox" id="toggle-metro"{checked}> '
            f'Metro lines <span class="muted">({len(metro["lines"])})</span></label></legend>\n'
            f'    <ul class="metro-legend">\n{chips}\n    </ul>\n  </fieldset>')
    return "\n".join(blocks)


def render_trip_page(data: dict, body: str, theme: dict[str, str]) -> str:
    t = data["trip"]
    about = markdown_to_html(body) if body.strip() else '<p class="muted">Nothing here yet.</p>'
    legend = render_legend(data)
    return f"""<!doctype html>
<html lang="en">
<head>
{HEAD_COMMON}
<title>{esc(t["name"])}</title>
<link rel="stylesheet" href="{LEAFLET_CSS_URL}" integrity="{LEAFLET_CSS_SRI}" crossorigin="">
<style>
{theme_css(theme)}
{marker_css()}
{PAGE_CSS}
</style>
</head>
<body>
<header class="site-header">
  <h1>{esc(t["name"])}</h1>
  <p class="meta">{esc(fmt_range(t["start"], t["end"]))} · {esc(t["city"])}, {esc(t["country"])}</p>
</header>
<main>
<section class="map-section" aria-label="Map">
  <div class="map-wrap">
    <div id="map" role="region" aria-label="Map of places"></div>
    <p class="map-tools">
      <button type="button" id="fit-all" class="linkish">Show all places on map</button>
{legend}
    </p>
  </div>
  <aside class="panel">
    <h2>Our places</h2>
{render_ours_list(data["ours"])}
    <h2>Popular places</h2>
{render_popular_panel(data["popular"])}
{render_transit_panel(data)}
  </aside>
</section>
<section class="events-section" aria-labelledby="events-h">
  <h2 id="events-h">Schedule</h2>
  <p class="muted legend-events"><span class="badge badge--plan">Our plan</span>
    <span class="badge badge--city">City event</span> · Times are local ({esc(t["timezone"])}).
    Click an event with ⌖ to show it on the map.</p>
{render_events(data)}
{render_outside(data)}
</section>
<section class="about" aria-labelledby="about-h">
  <h2 id="about-h">About this trip</h2>
{about}
</section>
</main>
<footer class="site-footer"><p class="muted">Private trip page. Map data © OpenStreetMap contributors.</p></footer>
<script type="application/json" id="trip-data">
{page_json(data)}
</script>
<script src="{LEAFLET_JS_URL}" integrity="{LEAFLET_JS_SRI}" crossorigin=""></script>
<script>
{PAGE_JS}
</script>
</body>
</html>
"""


def render_root_index() -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
{HEAD_COMMON}
<title>World Cities</title>
<style>
  body {{ font-family: system-ui, sans-serif; display: grid; place-items: center; min-height: 100vh;
         margin: 0; background: #F5EDE4; color: #8B4513; }}
</style>
</head>
<body>
<main><h1>World Cities</h1></main>
</body>
</html>
"""


def render_not_found() -> str:
    """dist/404.html. With a top-level 404.html, Cloudflare Pages answers a missing path
    with this page and status 404; without one it treats the site as a single-page app and
    serves index.html with 200. Neutral: no trip slugs, same look as the root placeholder."""
    return f"""<!doctype html>
<html lang="en">
<head>
{HEAD_COMMON}
<title>Not found</title>
<style>
  body {{ font-family: system-ui, sans-serif; display: grid; place-items: center; min-height: 100vh;
         margin: 0; background: #F5EDE4; color: #8B4513; }}
</style>
</head>
<body>
<main><h1>Not found</h1></main>
</body>
</html>
"""


ROBOTS_TXT = "User-agent: *\nDisallow: /\n"
HEADERS_TXT = "/*\n  X-Robots-Tag: noindex, nofollow\n"
SITE_FILES = ("index.html", "404.html", "robots.txt", "_headers")
# What may legitimately sit inside dist/<slug>/. metro.json is written only when the metro
# geometry is too big to embed in the page (see plan_metro_output).
TRIP_FILES = ("index.html", METRO_SIDECAR)


PAGE_CSS = """
:root {
  --bg: var(--theme-bg, #fff);
  --text: var(--theme-text, #222);
  --accent: var(--theme-road-motorway, var(--text));
  --accent-2: var(--theme-road-primary, var(--accent));
  --soft: var(--theme-parks, #eee);
  --line: var(--theme-road-residential, #ccc);
  --city: var(--theme-water, #9bc);
}
* { box-sizing: border-box; }
html { background: var(--bg); color: var(--text); }
body { margin: 0 auto; max-width: 1200px; padding: 1rem 1.25rem 2rem;
       font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
h1 { margin: 0; font-size: 2rem; letter-spacing: .02em; }
h2 { font-size: 1.2rem; margin: 1.5rem 0 .5rem; }
h3 { font-size: 1rem; margin: 0 0 .25rem; }
a { color: var(--accent); }
.meta { margin: .25rem 0 1rem; }
.muted { opacity: .75; }
.site-header { border-bottom: 3px solid var(--accent); margin-bottom: 1rem; }
.map-section { display: grid; grid-template-columns: minmax(0, 1fr) 300px; gap: 1rem; align-items: start; }
#map { height: 520px; border: 2px solid var(--line); border-radius: 6px; }
.map-tools { display: flex; flex-wrap: wrap; gap: .5rem 1.25rem; justify-content: space-between;
             font-size: .9rem; margin: .4rem 0 0; }
.dot { display: inline-block; width: .9em; height: .9em; border-radius: 50%; vertical-align: -.1em;
       border: 2px solid var(--mk-outline); box-shadow: 0 0 0 1px rgba(0, 0, 0, .45); margin-left: .5em; }
.dot--ours { background: var(--mk-ours); }
.dot--popular { background: var(--mk-popular); }
/* white ring behind the dark dashes so the edge shows on dark themes (noir) too */
.dot--stay { background: color-mix(in srgb, var(--mk-stay) 30%, #fff); border: 2px dashed var(--mk-stay-edge);
             box-shadow: 0 0 0 2px var(--mk-outline); }
.dot--airport { background: var(--mk-airport); }
/* the metro swatch is a bar, not a dot: it stands for lines, not a pin */
.dot--metro { width: 1.6em; height: .35em; border-radius: 2px; border: 0;
              background: linear-gradient(90deg, #E53935 0 33%, #1E88E5 33% 66%, #43A047 66%); }
/* airport marker: an amber disc with a white plane, deliberately unlike the round pins */
.mk-air { background: none; border: 0; }
.mk-air svg { display: block; filter: drop-shadow(0 0 1px rgba(0, 0, 0, .45)); }
.metro-legend { display: flex; flex-wrap: wrap; gap: .1rem .5rem; font-size: .85rem;
                font-variant-numeric: tabular-nums; }
.metro-legend li { display: flex; align-items: center; gap: .25rem; margin: .1rem 0; }
.mswatch { display: inline-block; width: .8rem; height: .5rem; border-radius: 2px;
           box-shadow: 0 0 0 1px rgba(0, 0, 0, .35); }
.popup hr { border: 0; border-top: 1px solid #ccc; margin: .4rem 0; }
.panel { background: var(--soft); border-radius: 6px; padding: .25rem 1rem 1rem; max-height: 560px; overflow: auto; }
.panel h2:first-child { margin-top: .75rem; }
.panel ul { list-style: none; margin: 0; padding: 0; }
.panel li { margin: .15rem 0; }
.cat { border: 1px solid var(--line); border-radius: 4px; margin: 0 0 .6rem; padding: .25rem .6rem .4rem; }
.cat legend { font-weight: 600; padding: 0 .25rem; }
.cat ul { padding-left: 1.2rem; }
label { cursor: pointer; }
.linkish { background: none; border: 0; padding: 0; font: inherit; color: var(--accent);
           text-decoration: underline; cursor: pointer; text-align: left; }
/* '↗' website link in the side lists; outside the label/button so it only follows the link */
.ext { text-decoration: none; color: var(--accent); padding: 0 .2rem; font-size: .9em; }
.ext:hover, .ext:focus { text-decoration: underline; }
.ext:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; border-radius: 2px; }
.days { list-style: none; padding: 0; margin: 0; display: grid;
        grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: .75rem; }
.day { border: 1px solid var(--line); border-radius: 6px; padding: .6rem .75rem; }
.events { list-style: none; margin: 0; padding: 0; }
.event { padding: .4rem .5rem; margin: .35rem 0; border-radius: 4px; border-left: 5px solid; }
.event--plan { border-left-color: var(--accent); background: var(--soft); }
.event--city { border-left-color: var(--city); border-left-style: dashed; }
.ev-main { display: flex; flex-wrap: wrap; gap: .1rem .5rem; align-items: baseline; }
.ev-name { font-weight: 600; }
.ev-date { font-size: .9rem; font-weight: 600; }
.ev-extra { font-size: .9rem; margin-top: .15rem; }
/* the kept-outside-the-dates block: below the day grid, visibly separate from it */
.outside { margin-top: 1rem; border-top: 1px dashed var(--line); padding-top: .5rem; }
.outside-h { font-size: 1rem; margin: 0 0 .25rem; }
.outside .events { max-width: 640px; }
.ev-extra .source { margin-left: .4rem; }
.time { font-variant-numeric: tabular-nums; font-size: .9rem; }
.badge { font-size: .7rem; text-transform: uppercase; letter-spacing: .06em; padding: .05rem .4rem;
         border-radius: 3px; background: var(--accent); color: var(--bg); }
.event--city .badge, .badge--city { background: var(--city); color: var(--text); }
.badge--plan { background: var(--accent); color: var(--bg); }
.tag { font-size: .75rem; border: 1px solid var(--line); border-radius: 3px; padding: 0 .3rem; }
.tag--todo { border-style: dashed; }
.about { border-top: 1px solid var(--line); margin-top: 1.5rem; }
.popup strong { display: block; }
.popup p { margin: .25rem 0; }
.popup .cat-label { font-size: .8rem; opacity: .75; }
.site-footer { margin-top: 2rem; font-size: .85rem; }
@media (max-width: 800px) {
  body { padding: .75rem; }
  h1 { font-size: 1.5rem; }
  .map-section { grid-template-columns: 1fr; }
  #map { height: 60vh; min-height: 320px; }
  .panel { max-height: none; }
  .days { grid-template-columns: 1fr; }
}
"""


PAGE_JS = r"""
(function () {
  "use strict";
  if (!window.L) {
    document.getElementById("map").textContent = "Map could not load (Leaflet unavailable).";
    return;
  }
  var data = JSON.parse(document.getElementById("trip-data").textContent);
  var style = getComputedStyle(document.documentElement);
  function cssVar(name, fallback) { return style.getPropertyValue(name).trim() || fallback; }
  // Map features use a fixed tile-safe palette (see MARKER_COLOURS), not the theme.
  var C = {
    outline: cssVar("--mk-outline", "#fff"),
    ours: cssVar("--mk-ours", "#C62828"),
    popular: cssVar("--mk-popular", "#1565C0"),
    event: cssVar("--mk-event", "#00695C"),
    stay: cssVar("--mk-stay", "#7B1FA2"),
    stayEdge: cssVar("--mk-stay-edge", "#2A0A3A"),
    airport: cssVar("--mk-airport", "#EF6C00")
  };
  var MAX_APPROX_ZOOM = data.maxApproxZoom || 14;

  var map = L.map("map", { scrollWheelZoom: false })
    .setView([data.trip.center.lat, data.trip.center.lon], data.trip.zoom);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  }).addTo(map);
  map.on("focus", function () { map.scrollWheelZoom.enable(); });
  map.on("blur", function () { map.scrollWheelZoom.disable(); });

  function el(tag, text, cls) {
    var n = document.createElement(tag);
    if (text != null) n.textContent = text;
    if (cls) n.className = cls;
    return n;
  }
  function isHttp(u) { return typeof u === "string" && /^https?:\/\//i.test(u); }
  function link(href, text) {
    var a = el("a", text);
    a.href = href; a.target = "_blank"; a.rel = "noopener noreferrer";
    return a;
  }
  function gmaps(lat, lon) {
    return "https://www.google.com/maps/search/?api=1&query=" + lat + "," + lon;
  }
  // Category display names come from the page data (build.CATEGORY_LABELS), so the
  // popup and the side panel can't drift apart.
  var CAT_LABELS = data.catLabels || {};
  function pretty(cat) {
    var key = String(cat || "").toLowerCase();
    if (CAT_LABELS[key]) return CAT_LABELS[key];
    var s = String(cat || "").replace(/[_-]/g, " ");
    return s.charAt(0).toUpperCase() + s.slice(1);
  }

  function placePopup(p) {
    var box = el("div", null, "popup");
    if (p.approx) {
      box.appendChild(el("strong", p.label || "Private place"));
      box.appendChild(el("p", "Approximate area (about " + p.radius + " m).", "cat-label"));
      return box;
    }
    box.appendChild(el("strong", p.name));
    box.appendChild(el("span", pretty(p.category) + (p.group === "ours" ? " · our place" : ""), "cat-label"));
    if (p.address) box.appendChild(el("p", p.address));
    if (p.notes) box.appendChild(el("p", p.notes));
    var links = el("p");
    if (isHttp(p.url)) {
      links.appendChild(link(p.url, "Website"));
      links.appendChild(document.createTextNode(" · "));
    }
    links.appendChild(link(gmaps(p.lat, p.lon), "Open in Google Maps"));
    box.appendChild(links);
    return box;
  }

  var layers = {};   // place id -> Leaflet layer
  var placeById = {};
  data.places.forEach(function (p) {
    placeById[p.id] = p;
    var layer;
    if (p.approx) {
      layer = L.circle([p.lat, p.lon], {
        radius: p.radius, color: C.stayEdge, weight: 2.5, dashArray: "6 5",
        fillColor: C.stay, fillOpacity: 0.22
      });
    } else if (p.group === "ours") {
      layer = L.circleMarker([p.lat, p.lon], {
        radius: 10, color: C.outline, weight: 3, fillColor: C.ours, fillOpacity: 1
      });
    } else {
      layer = L.circleMarker([p.lat, p.lon], {
        radius: 7, color: C.outline, weight: 2, fillColor: C.popular, fillOpacity: 0.95
      });
    }
    layer.bindPopup(placePopup(p));
    layers[p.id] = layer;
    if (p.group === "ours" || p.default_on) layer.addTo(map);
  });

  // Popular-place checkboxes: one per place, plus one per category.
  var placeBoxes = Array.prototype.slice.call(document.querySelectorAll(".toggle-place"));
  var catBoxes = Array.prototype.slice.call(document.querySelectorAll(".toggle-cat"));
  function syncCategory(cat) {
    var boxes = placeBoxes.filter(function (b) { return b.dataset.category === cat; });
    var on = boxes.filter(function (b) { return b.checked; }).length;
    catBoxes.forEach(function (cb) {
      if (cb.dataset.category !== cat) return;
      cb.checked = on === boxes.length;
      cb.indeterminate = on > 0 && on < boxes.length;
    });
  }
  function setPlace(box, on) {
    box.checked = on;
    var layer = layers[box.dataset.id];
    if (!layer) return;
    if (on) layer.addTo(map); else map.removeLayer(layer);
  }
  placeBoxes.forEach(function (box) {
    box.addEventListener("change", function () {
      setPlace(box, box.checked);
      syncCategory(box.dataset.category);
    });
  });
  catBoxes.forEach(function (cb) {
    cb.addEventListener("change", function () {
      placeBoxes.forEach(function (b) { if (b.dataset.category === cb.dataset.category) setPlace(b, cb.checked); });
      syncCategory(cb.dataset.category);
    });
    syncCategory(cb.dataset.category);
  });

  function showMap() {
    var box = document.getElementById("map").getBoundingClientRect();
    if (box.top < 0 || box.bottom > window.innerHeight) {
      document.getElementById("map").scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }
  function focusLayer(layer, approx) {
    var target = layer.getLatLng();
    // Never zoom in far on an approximate area: its centre is deliberately not the stay.
    var zoom = approx ? MAX_APPROX_ZOOM : Math.max(map.getZoom(), 15);
    map.setView(target, zoom);
    layer.openPopup();
    showMap();
  }
  function eventHeader(ev) {
    var box = el("div");
    box.appendChild(el("strong", ev.name));
    box.appendChild(el("span", (ev.kind === "plan" ? "Our plan" : "City event") + " · " + ev.day +
      " · " + (ev.time || "All day"), "cat-label"));
    // url = the thing itself ("Website"); source = where the info came from ("Source").
    var links = el("p");
    if (isHttp(ev.url)) links.appendChild(link(ev.url, "Website"));
    if (isHttp(ev.source)) {
      if (links.childNodes.length) links.appendChild(document.createTextNode(" · "));
      links.appendChild(link(ev.source, "Source"));
    }
    if (links.childNodes.length) box.appendChild(links);
    return box;
  }
  function focusPlace(id, ev) {
    var layer = layers[id], p = placeById[id];
    if (!layer) return;
    if (!map.hasLayer(layer)) {
      var box = placeBoxes.filter(function (b) { return b.dataset.id === id; })[0];
      if (box) { setPlace(box, true); syncCategory(box.dataset.category); } else layer.addTo(map);
    }
    if (ev) {
      // Event + place in one popup; the plain place popup comes back when it closes.
      var combo = el("div", null, "popup");
      combo.appendChild(eventHeader(ev));
      combo.appendChild(el("hr"));
      combo.appendChild(placePopup(p));
      layer.setPopupContent(combo);
      layer.once("popupclose", function () { layer.setPopupContent(placePopup(p)); });
    }
    focusLayer(layer, !!p.approx);
  }

  // One shared marker for events with their own {lat, lon}: moved, never stacked.
  var eventMarker = null;
  function focusEvent(i) {
    var ev = data.events[i];
    if (!ev || !ev.loc) return;
    if (ev.loc.ref) { focusPlace(ev.loc.ref, ev); return; }
    var ll = [ev.loc.lat, ev.loc.lon];
    if (!eventMarker) {
      eventMarker = L.circleMarker(ll, {
        radius: 8, color: C.outline, weight: 3, fillColor: C.event, fillOpacity: 1
      }).bindPopup("");
    }
    var box = el("div", null, "popup");
    box.appendChild(eventHeader(ev));
    if (ev.loc.label) box.appendChild(el("p", ev.loc.label));
    var links = el("p");
    links.appendChild(link(gmaps(ev.loc.lat, ev.loc.lon), "Open in Google Maps"));
    box.appendChild(links);
    eventMarker.closePopup();
    eventMarker.setLatLng(ll).setPopupContent(box);
    if (!map.hasLayer(eventMarker)) eventMarker.addTo(map);
    focusLayer(eventMarker, false);
  }

  // --- Airports ------------------------------------------------------------
  // Reference points, never places: their own list in the page data, their own marker
  // shape (an amber disc with a white plane, not a circle), their own checkbox, and no
  // part in the category toggles, the privacy rules or the initial view.
  var PLANE_SVG = '<svg viewBox="0 0 24 24" width="26" height="26" aria-hidden="true">' +
    '<circle cx="12" cy="12" r="10.5" fill="' + C.airport + '" stroke="' + C.outline +
    '" stroke-width="2"/><g transform="translate(12 12) scale(.58) translate(-12 -12)">' +
    '<path fill="' + C.outline + '" d="M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 ' +
    '3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z"/></g></svg>';
  var airIcon = L.divIcon({ className: "mk-air", html: PLANE_SVG, iconSize: [26, 26],
                            iconAnchor: [13, 13], popupAnchor: [0, -13] });
  function airportPopup(a) {
    var box = el("div", null, "popup");
    box.appendChild(el("strong", a.name || a.code));
    box.appendChild(el("span", "Airport · " + a.code, "cat-label"));
    var links = el("p");
    links.appendChild(link(gmaps(a.lat, a.lon), "Open in Google Maps"));
    box.appendChild(links);
    return box;
  }
  var airports = data.airports || [];
  var airportLayers = [];
  var airportGroup = L.layerGroup();
  var airBox = document.getElementById("toggle-airport");
  airports.forEach(function (a) {
    var m = L.marker([a.lat, a.lon], { icon: airIcon, alt: "Airport " + a.code,
                                       title: a.code + " — " + (a.name || "") });
    m.bindPopup(airportPopup(a));
    airportLayers.push(m);
    airportGroup.addLayer(m);
  });
  if (airports.length) {
    if (!airBox || airBox.checked) airportGroup.addTo(map);   // on by default
    if (airBox) airBox.addEventListener("change", function () {
      if (airBox.checked) airportGroup.addTo(map); else map.removeLayer(airportGroup);
    });
  }
  function focusAirport(i) {
    var m = airportLayers[i];
    if (!m) return;
    if (!map.hasLayer(airportGroup)) {
      if (airBox) airBox.checked = true;
      airportGroup.addTo(map);
    }
    // animate:false on purpose. The airport is usually far outside the current view, and
    // an animated pan is cut short by the popup's own auto-pan (openPopup nudges the map
    // relative to wherever the animation has got to), leaving the map stranded part-way.
    map.setView(m.getLatLng(), Math.max(map.getZoom(), 12), { animate: false });
    m.openPopup();
    showMap();
  }

  // --- Metro lines ---------------------------------------------------------
  // One checkbox for the whole network. The lines go in their own pane below the
  // overlay pane, so they never draw over a pin or swallow a click.
  var metro = data.metro || null;
  var metroGroup = null, metroDrawn = false, metroPending = false;
  var metroBox = document.getElementById("toggle-metro");
  if (metro) {
    map.createPane("metro");
    map.getPane("metro").style.zIndex = 380;
    metroGroup = L.layerGroup();
  }
  function drawMetro(lines) {
    (lines || []).forEach(function (ln) {
      (ln.segs || []).forEach(function (seg) {
        L.polyline(seg, { color: ln.colour, weight: 3, opacity: 0.85, interactive: false,
                          pane: "metro", smoothFactor: 1.5 }).addTo(metroGroup);
      });
    });
    metroDrawn = true;
  }
  function showMetro(on) {
    if (!metroGroup) return;
    if (!on) { map.removeLayer(metroGroup); return; }
    if (!metroDrawn && metro.lines) drawMetro(metro.lines);
    if (metroDrawn) { metroGroup.addTo(map); return; }
    if (metroPending || !metro.url) return;
    metroPending = true;   // sibling metro.json: fetched the first time it is switched on
    fetch(metro.url, { credentials: "same-origin" })
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(function (j) {
        drawMetro(j.lines);
        if (!metroBox || metroBox.checked) metroGroup.addTo(map);
      })
      .catch(function (err) { console.warn("metro lines not loaded:", err.message); })
      .then(function () { metroPending = false; });
  }
  if (metro && metroBox) {
    metroBox.addEventListener("change", function () { showMetro(metroBox.checked); });
    if (metroBox.checked) showMetro(true);
  }

  document.addEventListener("click", function (e) {
    if (!e.target.closest) return;
    // The '↗' links in the side lists open normally: never pan the map, never toggle a
    // checkbox (they also sit outside the <label>, so label activation can't fire either).
    if (e.target.closest("a[href]")) return;
    var t = e.target.closest(".event-go, .focus-place, .focus-airport");
    if (!t) return;
    if (t.classList.contains("event-go")) focusEvent(Number(t.dataset.event));
    else if (t.classList.contains("focus-airport")) focusAirport(Number(t.dataset.air));
    else focusPlace(t.dataset.id);
  });

  // Places and airports (event markers excluded); an approximate area counts as its whole
  // circle. Metro lines are deliberately left out: a 30 km network would zoom the trip away.
  document.getElementById("fit-all").addEventListener("click", function () {
    var bounds = null;
    Object.keys(layers).forEach(function (id) {
      var l = layers[id];
      if (!map.hasLayer(l)) return;
      var b = placeById[id].approx ? l.getBounds() : L.latLngBounds([l.getLatLng()]);
      bounds = bounds ? bounds.extend(b) : b;
    });
    if (map.hasLayer(airportGroup)) {
      airportLayers.forEach(function (m) {
        var b = L.latLngBounds([m.getLatLng()]);
        bounds = bounds ? bounds.extend(b) : b;
      });
    }
    if (bounds) map.fitBounds(bounds, { padding: [30, 30], maxZoom: MAX_APPROX_ZOOM });
  });
})();
"""


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


JUNK_FILES = (".DS_Store",)


NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


def is_real_file(path: Path) -> bool:
    """True only for a regular file. A symlink is never followed (always False)."""
    try:
        return stat.S_ISREG(path.lstat().st_mode)
    except OSError:
        return False


_HTML_COMMENT_RE = re.compile(rb"<!--.*?(?:-->|\Z)", re.DOTALL)
_HEAD_END_RE = re.compile(rb"</head\s*>|<body[\s>]", re.IGNORECASE)


def has_marker(path: Path) -> bool:
    """True if path is a real file (not a symlink) whose <head> carries GENERATOR_META.

    Only the first 4096 bytes are read. HTML comments are ignored, and so is everything
    from </head> (or <body>) on, so a hand-made page that mentions the marker in its body
    or in a comment is not mistaken for one of ours."""
    if not is_real_file(path):
        return False
    try:
        fd = os.open(path, os.O_RDONLY | NOFOLLOW)
    except OSError:
        return False
    with os.fdopen(fd, "rb") as fh:
        head = _HTML_COMMENT_RE.sub(b"", fh.read(4096))
    end = _HEAD_END_RE.search(head)
    if end:
        head = head[:end.start()]
    return GENERATOR_META.encode("utf-8") in head


def write_file(path: Path, text: str) -> None:
    """Write text to a temp file in path's folder, then os.replace it into place.

    Replacing (not truncating) means a hardlinked output gets a new inode and the other
    link keeps its content. os.replace over a symlink would swap the link itself, so a
    symlink is refused first (plan_out_dir refuses those earlier still)."""
    if path.is_symlink():
        raise OSError(f"{path} is a symlink; refusing to replace it")
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        if os.path.lexists(tmp):
            os.unlink(tmp)
        raise


def plan_out_dir(out_dir: Path, slugs: set[str]) -> tuple[list[Path], list[str]]:
    """Decide what to remove so out_dir holds only SITE_FILES and the slugs being built.

    Returns (paths to delete, problems). Only things this tool writes are ever deleted:
    a stale trip folder is removed only if it matches the slug pattern and holds nothing
    but an index.html carrying GENERATOR_META (plus .DS_Store). Symlinks are never
    followed, written through or deleted. Anything else is reported, never deleted."""
    remove: list[Path] = []
    problems: list[str] = []
    if not out_dir.exists():
        return remove, problems
    if not out_dir.is_dir():
        return remove, [f"{out_dir} exists and is not a folder"]
    not_ours = "was not written by this tool"
    for entry in sorted(out_dir.iterdir()):
        if entry.is_symlink():
            problems.append(f"{entry} is a symlink, so it {not_ours} (never followed or replaced)")
            continue
        if entry.name in SITE_FILES and is_real_file(entry):
            continue
        if entry.name in JUNK_FILES and is_real_file(entry):
            remove.append(entry)
            continue
        if entry.is_dir() and SLUG_RE.match(entry.name):
            inner = sorted(entry.iterdir())
            links = [f for f in inner if f.is_symlink()]
            for f in links:
                problems.append(f"{f} is a symlink, so it {not_ours} (never followed or replaced)")
            if links:
                continue
            if all(is_real_file(f) and f.name in TRIP_FILES + JUNK_FILES for f in inner):
                if entry.name in slugs:  # rebuilt now: its index.html is overwritten
                    remove.extend(f for f in inner if f.name in JUNK_FILES)
                    continue
                if not any(f.name == "index.html" for f in inner):  # empty, or .DS_Store only
                    problems.append(f"{entry} has no index.html, so it {not_ours} (not deleted)")
                    continue
                if has_marker(entry / "index.html"):
                    remove.extend(inner + [entry])
                    continue
                problems.append(f"{entry} has no tripsite marker in index.html, so it {not_ours} "
                                "(not deleted)")
                continue
        problems.append(f"{entry} {not_ours}")
    return remove, problems


def slugs_in(out_dir: Path) -> list[str]:
    if not out_dir.is_dir():
        return []
    return sorted(d.name for d in out_dir.iterdir() if d.is_dir() and (d / "index.html").is_file())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Build a static trip website from trip profiles. Pass EVERY live trip in one run "
                    "(e.g. trips/*.md): the output folder is trimmed to exactly these trips.")
    ap.add_argument("trip_files", type=Path, nargs="+", metavar="trip_file",
                    help="trip profile(s), e.g. trips/mexico-city-2026.md or trips/*.md")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"output folder (default: {DEFAULT_OUT})")
    ap.add_argument("--dry-run", action="store_true", help="validate and report, write nothing")
    ap.add_argument("--refresh-transit", action="store_true",
                    help="re-fetch the airport coordinates and metro lines from Overpass, "
                         f"ignoring (and replacing) what is cached in {DEFAULT_CACHE_DIR}")
    args = ap.parse_args(argv)

    # 1. Validate every trip; nothing is written unless all of them pass.
    trips: list[tuple[Path, dict, str, int]] = []
    failed = 0
    slug_owner: dict[str, Path] = {}
    for path in args.trip_files:
        data, body, p = load_trip(path)
        dropped = 0
        if not p.errors:
            dropped = filter_events(data, p)
            apply_privacy(data, body, p)
            # The only step that may touch the network, and only for a trip that asked
            # for an airport or a metro layer. Everything it fetches is cached on disk.
            resolve_transit(data, p, refresh=args.refresh_transit)
            slug = data["trip"]["slug"]
            if slug in slug_owner:
                p.err("trip.slug", f"{slug!r} is also used by {slug_owner[slug]}")
            slug_owner.setdefault(slug, path)
        for w in p.warnings:
            print(f"warning: {path}: {w}", file=sys.stderr)
        if p.errors:
            print(f"error: {path} has {len(p.errors)} problem(s):", file=sys.stderr)
            for e in p.errors:
                print(f"  - {e}", file=sys.stderr)
            failed += 1
            continue
        trips.append((path, data, body, dropped))
    if failed:
        return 1

    # 2. Render and run the leak scan before touching the output folder.
    pages: dict[str, str] = {}
    sidecars: dict[str, str | None] = {}
    for path, data, body, dropped in trips:
        t = data["trip"]
        print(f"trip:    {t['name']} ({t['start']} → {t['end']}), theme {t['theme']}, slug {t['slug']}")
        print(f"places:  {len(data['ours'])} ours (stay: {data['privacy']['hotel_display']}), "
              f"{len(data['popular'])} popular")
        for air in t.get("airports") or []:
            print(f"airport: {air['code']} {air['name']} at {air['lat']}, {air['lon']} "
                  f"(from {air['source']})")
        sidecars[t["slug"]] = plan_metro_output(data)
        metro = data.get("metro")
        if metro:
            where = "embedded in the page" if metro["inline"] else f"written to {METRO_SIDECAR}"
            print(f"metro:   {len(metro['lines'])} line(s), {metro_point_count(metro['lines'])} "
                  f"points, {metro['bytes'] / 1024:.0f} KB {where}, default "
                  f"{'on' if metro['on'] else 'off'} (from {metro['source']}: {metro['cache']})")
        print(f"events:  {len(data['events'])} kept, {len(data['outside'])} kept outside the "
              f"dates (keep: true), {dropped} dropped (outside trip dates)")
        for ev in data["outside"]:
            print(f"         kept outside the dates: '{ev['name']}' on {ev['date']}")
        page = render_trip_page(data, body, load_theme(t["theme"]))
        leaks = scan_for_leaks(page, data.get("_private_stays", []))
        if leaks:
            print(f"error: {path}: privacy check failed, nothing written "
                  f"(hotel_display: {data['privacy']['hotel_display']}):", file=sys.stderr)
            for leak in leaks:
                print(f"  - {leak}", file=sys.stderr)
            print("  Remove it from the body, event names/notes and other places, then rebuild.",
                  file=sys.stderr)
            return 1
        pages[t["slug"]] = page

    # 3. Output folder: exactly the site files + the slugs built now.
    out_dir = args.out.resolve()
    remove, problems = plan_out_dir(out_dir, set(pages))
    if problems:
        print(f"error: {out_dir} holds things this tool didn't write, and a Pages upload would publish "
              "them. Move them out (or use a fresh --out folder):", file=sys.stderr)
        for prob in problems:
            print(f"  - {prob}", file=sys.stderr)
        return 1
    stale = sorted({p.name for p in remove if p.is_dir()})
    if args.dry_run:
        print(f"dry run: would write {', '.join(sorted(pages))} and {', '.join(SITE_FILES)} in {out_dir}")
        if stale:
            print(f"dry run: would REMOVE stale trip folder(s) not in this run: {', '.join(stale)}")
        return 0

    for path in remove:  # files first, then the (now empty) stale folders
        if is_real_file(path):
            path.unlink()
    for path in remove:
        if path.is_dir() and not path.is_symlink():
            path.rmdir()
    for slug, page in pages.items():
        (out_dir / slug).mkdir(parents=True, exist_ok=True)
        write_file(out_dir / slug / "index.html", page)
        side = out_dir / slug / METRO_SIDECAR
        if sidecars.get(slug) is not None:
            write_file(side, sidecars[slug] or "")
        elif is_real_file(side):
            side.unlink()  # a previous build wrote one; this page embeds its metro data
    write_file(out_dir / "index.html", render_root_index())
    write_file(out_dir / "404.html", render_not_found())
    write_file(out_dir / "robots.txt", ROBOTS_TXT)
    write_file(out_dir / "_headers", HEADERS_TXT)
    for slug in sorted(pages):
        print(f"wrote:   {out_dir / slug / 'index.html'}")
        if sidecars.get(slug) is not None:
            print(f"         {out_dir / slug / METRO_SIDECAR}  (metro geometry, loaded on demand; "
                  "it must be uploaded with the page)")
    for name in SITE_FILES:
        print(f"         {out_dir / name}")
    if stale:
        print(f"removed: stale trip folder(s) not in this run: {', '.join(stale)}")
    held = slugs_in(out_dir)
    if out_dir == DEFAULT_OUT.resolve():  # the deploy folder: say what an upload would do
        print(f"\ndist now holds {len(held)} trip(s): {', '.join(held)}")
        print("  Each needs its own Access app before upload (tripsite/README.md, Deploy). An upload replaces the "
              "whole site, so any live trip not built in this run would be taken down.")
    else:
        print(f"\n{out_dir} now holds {len(held)} trip(s): {', '.join(held)}")
    print("\npreview (file:// may not load OSM tiles because it sends no Referer):")
    print(f"  python -m http.server -d {out_dir}")
    for slug in sorted(pages):
        print(f"  open http://localhost:8000/{slug}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
