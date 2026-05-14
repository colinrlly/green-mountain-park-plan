# Green Mountain Park Plan — 3D Viewer

A citizen-science 3D terrain viewer for the City of Lakewood's
**William F. Hayden Park / Green Mountain Enhancement Plan**.

Overlays existing trails and parking against the proposed new trails and parking
on top of satellite imagery and a 3D digital elevation model, so anyone can fly
around and see what the plan actually changes.

## Run it

It's a single static HTML file with no build step. Either:

```bash
# Option 1: any static server
python3 -m http.server 8000
# then open http://localhost:8000/
```

```bash
# Option 2: VS Code Live Server, npx serve, etc.
npx serve .
```

Opening `index.html` directly via `file://` will *not* work — the browser
blocks `fetch()` of the GeoJSON files under that scheme.

## What's wired up

| Layer            | Source                                                                |
| ---------------- | --------------------------------------------------------------------- |
| Satellite        | Esri World Imagery (free, no key)                                     |
| Terrain (3D DEM) | AWS Open Data — Terrain Tiles (terrarium encoding, free, no key)      |
| Hillshade        | Derived from the same DEM by MapLibre                                 |
| Trails           | `data/trails.geojson` — `status` ∈ `existing` \| `new` \| `removed`   |
| Parking          | `data/parking.geojson` — `status` ∈ `existing` \| `expanded` \| `new` |
| Library          | [MapLibre GL JS](https://maplibre.org/) v4.7 (open source, WebGL)     |

The UI panel toggles each layer independently and has fly-to buttons for the
summit and each trailhead. The terrain-exaggeration slider goes 1×–3× (1.4×
reads well for Green Mountain's modest ~1000 ft of relief).

## ⚠️ The GeoJSON files are placeholders

The features currently in `data/trails.geojson` and `data/parking.geojson` are
**fake stand-ins** so the styling is visible on first load. You need to replace
them with real digitized geometry before the map is meaningful.

### Where to get the existing trails (easy)

Run the bundled fetcher — it queries OpenStreetMap via the Overpass API and
merges the result into `data/trails.geojson` as `status: "existing"`
features. Any hand-maintained `new` / `removed` features in the file are
preserved.

```bash
python3 scripts/fetch_osm_trails.py
```

(Lakewood / Jefferson County GIS Open Data may also publish trails as a
shapefile; that would be an alternative authoritative source.)

### Where to get the proposed new trails and parking (manual)

The City of Lakewood publishes the plan only as PDFs at
<https://www.lakewoodtogether.org/williamfhaydenpark>. The relevant board is
**"Open House 2 — Proposed Trails Aerial.pdf"**.

Two ways to digitize it:

- **Quick**: open <https://geojson.io>, switch the basemap to satellite, and
  trace the new trails and parking lots by eye against the same aerial. Save
  out the resulting features and merge them into the right GeoJSON file with
  the correct `status`.

- **Accurate**: open the PDF in QGIS, georeference it against the satellite
  basemap (use 4–6 control points along Alameda Pkwy and the Rooney Rd
  trailhead), then digitize trails as `LineString` and parking as `Polygon`
  features into a new layer and export GeoJSON.

### Optional upgrades

- **Better terrain**: download the USGS 3DEP 1-meter LiDAR DEM for the park
  bbox from <https://apps.nationalmap.gov/downloader/>, convert to Terrain RGB
  PNG tiles with [`rio-rgbify`](https://github.com/mapbox/rio-rgbify), host
  the tiles as static files, and point the `terrain` source at them.
- **Better imagery**: USDA NAIP 2023 (~0.6 m, public domain) for Jefferson
  County is on AWS Open Data; tile and host the same way.
- **MapTiler / Mapbox satellite**: requires an API key but the imagery is
  sharper and globally consistent.

## File layout

```
index.html              single-page viewer
data/
  trails.geojson        line features, status: existing|new|removed
  parking.geojson       polygon features, status: existing|expanded|new
```

## Attribution

Imagery, terrain, and plan documents belong to their respective sources
(Esri, AWS Open Data, City of Lakewood) — see the attribution strip in the
bottom-right of the map.
