"""Tests for the airport field and the metro-lines layer (stdlib unittest only).

Run:  uv run python -m unittest tripsite/test_transit.py -v

NOTHING HERE TOUCHES THE NETWORK. Every test either seeds the on-disk cache
(TRIPSITE_CACHE_DIR points at a temp folder) or replaces build.overpass_get with a
stub; the "cache is reused" test replaces it with one that fails the test if it is
called at all. All trip data is fictional apart from the two real IATA codes.
"""

from __future__ import annotations

import contextlib
import io
import json
import math
import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build

SLUG = "transit-trip-4242"

BASE = """\
trip:
  name: Transit Trip
  slug: {slug}
  start: 2026-10-22
  end: 2026-10-24
  timezone: America/Mexico_City
  city: Testville
  country: Testland
  center: {{lat: 19.42, lon: -99.155}}
  zoom: 12
  theme: terracotta
{extra_trip}privacy:
  hotel_display: exact
locations:
  - {{id: inn, name: The Inn, category: food, address: 1 Main St, lat: 19.41, lon: -99.16}}
"""

# One aerodrome node, as Overpass answers aeroway=aerodrome + iata=MEX.
AIRPORT_HIT = {"elements": [{
    "type": "node", "id": 26847302, "lat": 19.43433, "lon": -99.0696,
    "tags": {"aeroway": "aerodrome", "iata": "MEX", "icao": "MMMX",
             "name": "Aeropuerto Internacional Benito Juárez",
             "name:en": "Mexico City International Airport"},
}]}
AIRPORT_MISS: dict = {"elements": []}


def way(points: list[tuple[float, float]], role: str = "") -> dict:
    return {"type": "way", "ref": 1, "role": role,
            "geometry": [{"lat": lat, "lon": lon} for lat, lon in points]}


def relation(rid: int, ref: str, name: str, members: list[dict], colour: str | None = None) -> dict:
    tags = {"type": "route", "route": "subway", "ref": ref, "name": name}
    if colour:
        tags["colour"] = colour
    return {"type": "relation", "id": rid, "tags": tags, "members": members}


# Two lines. Line 1 appears twice (the two running directions share the same way
# geometry, as they do in OSM); line 2 has no colour tag, so it gets a fallback.
LINE1 = [(19.40, -99.20), (19.40, -99.19), (19.40, -99.18), (19.40, -99.17)]
LINE2 = [(19.45, -99.20), (19.44, -99.18), (19.43, -99.16)]
METRO_HIT = {"elements": [
    relation(1, "1", "Línea 1 (A → B)", [way(LINE1), way([(19.4, -99.17)], role="stop")], "#F04E98"),
    relation(2, "1", "Línea 1 (B → A)", [way(list(reversed(LINE1)))], "#F04E98"),
    relation(3, "2", "Línea 2 (C → D)", [way(LINE2)]),
]}
METRO_EMPTY: dict = {"elements": []}


def no_network(*_args, **_kwargs):
    raise AssertionError("overpass_get was called; this build should have used the cache")


class TransitCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.cache = self.tmp / "cache"
        self.cache.mkdir()
        patcher = mock.patch.dict(os.environ, {"TRIPSITE_CACHE_DIR": str(self.cache)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # --- helpers ----------------------------------------------------------- #

    def seed_airport(self, code: str = "MEX", **over) -> None:
        rec = {"code": code, "name": "Cached Airport Name", "lat": 19.43433,
               "lon": -99.0696, "source": "overpass", "fetched": "2026-09-20"}
        rec.update(over)
        (self.cache / build.AIRPORT_CACHE_FILE).write_text(
            json.dumps({code: rec}), encoding="utf-8")

    def seed_metro(self, response: dict) -> str:
        bbox = build.bbox_around(19.42, -99.155, build.METRO_RADIUS_M)
        name = build.metro_cache_name("Testville", bbox)
        (self.cache / name).write_text(json.dumps(
            {"meta": {"city": "Testville", "bbox": list(bbox)}, "response": response}),
            encoding="utf-8")
        return name

    def build(self, extra_trip: str = "", extra_top: str = "", argv: list[str] | None = None
              ) -> tuple[int, str, str]:
        """Returns (exit code, trip page html or '', stderr).

        `extra_trip` is pasted inside the `trip:` mapping, so its two-space indent is
        load-bearing and must NOT be dedented; `extra_top` is top-level."""
        trip = self.tmp / "trip.md"
        trip.write_text("---\n" + BASE.format(slug=SLUG, extra_trip=extra_trip)
                        + textwrap.dedent(extra_top) + "---\n", encoding="utf-8")
        out = self.tmp / "dist"
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            rc = build.main([str(trip), "--out", str(out)] + (argv or []))
        page = out / SLUG / "index.html"
        return rc, (page.read_text(encoding="utf-8") if page.exists() else ""), err.getvalue()

    def payload(self, page: str) -> dict:
        body = page.split('<script type="application/json" id="trip-data">')[1].split("</script>")[0]
        return json.loads(body.replace("\\u0026", "&").replace("\\u003c", "<").replace("\\u003e", ">"))


# --------------------------------------------------------------------------- #
# Airport
# --------------------------------------------------------------------------- #


class TestAirportShortForm(TransitCase):
    def test_short_form_resolved_via_overpass_and_cached(self) -> None:
        with mock.patch.object(build, "overpass_get", return_value=AIRPORT_HIT) as get:
            rc, page, _ = self.build("  airport: MEX\n")
        self.assertEqual(rc, 0)
        self.assertEqual(get.call_count, 1)
        self.assertIn('["iata"="MEX"]', get.call_args[0][0])
        self.assertIn('["aeroway"="aerodrome"]', get.call_args[0][0])
        air = self.payload(page)["airports"]
        self.assertEqual(air, [{"code": "MEX", "name": "Mexico City International Airport",
                                "lat": 19.43433, "lon": -99.0696}])
        # the lookup is written to the shared sidecar, so a later build needs no network
        store = json.loads((self.cache / build.AIRPORT_CACHE_FILE).read_text())
        self.assertEqual(store["MEX"]["lat"], 19.43433)

    def test_lowercase_code_is_accepted(self) -> None:
        with mock.patch.object(build, "overpass_get", return_value=AIRPORT_HIT):
            rc, page, _ = self.build("  airport: mex\n")
        self.assertEqual(rc, 0)
        self.assertEqual(self.payload(page)["airports"][0]["code"], "MEX")

    def test_marker_legend_toggle_and_popup_markup(self) -> None:
        self.seed_airport()
        with mock.patch.object(build, "overpass_get", no_network):
            rc, page, _ = self.build("  airport: MEX\n")
        self.assertEqual(rc, 0)
        self.assertIn('<input type="checkbox" id="toggle-airport" checked>', page)  # on by default
        self.assertIn("Getting around", page)
        self.assertIn('class="linkish focus-airport" data-air="0"', page)
        self.assertIn("dot dot--airport", page)          # its own legend entry
        self.assertIn("MEX — Cached Airport Name", page)
        self.assertIn("airportPopup", page)              # popup: name, code, Google Maps link
        self.assertIn('"Airport · " + a.code', page)
        self.assertIn("--mk-airport: #EF6C00;", page)    # a colour of its own, not a place colour

    def test_airport_is_never_a_place_and_never_a_stay(self) -> None:
        self.seed_airport()
        with mock.patch.object(build, "overpass_get", no_network):
            _, page, _ = self.build("  airport: MEX\n")
        data = self.payload(page)
        self.assertEqual([p["id"] for p in data["places"]], ["inn"])
        self.assertNotIn("MEX", json.dumps(data["places"]))
        self.assertNotIn("stay", json.dumps(data["airports"]))

    def test_initial_view_is_untouched_by_the_airport(self) -> None:
        self.seed_airport()
        with mock.patch.object(build, "overpass_get", no_network):
            _, page, _ = self.build("  airport: MEX\n")
        self.assertEqual(self.payload(page)["trip"]["center"], {"lat": 19.42, "lon": -99.155})
        self.assertEqual(self.payload(page)["trip"]["zoom"], 12)

    def test_focus_does_not_animate_the_pan(self) -> None:
        """Regression, found in the browser on 2026-09-20: with an animated pan, the
        popup's own auto-pan interrupts the flight and the map stops ~600 m into a 9 km
        move. animate:false makes the jump land on the airport every time."""
        self.seed_airport()
        with mock.patch.object(build, "overpass_get", no_network):
            _, page, _ = self.build("  airport: MEX\n")
        focus = page.split("function focusAirport(")[1].split("function ")[0]
        self.assertIn("{ animate: false }", focus)
        self.assertLess(focus.index("map.setView"), focus.index("m.openPopup()"))

    def test_fit_all_includes_the_airport(self) -> None:
        self.seed_airport()
        with mock.patch.object(build, "overpass_get", no_network):
            _, page, _ = self.build("  airport: MEX\n")
        fit = page.split('document.getElementById("fit-all")')[1].split("map.fitBounds")[0]
        self.assertIn("airportLayers.forEach", fit)
        self.assertIn("map.hasLayer(airportGroup)", fit)

    def test_no_airport_means_no_markup_and_no_request(self) -> None:
        with mock.patch.object(build, "overpass_get", no_network):
            rc, page, _ = self.build()
        self.assertEqual(rc, 0)
        # the page script always carries the airport code; the MARKUP is what must be absent
        self.assertNotIn('<input type="checkbox" id="toggle-airport"', page)
        self.assertNotIn("Getting around", page)
        self.assertNotIn("airports", self.payload(page))


class TestAirportLongForm(TransitCase):
    def test_long_form_with_coordinates_makes_no_request(self) -> None:
        with mock.patch.object(build, "overpass_get", no_network):
            rc, page, _ = self.build(
                "  airport: {code: TLC, name: Toluca, lat: 19.337, lon: -99.566}\n")
        self.assertEqual(rc, 0)
        self.assertEqual(self.payload(page)["airports"],
                         [{"code": "TLC", "name": "Toluca", "lat": 19.337, "lon": -99.566}])

    def test_long_form_name_overrides_the_openstreetmap_name(self) -> None:
        with mock.patch.object(build, "overpass_get", return_value=AIRPORT_HIT):
            rc, page, _ = self.build(
                "  airport: {code: MEX, name: Aeropuerto Internacional Benito Juárez}\n")
        self.assertEqual(rc, 0)
        air = self.payload(page)["airports"][0]
        self.assertEqual(air["name"], "Aeropuerto Internacional Benito Juárez")
        self.assertEqual((air["lat"], air["lon"]), (19.43433, -99.0696))  # coords still looked up

    def test_list_of_two_airports(self) -> None:
        self.seed_airport()
        with mock.patch.object(build, "overpass_get", no_network):
            rc, page, _ = self.build(
                "  airport: [MEX, {code: TLC, name: Toluca, lat: 19.337, lon: -99.566}]\n")
        self.assertEqual(rc, 0)
        self.assertEqual([a["code"] for a in self.payload(page)["airports"]], ["MEX", "TLC"])
        self.assertIn('Airport <span class="muted">(2)</span>', page)
        self.assertIn('data-air="1"', page)

    def test_half_a_coordinate_pair_is_rejected(self) -> None:
        with mock.patch.object(build, "overpass_get", no_network):
            rc, _, err = self.build("  airport: {code: TLC, lat: 19.337}\n")
        self.assertEqual(rc, 1)
        self.assertIn("give both lat and lon", err)

    def test_duplicate_codes_rejected(self) -> None:
        with mock.patch.object(build, "overpass_get", no_network):
            rc, _, err = self.build("  airport: [{code: TLC, lat: 1, lon: 1}, "
                                    "{code: TLC, lat: 2, lon: 2}]\n")
        self.assertEqual(rc, 1)
        self.assertIn("duplicate airport code 'TLC'", err)


class TestAirportFailures(TransitCase):
    def test_malformed_iata_code_fails_without_a_request(self) -> None:
        with mock.patch.object(build, "overpass_get", no_network):
            rc, _, err = self.build("  airport: MEXICO\n")
        self.assertEqual(rc, 1)
        self.assertIn("not a 3-letter IATA code", err)

    def test_unknown_iata_code_fails_and_says_what_to_type(self) -> None:
        with mock.patch.object(build, "overpass_get", return_value=AIRPORT_MISS):
            rc, _, err = self.build("  airport: ZZZ\n")
        self.assertEqual(rc, 1)
        self.assertIn("no airport with iata=ZZZ", err)
        self.assertIn("add the coordinates by hand", err)
        self.assertIn("airport: {code: ZZZ, name:", err)

    def test_a_miss_is_not_cached(self) -> None:
        with mock.patch.object(build, "overpass_get", return_value=AIRPORT_MISS):
            self.build("  airport: ZZZ\n")
        store = self.cache / build.AIRPORT_CACHE_FILE
        self.assertFalse(store.exists() and "ZZZ" in store.read_text())

    def test_overpass_down_fails_the_build_with_the_same_hint(self) -> None:
        with mock.patch.object(build, "overpass_get",
                               side_effect=build.OverpassError("boom")):
            rc, _, err = self.build("  airport: MEX\n")
        self.assertEqual(rc, 1)
        self.assertIn("could not reach Overpass", err)
        self.assertIn("add the coordinates by hand", err)


class TestAirportCacheReuse(TransitCase):
    def test_cached_lookup_is_reused_with_no_network_call(self) -> None:
        self.seed_airport()
        with mock.patch.object(build, "overpass_get", no_network):   # calling it fails the test
            rc, page, _ = self.build("  airport: MEX\n")
        self.assertEqual(rc, 0)
        self.assertEqual(self.payload(page)["airports"][0]["name"], "Cached Airport Name")

    def test_refresh_transit_goes_back_to_overpass(self) -> None:
        self.seed_airport()
        with mock.patch.object(build, "overpass_get", return_value=AIRPORT_HIT) as get:
            rc, page, _ = self.build("  airport: MEX\n", argv=["--refresh-transit"])
        self.assertEqual(rc, 0)
        self.assertEqual(get.call_count, 1)
        self.assertEqual(self.payload(page)["airports"][0]["name"],
                         "Mexico City International Airport")


# --------------------------------------------------------------------------- #
# Metro lines
# --------------------------------------------------------------------------- #


class TestMetroMarkup(TransitCase):
    def test_toggle_markup_default_on(self) -> None:
        self.seed_metro(METRO_HIT)
        with mock.patch.object(build, "overpass_get", no_network):
            rc, page, _ = self.build(extra_top="map:\n  metro: on\n")
        self.assertEqual(rc, 0)
        self.assertIn('<input type="checkbox" id="toggle-metro" checked>', page)
        self.assertIn('Metro lines <span class="muted">(2)</span>', page)
        self.assertIn("dot dot--metro", page)                       # legend entry under the map
        self.assertEqual(self.payload(page)["metro"]["on"], True)

    def test_toggle_markup_default_off(self) -> None:
        self.seed_metro(METRO_HIT)
        with mock.patch.object(build, "overpass_get", no_network):
            rc, page, _ = self.build(extra_top="map:\n  metro: off\n")
        self.assertEqual(rc, 0)
        self.assertIn('<input type="checkbox" id="toggle-metro">', page)   # present, not checked
        self.assertNotIn('id="toggle-metro" checked', page)
        self.assertEqual(self.payload(page)["metro"]["on"], False)
        # the data is still on the page, so the checkbox works without a request
        self.assertEqual(len(self.payload(page)["metro"]["lines"]), 2)

    def test_one_checkbox_drives_every_line(self) -> None:
        self.seed_metro(METRO_HIT)
        with mock.patch.object(build, "overpass_get", no_network):
            _, page, _ = self.build(extra_top="map:\n  metro: on\n")
        self.assertEqual(page.count('id="toggle-metro"'), 1)
        self.assertIn('metroBox.addEventListener("change", function () '
                      "{ showMetro(metroBox.checked); });", page)

    def test_compact_line_legend_uses_the_official_colours(self) -> None:
        self.seed_metro(METRO_HIT)
        with mock.patch.object(build, "overpass_get", no_network):
            _, page, _ = self.build(extra_top="map:\n  metro: on\n")
        self.assertIn('<ul class="metro-legend">', page)
        self.assertIn('style="background:#f04e98"', page)     # from the relation's colour tag
        self.assertIn('title="Línea 1 (A → B)"', page)
        self.assertIn(build.METRO_FALLBACK_COLOURS[1], page)  # line 2 has no colour tag

    def test_lines_are_drawn_below_the_pins_and_take_no_clicks(self) -> None:
        self.seed_metro(METRO_HIT)
        with mock.patch.object(build, "overpass_get", no_network):
            _, page, _ = self.build(extra_top="map:\n  metro: on\n")
        self.assertIn('map.createPane("metro")', page)
        self.assertIn('map.getPane("metro").style.zIndex = 380', page)
        self.assertIn("interactive: false", page)

    def test_no_map_section_means_no_metro_and_no_request(self) -> None:
        with mock.patch.object(build, "overpass_get", no_network):
            rc, page, _ = self.build()
        self.assertEqual(rc, 0)
        self.assertNotIn('<input type="checkbox" id="toggle-metro"', page)
        self.assertNotIn("metro", self.payload(page))

    def test_unknown_map_key_warns(self) -> None:
        self.seed_metro(METRO_HIT)
        with mock.patch.object(build, "overpass_get", no_network):
            rc, _, err = self.build(extra_top="map:\n  metro: on\n  tram: on\n")
        self.assertEqual(rc, 0)
        self.assertIn("unknown key 'tram' ignored", err)


class TestMetroEmptyAndFailures(TransitCase):
    def test_no_subway_relations_warns_and_builds_without_the_layer(self) -> None:
        self.seed_metro(METRO_EMPTY)
        with mock.patch.object(build, "overpass_get", no_network):
            rc, page, err = self.build(extra_top="map:\n  metro: on\n")
        self.assertEqual(rc, 0)                       # a warning, never a failed build
        self.assertIn("no subway route relations", err)
        self.assertNotIn('<input type="checkbox" id="toggle-metro"', page)
        self.assertNotIn('<ul class="metro-legend">', page)
        self.assertNotIn("metro", self.payload(page))

    def test_overpass_down_warns_and_builds_without_the_layer(self) -> None:
        with mock.patch.object(build, "overpass_get", side_effect=build.OverpassError("boom")):
            rc, page, err = self.build(extra_top="map:\n  metro: on\n")
        self.assertEqual(rc, 0)
        self.assertIn("no metro layer", err)
        self.assertIn("--refresh-transit", err)
        self.assertNotIn('<input type="checkbox" id="toggle-metro"', page)
        self.assertNotIn("metro", self.payload(page))

    def test_metro_without_a_toggle_value_is_rejected(self) -> None:
        with mock.patch.object(build, "overpass_get", no_network):
            rc, _, err = self.build(extra_top="map:\n  metro:\n")
        self.assertEqual(rc, 1)
        self.assertIn("map.metro: expected on or off", err)


class TestMetroCacheReuse(TransitCase):
    def test_cached_response_is_reused_with_no_network_call(self) -> None:
        name = self.seed_metro(METRO_HIT)
        with mock.patch.object(build, "overpass_get", no_network):
            rc, page, _ = self.build(extra_top="map:\n  metro: on\n")
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.payload(page)["metro"]["lines"]), 2)
        self.assertTrue((self.cache / name).exists())

    def test_first_build_fetches_and_writes_the_raw_response(self) -> None:
        with mock.patch.object(build, "overpass_get", return_value=METRO_HIT) as get:
            rc, _, _ = self.build(extra_top="map:\n  metro: on\n")
        self.assertEqual(rc, 0)
        self.assertEqual(get.call_count, 1)
        ql = get.call_args[0][0]
        self.assertIn('relation["type"="route"]["route"="subway"]', ql)
        self.assertIn("[out:json]", ql)
        self.assertIn("out geom;", ql)
        written = list(self.cache.glob("metro-testville-*.json"))
        self.assertEqual(len(written), 1)
        blob = json.loads(written[0].read_text())
        self.assertEqual(blob["response"], METRO_HIT)     # the RAW response is what is cached
        self.assertEqual(blob["meta"]["city"], "Testville")

    def test_refresh_transit_refetches_and_overwrites_the_cached_response(self) -> None:
        name = self.seed_metro(METRO_EMPTY)          # a stale (empty) cached response
        with mock.patch.object(build, "overpass_get", return_value=METRO_HIT) as get:
            rc, page, _ = self.build(extra_top="map:\n  metro: on\n",
                                     argv=["--refresh-transit"])
        self.assertEqual(rc, 0)
        self.assertEqual(get.call_count, 1)
        self.assertEqual(len(self.payload(page)["metro"]["lines"]), 2)
        self.assertEqual(json.loads((self.cache / name).read_text())["response"], METRO_HIT)

    def test_cache_key_follows_the_bounding_box(self) -> None:
        a = build.metro_cache_name("Testville", build.bbox_around(19.42, -99.155, 30000))
        b = build.metro_cache_name("Testville", build.bbox_around(19.42, -99.155, 30000))
        c = build.metro_cache_name("Testville", build.bbox_around(41.38, 2.17, 30000))
        d = build.metro_cache_name("Barcelona", build.bbox_around(41.38, 2.17, 30000))
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertNotEqual(c, d)


# --------------------------------------------------------------------------- #
# Geometry
# --------------------------------------------------------------------------- #


class TestSimplify(unittest.TestCase):
    def test_endpoints_are_always_kept(self) -> None:
        pts = [(19.4 + i * 0.00002, -99.2 + i * 0.00001) for i in range(200)]
        out = build.simplify_line(pts, 15.0)
        self.assertEqual(out[0], pts[0])
        self.assertEqual(out[-1], pts[-1])
        self.assertLess(len(out), len(pts))
        self.assertGreaterEqual(len(out), 2)

    def test_a_straight_line_collapses_to_its_two_ends(self) -> None:
        pts = [(19.4, -99.2 + i * 0.0005) for i in range(50)]
        self.assertEqual(build.simplify_line(pts, 15.0), [pts[0], pts[-1]])

    def test_a_detour_bigger_than_the_tolerance_survives(self) -> None:
        # the middle point is ~110 m off the straight line: far more than 15 m
        pts = [(19.4, -99.2), (19.401, -99.1), (19.4, -99.0)]
        self.assertEqual(build.simplify_line(pts, 15.0), pts)

    def test_two_point_and_short_lines_are_returned_unchanged(self) -> None:
        self.assertEqual(build.simplify_line([(1.0, 2.0), (3.0, 4.0)], 15.0),
                         [(1.0, 2.0), (3.0, 4.0)])
        self.assertEqual(build.simplify_line([], 15.0), [])

    def test_a_very_long_line_is_handled(self) -> None:
        """20 000 points, the shape of a real (wandering) track. The longest CDMX member
        way is a few hundred points, so this is far past anything OSM will hand us."""
        pts = [(19.4 + math.sin(i / 50.0) * 0.001, -99.2 + i * 0.0001) for i in range(20000)]
        out = build.simplify_line(pts, 15.0)
        self.assertGreater(len(out), 2)
        self.assertLess(len(out), len(pts))

    def test_the_worst_case_shape_does_not_hit_the_recursion_limit(self) -> None:
        """Two diverging rays: Douglas-Peucker's pathological input, where every split
        peels off one point. A recursive implementation would raise RecursionError here
        (2000 > sys.getrecursionlimit()); the iterative one just returns."""
        pts = [(19.4 + i * 0.00001 * (-1 if i % 2 else 1), -99.2 + i * 0.0001)
               for i in range(2000)]
        self.assertGreater(len(build.simplify_line(pts, 15.0)), 2)


class TestMetroParsing(unittest.TestCase):
    def test_both_directions_collapse_into_one_line(self) -> None:
        lines = build.metro_lines_from_overpass(METRO_HIT, 0)
        self.assertEqual([ln["ref"] for ln in lines], ["1", "2"])
        self.assertEqual(len(lines[0]["segs"]), 1)      # the reversed duplicate is dropped

    def test_platform_and_stop_members_are_ignored(self) -> None:
        raw = {"elements": [relation(9, "9", "Línea 9", [
            way([(1.0, 1.0), (1.0, 1.001)], role="platform"),
            way([(1.0, 1.0), (1.0, 1.001)], role="stop"),
            way([(2.0, 2.0), (2.0, 2.001)]),
        ])]}
        lines = build.metro_lines_from_overpass(raw, 0)
        self.assertEqual(lines[0]["segs"], [[[2.0, 2.0], [2.0, 2.001]]])

    def test_colour_tag_forms_and_fallback(self) -> None:
        self.assertEqual(build._metro_colour({"colour": "#F04E98"}), "#f04e98")
        self.assertEqual(build._metro_colour({"color": "f04e98"}), "#f04e98")
        self.assertEqual(build._metro_colour({"colour": "#abc"}), "#abc")
        self.assertIsNone(build._metro_colour({"colour": "red"}))          # not a hex colour
        self.assertIsNone(build._metro_colour({"colour": "#11223344"}))    # alpha: would vanish
        self.assertIsNone(build._metro_colour({}))

    def test_lines_are_ordered_by_number_then_letter(self) -> None:
        raw = {"elements": [relation(i, ref, f"L{ref}", [way([(1.0, 1.0), (1.0, 1.01)])])
                            for i, ref in enumerate(["12", "2", "B", "A", "1"])]}
        self.assertEqual([ln["ref"] for ln in build.metro_lines_from_overpass(raw, 0)],
                         ["1", "2", "12", "A", "B"])

    def test_coordinates_are_rounded_to_five_decimals(self) -> None:
        raw = {"elements": [relation(1, "1", "L1", [way([(19.4823456789, -99.1987654321),
                                                         (19.5, -99.3)])])]}
        self.assertEqual(build.metro_lines_from_overpass(raw, 0)[0]["segs"][0][0],
                         [19.48235, -99.19877])

    def test_junk_elements_do_not_crash_the_parser(self) -> None:
        raw = {"elements": [{"type": "node", "id": 1}, "not a dict", {},
                            {"type": "relation", "id": 2, "tags": {}},
                            {"type": "relation", "id": 3, "tags": {"ref": "7"}, "members": None}]}
        self.assertEqual(build.metro_lines_from_overpass(raw, 0), [])
        self.assertEqual(build.metro_lines_from_overpass({}, 0), [])
        self.assertEqual(build.metro_lines_from_overpass(None, 0), [])


class TestMetroPageWeight(TransitCase):
    def test_small_data_is_embedded_and_no_sibling_file_is_written(self) -> None:
        self.seed_metro(METRO_HIT)
        with mock.patch.object(build, "overpass_get", no_network):
            _, page, _ = self.build(extra_top="map:\n  metro: on\n")
        self.assertIn("lines", self.payload(page)["metro"])
        self.assertNotIn("url", self.payload(page)["metro"])
        self.assertFalse((self.tmp / "dist" / SLUG / build.METRO_SIDECAR).exists())

    def test_big_data_goes_to_a_sibling_file_loaded_on_demand(self) -> None:
        self.seed_metro(METRO_HIT)
        with mock.patch.object(build, "overpass_get", no_network), \
                mock.patch.object(build, "METRO_INLINE_MAX_BYTES", 10):
            rc, page, _ = self.build(extra_top="map:\n  metro: on\n")
        self.assertEqual(rc, 0)
        self.assertEqual(self.payload(page)["metro"]["url"], build.METRO_SIDECAR)
        self.assertNotIn("lines", self.payload(page)["metro"])
        side = self.tmp / "dist" / SLUG / build.METRO_SIDECAR
        self.assertTrue(side.exists())
        self.assertEqual(len(json.loads(side.read_text())["lines"]), 2)
        self.assertIn("fetch(metro.url", page)

    def test_a_stale_sibling_file_is_removed_when_the_data_fits_inline(self) -> None:
        self.seed_metro(METRO_HIT)
        stale = self.tmp / "dist" / SLUG / build.METRO_SIDECAR
        stale.parent.mkdir(parents=True)
        (stale.parent / "index.html").write_text(
            f"<!doctype html><head>{build.GENERATOR_META}</head>old", encoding="utf-8")
        stale.write_text('{"lines": []}', encoding="utf-8")
        with mock.patch.object(build, "overpass_get", no_network):
            rc, _, err = self.build(extra_top="map:\n  metro: on\n")
        self.assertEqual(rc, 0, err)
        self.assertFalse(stale.exists())

    def test_the_geometry_is_not_indented(self) -> None:
        """page_json uses indent=1; thousands of coordinates must not get a line each."""
        self.seed_metro(METRO_HIT)
        with mock.patch.object(build, "overpass_get", no_network):
            _, page, _ = self.build(extra_top="map:\n  metro: on\n")
        block = page.split('"metro":')[1].split("\n}\n</script>")[0]
        self.assertIn('[[19.4,-99.2],', block.replace(" ", ""))


class TestOutputFolderTolerance(TransitCase):
    def test_a_trip_folder_with_a_metro_file_is_still_recognised_as_ours(self) -> None:
        out = self.tmp / "dist"
        stale = out / "old-trip-0001"
        stale.mkdir(parents=True)
        (stale / "index.html").write_text(
            f"<!doctype html><head>{build.GENERATOR_META}</head>old", encoding="utf-8")
        (stale / build.METRO_SIDECAR).write_text('{"lines": []}', encoding="utf-8")
        remove, problems = build.plan_out_dir(out, {SLUG})
        self.assertEqual(problems, [])                       # not "wasn't written by this tool"
        self.assertIn(stale / build.METRO_SIDECAR, remove)
        self.assertIn(stale, remove)


if __name__ == "__main__":
    unittest.main()
