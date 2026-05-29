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

### Where the existing trails come from

A snapshot of the OSM trail network for the park is baked into
`data/trails.geojson` with `status: "existing"`. To refresh it from
OpenStreetMap (e.g. if someone has added or fixed trails upstream), run:

```bash
python3 scripts/fetch_osm_trails.py
```

The script preserves any hand-maintained `new` / `removed` features in the
file and only rewrites the existing-trail features. Commit the result.

(Lakewood / Jefferson County GIS Open Data may also publish trails as a
shapefile; that would be an alternative authoritative source.)

### Where to get the proposed new trails and parking (manual)

The City of Lakewood publishes the plan only as PDFs at
<https://www.lakewoodtogether.org/williamfhaydenpark>. The relevant board is
**"Open House 2 — Proposed Trails Aerial.pdf"**.

The viewer has a built-in drawing tool that handles this:

1. **Export the plan page as a PNG.** Open the PDF, screenshot or "save page
   as image" the proposed-trails page.
2. **Load it as an overlay.** In the viewer's "PDF / image overlay" panel,
   pick the PNG with the file input, toggle "Show overlay", and adjust the
   opacity slider so you can see both the overlay and the satellite imagery.
3. **Align the corners.** Check "Drag corners to align", then drag the four
   pink markers (clockwise from top-left) until the overlay's roads and
   landmarks line up with the satellite imagery underneath. Uncheck the box
   to lock the alignment. Corner positions are saved to localStorage.
4. **Draw.** In the "Draw" panel, pick the intended status (`new` /
   `removed` / `expanded`), click "Trail" or "Parking", then click points
   on the map to trace. Press **Finish** (or Enter) to save the shape and
   give it a name; press **Esc** or Backspace to undo the last vertex.
   Drafts render as pink dashed lines/polygons and persist across reloads.
5. **Hand them off.** Hit "Copy GeoJSON" to copy the entire drafts
   `FeatureCollection` to your clipboard. Paste it into a message and
   they'll get merged into `data/trails.geojson` / `data/parking.geojson`
   with the right status, committed and deployed.

Alternative low-tech paths if you don't want the in-app tool:

- <https://geojson.io> with a satellite basemap, trace by eye, copy the
  result.
- QGIS with the PDF georeferenced via 4–6 control points (most accurate,
  most setup).

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
