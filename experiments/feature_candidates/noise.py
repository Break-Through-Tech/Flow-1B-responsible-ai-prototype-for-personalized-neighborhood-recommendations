"""Transportation noise per ZIP for the quiet feature.

Run from the repo root:  python experiments/feature_candidates/noise.py
Downloads are cached under experiments/feature_candidates/noise/.

Source: BTS National Transportation Noise Map 2020, road + aviation, 24-hour
LAeq, read from its public map tiles (zoom 12, ~35 m pixels at Miami's
latitude). Tile colors map exactly to the legend bands; uncolored = below 45 dB.
ZIP boundaries: Census TIGERweb 2020 ZCTAs. BTS notes the data is modeled for
national analysis and should not be used for individual locations, so only
ZIP-wide shares are computed.

Metrics fixed before evaluation:
- share_ge_55: share of the ZIP's pixels at >= 55 dB (primary)
- mean_db: mean of band midpoints, with below-45 counted as 40 dB (secondary)
"""

import csv
import io
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, "src")
from flow_neighborhoods import Recommender  # noqa: E402

HERE = Path(__file__).parent / "noise"
TILES = "https://geo.dot.gov/server/rest/services/hosted/NTAD_Noise_2020_CONUS_Aviation_Road/MapServer/tile/{z}/{y}/{x}"
ZCTA = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/PUMA_TAD_TAZ_UGA_ZCTA/MapServer/1/query"
Z = 12
# Legend colors -> band midpoint (dB). Transparent = below 45 dB.
BANDS = {
    (255, 193, 7): 47.5, (255, 128, 0): 52.5, (255, 0, 0): 57.5, (255, 51, 153): 65.0,
    (163, 0, 204): 75.0, (82, 0, 204): 85.0, (0, 0, 255): 92.5,
}
BELOW_45 = 40.0


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "flow-neighborhoods-research"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except OSError:
            if attempt == 2:
                raise
            time.sleep(2)


def boundaries(zips: list[str]) -> dict:
    HERE.mkdir(parents=True, exist_ok=True)
    path = HERE / "zcta_2020_miami.geojson"
    if not path.exists():
        where = "ZCTA5 IN (" + ",".join(f"'{z}'" for z in zips) + ")"
        query = urllib.parse.urlencode(
            {"where": where, "outFields": "ZCTA5", "outSR": 4326, "f": "geojson",
             "returnGeometry": "true"}
        )
        path.write_bytes(fetch(f"{ZCTA}?{query}"))
    data = json.loads(path.read_text())
    return {f["properties"]["ZCTA5"]: f["geometry"] for f in data["features"]}


def tile_xy(lon: float, lat: float) -> tuple[float, float]:
    n = 2**Z
    x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def polygons(geometry: dict) -> list[list[np.ndarray]]:
    """Each polygon as [outer ring, *holes]."""
    polys = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
    return [[np.asarray(ring, dtype=float) for ring in poly] for poly in polys]


def noise_by_zip(zips: list[str]) -> dict[str, dict]:
    out = HERE / "noise_by_zip.csv"
    if out.exists():
        return {r["zip"]: r for r in csv.DictReader(out.open())}
    shapes = boundaries(zips)
    allr = [r for g in shapes.values() for poly in polygons(g) for r in poly]
    lons = np.concatenate([r[:, 0] for r in allr])
    lats = np.concatenate([r[:, 1] for r in allr])
    x0, y0 = tile_xy(lons.min(), lats.max())
    x1, y1 = tile_xy(lons.max(), lats.min())
    tx = range(int(x0), int(x1) + 1)
    ty = range(int(y0), int(y1) + 1)
    mosaic = np.full((len(ty) * 256, len(tx) * 256), BELOW_45)
    (HERE / "tiles").mkdir(parents=True, exist_ok=True)
    for j, y in enumerate(ty):
        for i, x in enumerate(tx):
            cache = HERE / "tiles" / f"{Z}_{y}_{x}.png"
            if not cache.exists():
                cache.write_bytes(fetch(TILES.format(z=Z, y=y, x=x)))
                time.sleep(0.2)
            rgba = np.asarray(Image.open(io.BytesIO(cache.read_bytes())).convert("RGBA"))
            block = np.full((256, 256), BELOW_45)
            for color, db in BANDS.items():
                block[(rgba[..., :3] == color).all(axis=-1) & (rgba[..., 3] > 0)] = db
            mosaic[j * 256:(j + 1) * 256, i * 256:(i + 1) * 256] = block
    print(f"tiles: {len(tx)} x {len(ty)}")
    # Rasterize each ZIP onto the mosaic's pixel grid (holes drawn back as 0).
    from PIL import ImageDraw

    ox, oy = tx.start * 256, ty.start * 256
    results = {}
    for z, geom in shapes.items():
        polys = [
            [np.array([tile_xy(lon, lat) for lon, lat in ring]) * 256 - (ox, oy) for ring in poly]
            for poly in polygons(geom)
        ]
        pts = np.concatenate([r for poly in polys for r in poly])
        c0, r0 = np.floor(pts.min(axis=0)).astype(int)
        c1, r1 = np.ceil(pts.max(axis=0)).astype(int)
        c0, r0 = max(c0, 0), max(r0, 0)
        c1, r1 = min(c1, mosaic.shape[1]), min(r1, mosaic.shape[0])
        canvas = Image.new("1", (c1 - c0, r1 - r0), 0)
        draw = ImageDraw.Draw(canvas)
        for poly in polys:
            draw.polygon([tuple(v) for v in poly[0] - (c0, r0)], fill=1)
            for hole in poly[1:]:
                draw.polygon([tuple(v) for v in hole - (c0, r0)], fill=0)
        mask = np.asarray(canvas, dtype=bool)
        values = mosaic[r0:r1, c0:c1][mask]
        if values.size:
            results[z] = {
                "zip": z,
                "pixels": int(values.size),
                "share_ge_55": float((values >= 55).mean()),
                "share_ge_45": float((values >= 45).mean()),
                "mean_db": float(values.mean()),
            }
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["zip", "pixels", "share_ge_55", "share_ge_45", "mean_db"])
        w.writeheader()
        w.writerows(results[z] for z in sorted(results))
    return {z: {k: str(v) for k, v in r.items()} for z, r in results.items()}


def main():
    engine = Recommender("data", feature_set="provided")
    names = {a["zip"]: a["area_name"].replace("ZCTA5 ", "") for a in engine.areas}
    noise = noise_by_zip(list(names))
    print(f"noise computed for {len(noise)} of {len(names)} ZIPs -> {HERE / 'noise_by_zip.csv'}")
    print("Reference ZIPs (share of area >= 55 dB, mean dB):")
    for z in ("33130", "33128", "33127", "33133", "33134", "33156", "33031", "33166", "33122"):
        if z in noise:
            print(f"  {z} {names[z]:16} {float(noise[z]['share_ge_55']):.2f}  {float(noise[z]['mean_db']):.1f}")
    print("Next: build_data.py writes it into data/census_features.csv; decisions.py tests it.")


if __name__ == "__main__":
    main()
