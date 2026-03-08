"""
Combined Multi-Criteria Scoring Model
======================================
Merges all four component scores into a single suitability ranking
for where to build a new London Tube station.

Components:
  1. Gravity Score       — population demand (higher = more people nearby)
  2. Connectivity Score  — accessibility gap (higher = more underserved)
  3. Crowding Score      — congestion relief potential (higher = more relief)
  4. Travel Time Score   — journey-time reduction (higher = more time saved)

All scores are normalised to [0, 1] before combination.
"""

import pandas as pd
import numpy as np
import os
import sys
import warnings

warnings.filterwarnings("ignore")


# ──────────────────────────────────────────────
# 0.  Configuration
# ──────────────────────────────────────────────

# ──────────────────────────────────────────────
# Weight justification (Literature-based baseline)
# ──────────────────────────────────────────────
# Transport planning MCA literature consistently places population
# demand / ridership potential as the dominant criterion when siting
# new rail stations.
#
# Key references:
#   [1] Çalışkan, Ö. (2023). "Cartographic Modelling and Multi-Criteria
#       Analysis (CMCA) for Rail Transit Suitability." Urban Rail Transit,
#       9, 81–103. doi:10.1007/s40864-023-00186-1
#       → AHP expert panel assigned Population 38%, with remaining
#         criteria (geology, slope, land use, stream) sharing the rest.
#
#   [2] Akin, D. & Kara, D. (2020). "Multicriteria analysis of planned
#       intercity bus terminals in Istanbul." Transportation Research
#       Part A, 132, 465–489. doi:10.1016/j.tra.2019.12.003
#       → Weighted linear combination using population coverage/density
#         and accessibility as the two highest-weighted criteria.
#
#   [3] Litman, T. (2024). "Evaluating Accessibility for Transportation
#       Planning." Victoria Transport Policy Institute (vtpi.org).
#       → Identifies demand, connectivity, and travel time as the three
#         pillars of accessibility-based transport planning.
#
# Mapping to our four criteria:
#   - Population demand (gravity):   highest weight — a station with
#     no surrounding population cannot succeed regardless of other
#     factors (Çalışkan 2023: 38% for population alone).
#   - Accessibility gap (connectivity): second — filling gaps in the
#     existing network is the primary planning rationale (Litman 2024).
#   - Crowding relief: third — reduces load on the existing system,
#     but is secondary to ensuring the new station is needed and
#     reachable.
#   - Travel time reduction: fourth — important for user benefit but
#     hardest to estimate precisely and partially captured by
#     connectivity.
#
# We adopt a 0.35 / 0.30 / 0.20 / 0.15 split as our literature-based
# baseline, and run sensitivity analysis across alternative schemes.
# ──────────────────────────────────────────────

WEIGHTS = {
    "gravity":      0.35,   # population demand (dominant criterion)
    "connectivity": 0.30,   # accessibility gap
    "crowding":     0.20,   # congestion relief
    "travel_time":  0.15,   # journey-time reduction
}

assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "Weights must sum to 1"

# Paths (relative to repo root)
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GRAVITY_CSV      = os.path.join(REPO_ROOT, "Demand Prediction Model", "Output", "sorted_grid.csv")
CROWDING_CSV     = os.path.join(REPO_ROOT, "Crowding_reduction", "output", "team_crowding_scores.csv")
TRAVEL_CSV       = os.path.join(REPO_ROOT, "Travel  Time Reduction", "output", "candidate_reduction_scores(n=50).csv")
CONNECTIVITY_CSV = os.path.join(REPO_ROOT, "Connectivity", "connectivity_scores.csv")

OUTPUT_DIR = os.path.join(REPO_ROOT, "final_weighting_score", "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ──────────────────────────────────────────────
# 1.  Helper: min-max normalise to [0, 1]
# ──────────────────────────────────────────────

def minmax(series):
    s_min, s_max = series.min(), series.max()
    if s_max - s_min < 1e-12:
        return pd.Series(0.0, index=series.index)
    return (series - s_min) / (s_max - s_min)


# ──────────────────────────────────────────────
# 2.  Load base grid
# ──────────────────────────────────────────────

print("Loading base grid (sorted_grid.csv) ...")
grid = pd.read_csv(GRAVITY_CSV)
grid["lat_r"] = grid["lat"].round(6)
grid["lon_r"] = grid["lon"].round(6)
print(f"  {len(grid)} grid points loaded")


# ──────────────────────────────────────────────
# 3.  Gravity score
# ──────────────────────────────────────────────

print("\n[1/4] Gravity score ...")
# gravity_log is already in the grid CSV
grid["gravity_norm"] = minmax(grid["gravity_log"])
print(f"  range: {grid['gravity_norm'].min():.4f} – {grid['gravity_norm'].max():.4f}")


# ──────────────────────────────────────────────
# 4.  Crowding score
# ──────────────────────────────────────────────

print("\n[2/4] Crowding score ...")
crowding = pd.read_csv(CROWDING_CSV)
crowding["lat_r"] = crowding["lat"].round(6)
crowding["lon_r"] = crowding["lon"].round(6)

grid = grid.merge(
    crowding[["lat_r", "lon_r", "crowding_score", "crowding_score_norm",
              "min_distance_to_station_km", "top_relieved_stations"]],
    on=["lat_r", "lon_r"],
    how="left"
)
# Re-normalise from raw score to ensure consistency
grid["crowding_norm"] = minmax(grid["crowding_score"].fillna(0))
print(f"  matched: {grid['crowding_score'].notna().sum()} / {len(grid)}")
print(f"  range: {grid['crowding_norm'].min():.4f} – {grid['crowding_norm'].max():.4f}")


# ──────────────────────────────────────────────
# 5.  Travel time reduction score
# ──────────────────────────────────────────────

print("\n[3/4] Travel time reduction score ...")
travel = pd.read_csv(TRAVEL_CSV)
travel["lat_r"] = travel["lat"].round(6)
travel["lon_r"] = travel["lon"].round(6)

grid = grid.merge(
    travel[["lat_r", "lon_r", "total_reduction"]],
    on=["lat_r", "lon_r"],
    how="left"
)
# Only 50 grid points have travel time scores; fill rest with 0
grid["total_reduction"] = grid["total_reduction"].fillna(0)
grid["travel_time_norm"] = minmax(grid["total_reduction"])
print(f"  grid points with TfL API data: {(grid['total_reduction'] > 0).sum()}")
print(f"  range: {grid['travel_time_norm'].min():.4f} – {grid['travel_time_norm'].max():.4f}")


# ──────────────────────────────────────────────
# 6.  Connectivity score
# ──────────────────────────────────────────────

print("\n[4/4] Connectivity score ...")
has_connectivity = False

if os.path.exists(CONNECTIVITY_CSV):
    conn = pd.read_csv(CONNECTIVITY_CSV)
    # Use round(4) for matching — the connectivity CSV was generated from
    # grids.geojson which has slight float differences from sorted_grid.csv
    # due to EPSG:27700 → EPSG:4326 reprojection
    conn["lat_r"] = conn["lat"].round(4)
    conn["lon_r"] = conn["lon"].round(4)
    grid["lat_r4"] = grid["lat"].round(4)
    grid["lon_r4"] = grid["lon"].round(4)

    grid = grid.merge(
        conn[["lat_r", "lon_r", "connectivity_score",
              "harmonic_mean_adj_dist_norm", "line_unique_count_norm"]].rename(
            columns={"lat_r": "lat_r4", "lon_r": "lon_r4"}),
        on=["lat_r4", "lon_r4"],
        how="left"
    )
    grid.drop(columns=["lat_r4", "lon_r4"], inplace=True, errors="ignore")
    grid["connectivity_norm"] = minmax(grid["connectivity_score"].fillna(0))
    has_connectivity = grid["connectivity_score"].notna().sum() > 100
    print(f"  matched: {grid['connectivity_score'].notna().sum()} / {len(grid)}")
    print(f"  range: {grid['connectivity_norm'].min():.4f} – {grid['connectivity_norm'].max():.4f}")
else:
    # Fallback: run connectivity inline using dist_func
    print("  connectivity_scores.csv not found — computing inline ...")
    sys.path.insert(0, os.path.join(REPO_ROOT, "Connectivity", "model"))
    try:
        import geopandas as gpd
        from dist_func import nearest_neighbor, find_line_diversity, combine_connectivity_score

        # Load all station datasets (underground + Elizabeth + DLR)
        station_files = ["underground.geojson", "Elizabeth.geojson", "DLR.geojson"]
        station_gdfs = []
        for fname in station_files:
            fpath = os.path.join(REPO_ROOT, "Connectivity", "data", fname)
            if os.path.exists(fpath):
                sdf = gpd.read_file(fpath)
                # Fix mislabelled CRS: ArcGIS API returns EPSG:27700 coords
                # but GeoJSON format defaults to EPSG:4326
                if sdf.geometry.x.max() > 10000:
                    sdf = sdf.set_crs("EPSG:27700", allow_override=True)
                sdf = sdf.drop_duplicates(subset=["NAME"], keep="first").reset_index(drop=True)
                # Add lat/lon columns from reprojected geometry
                sdf_wgs84 = sdf.to_crs(epsg=4326)
                sdf["lat"] = sdf_wgs84.geometry.y
                sdf["lon"] = sdf_wgs84.geometry.x
                station_gdfs.append(sdf)
                print(f"    loaded {fname}: {len(sdf)} stations")

        if station_gdfs:
            stations = gpd.GeoDataFrame(
                pd.concat(station_gdfs, ignore_index=True),
                geometry="geometry",
                crs="EPSG:27700"
            )
            print(f"    combined: {len(stations)} stations in EPSG:27700")

            # Load grid in EPSG:27700 (matching station CRS for correct distances)
            grids_geojson = os.path.join(REPO_ROOT, "Connectivity", "data", "grids.geojson")
            if os.path.exists(grids_geojson):
                grid_gdf = gpd.read_file(grids_geojson)
                if grid_gdf.crs is None or grid_gdf.crs.to_epsg() != 27700:
                    grid_gdf = grid_gdf.set_crs("EPSG:27700", allow_override=True)
                # Ensure lat/lon columns exist
                grid_wgs84 = grid_gdf.to_crs(epsg=4326)
                grid_gdf["lat"] = grid_wgs84.geometry.y
                grid_gdf["lon"] = grid_wgs84.geometry.x
            else:
                # Fallback: build grid GDF from lat/lon
                grid_gdf = gpd.GeoDataFrame(
                    grid[["lat", "lon"]].copy(),
                    geometry=gpd.points_from_xy(grid["lon"], grid["lat"]),
                    crs="EPSG:4326"
                ).to_crs("EPSG:27700")
                grid_gdf["lat"] = grid["lat"].values
                grid_gdf["lon"] = grid["lon"].values

            # Run connectivity pipeline (k=5 to match updated notebook)
            result = nearest_neighbor(grid_gdf, stations, k=5)
            result = find_line_diversity(result, stations, k=5)
            result = combine_connectivity_score(result, alpha=0.5, beta=0.5)

            grid["connectivity_score"] = result["connectivity_score"].values
            grid["connectivity_norm"] = minmax(grid["connectivity_score"])
            has_connectivity = True

            # Save for future use
            result.to_csv(CONNECTIVITY_CSV, index=False)
            print(f"  computed and saved to {CONNECTIVITY_CSV}")
            print(f"  range: {grid['connectivity_norm'].min():.4f} – {grid['connectivity_norm'].max():.4f}")
        else:
            print(f"  WARNING: no station geojson files found")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"  WARNING: could not compute connectivity: {e}")

if not has_connectivity:
    print("  *** Connectivity scores unavailable — redistributing weights ***")
    grid["connectivity_norm"] = 0.0
    # Redistribute connectivity weight equally across other 3
    extra = WEIGHTS["connectivity"] / 3
    WEIGHTS["gravity"] += extra
    WEIGHTS["crowding"] += extra
    WEIGHTS["travel_time"] += extra
    WEIGHTS["connectivity"] = 0.0
    print(f"  Adjusted weights: {WEIGHTS}")


# ──────────────────────────────────────────────
# 7.  Combined score
# ──────────────────────────────────────────────

print("\n" + "=" * 55)
print("COMBINING SCORES")
print("=" * 55)
print(f"  Weights: {WEIGHTS}")

# Filter: exclude candidates too close to an existing station (< 0.8 km)
MIN_STATION_DIST_KM = 0.8
if "min_distance_to_station_km" in grid.columns:
    too_close = grid["min_distance_to_station_km"] < MIN_STATION_DIST_KM
    print(f"  Excluding {too_close.sum()} grid points within {MIN_STATION_DIST_KM} km of existing station")
else:
    too_close = pd.Series(False, index=grid.index)

grid["combined_score"] = (
    WEIGHTS["gravity"]      * grid["gravity_norm"]
    + WEIGHTS["connectivity"] * grid["connectivity_norm"]
    + WEIGHTS["crowding"]     * grid["crowding_norm"]
    + WEIGHTS["travel_time"]  * grid["travel_time_norm"]
)

# Zero out candidates too close to existing stations
grid.loc[too_close, "combined_score"] = 0.0

grid["rank"] = grid["combined_score"].rank(ascending=False, method="min").astype(int)
grid = grid.sort_values("rank")


# ──────────────────────────────────────────────
# 8.  Results
# ──────────────────────────────────────────────

print("\n" + "=" * 55)
print("TOP 20 CANDIDATE LOCATIONS")
print("=" * 55)

top20 = grid.head(20).copy()
display_cols = [
    "rank", "lat", "lon",
    "gravity_norm", "connectivity_norm", "crowding_norm", "travel_time_norm",
    "combined_score", "top_relieved_stations", "min_distance_to_station_km"
]
display_cols = [c for c in display_cols if c in top20.columns]

pd.set_option("display.max_columns", 20)
pd.set_option("display.width", 200)
pd.set_option("display.max_colwidth", 40)

for _, row in top20.iterrows():
    print(f"\n  #{int(row['rank']):>3d}  ({row['lat']:.4f}, {row['lon']:.4f})")
    print(f"        gravity={row['gravity_norm']:.3f}  "
          f"connectivity={row.get('connectivity_norm', 0):.3f}  "
          f"crowding={row['crowding_norm']:.3f}  "
          f"travel_time={row['travel_time_norm']:.3f}")
    print(f"        COMBINED = {row['combined_score']:.4f}")
    if pd.notna(row.get("top_relieved_stations", None)) and row.get("top_relieved_stations", ""):
        print(f"        relieves: {row['top_relieved_stations']}")


# ──────────────────────────────────────────────
# 9.  Sensitivity analysis
# ──────────────────────────────────────────────

print("\n\n" + "=" * 55)
print("SENSITIVITY ANALYSIS")
print("=" * 55)

weight_scenarios = {
    # Baseline: literature-informed (Çalışkan 2023; Akin & Kara 2020; Litman 2024)
    "Literature baseline (0.35/0.30/0.20/0.15)": {
        "gravity": 0.35, "connectivity": 0.30, "crowding": 0.20, "travel_time": 0.15},

    # Equal weighting — no prior assumption
    "Equal (0.25 each)": {
        "gravity": 0.25, "connectivity": 0.25, "crowding": 0.25, "travel_time": 0.25},

    # Single-criterion dominance scenarios (0.55 dominant, 0.15 each other)
    "Demand-dominant (0.55)": {
        "gravity": 0.55, "connectivity": 0.15, "crowding": 0.15, "travel_time": 0.15},
    "Connectivity-dominant (0.55)": {
        "gravity": 0.15, "connectivity": 0.55, "crowding": 0.15, "travel_time": 0.15},
    "Crowding-dominant (0.55)": {
        "gravity": 0.15, "connectivity": 0.15, "crowding": 0.55, "travel_time": 0.15},
    "Travel-time-dominant (0.55)": {
        "gravity": 0.15, "connectivity": 0.15, "crowding": 0.15, "travel_time": 0.55},

    # Two-factor emphasis scenarios
    "Demand + Connectivity (0.35/0.35/0.15/0.15)": {
        "gravity": 0.35, "connectivity": 0.35, "crowding": 0.15, "travel_time": 0.15},
    "Demand + Crowding (0.35/0.15/0.35/0.15)": {
        "gravity": 0.35, "connectivity": 0.15, "crowding": 0.35, "travel_time": 0.15},
    "Connectivity + Crowding (0.15/0.35/0.35/0.15)": {
        "gravity": 0.15, "connectivity": 0.35, "crowding": 0.35, "travel_time": 0.15},
}

sensitivity_results = []
# Track how often each grid point appears in top-5 across all scenarios
from collections import Counter
top5_counter = Counter()

for label, w in weight_scenarios.items():
    # If connectivity isn't available, redistribute
    if not has_connectivity and w["connectivity"] > 0:
        extra = w["connectivity"] / 3
        w = {k: (v + extra if k != "connectivity" else 0) for k, v in w.items()}

    score = (
        w["gravity"]      * grid["gravity_norm"]
        + w["connectivity"] * grid["connectivity_norm"]
        + w["crowding"]     * grid["crowding_norm"]
        + w["travel_time"]  * grid["travel_time_norm"]
    )
    # Apply same distance filter
    score.loc[too_close] = 0.0
    top5_idx = score.nlargest(5).index
    top5 = grid.loc[top5_idx, ["lat", "lon"]].copy()
    top5["score"] = score.loc[top5_idx].values
    top5["scenario"] = label

    sensitivity_results.append(top5)

    # Count appearances
    for _, r in top5.iterrows():
        key = f"({r['lat']:.4f}, {r['lon']:.4f})"
        top5_counter[key] += 1

    print(f"\n  {label}:")
    for i, (_, r) in enumerate(top5.iterrows(), 1):
        print(f"    {i}. ({r['lat']:.4f}, {r['lon']:.4f})  score={r['score']:.4f}")

sensitivity_df = pd.concat(sensitivity_results, ignore_index=True)

# Robustness summary: which locations appear most often across scenarios?
print("\n\n" + "=" * 55)
print("ROBUSTNESS SUMMARY")
print("=" * 55)
print(f"  Across {len(weight_scenarios)} weighting scenarios, top-5 appearances:")
n_scenarios = len(weight_scenarios)
for loc, count in top5_counter.most_common(15):
    pct = count / n_scenarios * 100
    print(f"    {loc}  appears {count}/{n_scenarios} times ({pct:.0f}%)")

sensitivity_df = pd.concat(sensitivity_results, ignore_index=True)


# ──────────────────────────────────────────────
# 10. Save outputs
# ──────────────────────────────────────────────

# Full grid with all scores
output_cols = [
    "lat", "lon", "rank", "combined_score",
    "gravity_norm", "connectivity_norm", "crowding_norm", "travel_time_norm",
    "gravity_log", "crowding_score", "total_reduction",
    "min_distance_to_station_km", "top_relieved_stations"
]
output_cols = [c for c in output_cols if c in grid.columns]

full_path = os.path.join(OUTPUT_DIR, "combined_scores_full.csv")
grid[output_cols].to_csv(full_path, index=False)
print(f"\nSaved full grid: {full_path}")

# Top 20
top20_path = os.path.join(OUTPUT_DIR, "top20_combined.csv")
grid.head(20)[output_cols].to_csv(top20_path, index=False)
print(f"Saved top 20:    {top20_path}")

# Sensitivity
sens_path = os.path.join(OUTPUT_DIR, "sensitivity_analysis.csv")
sensitivity_df.to_csv(sens_path, index=False)
print(f"Saved sensitivity: {sens_path}")

# Final recommendation
best = grid.iloc[0]
print("\n" + "=" * 55)
print("FINAL RECOMMENDATION")
print("=" * 55)
print(f"  Location:  ({best['lat']:.6f}, {best['lon']:.6f})")
print(f"  Combined score: {best['combined_score']:.4f}")
print(f"  Component scores:")
print(f"    Gravity (population demand): {best['gravity_norm']:.3f}")
print(f"    Connectivity (access gap):   {best.get('connectivity_norm', 0):.3f}")
print(f"    Crowding relief:             {best['crowding_norm']:.3f}")
print(f"    Travel time reduction:       {best['travel_time_norm']:.3f}")
if pd.notna(best.get("top_relieved_stations", None)):
    print(f"  Relieves: {best['top_relieved_stations']}")
print(f"  Distance to nearest station:   {best.get('min_distance_to_station_km', 'N/A')} km")


# ──────────────────────────────────────────────
# 11. Gravity model sensitivity analysis
# ──────────────────────────────────────────────

print("\n\n" + "=" * 55)
print("GRAVITY MODEL SENSITIVITY (beta × radius)")
print("=" * 55)

try:
    import geopandas as gpd
    from shapely.geometry import Point as ShapelyPoint
    from sklearn.neighbors import BallTree

    pop_csv = os.path.join(REPO_ROOT, "Demand Prediction Model", "Data", "Population.csv")
    coord_csv = os.path.join(REPO_ROOT, "Demand Prediction Model", "Data", "Coordinate_filter.csv")

    if os.path.exists(pop_csv) and os.path.exists(coord_csv):
        population = pd.read_csv(pop_csv, sep=";", usecols=[0, 2])
        population = population.rename(columns={"All Ages": "Population", "OA11CD": "Area"})
        coordinate = pd.read_csv(coord_csv, sep=",")
        pop_data = pd.merge(population, coordinate, on="Area")

        geom = [ShapelyPoint(xy) for xy in zip(pop_data["LONG"], pop_data["LAT"])]
        gdf_pop = gpd.GeoDataFrame(pop_data, geometry=geom, crs="EPSG:4326").to_crs(epsg=27700)
        coords_pop = np.array([[pt.x, pt.y] for pt in gdf_pop.geometry])
        pop_vals = gdf_pop["Population"].values

        # Use same grid
        xmin, ymin, xmax, ymax = gdf_pop.total_bounds
        step = 1000
        grid_pts = [ShapelyPoint(x, y) for x in np.arange(xmin, xmax, step)
                     for y in np.arange(ymin, ymax, step)]
        grid_grav = gpd.GeoDataFrame(geometry=grid_pts, crs=gdf_pop.crs)
        grid_grav_coords = np.array([[pt.x, pt.y] for pt in grid_grav.geometry])
        grid_grav_latlon = grid_grav.to_crs(epsg=4326)
        grid_grav["lat"] = grid_grav_latlon.geometry.y
        grid_grav["lon"] = grid_grav_latlon.geometry.x

        tree_pop = BallTree(coords_pop, leaf_size=50, metric="euclidean")

        grav_scenarios = [
            (1.0, 2500), (1.5, 2500), (2.0, 2500),  # vary beta
            (1.5, 2000), (1.5, 3000),                 # vary radius
        ]

        grav_sensitivity = []
        for beta_val, radius_val in grav_scenarios:
            idxs_list, dists_list = tree_pop.query_radius(grid_grav_coords, r=radius_val, return_distance=True)
            scores = []
            for idxs, d in zip(idxs_list, dists_list):
                idxs = np.array(idxs, dtype=int)
                d = np.array(d)
                if len(idxs) == 0:
                    scores.append(0)
                    continue
                d = np.where(d == 0, 1e-6, d)
                scores.append((pop_vals[idxs] / (d ** beta_val)).sum())
            scores = np.log1p(np.array(scores))
            top5_idx = np.argsort(scores)[-5:][::-1]
            label = f"beta={beta_val}, radius={radius_val}m"
            print(f"\n  {label}:")
            for rank, idx in enumerate(top5_idx, 1):
                print(f"    {rank}. ({grid_grav.iloc[idx]['lat']:.4f}, {grid_grav.iloc[idx]['lon']:.4f})  score={scores[idx]:.2f}")
                grav_sensitivity.append({
                    "scenario": label, "rank": rank,
                    "lat": grid_grav.iloc[idx]["lat"], "lon": grid_grav.iloc[idx]["lon"],
                    "score": scores[idx]
                })

        grav_sens_df = pd.DataFrame(grav_sensitivity)
        grav_sens_path = os.path.join(OUTPUT_DIR, "gravity_sensitivity.csv")
        grav_sens_df.to_csv(grav_sens_path, index=False)
        print(f"\n  Saved: {grav_sens_path}")
    else:
        print("  Skipped — population/coordinate data not found")
except Exception as e:
    print(f"  Skipped — {e}")


# ──────────────────────────────────────────────
# 12. Connectivity sensitivity analysis (alpha/beta weights)
# ──────────────────────────────────────────────

print("\n\n" + "=" * 55)
print("CONNECTIVITY SENSITIVITY (distance α vs diversity β)")
print("=" * 55)

if has_connectivity and "harmonic_mean_adj_dist_norm" in grid.columns and "line_unique_count_norm" in grid.columns:
    conn_sensitivity = []
    alpha_values = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]

    for alpha_val in alpha_values:
        beta_val = 1.0 - alpha_val
        score = alpha_val * grid["harmonic_mean_adj_dist_norm"].fillna(0) + beta_val * grid["line_unique_count_norm"].fillna(0)
        top5_idx = score.nlargest(5).index
        label = f"α={alpha_val:.1f}, β={beta_val:.1f}"
        print(f"\n  {label}:")
        for rank, idx in enumerate(top5_idx, 1):
            r = grid.loc[idx]
            print(f"    {rank}. ({r['lat']:.4f}, {r['lon']:.4f})  score={score.loc[idx]:.4f}")
            conn_sensitivity.append({
                "scenario": label, "rank": rank,
                "lat": r["lat"], "lon": r["lon"],
                "score": score.loc[idx]
            })

    conn_sens_df = pd.DataFrame(conn_sensitivity)
    conn_sens_path = os.path.join(OUTPUT_DIR, "connectivity_sensitivity.csv")
    conn_sens_df.to_csv(conn_sens_path, index=False)
    print(f"\n  Saved: {conn_sens_path}")
else:
    print("  Skipped — connectivity scores not available")


print("\nDone.")