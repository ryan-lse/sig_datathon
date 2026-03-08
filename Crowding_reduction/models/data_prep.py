import pandas as pd
import geopandas as gpd
import numpy as np
import re


# ----------------------------
# 1. Helper function
# ----------------------------
def clean_station_name(x: str) -> str:
    x = str(x).lower().strip()
    x = re.sub(r"[’']", "", x)      # remove apostrophes
    x = re.sub(r"\.", "", x)        # remove full stops
    x = re.sub(r"\s+", " ", x)      # normalize spaces
    return x


# ----------------------------
# 2. Load station CSV files
# ----------------------------
underground = pd.read_csv("data/Underground_Stations.csv")
overground = pd.read_csv("data/Overground_Stations.csv")
dlr = pd.read_csv("data/DLR_Stations.csv")
elizabeth = pd.read_csv("data/Elizabeth_Line_Stations.csv")

print("Loaded station CSV files.")
print("Underground columns:", underground.columns.tolist())
print("Overground columns:", overground.columns.tolist())
print("DLR columns:", dlr.columns.tolist())
print("Elizabeth columns:", elizabeth.columns.tolist())


# ----------------------------
# 3. Convert each to GeoDataFrame
#    Assumes X/Y are British National Grid (EPSG:27700)
# ----------------------------
underground = gpd.GeoDataFrame(
    underground,
    geometry=gpd.points_from_xy(underground["X"], underground["Y"]),
    crs="EPSG:27700"
)

overground = gpd.GeoDataFrame(
    overground,
    geometry=gpd.points_from_xy(overground["X"], overground["Y"]),
    crs="EPSG:27700"
)

dlr = gpd.GeoDataFrame(
    dlr,
    geometry=gpd.points_from_xy(dlr["X"], dlr["Y"]),
    crs="EPSG:27700"
)

elizabeth = gpd.GeoDataFrame(
    elizabeth,
    geometry=gpd.points_from_xy(elizabeth["X"], elizabeth["Y"]),
    crs="EPSG:27700"
)


# ----------------------------
# 4. Convert coordinates to WGS84 (lat/lon)
# ----------------------------
underground = underground.to_crs("EPSG:4326")
overground = overground.to_crs("EPSG:4326")
dlr = dlr.to_crs("EPSG:4326")
elizabeth = elizabeth.to_crs("EPSG:4326")


# ----------------------------
# 5. Extract lon/lat columns
# ----------------------------
for df in [underground, overground, dlr, elizabeth]:
    df["lon"] = df.geometry.x
    df["lat"] = df.geometry.y


# ----------------------------
# 6. Add mode labels
# ----------------------------
underground["mode"] = "underground"
overground["mode"] = "overground"
dlr["mode"] = "dlr"
elizabeth["mode"] = "elizabeth"


# ----------------------------
# 7. Combine all station datasets
# ----------------------------
stations = gpd.GeoDataFrame(
    pd.concat([underground, overground, dlr, elizabeth], ignore_index=True),
    geometry="geometry",
    crs="EPSG:4326"
)

print("\nCombined station dataset created.")
print("Number of station rows:", len(stations))


# ----------------------------
# 8. Load passenger flow Excel file
#    header=5 because the real headers start on row 6
# ----------------------------
flows = pd.read_excel(
    "data/AC2024_AnnualisedEntryExit_Public.xlsx",
    header=5
)

print("\nLoaded flow dataset.")
print("Flow columns:", flows.columns.tolist())


# ----------------------------
# 9. Clean station names in both datasets
# ----------------------------
stations["station"] = stations["NAME"].apply(clean_station_name)
flows["station"] = flows["Station"].apply(clean_station_name)


# ----------------------------
# 10. Keep only needed columns from flows
# ----------------------------
flows = flows[["station", "Mode", "Station", "Annualised"]].copy()


# ----------------------------
# 11. Convert Annualised to numeric
# ----------------------------
flows["Annualised"] = pd.to_numeric(flows["Annualised"], errors="coerce")


# ----------------------------
# 12. Merge passenger flows into stations
# ----------------------------
stations = stations.merge(
    flows[["station", "Annualised"]],
    on="station",
    how="left"
)


# ----------------------------
# 13. Remove duplicate station names across modes
#    so Stratford is not counted 3 times
# ----------------------------
stations = stations.groupby("station").agg({
    "lon": "first",
    "lat": "first",
    "Annualised": "first",
    "geometry": "first"
}).reset_index()

stations = gpd.GeoDataFrame(
    stations,
    geometry="geometry",
    crs="EPSG:4326"
)


# ----------------------------
# 14. Diagnostics
# ----------------------------
print("\nMerge complete.")
print("Matched passenger counts:", stations["Annualised"].notna().sum())
print("Unmatched station rows:", stations["Annualised"].isna().sum())

print("\nSample rows:")
print(stations[["station", "lon", "lat", "Annualised"]].head(10))

print("\nTop 15 stations by annualised flow:")
print(
    stations.sort_values("Annualised", ascending=False)[
        ["station", "Annualised"]
    ].head(15)
)

print("\nCoordinate system:", stations.crs)
print("Bounding box:", stations.total_bounds)
print("Object type:", type(stations))


# ----------------------------
# 14b. Check unmatched stations
# ----------------------------
unmatched = stations[stations["Annualised"].isna()][["station"]].copy()
print("\nSample unmatched stations:")
print(unmatched.sort_values("station").head(30))


# ----------------------------
# 15. Save cleaned combined dataset
# ----------------------------
stations.to_file("ss/combined_stations.geojson", driver="GeoJSON")
stations.drop(columns="geometry").to_csv("ss/combined_stations.csv", index=False)

print("\nSaved:")
print("- output/combined_stations.geojson")
print("- output/combined_stations.csv")
