import pandas as pd
import geopandas as gpd
import numpy as np
import matplotlib.pyplot as plt


def pretty_station_name(name):
    name = str(name).strip().title()

    fixes = {
        "King'S Cross": "King's Cross",
        "St Pancras": "St Pancras",
        "St Johns Wood": "St John's Wood",
        "Earls Court": "Earl's Court",
        "Bromley-By-Bow": "Bromley-by-Bow",
        "Caledonian Road & Barnsbury": "Caledonian Road & Barnsbury"
    }

    for bad, good in fixes.items():
        name = name.replace(bad, good)

    return name


# ----------------------------
# 1. Load cleaned station dataset
# ----------------------------
stations = gpd.read_file("ss/combined_stations.geojson")
stations["station"] = stations["station"].apply(pretty_station_name)

print("Stations loaded:", len(stations))
print(stations.head())


# ----------------------------
# 2. Keep only stations with valid passenger flow
# ----------------------------
stations = stations.dropna(subset=["Annualised"]).copy()
stations["Annualised"] = pd.to_numeric(stations["Annualised"], errors="coerce")
stations = stations.dropna(subset=["Annualised"]).copy()

print("\nStations with valid Annualised flow:", len(stations))


# ----------------------------
# 3. Haversine distance function (km)
# ----------------------------
def haversine(lat1, lon1, lat2, lon2):
    """Great-circle distance in km."""
    R = 6371.0

    lat1 = np.radians(lat1)
    lon1 = np.radians(lon1)
    lat2 = np.radians(lat2)
    lon2 = np.radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2
    c = 2 * np.arcsin(np.sqrt(a))

    return R * c


def find_nearest_station(lat, lon, station_lats, station_lons, station_names):
    distances = haversine(lat, lon, station_lats, station_lons)
    idx = np.argmin(distances)
    return station_names[idx], distances[idx]


# ----------------------------
# 4. Generate candidate station locations
# ----------------------------
lat_min, lat_max = 51.35, 51.65
lon_min, lon_max = -0.35, 0.20

lat_range = np.linspace(lat_min, lat_max, 70)
lon_range = np.linspace(lon_min, lon_max, 70)

candidate_points = [(lat, lon) for lat in lat_range for lon in lon_range]
candidates = pd.DataFrame(candidate_points, columns=["lat", "lon"])

candidates = gpd.GeoDataFrame(
    candidates,
    geometry=gpd.points_from_xy(candidates["lon"], candidates["lat"]),
    crs="EPSG:4326"
)

print("\nNumber of candidate locations:", len(candidates))


# ----------------------------
# 5. Model parameters
# ----------------------------
alpha = 0.25
beta = 1.5
radius_km = 2.0
min_station_distance_km = 0.8

print("\nModel parameters:")
print("alpha =", alpha)
print("beta =", beta)
print("radius_km =", radius_km)
print("min_station_distance_km =", min_station_distance_km)


# ----------------------------
# 6. Pre-extract station arrays
# ----------------------------
station_lats = stations["lat"].to_numpy()
station_lons = stations["lon"].to_numpy()
station_flows = stations["Annualised"].to_numpy()
station_names = stations["station"].to_numpy()


# ----------------------------
# 7. Compute crowding scores
# ----------------------------
scores = []
top_contributors = []
min_distances = []
valid_candidate = []

for idx, candidate in candidates.iterrows():
    cand_lat = candidate["lat"]
    cand_lon = candidate["lon"]

    distances = haversine(cand_lat, cand_lon, station_lats, station_lons)
    min_d = distances.min()
    min_distances.append(min_d)

    if min_d < min_station_distance_km:
        scores.append(np.nan)
        top_contributors.append("")
        valid_candidate.append(False)
    else:
        local_mask = distances < radius_km

        if local_mask.sum() == 0:
            scores.append(0.0)
            top_contributors.append("")
            valid_candidate.append(True)
        else:
            local_distances = distances[local_mask]
            local_flows = station_flows[local_mask]
            local_names = station_names[local_mask]

            diverted = alpha * local_flows * np.exp(-beta * local_distances)
            total_diverted = diverted.sum()

            scores.append(total_diverted)
            valid_candidate.append(True)

            contrib_df = pd.DataFrame({
                "station": local_names,
                "diverted": diverted
            }).sort_values("diverted", ascending=False)

            top3 = ", ".join(contrib_df["station"].head(3).tolist())
            top_contributors.append(top3)

    if idx % 500 == 0:
        print(f"Processed {idx} / {len(candidates)} candidates")

candidates["crowding_score"] = scores
candidates["top_relieved_stations"] = top_contributors
candidates["min_distance_to_station_km"] = min_distances
candidates["valid_candidate"] = valid_candidate


# ----------------------------
# 8. Rank best candidate locations
# ----------------------------
valid_candidates = candidates.dropna(subset=["crowding_score"]).copy()

# Normalize for team scoring use
score_min = valid_candidates["crowding_score"].min()
score_max = valid_candidates["crowding_score"].max()

valid_candidates["crowding_score_norm"] = (
    (valid_candidates["crowding_score"] - score_min) / (score_max - score_min)
)

# write normalized score back to full candidates
candidates = candidates.merge(
    valid_candidates[["lat", "lon", "crowding_score_norm"]],
    on=["lat", "lon"],
    how="left"
)

top20 = valid_candidates.sort_values("crowding_score", ascending=False).head(20).copy()
top100 = valid_candidates.sort_values("crowding_score", ascending=False).head(100).copy()

print("\nTop 20 candidate locations:")
print(top20[["lat", "lon", "crowding_score", "min_distance_to_station_km", "top_relieved_stations"]])


# ----------------------------
# 8b. Add nearest existing station to top candidates
# ----------------------------
nearest_names = []
nearest_distances = []

for _, row in top20.iterrows():
    nearest_name, nearest_distance = find_nearest_station(
        row["lat"], row["lon"], station_lats, station_lons, station_names
    )
    nearest_names.append(pretty_station_name(nearest_name))
    nearest_distances.append(round(nearest_distance, 3))

top20["nearest_station"] = nearest_names
top20["nearest_station_distance_km"] = nearest_distances

nearest_names_100 = []
nearest_distances_100 = []

for _, row in top100.iterrows():
    nearest_name, nearest_distance = find_nearest_station(
        row["lat"], row["lon"], station_lats, station_lons, station_names
    )
    nearest_names_100.append(pretty_station_name(nearest_name))
    nearest_distances_100.append(round(nearest_distance, 3))

top100["nearest_station"] = nearest_names_100
top100["nearest_station_distance_km"] = nearest_distances_100


# ----------------------------
# 9. Clean Top 10 table
# ----------------------------
top10 = top20.head(10).copy()
top10["rank"] = range(1, len(top10) + 1)
top10["lat"] = top10["lat"].round(4)
top10["lon"] = top10["lon"].round(4)
top10["crowding_score_m"] = (top10["crowding_score"] / 1_000_000).round(2)
top10["crowding_score_norm"] = top10["crowding_score_norm"].round(3)

def clean_station_list(x):
    if not x:
        return ""
    station_list = [pretty_station_name(s.strip()) for s in x.split(",")]
    return ", ".join(station_list)

top10["top_relieved_stations"] = top10["top_relieved_stations"].apply(clean_station_list)

top10_table = top10[
    [
        "rank",
        "lat",
        "lon",
        "crowding_score_m",
        "crowding_score_norm",
        "nearest_station",
        "nearest_station_distance_km",
        "top_relieved_stations"
    ]
].copy()

top10_table.columns = [
    "Rank",
    "Latitude",
    "Longitude",
    "Crowding Relief (millions)",
    "Normalized Crowding Score",
    "Nearest Existing Station",
    "Nearest Station Distance (km)",
    "Main Relieved Stations"
]

print("\nTop 10 Candidate Locations (Clean Table):")
print(top10_table)

print("\nTop 10 normalized crowding scores:")
print(
    top10_table[
        [
            "Rank",
            "Latitude",
            "Longitude",
            "Crowding Relief (millions)",
            "Normalized Crowding Score",
            "Nearest Existing Station"
        ]
    ].to_string(index=False)
)


# ----------------------------
# 10. Baseline: busiest stations
# ----------------------------
busiest_stations = stations.sort_values("Annualised", ascending=False)[
    ["station", "Annualised"]
].head(20).copy()

busiest_stations["station"] = busiest_stations["station"].apply(pretty_station_name)
busiest_stations["Annualised"] = (busiest_stations["Annualised"] / 1_000_000).round(2)
busiest_stations.columns = ["Station", "Annualised Passengers (millions)"]

print("\nTop 20 busiest stations:")
print(busiest_stations)


# ----------------------------
# 11. Station relief summary from top 100 candidates
# ----------------------------
station_relief = {}

for _, row in top100.iterrows():
    candidate_lat = row["lat"]
    candidate_lon = row["lon"]

    distances = haversine(candidate_lat, candidate_lon, station_lats, station_lons)
    local_mask = distances < radius_km

    if local_mask.sum() == 0:
        continue

    local_distances = distances[local_mask]
    local_flows = station_flows[local_mask]
    local_names = station_names[local_mask]

    diverted = alpha * local_flows * np.exp(-beta * local_distances)

    for s, d in zip(local_names, diverted):
        station_relief[s] = station_relief.get(s, 0) + d

relief_df = pd.DataFrame(
    station_relief.items(),
    columns=["station", "estimated_relieved_flow"]
).sort_values("estimated_relieved_flow", ascending=False)

relief_df["estimated_relieved_flow"] = (relief_df["estimated_relieved_flow"] / 1_000_000).round(2)
relief_df["station"] = relief_df["station"].apply(pretty_station_name)
relief_df.columns = ["Station", "Estimated Relieved Flow (millions)"]

print("\nTop 20 stations most relieved by top 100 candidates:")
print(relief_df.head(20))


# ----------------------------
# 12. Assign manual hotspot zones
# ----------------------------
def classify_zone(row):
    lat = row["lat"]
    lon = row["lon"]

    if 51.52 < lat < 51.55 and -0.17 < lon < -0.09:
        return "King's Cross / Camden"

    if 51.52 < lat < 51.56 and -0.02 < lon < 0.05:
        return "Stratford / East London"

    if 51.48 < lat < 51.51 and -0.20 < lon < -0.15:
        return "South Kensington"

    if 51.52 < lat < 51.54 and -0.18 < lon < -0.14:
        return "Baker Street / Marylebone"

    if 51.55 < lat < 51.58 and -0.12 < lon < -0.07:
        return "Finsbury Park / Highbury"

    return "Other"


top20["zone"] = top20.apply(classify_zone, axis=1)
top100["zone"] = top100.apply(classify_zone, axis=1)

zone_summary = top20.groupby("zone").agg({
    "crowding_score": "mean",
    "lat": "mean",
    "lon": "mean",
    "zone": "count"
}).rename(columns={"zone": "count_of_top20_points"}).reset_index()

zone_summary["crowding_score"] = (zone_summary["crowding_score"] / 1_000_000).round(2)
zone_summary["lat"] = zone_summary["lat"].round(4)
zone_summary["lon"] = zone_summary["lon"].round(4)

zone_summary.columns = [
    "Hotspot",
    "Average Crowding Relief (millions)",
    "Average Latitude",
    "Average Longitude",
    "Count of Top 20 Points"
]

print("\nCrowding Relief Hotspots:")
print(zone_summary)


# ----------------------------
# 13. Sensitivity analysis
# ----------------------------
def compute_top5_for_params(beta_value, radius_value):
    scores_tmp = []

    for _, candidate in candidates.iterrows():
        cand_lat = candidate["lat"]
        cand_lon = candidate["lon"]

        distances = haversine(cand_lat, cand_lon, station_lats, station_lons)
        min_d = distances.min()

        if min_d < min_station_distance_km:
            scores_tmp.append(np.nan)
            continue

        mask = distances < radius_value
        if mask.sum() == 0:
            scores_tmp.append(0.0)
            continue

        diverted = alpha * station_flows[mask] * np.exp(-beta_value * distances[mask])
        scores_tmp.append(diverted.sum())

    tmp = candidates.copy()
    tmp["score"] = scores_tmp
    tmp = tmp.dropna(subset=["score"]).sort_values("score", ascending=False).head(5)
    tmp["score"] = (tmp["score"] / 1_000_000).round(2)
    return tmp[["lat", "lon", "score"]]

print("\nSensitivity analysis:")
print("\nTop 5 with beta=1.0, radius=2.0")
print(compute_top5_for_params(beta_value=1.0, radius_value=2.0))

print("\nTop 5 with beta=2.0, radius=2.0")
print(compute_top5_for_params(beta_value=2.0, radius_value=2.0))

print("\nTop 5 with beta=1.5, radius=1.5")
print(compute_top5_for_params(beta_value=1.5, radius_value=1.5))

print("\nTop 5 with beta=1.5, radius=2.5")
print(compute_top5_for_params(beta_value=1.5, radius_value=2.5))


# ----------------------------
# 14. Save outputs
# ----------------------------
candidates.to_file("ss/candidate_crowding_scores.geojson", driver="GeoJSON")
candidates.drop(columns="geometry").to_csv("ss/candidate_crowding_scores.csv", index=False)

top20.to_file("ss/top20_crowding_locations.geojson", driver="GeoJSON")
top20.drop(columns="geometry").to_csv("ss/top20_crowding_locations.csv", index=False)

top100.to_file("ss/top100_crowding_locations.geojson", driver="GeoJSON")
top100.drop(columns="geometry").to_csv("ss/top100_crowding_locations.csv", index=False)

top10_table.to_csv("ss/top10_candidate_locations_clean.csv", index=False)
busiest_stations.to_csv("ss/top20_busiest_stations.csv", index=False)
relief_df.to_csv("ss/top_relieved_stations.csv", index=False)
zone_summary.to_csv("ss/candidate_zones_summary.csv", index=False)

# Team-ready export
team_scoring = valid_candidates[
    [
        "lat",
        "lon",
        "crowding_score",
        "crowding_score_norm",
        "min_distance_to_station_km",
        "top_relieved_stations"
    ]
].copy()

team_scoring.to_csv("ss/team_crowding_scores.csv", index=False)

print("\nSaved:")
print("- ss/candidate_crowding_scores.geojson")
print("- ss/candidate_crowding_scores.csv")
print("- ss/top20_crowding_locations.geojson")
print("- ss/top20_crowding_locations.csv")
print("- ss/top100_crowding_locations.geojson")
print("- ss/top100_crowding_locations.csv")
print("- ss/top10_candidate_locations_clean.csv")
print("- ss/top20_busiest_stations.csv")
print("- ss/top_relieved_stations.csv")
print("- ss/candidate_zones_summary.csv")
print("- ss/team_crowding_scores.csv")


# ----------------------------
# 15. Useful visual 1: Top 100 candidates
# ----------------------------
fig, ax = plt.subplots(figsize=(10, 8))

stations.plot(
    ax=ax,
    color="lightgray",
    markersize=8,
    alpha=0.7
)

top100.plot(
    ax=ax,
    column="crowding_score",
    cmap="hot",
    markersize=35,
    legend=True,
    alpha=0.9
)

ax.set_title("Top 100 Candidate Locations by Crowding Reduction")
ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")
plt.tight_layout()
plt.show()


# ----------------------------
# 16. Useful visual 2: Top 20 candidates with ranks
# ----------------------------
fig, ax = plt.subplots(figsize=(10, 8))

stations.plot(
    ax=ax,
    color="gray",
    markersize=8,
    alpha=0.5
)

top20.plot(
    ax=ax,
    color="red",
    markersize=45
)
for i, (_, row) in enumerate(top20.iterrows(), start=1):
    ax.text(
        row["lon"] + 0.003,
        row["lat"] + 0.002,
        str(i),
        fontsize=9,
        weight="bold",
        color="black"
    )

ax.set_title("Top 20 Candidate Locations for Crowding Reduction")
ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")
plt.tight_layout()
plt.show()
