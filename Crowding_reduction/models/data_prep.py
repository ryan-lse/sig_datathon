import pandas as pd
import geopandas as gpd
import numpy as np
import re


# ----------------------------
# 1. Helper function
# ----------------------------
def clean_station_name(x: str) -> str:

    x = str(x).lower().strip()

    # remove punctuation
    x = re.sub(r"[’']", "", x)
    x = re.sub(r"\.", "", x)

    # remove "- dlr" suffix from station CSVs
    x = re.sub(r"\s*-\s*dlr$", "", x)

    # remove mode suffixes from flow dataset
    x = re.sub(r"\s+(lu|lo|dlr|nr|el|tfl|ezl)$", "", x)

    # special case
    x = x.replace("bank and monument", "bank")

    # normalize whitespace
    x = re.sub(r"\s+", " ", x)

    return x


# ----------------------------
# 2. Load station CSV files
# ----------------------------
underground = pd.read_csv("ss/Underground_Stations.csv")
overground = pd.read_csv("ss/Overground_Stations.csv")
dlr = pd.read_csv("ss/DLR_Stations.csv")
elizabeth = pd.read_csv("ss/Elizabeth_Line_Stations.csv")

print("Loaded station CSV files.")

print("Underground columns:", underground.columns.tolist())
print("Overground columns:", overground.columns.tolist())
print("DLR columns:", dlr.columns.tolist())
print("Elizabeth columns:", elizabeth.columns.tolist())


# ----------------------------
# 3. Convert each to GeoDataFrame
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
# 4. Convert coordinates to WGS84
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
# 7. Combine station datasets
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
# ----------------------------
flows = pd.read_excel(
    "ss/AC2024_AnnualisedEntryExit_Public.xlsx",
    header=5
)

print("\nLoaded flow dataset.")
print("Flow columns:", flows.columns.tolist())


# ----------------------------
# 9. Clean station names
# ----------------------------
stations["station"] = stations["NAME"].apply(clean_station_name)
flows["station"] = flows["Station"].apply(clean_station_name)


# ----------------------------
# 10. Keep only necessary flow columns
# ----------------------------
flows = flows[["station", "Annualised"]].copy()


# ----------------------------
# 11. Convert passenger counts to numeric
# ----------------------------
flows["Annualised"] = pd.to_numeric(flows["Annualised"], errors="coerce")


# ----------------------------
# 12. Aggregate flows BEFORE merging
# ----------------------------
flows = flows.groupby("station", as_index=False)["Annualised"].sum()

print("\nUnique stations in flow dataset:", len(flows))


# ----------------------------
# 13. Merge passenger flows into station locations
# ----------------------------
stations = stations.merge(
    flows,
    on="station",
    how="left"
)


# ----------------------------
# 14. Collapse duplicate station rows
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
# 15. Diagnostics
# ----------------------------
print("\nMerge complete.")

print("Stations with passenger data:",
      stations["Annualised"].notna().sum())

print("Stations without passenger data:",
      stations["Annualised"].isna().sum())


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


# ----------------------------
# 16. Check unmatched stations
# ----------------------------
unmatched = stations[stations["Annualised"].isna()][["station"]]

print("\nSample unmatched stations:")
print(unmatched.sort_values("station").head(30))


# ----------------------------
# 17. Dataset sanity checks
# ----------------------------
print("\nTotal passengers in dataset:",
      stations["Annualised"].sum())

print("\nTotal number of stations:",
      len(stations))


# ----------------------------
# 18. Save cleaned dataset
# ----------------------------
stations.to_file(
    "ss/combined_stations.geojson",
    driver="GeoJSON"
)

stations.drop(columns="geometry").to_csv(
    "ss/combined_stations.csv",
    index=False
)

print("\nSaved:")
print("- ss/combined_stations.geojson")
print("- ss/combined_stations.csv")
