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

# Overpass is anonymous-rate-limited per IP, and Vercel's egress IPs are
# shared with a lot of other clients, so the main instance frequently
# returns 429. Try a chain of public mirrors before giving up.
OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

# Tight bbox around the park (S, W, N, E). Area-polygon filtering is more
# precise but Overpass area lookups blow past Vercel's function timeout.
# Bbox + tag exclusions (no sidewalks, no driveways) gets an equivalent
# result much cheaper.
BBOX = (39.695, -105.180, 39.717, -105.140)
QUERY = f"""
[out:json][timeout:25];
(
  way["highway"~"path|footway|track|bridleway"]
    ["footway"!~"sidewalk|crossing"]
    ["service"!~"driveway|parking_aisle"]
    ({BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]});
);
out geom tags;
""".strip()


def fetch_overpass() -> tuple[dict | None, list[str]]:
    """Try each mirror in order. Return (response, error_log)."""
    body = urllib.parse.urlencode({"data": QUERY}).encode()
    errors: list[str] = []
    for url in OVERPASS_MIRRORS:
        try:
            req = urllib.request.Request(
                url,
                data=body,
                headers={
                    "User-Agent": "green-mountain-park-plan/0.1 (citizen-science viewer)",
                },
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.load(resp), errors
        except Exception as exc:
            errors.append(f"{url}: {type(exc).__name__}: {exc}")
    return None, errors


def load_static_geojson() -> dict | None:
    path = Path(__file__).resolve().parent.parent / "data" / "trails.geojson"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (ValueError, OSError):
        return None


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
        data, errors = fetch_overpass()

        if data is not None:
            osm_features = [
                f for f in (way_to_feature(w) for w in data.get("elements", []))
                if f
            ]
            features = load_handmaintained() + osm_features
            body = {
                "type": "FeatureCollection",
                "_source": "Existing trails from OSM via Overpass; merged with hand-maintained features.",
                "_count": {
                    "existing": len(osm_features),
                    "other": len(features) - len(osm_features),
                },
                "features": features,
            }
            cache_header = "public, s-maxage=300, stale-while-revalidate=86400"
        else:
            fallback = load_static_geojson()
            if fallback is None:
                err = json.dumps({
                    "error": "all_overpass_mirrors_failed",
                    "mirrors": errors,
                    "fallback": "no static data/trails.geojson present",
                }).encode()
                self.send_response(502)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(err)))
                self.end_headers()
                self.wfile.write(err)
                return
            body = fallback
            body["_source"] = "Static fallback (Overpass unreachable). Errors: " + "; ".join(errors)
            # Short cache so we re-try Overpass soon.
            cache_header = "public, s-maxage=60, stale-while-revalidate=600"

        payload = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/geo+json; charset=utf-8")
        self.send_header("Cache-Control", cache_header)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
