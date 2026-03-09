"""
Gravity Model Heatmap Visualisation
====================================
Reads sorted_grid.csv and produces an interactive Folium heatmap
of gravity scores across London, matching the style used in
Connectivity/pipeline.ipynb (Cell 8).

Outputs:
  - gravity_citywise_score_map.html  (interactive city-wide map)
  - gravity_top10_map.html           (top 10 locations highlighted)
"""

import os
import pandas as pd
import numpy as np
import folium
import branca.colormap as cm

# ──────────────────────────────────────────────
# 1.  Load data
# ──────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
grid = pd.read_csv(os.path.join(SCRIPT_DIR, "sorted_grid.csv"))

print(f"Loaded {len(grid)} grid points")
print(f"gravity_log range: {grid['gravity_log'].min():.4f} – {grid['gravity_log'].max():.4f}")


# ──────────────────────────────────────────────
# 2.  City-wide gravity score map
# ──────────────────────────────────────────────
center_lat = float(grid["lat"].mean())
center_lon = float(grid["lon"].mean())

m_all = folium.Map(location=[center_lat, center_lon], zoom_start=10, tiles=None)
folium.TileLayer("OpenStreetMap", name="OpenStreetMap", control=True).add_to(m_all)
folium.TileLayer("CartoDB positron", name="CartoDB Positron", control=True).add_to(m_all)

vmin = float(grid["gravity_log"].min())
vmax = float(grid["gravity_log"].max())

cmap = cm.LinearColormap(
    ["#2c7bb6", "#abd9e9", "#ffffbf", "#fdae61", "#d7191c"],
    vmin=vmin,
    vmax=vmax,
)
cmap.caption = "Gravity Score (log)"

for _, r in grid.iterrows():
    folium.CircleMarker(
        location=[float(r["lat"]), float(r["lon"])],
        radius=5.0,
        color=cmap(float(r["gravity_log"])),
        fill=True,
        fill_opacity=0.8,
        weight=0,
        popup=(
            f"gravity_score={r['gravity_score']:.2f}<br>"
            f"gravity_log={r['gravity_log']:.4f}<br>"
            f"lat={r['lat']:.6f}, lon={r['lon']:.6f}"
        ),
    ).add_to(m_all)

cmap.add_to(m_all)
folium.LayerControl(collapsed=False).add_to(m_all)

city_html = os.path.abspath(os.path.join(SCRIPT_DIR, "gravity_citywise_score_map.html"))
m_all.save(city_html)
print(f"Saved city-wise score map to: {city_html}")


# ──────────────────────────────────────────────
# 3.  Top 10 locations map
# ──────────────────────────────────────────────
top10 = grid.sort_values("gravity_log", ascending=False).head(10).reset_index(drop=True)

center_lat_top = float(grid["lat"].mean())
center_lon_top = float(grid["lon"].mean())

m_top = folium.Map(location=[center_lat_top, center_lon_top], zoom_start=10, tiles=None)
folium.TileLayer("CartoDB positron", name="CartoDB Positron", control=True).add_to(m_top)
folium.TileLayer("OpenStreetMap", name="OpenStreetMap", control=True).add_to(m_top)

# Background: full heatmap in muted tones so top 10 stands out
for _, r in grid.iterrows():
    folium.CircleMarker(
        location=[float(r["lat"]), float(r["lon"])],
        radius=4.0,
        color=cmap(float(r["gravity_log"])),
        fill=True,
        fill_opacity=0.25,
        weight=0,
    ).add_to(m_top)

# Top 10: large red circle + numbered label
for rank, (_, row) in enumerate(top10.iterrows(), start=1):
    lat = float(row["lat"])
    lon = float(row["lon"])

    # Outer ring for visibility
    folium.CircleMarker(
        location=[lat, lon],
        radius=16,
        color="#d7191c",
        fill=True,
        fill_color="#d7191c",
        fill_opacity=0.85,
        weight=2,
        popup=folium.Popup(
            f"<b>Rank #{rank}</b><br>"
            f"gravity_score={row['gravity_score']:.2f}<br>"
            f"gravity_log={row['gravity_log']:.4f}<br>"
            f"lat={row['lat']:.6f}, lon={row['lon']:.6f}",
            max_width=300,
        ),
    ).add_to(m_top)

    # Rank number label
    folium.Marker(
        location=[lat, lon],
        icon=folium.DivIcon(
            html=(
                f'<div style="font-size:12px; font-weight:bold; color:white; '
                f'text-align:center; line-height:26px; '
                f'width:26px; height:26px;">'
                f'{rank}</div>'
            ),
            icon_size=(26, 26),
            icon_anchor=(13, 13),
        ),
    ).add_to(m_top)

folium.LayerControl(collapsed=False).add_to(m_top)

top10_html = os.path.abspath(os.path.join(SCRIPT_DIR, "gravity_top10_map.html"))
m_top.save(top10_html)
print(f"Saved top-10 map: {top10_html}")


# ──────────────────────────────────────────────
# 4.  Summary table
# ──────────────────────────────────────────────
print("\nTop 10 Gravity Model Locations:")
for rank, (_, row) in enumerate(top10.iterrows(), start=1):
    print(f"  #{rank:>2d}  ({row['lat']:.4f}, {row['lon']:.4f})  "
          f"gravity_log={row['gravity_log']:.4f}  "
          f"gravity_score={row['gravity_score']:.2f}")
