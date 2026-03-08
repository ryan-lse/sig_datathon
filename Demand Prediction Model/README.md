# Gravity Model Scoring Pipeline

## Overview

This pipeline computes a per-grid-cell **gravity score** across London, quantifying the influence of surrounding population on each location. The score considers both **population density** and **distance decay**, assigning higher scores to areas with dense nearby populations.

This metric serves as **one parameter in a Multi-Criteria Scoring Model**, combined with other metrics such as travel accessibility and economic potential, to produce a final suitability heatmap for site selection or spatial prioritisation.

---

## Pipeline Stages

### Stage 1 — Data Loading & Preprocessing

Load population and geographic coordinates for small areas (OAs) across London.

**Input:**

* Population CSV: OA codes and total population
* Coordinates CSV: OA codes with latitude/longitude

**Output:** A merged GeoDataFrame with population counts and point geometries.

**Robustness notes:**

* Ensure OA codes match between datasets
* Confirm coordinate CRS is EPSG:4326 initially

---

### Stage 2 — Spatial Conversion

Convert geographic coordinates into a **projected CRS (EPSG:27700)** for accurate distance computations in meters.

**Output:** GeoDataFrame with population points in projected coordinates.

**Robustness notes:**

* All spatial operations (distance, grid creation) must use the projected CRS
* Validate total bounds of points for correct grid coverage

---

### Stage 3 — Candidate Grid Generation

Generate a uniform grid across London for analysis.

**Input:** Projected population points (Stage 2).

**Output:** GeoDataFrame of grid points covering the study area.

**Parameters:**

* Grid spacing: **1,000m × 1,000m** (adjustable for granularity vs. performance)

**Robustness notes:**

* Clip the grid to the study area if necessary
* Log total number of grid points for reproducibility

---

### Stage 4 — Gravity Score Computation

Compute the **gravity score** for each grid cell based on surrounding populations.

**Method:**

1. Convert population points and grid points to arrays of coordinates
2. Use a **BallTree** for efficient neighbor lookup
3. For each grid point, identify all population points within a **radius** (e.g., 2,500m)
4. Compute:

[
\text{Gravity Score} = \sum \frac{\text{Population}_i}{(\text{Distance}_i)^\beta}
]

where β controls the distance decay (e.g., β = 1.5)

**Output:** Gravity score per grid point.

**Robustness notes:**

* Replace zero distances with a small epsilon to avoid division errors
* Consider varying β to test sensitivity

---

### Stage 5 — Normalisation & Ranking

Normalise scores for comparability and rank grid points.

**Method:**

1. Apply log transformation: `gravity_log = log1p(gravity_score)`
2. Rank points descending by log-transformed score

**Output:** GeoDataFrame with: `lat`, `lon`, `gravity_score`, `gravity_log`, `rank`.

**Robustness notes:**

* Sorting by descending gravity ensures rank 1 = highest influence
* Optional: extract **top N points** for quick analysis

---

### Stage 6 — Output & Export

Export the results for downstream use.

**Output formats:**

* CSV: `grid_latlon_ranked.csv`
* Top 10 locations CSV: `top10_grid.csv`
* Optional GeoJSON for GIS visualisation

**Recommended usage:**

* Feed into a **multi-value scoring model** alongside other metrics (travel time, crowding, accessibility)
* Normalise each metric to 0–1 before weighted combination

---

## Parameters

| Parameter | Description                                                  |
| --------- | ------------------------------------------------------------ |
| `radius`  | Neighborhood search radius (meters) for population influence |
| `beta`    | Distance decay exponent controlling influence drop-off       |
| `step`    | Grid spacing (meters)                                        |

Adjust for sensitivity and computation efficiency.

---

## Outputs

| Output                  | Description                             | Format             |
| ----------------------- | --------------------------------------- | ------------------ |
| Gravity scores per grid | Influence of surrounding population     | CSV / GeoDataFrame |
| Top-ranked points       | Highest-scoring grid cells              | CSV                |
| Grid for mapping        | Full spatial coverage for visualization | GeoJSON            |

---

## Dependencies

| Library      | Purpose                               |
| ------------ | ------------------------------------- |
| Python 3.8+  | Runtime                               |
| pandas       | Data handling                         |
| geopandas    | Spatial operations and CRS management |
| shapely      | Geometries                            |
| numpy        | Distance calculations                 |
| matplotlib   | Visualization                         |
| scikit-learn | BallTree for neighbor search          |

Install dependencies:

```bash
pip install pandas geopandas shapely numpy matplotlib scikit-learn
```

---

## Data Sources

| Dataset     | Source                 | Notes                       |
| ----------- | ---------------------- | --------------------------- |
| Population  | ONS / Census CSV       | Total population per OA     |
| Coordinates | ONS / London Datastore | Latitude & Longitude per OA |

---

## Key Assumptions

1. **Projected CRS (EPSG:27700)** is used for all distance computations
2. **Distance decay (β)** approximates how influence decreases with distance
3. **Radius** defines the maximum neighborhood considered for influence
4. Grid points represent **centroids of analysis cells**

---

## Integration with Multi-Criteria Model

The gravity score forms **one layer** in a weighted combination of metrics:

1. **Gravity Score** (population influence)
2. **Travel time reduction** (from transport analysis)
3. **Crowding reduction potential**

All scores are normalised to 0–1, then combined to produce a final suitability heatmap. Top-ranked cells highlight locations with high population influence, making them candidates for further analysis or intervention.

