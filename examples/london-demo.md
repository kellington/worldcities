---
# Trip profile for tripsite (see tripsite/README.md).
# PUBLIC FICTIONAL EXAMPLE, committed to the repo on purpose. The trip, the dates and the
# plans are invented; there are no real people in it. Every place is a well-known public
# landmark or a public hotel. Real trip profiles live in trips/, which is gitignored.
#
# Build it (writes to examples/site/, never to dist/):
#   uv run tripsite/build.py examples/london-demo.md --out examples/site
#
# Coordinates: looked up via Nominatim (OpenStreetMap) on 2026-09-22 unless marked otherwise.
# Links: official sites, checked 2026-09-22. Some answer a plain curl with 403 (bot
#   protection) but open normally in a browser; they are marked "403 to curl".
# Times: always quote them ("11:00"), otherwise YAML may read 11:00 as a number.

trip:
  name: London in Spring (demo)
  slug: london-demo                     # a public demo: no random suffix needed. A real
                                        # trip should add one (see tripsite/README.md)
  start: 2027-04-10                     # Sat
  end: 2027-04-16                       # Fri
  timezone: Europe/London
  city: London
  country: United Kingdom
  center: {lat: 51.5070, lon: -0.1150}  # between Westminster and the City
  zoom: 12
  theme: midnight_blue
  airport: LHR                          # resolved once from Overpass, then cached

privacy:
  hotel_display: exact   # a public hotel, so the exact pin is fine here
  noindex: true

# Reference layers on the map.
map:
  metro: on    # London Underground lines drawn at load; `off` keeps the checkbox, lines hidden

# Our places: always shown on the map.
locations:
  - id: savoy
    name: The Savoy
    category: stay
    address: Strand, London WC2R 0EZ
    lat: 51.5101273     # coords: nominatim ("Savoy Hotel, 105-109, Strand"), verify
    lon: -0.1204993
    url: https://www.thesavoylondon.com/
    notes: "Fictional stay for the demo. Five minutes' walk to Covent Garden and the river."

# Popular places: toggleable pins.
popular:
  - id: british-museum
    name: British Museum
    category: museum
    lat: 51.5193118     # coords: nominatim, verify
    lon: -0.1267051
    default_on: true
    url: https://www.britishmuseum.org/           # 403 to curl

  - id: tower-of-london
    name: Tower of London
    category: sight
    lat: 51.5082170     # coords: nominatim, verify
    lon: -0.0761879
    default_on: true
    url: https://www.hrp.org.uk/tower-of-london/  # 403 to curl

  - id: buckingham-palace
    name: Buckingham Palace
    category: sight
    lat: 51.5008349     # coords: nominatim, verify
    lon: -0.1430045
    default_on: true
    url: https://www.rct.uk/visit/buckingham-palace   # 403 to curl

  - id: westminster-abbey
    name: Westminster Abbey
    category: sight
    lat: 51.4993990     # coords: nominatim, verify
    lon: -0.1273910
    default_on: true
    url: https://www.westminster-abbey.org/

  - id: big-ben
    name: Big Ben (Elizabeth Tower)
    category: sight
    lat: 51.5006944     # coords: nominatim, verify
    lon: -0.1245749
    default_on: false

  - id: st-pauls
    name: St Paul's Cathedral
    category: sight
    lat: 51.5137872     # coords: nominatim, verify
    lon: -0.0984506
    default_on: false
    url: https://www.stpauls.co.uk/

  - id: tate-modern
    name: Tate Modern
    category: museum
    lat: 51.5074293     # coords: nominatim, verify
    lon: -0.0993416
    default_on: true
    url: https://www.tate.org.uk/visit/tate-modern

  - id: natural-history-museum
    name: Natural History Museum
    category: museum
    lat: 51.4965109     # coords: nominatim, verify
    lon: -0.1760019
    default_on: false
    url: https://www.nhm.ac.uk/

  - id: borough-market
    name: Borough Market
    category: market
    lat: 51.5055264     # coords: nominatim, verify
    lon: -0.0904380
    default_on: true
    url: https://boroughmarket.org.uk/

  - id: covent-garden
    name: Covent Garden Market
    category: market
    lat: 51.5119791     # coords: nominatim, verify
    lon: -0.1227413
    default_on: false
    url: https://www.coventgarden.london/

  - id: columbia-road
    name: Columbia Road Flower Market
    category: market
    lat: 51.5292185     # coords: nominatim, verify
    lon: -0.0696196
    default_on: false
    url: https://www.columbiaroad.info/
    notes: "Sundays only."

  - id: hyde-park
    name: Hyde Park
    category: park
    lat: 51.5074889     # coords: nominatim, verify
    lon: -0.1622074
    default_on: true
    url: https://www.royalparks.org.uk/visit/parks/hyde-park

  - id: kew-gardens
    name: Royal Botanic Gardens, Kew
    category: daytrip
    lat: 51.4781974     # coords: nominatim, verify
    lon: -0.2968861
    default_on: true
    url: https://www.kew.org/                     # 403 to curl
    notes: "About 45 minutes west by District line or Overground."

  - id: royal-observatory
    name: Royal Observatory Greenwich
    category: daytrip
    lat: 51.4773623     # coords: nominatim, verify
    lon: -0.0008456
    default_on: false
    url: https://www.rmg.co.uk/royal-observatory

# Plans are fictional. "city" events are real recurring ceremonies or markets, shown for
# illustration only: their days and times vary, so check the source before relying on one.
events:
  - date: 2027-04-10
    kind: plan
    name: Arrive at Heathrow, check in
    location: savoy
    notes: "Piccadilly line or Elizabeth line into town."

  - date: 2027-04-11
    time: "10:00"
    kind: plan
    name: British Museum
    location: british-museum
    url: https://www.britishmuseum.org/

  - date: 2027-04-12
    time: "11:00"
    kind: city
    name: Changing of the Guard (illustrative)
    location: buckingham-palace
    source: https://www.householddivision.org.uk/changing-the-guard
    notes: "Illustrative: the ceremony does not run every day. Check the official schedule."

  - date: 2027-04-12
    time: "14:00"
    kind: plan
    name: Walk along the Thames past Big Ben and the Abbey
    location: big-ben

  - date: 2027-04-13
    time: "09:30"
    kind: plan
    name: Tower of London and the Crown Jewels
    location: tower-of-london
    booked: true
    url: https://www.hrp.org.uk/tower-of-london/
    notes: "Fictional booking for the demo."

  - date: 2027-04-14
    time: "12:00"
    kind: plan
    name: Lunch at Borough Market, then Tate Modern
    location: borough-market

  - date: 2027-04-14
    time: "17:00"
    kind: city
    name: Choral Evensong at Westminster Abbey (illustrative)
    location: westminster-abbey
    source: https://www.westminster-abbey.org/worship/
    notes: "Illustrative: service times vary. Check the Abbey's worship page."

  - date: 2027-04-15
    kind: plan
    name: Day trip to Kew Gardens
    location: kew-gardens

  - date: 2027-04-16
    time: "11:00"
    kind: city
    name: Household Cavalry guard change (illustrative)
    location:
      lat: 51.5046617     # coords: nominatim ("Horse Guards Parade"), verify
      lon: -0.1282623
      label: Horse Guards Parade
    source: https://www.householddivision.org.uk/changing-the-guard
    notes: "Illustrative: an inline location rather than a place id, to show the feature."

  - date: 2027-04-16
    time: "15:00"
    kind: plan
    name: Greenwich and the Royal Observatory
    location: royal-observatory

  - date: 2027-04-18
    time: "08:00"
    kind: city
    keep: true          # outside start..end, but kept: shown under "Just outside your dates"
    name: Columbia Road Flower Market (illustrative)
    location: columbia-road
    url: https://www.columbiaroad.info/
    notes: "Illustrative: a Sunday market, two days after the demo trip ends."
---

# London in Spring (demo)

This is a **fictional example trip** that ships with the worldcities repo. The dates and plans are made up; the places are real public landmarks.

A week in London to show what a trip page looks like:

- **The stay** is pinned exactly (`hotel_display: exact`). A real trip can use `approximate` or `hidden` instead.
- **Popular places** can be switched on and off one at a time or by category.
- **Events** are grouped by day. `plan` is ours; `city` is something happening in town.
- **Getting around** shows Heathrow and the London Underground lines.

See `tripsite/README.md` for the full profile format.
