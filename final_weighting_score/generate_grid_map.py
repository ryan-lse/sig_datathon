"""
Station Grid Map — Top 20 Candidates with Line Connections
============================================================
Shows the top 20 candidate grid cells as 1km x 1km squares,
colour-coded by combined score (literature baseline weights).

NOTE: The lat/lon in the output CSVs are the BOTTOM-LEFT CORNER
of each 1km grid cell, not the centre. This script builds the
full square polygon from that corner.

Usage:
  - Jupyter notebook: run all cells, the last line `m` renders inline
  - Standalone: `python generate_grid_map.py` → saves station_grid_map.html

Requires: folium, geopandas, pandas, numpy, branca, shapely
"""

import os
import pandas as pd
import geopandas as gpd
import numpy as np
import folium
import branca.colormap as cm
from shapely.geometry import Point, box


# ─── CONFIG ───
if os.path.exists("Demand Prediction Model"):
    REPO_ROOT = "."
elif os.path.exists("sig_datathon"):
    REPO_ROOT = "sig_datathon"
else:
    print("Cloning repository...")
    os.system("git clone https://github.com/ryan-lse/sig_datathon.git")
    REPO_ROOT = "sig_datathon"

CONN_DATA    = os.path.join(REPO_ROOT, "Connectivity", "data")
FINAL_OUTPUT = os.path.join(REPO_ROOT, "final_weighting_score", "output")

LINE_COLORS = {
    "Bakerloo": "#B36305",
    "Central": "#E32017",
    "Circle": "#FFD300",
    "District": "#00782A",
    "DLR": "#00A4A7",
    "Elizabeth Line": "#6950A1",
    "Hammersmith & City": "#F3A9BB",
    "Jubilee": "#A0A5A9",
    "Metropolitan": "#9B0056",
    "Northern": "#000000",
    "Piccadilly": "#003688",
    "Victoria": "#0098D4",
    "Waterloo & City": "#95CDBA",
}

GRID_CELL_SIZE = 1000  # meters in EPSG:27700


# ─── LOAD DATA ───
print("Loading data...")

df = pd.read_csv(os.path.join(FINAL_OUTPUT, "combined_scores_full.csv"))

ug = gpd.read_file(os.path.join(CONN_DATA, "underground.geojson")).set_crs(epsg=27700, allow_override=True)
ug = ug.drop_duplicates(subset=["NAME"], keep="first").reset_index(drop=True)
ug_wgs = ug.to_crs(epsg=4326)
ug["lat"], ug["lon"] = ug_wgs.geometry.y, ug_wgs.geometry.x

eliz = gpd.read_file(os.path.join(CONN_DATA, "Elizabeth.geojson")).set_crs(epsg=27700, allow_override=True)
eliz_wgs = eliz.to_crs(epsg=4326)
eliz["lat"], eliz["lon"] = eliz_wgs.geometry.y, eliz_wgs.geometry.x

dlr = gpd.read_file(os.path.join(CONN_DATA, "DLR.geojson")).set_crs(epsg=27700, allow_override=True)
dlr_wgs = dlr.to_crs(epsg=4326)
dlr["lat"], dlr["lon"] = dlr_wgs.geometry.y, dlr_wgs.geometry.x
if "LINES" not in dlr.columns:
    dlr["LINES"] = "DLR"

all_stations = pd.concat([
    ug[["NAME", "LINES", "lat", "lon"]],
    eliz[["NAME", "LINES", "lat", "lon"]],
    dlr[["NAME", "LINES", "lat", "lon"]],
], ignore_index=True)

def parse_lines(val):
    if pd.isna(val):
        return []
    return [l.strip() for l in str(val).split(",") if l.strip()]

all_stations["line_list"] = all_stations["LINES"].apply(parse_lines)

# London GLA Boundary
BOUNDARY_PATH = os.path.join(REPO_ROOT, "boundary", "London_GLA_Boundary.shp")
if os.path.exists(BOUNDARY_PATH):
    london_boundary = gpd.read_file(BOUNDARY_PATH).to_crs(epsg=4326)
    print(f"  London boundary loaded")
else:
    london_boundary = None
    print(f"  WARNING: London boundary not found at {BOUNDARY_PATH}")

print(f"  Grid points: {len(df)}")
print(f"  Stations: {len(all_stations)}")


# ─── BUILD GRID SQUARES ───
# Coordinates in CSV are BOTTOM-LEFT corners of 1km cells in EPSG:27700.
# We convert corners → EPSG:27700, build 1km box, then convert back to EPSG:4326.

print("Building grid squares...")

top20 = df.head(20).copy()

gdf_corners = gpd.GeoDataFrame(
    top20,
    geometry=[Point(xy) for xy in zip(top20["lon"], top20["lat"])],
    crs="EPSG:4326",
).to_crs(epsg=27700)

squares_27700 = []
for _, row in gdf_corners.iterrows():
    x, y = row.geometry.x, row.geometry.y
    squares_27700.append(box(x, y, x + GRID_CELL_SIZE, y + GRID_CELL_SIZE))

gdf_squares = gpd.GeoDataFrame(
    top20.reset_index(drop=True),
    geometry=squares_27700,
    crs="EPSG:27700",
)

# Compute centres in EPSG:27700 (accurate), then convert to 4326
centres_27700 = gdf_squares.geometry.centroid
centres_4326 = gpd.GeoSeries(centres_27700, crs="EPSG:27700").to_crs(epsg=4326)

gdf_squares_wgs = gdf_squares.to_crs(epsg=4326)
gdf_squares_wgs["center_lat"] = centres_4326.y
gdf_squares_wgs["center_lon"] = centres_4326.x

print(f"  Built {len(gdf_squares_wgs)} grid squares")


# ─── CANDIDATE LINE CONNECTIONS ───
# For the key candidates, which existing lines could they connect to?

top_candidates = [
    {"name": "Hayes / West Drayton", "rank": 1,
     "connections": [("Elizabeth Line", "Hayes & Harlington", 51.5031, -0.4207, 1.36)]},
    {"name": "Archway / Upper Holloway", "rank": 4,
     "connections": [("Northern", "Highgate", 51.5736, -0.1466, 0.86),
                     ("Northern", "Archway", 51.5653, -0.1353, 0.99)]},
    {"name": "Lewisham / Brockley", "rank": 5,
     "connections": [("DLR", "Lewisham DLR", 51.4657, -0.0142, 0.83),
                     ("DLR", "Elverson Road DLR", 51.4693, -0.0199, 0.85),
                     ("DLR", "Deptford Bridge DLR", 51.4740, -0.0226, 1.20)]},
    {"name": "Deptford / New Cross", "rank": 6,
     "connections": [("Jubilee", "Canada Water", 51.4982, -0.0498, 0.83),
                     ("DLR", "Heron Quays DLR", 51.5087, -0.0261, 1.23),
                     ("Elizabeth Line", "Canary Wharf EL", 51.5065, -0.0183, 1.62)]},
    {"name": "Woolwich / Plumstead", "rank": 12,
     "connections": [("DLR", "Woolwich Arsenal DLR", 51.4905, 0.0691, 1.20),
                     ("Elizabeth Line", "Woolwich EL", 51.4917, 0.0713, 1.47)]},
    {"name": "Brixton / Clapham", "rank": 16,
     "connections": [("Northern", "Clapham Common", 51.4618, -0.1384, 0.98),
                     ("Victoria", "Brixton", 51.4627, -0.1145, 1.08)]},
    {"name": "South Ken / Earl's Court", "rank": 19,
     "connections": [("District", "Fulham Broadway", 51.4802, -0.1953, 0.89),
                     ("Piccadilly", "Earl's Court", 51.4914, -0.1931, 1.11)]},
]


# ─── BUILD MAP ───
print("Building map...")

m = folium.Map(location=[51.49, -0.08], zoom_start=11, tiles=None)
folium.TileLayer("CartoDB positron", name="CartoDB Positron", control=True).add_to(m)
folium.TileLayer("OpenStreetMap", name="OpenStreetMap", control=True).add_to(m)

# Colormap
vmin = float(gdf_squares_wgs["combined_score"].min())
vmax = float(gdf_squares_wgs["combined_score"].max())
cmap_sq = cm.LinearColormap(
    ["#08306b", "#2171b5", "#6baed6", "#ef6548", "#cb181d", "#99000d"],
    vmin=vmin, vmax=vmax,
)
cmap_sq.caption = "Combined Score (Literature Baseline: 0.35 / 0.30 / 0.20 / 0.15)"
cmap_sq.add_to(m)


# ── Layer 1: Stations per line (toggleable) ──
line_groups = {}
for line_name in sorted(LINE_COLORS.keys()):
    fg = folium.FeatureGroup(name=f"Line: {line_name}", show=False)
    line_groups[line_name] = fg

all_stations_fg = folium.FeatureGroup(name="All Stations", show=True)

for _, s in all_stations.iterrows():
    lat, lon = float(s["lat"]), float(s["lon"])
    lines = s["line_list"]
    lines_str = ", ".join(lines) if lines else "Unknown"
    popup_html = f"<b>{s['NAME']}</b><br>{lines_str}"

    if len(lines) <= 1:
        line = lines[0] if lines else "Unknown"
        color = LINE_COLORS.get(line, "#888")
        folium.CircleMarker(
            location=[lat, lon], radius=4,
            color=color, fill=True, fill_color=color,
            fill_opacity=0.8, weight=1, popup=popup_html,
        ).add_to(all_stations_fg)
        if line in line_groups:
            folium.CircleMarker(
                location=[lat, lon], radius=5,
                color=color, fill=True, fill_color=color,
                fill_opacity=0.9, weight=1.5, popup=popup_html,
            ).add_to(line_groups[line])
    else:
        # Multi-line station: concentric rings
        for ring_i, line in enumerate(lines):
            color = LINE_COLORS.get(line, "#888")
            r = 4 + ring_i * 2.5
            folium.CircleMarker(
                location=[lat, lon], radius=r,
                color=color, fill=False, weight=2.5, opacity=0.85,
                popup=popup_html,
            ).add_to(all_stations_fg)
            if line in line_groups:
                folium.CircleMarker(
                    location=[lat, lon], radius=5,
                    color=color, fill=True, fill_color=color,
                    fill_opacity=0.9, weight=1.5, popup=popup_html,
                ).add_to(line_groups[line])

all_stations_fg.add_to(m)
for fg in line_groups.values():
    fg.add_to(m)


# ── Layer 2: Top 20 grid squares ──
squares_fg = folium.FeatureGroup(name="Top 20 Grid Cells (1km²)", show=True)

# Ranks that have line connection data
has_connections = {c["rank"] for c in top_candidates}

for _, row in gdf_squares_wgs.iterrows():
    rank = int(row["rank"])
    score = row["combined_score"]
    color = cmap_sq(score)
    dist = row["min_distance_to_station_km"]
    realistic = dist <= 3.0
    relieves = row["top_relieved_stations"] if pd.notna(row.get("top_relieved_stations")) else ""

    # Highlight border for candidates with connections
    border_color = "#ffffff" if rank in has_connections else "#aaaaaa"
    border_weight = 2.5 if rank in has_connections else 1.5

    # Popup
    buildable_tag = "✓ Buildable" if realistic else f"✗ {dist:.1f}km from network"
    popup_html = (
        f"<div style='min-width:240px;font-family:sans-serif;'>"
        f"<h3 style='margin:0 0 6px 0;font-size:14px;'>Rank #{rank}</h3>"
        f"<div style='font-size:11px;color:{'green' if realistic else 'red'};margin-bottom:6px;'>"
        f"{buildable_tag}</div>"
        f"<table style='font-size:12px;border-collapse:collapse;'>"
        f"<tr><td style='padding:2px 8px 2px 0;'>Combined:</td><td><b>{score:.4f}</b></td></tr>"
        f"<tr><td style='padding:2px 8px 2px 0;'>Demand:</td><td>{row['gravity_norm']:.3f}</td></tr>"
        f"<tr><td style='padding:2px 8px 2px 0;'>Connectivity:</td><td>{row['connectivity_norm']:.3f}</td></tr>"
        f"<tr><td style='padding:2px 8px 2px 0;'>Crowding:</td><td>{row['crowding_norm']:.3f}</td></tr>"
        f"<tr><td style='padding:2px 8px 2px 0;'>Travel time:</td><td>{row['travel_time_norm']:.3f}</td></tr>"
        f"<tr><td style='padding:2px 8px 2px 0;'>Dist to station:</td><td>{dist:.2f}km</td></tr>"
        f"</table>"
    )
    if relieves:
        popup_html += f"<div style='margin-top:6px;font-size:11px;'>Relieves: {relieves}</div>"
    popup_html += "</div>"

    # Draw square
    coords = list(row.geometry.exterior.coords)
    folium.Polygon(
        locations=[(c[1], c[0]) for c in coords],
        color=border_color,
        weight=border_weight,
        fill=True,
        fill_color=color,
        fill_opacity=0.65,
        popup=folium.Popup(popup_html, max_width=320),
    ).add_to(squares_fg)

    # Rank label at centre
    c_lat, c_lon = row["center_lat"], row["center_lon"]
    fs = 13 if rank in has_connections else 11
    folium.Marker(
        location=[c_lat, c_lon],
        icon=folium.DivIcon(
            html=(
                f'<div style="font-size:{fs}px;font-weight:bold;color:white;'
                f'text-align:center;line-height:22px;'
                f'text-shadow:0 0 4px rgba(0,0,0,0.7);">#{rank}</div>'
            ),
            icon_size=(34, 22), icon_anchor=(17, 11),
        ),
    ).add_to(squares_fg)

squares_fg.add_to(m)


# ── Layer 3: Line connection lines ──
conn_fg = folium.FeatureGroup(name="Potential Line Connections", show=True)

for cand in top_candidates:
    rank = cand["rank"]

    # Get centre of this candidate's grid square
    sq_row = gdf_squares_wgs[gdf_squares_wgs["rank"] == rank]
    if len(sq_row) == 0:
        continue
    sq_row = sq_row.iloc[0]
    c_lat, c_lon = sq_row["center_lat"], sq_row["center_lon"]

    for line, station, s_lat, s_lon, dist in cand["connections"]:
        lc = LINE_COLORS.get(line, "#888888")

        # Dashed line from grid centre to existing station
        folium.PolyLine(
            locations=[[c_lat, c_lon], [s_lat, s_lon]],
            color=lc, weight=3.5, opacity=0.85, dash_array="8 6",
            popup=f"Connect to <b>{line}</b> via {station} ({dist:.1f}km)",
        ).add_to(conn_fg)

        # Station endpoint dot
        folium.CircleMarker(
            location=[s_lat, s_lon], radius=7,
            color=lc, fill=True, fill_color=lc,
            fill_opacity=0.95, weight=1.5,
            popup=f"<b>{station}</b><br>{line}",
        ).add_to(conn_fg)

conn_fg.add_to(m)


# ── Layer 4: London GLA Boundary ──
if london_boundary is not None:
    folium.GeoJson(
        london_boundary.__geo_interface__,
        name="London Boundary",
        style_function=lambda _: {"color": "black", "weight": 2, "fillOpacity": 0},
    ).add_to(m)


# ── Legend ──
legend_items = ""
for ln in sorted(LINE_COLORS.keys()):
    c = LINE_COLORS[ln]
    legend_items += (
        f'<div style="margin:2px 0;">'
        f'<span style="display:inline-block;width:12px;height:12px;border-radius:50%;'
        f'background:{c};margin-right:6px;vertical-align:middle;'
        f'border:1px solid rgba(0,0,0,0.15);"></span>{ln}</div>'
    )

legend_html = f"""
<div style="position:fixed;bottom:30px;left:30px;z-index:1000;
     background:white;padding:14px 18px;border-radius:8px;
     font-size:11.5px;line-height:1.6;
     box-shadow:0 2px 12px rgba(0,0,0,0.2);max-width:210px;">
<b style="font-size:13px;">Tube Lines</b><br>
{legend_items}
<hr style="margin:8px 0;border:none;border-top:1px solid #ddd;">
<div style="margin:3px 0;">
  <span style="display:inline-block;width:14px;height:14px;background:#cb181d;
  opacity:0.65;margin-right:6px;vertical-align:middle;border:2px solid white;"></span>
  Top grid cell (1km²)
</div>
<div style="margin:3px 0;">
  <span style="border-bottom:2.5px dashed #888;width:20px;display:inline-block;
  margin-right:6px;vertical-align:middle;"></span>Potential connection
</div>
<div style="margin:3px 0;">
  <span style="display:inline-block;width:16px;height:16px;border-radius:50%;
  border:2.5px solid #003688;margin-right:4px;vertical-align:middle;">
  <span style="display:block;width:10px;height:10px;border-radius:50%;
  border:2px solid #E32017;margin:1px auto;"></span></span>
  Multi-line station
</div>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

folium.LayerControl(collapsed=False).add_to(m)


# ─── SAVE ───
output_path = os.path.join(REPO_ROOT, "station_grid_map.html")
m.save(output_path)
print(f"\nSaved: {output_path}")
print(f"Grid squares: {len(gdf_squares_wgs)} | Stations: {len(all_stations)}")
print(f"\nNote: coordinates in output CSVs are BOTTOM-LEFT corners of 1km grid cells.")
print("To display in Jupyter: put `m` as the last line of a cell.")

# Display in Jupyter (does nothing when run as script)
m