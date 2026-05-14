#!/usr/bin/env python3
"""
Fetch existing trails in William F. Hayden Park from OpenStreetMap via the
Overpass API and merge them into data/trails.geojson as features with
status="existing".

Any features in the file whose status is NOT "existing" (i.e. hand-digitized
"new" or "removed" lines) are preserved untouched. Only the existing-trail
features are rewritten from OSM.

Run from the repo root:

    python3 scripts/fetch_osm_trails.py
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

# Park bbox (south, west, north, east) — generous, covers all of Hayden Park.
BBOX = (39.685, -105.185, 39.720, -105.135)
OUTPUT = Path(__file__).resolve().parent.parent / "data" / "trails.geojson"

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
QUERY = f"""
[out:json][timeout:60];
(
  way["highway"~"path|footway|track|bridleway|cycleway"]
    ({BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]});
);
out geom tags;
""".strip()


def fetch_overpass() -> dict:
    body = urllib.parse.urlencode({"data": QUERY}).encode()
    req = urllib.request.Request(OVERPASS_URL, data=body)
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.load(resp)


def way_to_feature(way: dict) -> dict | None:
    geom = way.get("geometry") or []
    if len(geom) < 2:
        return None
    tags = way.get("tags") or {}
    name = tags.get("name") or tags.get("ref") or f"OSM way {way['id']}"
    return {
        "type": "Feature",
        "properties": {
            "name": name,
            "status": "existing",
            "osm_id": way["id"],
            "highway": tags.get("highway"),
            "surface": tags.get("surface"),
            "bicycle": tags.get("bicycle"),
            "foot": tags.get("foot"),
            "horse": tags.get("horse"),
        },
        "geometry": {
            "type": "LineString",
            "coordinates": [[pt["lon"], pt["lat"]] for pt in geom],
        },
    }


def load_existing() -> dict:
    if not OUTPUT.exists():
        return {"type": "FeatureCollection", "features": []}
    return json.loads(OUTPUT.read_text())


def main() -> int:
    print(f"Querying Overpass for trails in bbox {BBOX} …", file=sys.stderr)
    data = fetch_overpass()
    ways = data.get("elements", [])
    print(f"  got {len(ways)} ways", file=sys.stderr)

    new_existing = [f for f in (way_to_feature(w) for w in ways) if f]
    print(f"  converted {len(new_existing)} to features", file=sys.stderr)

    fc = load_existing()
    preserved = [
        f for f in fc.get("features", [])
        if (f.get("properties") or {}).get("status") != "existing"
    ]
    print(f"  preserving {len(preserved)} non-existing features", file=sys.stderr)

    fc["features"] = preserved + new_existing
    fc.pop("_note", None)
    fc["_note"] = (
        "Existing trails sourced from OpenStreetMap via scripts/fetch_osm_trails.py. "
        "Non-existing features (new / removed) are hand-maintained."
    )

    OUTPUT.write_text(json.dumps(fc, indent=2) + "\n")
    print(f"Wrote {OUTPUT}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
