import numpy as np
import math 
import geopandas as gpd
import pandas as pd
from scipy.spatial import cKDTree
import requests
import os
import json

def load_tfl(url, df_name):

    batch_size = 2000
    offset = 0

    all_features = []
    res = []
    while True:
        params = {
        "where": "1=1",
        "outFields": "*",
        "returnGeometry": True,
        "outSR": 27700,  
        "f": "geojson",
        "resultOffset": offset,
        "resultRecordCount": batch_size
        }
        response = requests.get(url, params=params).json()
        res.extend([{k:v} for k,v in response.items()])
        #print(response)
        all_features.extend(response['features'])

        if not response['features']:
            break

        offset += batch_size

    print("Total records:", len(all_features))


    geojson_data = {
    "type": "FeatureCollection",
    "features": all_features
    }

    output_dir = "data"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{df_name}.geojson")

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(geojson_data, f, ensure_ascii=False, indent=2)

    print(f"Exported to {output_path}")












def nearest_neighbor(centroids, stations, k=3, correction_factor=1.3):


    if isinstance(centroids, gpd.GeoDataFrame) and 'geometry' in centroids.columns:
        centroid_coords = np.column_stack((centroids.geometry.x, centroids.geometry.y))
        result = pd.DataFrame({'lat':centroids['lat'], 'lon':centroids['lon']})
    else:
        print(f"input centroids is not in geopandas format")

    if isinstance(stations, gpd.GeoDataFrame) and 'geometry' in stations.columns:
        station_coords = np.column_stack((stations.geometry.x, stations.geometry.y))
    else:
        print(f"input stations is not in geopandas format")

    print(f"Total {len(centroid_coords)} grid points")
    print(f"Mapping {len(stations)} stations")


    tree = cKDTree(station_coords)
    dist, idx = tree.query(centroid_coords, k=k)


    # Make the results a dataframe
    for i in range(k):
        result[f"nearest_station_{i+1}"] = stations.iloc[idx[:,i]]['NAME'].values
        result[f"nearest_station_{i+1}_dist"] = dist[:,i] * correction_factor
        result[f"nearest_station_{i+1}_lat"] = stations.iloc[idx[:,i]]['lat'].values
        result[f"nearest_station_{i+1}_long"] = stations.iloc[idx[:,i]]['lon'].values

    if k >= 1:
        dist_cols = [f"nearest_station_{i+1}_dist" for i in range(k)]
        with np.errstate(divide='ignore', invalid='ignore'):
            reciprocal_sum = (1 / result[dist_cols]).sum(axis=1)
            result["harmonic_mean_adj_dist"] = k / reciprocal_sum

        hm = result["harmonic_mean_adj_dist"]
        hm_min = hm.min()
        hm_max = hm.max()
        if hm_max > hm_min:
            result["harmonic_mean_adj_dist_norm"] = (hm - hm_min) / (hm_max - hm_min)
        else:
            result["harmonic_mean_adj_dist_norm"] = 0.0
    
    return result 

def find_line_diversity(nearest_df, stations, k=3, station_col='NAME', lines_col='LINES'):
    station_cols = [f"nearest_station_{i+1}" for i in range(k)]
    missing_cols = [col for col in station_cols if col not in nearest_df.columns]
    if missing_cols:
        raise ValueError(f"Missing nearest-station columns: {missing_cols}")
    if station_col not in stations.columns or lines_col not in stations.columns:
        raise ValueError(
            f"stations must contain '{station_col}' and '{lines_col}' columns"
        )

    def _parse_lines(value):
        if isinstance(value, list):
            return [str(x).strip() for x in value if str(x).strip()]
        if pd.isna(value):
            return []
        return [x.strip() for x in str(value).split(',') if x.strip()]

    station_to_lines = {
        row[station_col]: _parse_lines(row[lines_col])
        for _, row in stations[[station_col, lines_col]].drop_duplicates(subset=[station_col]).iterrows()
    }

    result = nearest_df.copy()
    unique_counts = []

    for _, row in result[station_cols].iterrows():
        pooled_lines = []
        for station_name in row.values:
            pooled_lines.extend(station_to_lines.get(station_name, []))
        unique_counts.append(len(set(pooled_lines)))

    result['line_unique_count'] = unique_counts

    lc = result['line_unique_count']
    lc_min = lc.min()
    lc_max = lc.max()
    if lc_max > lc_min:
        # Higher line diversity means lower penalty.
        result['line_unique_count_norm'] = 1 - ((lc - lc_min) / (lc_max - lc_min))
    else:
        result['line_unique_count_norm'] = 0.0

    return result


def combine_connectivity_score(result_df, alpha=0.5, beta=0.5):
    if "harmonic_mean_adj_dist_norm" not in result_df.columns:
        raise ValueError("Missing required column: 'harmonic_mean_adj_dist_norm'")

    if "line_unique_count_norm" not in result_df.columns:
        raise ValueError("Missing required column: 'line_unique_count_norm'")

    if not np.isclose(alpha + beta, 1.0):
        raise ValueError("alpha and beta must sum to 1")

    result = result_df.copy()

    result["connectivity_score"] = (
        alpha * result["harmonic_mean_adj_dist_norm"]
        + beta * result["line_unique_count_norm"]
    )

    return result

def bus_norm(bus_df, buffer=500)