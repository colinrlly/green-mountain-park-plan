"""
Vercel serverless function: GET /api/trails

Queries OpenStreetMap (Overpass API) for trails inside the Hayden Park bbox,
returns them as GeoJSON LineString features with status="existing", and
merges in any hand-maintained non-existing features (proposed-new,
to-be-removed) from data/trails.geojson.

The response is cached at Vercel's edge for 24h (stale-while-revalidate 7d)
so Overpass is hit at most once per day per region — well under their fair
use limit.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler
from pathlib import Path

BBOX = (39.685, -105.185, 39.720, -105.135)  # south, west, north, east
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
QUERY = f"""
[out:json][timeout:55];
(
  way["highway"~"path|footway|track|bridleway|cycleway"]
    ({BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]});
);
out geom tags;
""".strip()


def fetch_overpass() -> dict:
    body = urllib.parse.urlencode({"data": QUERY}).encode()
    req = urllib.request.Request(
        OVERPASS_URL,
        data=body,
        headers={"User-Agent": "green-mountain-park-plan/0.1 (citizen-science viewer)"},
    )
    with urllib.request.urlopen(req, timeout=55) as resp:
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


def load_handmaintained() -> list[dict]:
    path = Path(__file__).resolve().parent.parent / "data" / "trails.geojson"
    if not path.exists():
        return []
    try:
        fc = json.loads(path.read_text())
    except (ValueError, OSError):
        return []
    return [
        f for f in fc.get("features", [])
        if (f.get("properties") or {}).get("status") != "existing"
    ]


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            data = fetch_overpass()
            osm_features = [
                f for f in (way_to_feature(w) for w in data.get("elements", []))
                if f
            ]
            features = load_handmaintained() + osm_features
            body = {
                "type": "FeatureCollection",
                "_source": (
                    "Existing trails from OpenStreetMap via Overpass API. "
                    "Non-existing features merged from data/trails.geojson."
                ),
                "_count": {
                    "existing": len(osm_features),
                    "other": len(features) - len(osm_features),
                },
                "features": features,
            }
            payload = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/geo+json; charset=utf-8")
            self.send_header(
                "Cache-Control",
                "public, s-maxage=86400, stale-while-revalidate=604800",
            )
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except Exception as exc:
            err = json.dumps({"error": type(exc).__name__, "message": str(exc)}).encode()
            self.send_response(502)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(err)))
            self.end_headers()
            self.wfile.write(err)
