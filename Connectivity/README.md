# Tube Accessibility Gap Scoring Pipeline

## Overview

This pipeline computes a per-grid-cell **accessibility gap score** across London, quantifying how underserved each area is by the existing Tube network. The score combines two components: **physical distance** to nearby stations (adjusted for real-world walking) and **line diversity** of those stations. High scores indicate areas that are both far from the Tube and lack variety in the lines available — making them strong candidates for a new station.

This metric feeds into a broader Multi-Criteria Scoring Model alongside travel time reduction and crowding reduction scores, using weighted linear combination to produce a final suitability heatmap.

---

## Pipeline Stages

### Stage 1 — Grid Generation

Divide the study area into a uniform grid of square cells. Each cell is the fundamental unit of analysis.

**Input:** London boundary shapefile or GeoJSON (source: London Datastore or ONS Open Geography Portal).

**Output:** A GeoDataFrame of grid cell polygons with centroid coordinates.

**Parameters:**
- Grid resolution: **500m × 500m** (recommended balance between granularity and computation time)
- CRS: **EPSG:27700** (British National Grid, units in metres) — all datasets must be reprojected to this CRS before any spatial operations
- Study area scope: Restrict to areas within a reasonable catchment of the Tube network (e.g. within 2km of any existing station, or Zones 1–3) to avoid edge effects inflating scores at London's periphery

**Robustness notes:**
- Verify the grid clips cleanly to the study boundary with no partial cells leaking outside
- Log the total cell count for reproducibility

---

### Stage 2 — Station Data Preparation

Assemble a dataset of all London Underground stations with their geographic coordinates and the lines serving each station.

**Input:**
- Station point locations (source: TfL GIS Open Data Hub)
- Station-to-line mapping: each station mapped to every Tube line it serves (source: TfL published data or compiled from official documentation)

**Output:** A table where each row is a station, with columns: `station_name`, `easting`, `northing`, `lines` (list of line names).

**Robustness notes:**
- Verify completeness — the Underground network has 272 stations; confirm your dataset matches
- Decide upfront whether to include Elizabeth line, DLR, or Overground and document the decision; **recommendation is Underground only** for consistency with the datathon brief
- Ensure station coordinates are in EPSG:27700

---

### Stage 3 — K-Nearest Station Distance Computation

For each grid cell centroid, find the 3 nearest Tube stations and compute adjusted walking distances.

**Input:** Grid centroids from Stage 1, station locations from Stage 2.

**Output:** For each grid cell: indices and adjusted distances to the 3 nearest stations (`d₁`, `d₂`, `d₃`).

**Method:**
1. Use a spatial indexing structure (e.g. KD-tree) to efficiently query the 3 nearest stations for every centroid in a single batch operation
2. Multiply each Euclidean distance by a **correction factor of 1.3** to approximate real walking distance along London's street network

**Parameters:**
- k = **3** nearest stations
- Correction factor = **1.3** (standard urban walking adjustment from transport literature)

**Robustness notes:**
- The correction factor of 1.3 is an empirical approximation; values between 1.2–1.4 are common in the literature — note this assumption in the report
- If computational resources allow, consider validating a sample of corrected distances against actual walking distances from OpenStreetMap routing to confirm the factor is reasonable for London

---

### Stage 4 — Line Diversity Penalty

Assess how varied the Tube line coverage is around each grid cell, based on the lines serving its 3 nearest stations.

**Input:** The 3 nearest stations per grid cell (from Stage 3), station-to-line mapping (from Stage 2).

**Output:** A line diversity penalty value between 0 and 1 for each grid cell.

**Method:**
1. For each grid cell, pool all line-station connections across its 3 nearest stations
2. Count **U** = number of unique lines and **T** = total line-station connections
3. Compute: `Diversity Penalty = 1 − (U / T)`

**Interpretation:**
- Penalty → **1.0**: all connections are redundant (same line repeated), area has poor line diversity
- Penalty → **0.0**: every connection is a different line, area already has diverse coverage

**Example:**
- 3 nearest stations all on the Northern line → U=1, T=3 → penalty = 1 − (1/3) = 0.67
- 3 nearest stations on Northern, Victoria, Central → U=3, T=3 → penalty = 1 − (3/3) = 0.00
- 3 nearest stations: one serves Northern + Victoria, one serves Northern, one serves Central → U=3, T=4 → penalty = 1 − (3/4) = 0.25

**Robustness notes:**
- Major interchanges (e.g. Baker Street, 5 lines) will naturally pull T upward — this is intentional, as proximity to a major interchange genuinely represents better connectivity
- If concerned about outlier interchange effects, apply a log transform or cap T; for the datathon scope the simple formula is sufficient

---

### Stage 5 — Score Normalisation and Combination

Combine distance and diversity into a single accessibility gap score per grid cell.

**Input:** Distances (`d₁`, `d₂`, `d₃`) and diversity penalty per cell from Stages 3–4.

**Output:** A single normalised accessibility gap score (0–1) per grid cell.

**Method:**
1. Compute average adjusted distance per cell: `D = (d₁ + d₂ + d₃) / 3`
2. Apply **min-max normalisation** to D across all cells: `D_norm = (D − D_min) / (D_max − D_min)`
3. Combine using weighted addition: `Accessibility Gap Score = α × D_norm + β × Diversity_Penalty` where α + β = 1

**Recommended weights:** α = 0.6 (distance), β = 0.4 (diversity). Physical proximity is weighted more heavily because it is the primary determinant of whether someone can realistically walk to a station.

**Robustness notes:**
- Run **sensitivity analysis** by varying α from 0.5 to 0.8 and checking whether the top-scoring areas change significantly — report this in the paper
- Inspect the score distribution: if scores cluster narrowly, apply a log transform to distances before normalisation to improve discrimination
- **Sanity check**: map the scores and verify that known underserved areas (e.g. parts of South London with poor Tube access) score highly, while central interchange-heavy areas score low

---

## Outputs

| Output | Description | Format |
|---|---|---|
| Accessibility gap scores | One score per grid cell | CSV / GeoDataFrame column |
| Heatmap visualisation | Spatial plot of scores across London | PNG / interactive HTML map |
| Sensitivity analysis results | Score rankings under varied weight parameters | Table / chart |

---

## Dependencies

| Tool / Library | Purpose |
|---|---|
| Python 3.9+ | Runtime |
| GeoPandas | Spatial data handling, grid generation, CRS management |
| Scipy (`cKDTree`) or scikit-learn (`BallTree`) | Efficient k-nearest neighbour queries |
| pandas | Data manipulation, merging station-line lookups |
| numpy | Distance computation, normalisation |
| matplotlib / folium | Mapping results for validation and report figures |

---

## Data Sources

| Dataset | Source | Notes |
|---|---|---|
| London boundary | London Datastore / ONS Open Geography Portal | Use generalised boundary for performance |
| Tube station locations | TfL GIS Open Data Hub | Point geometries, reproject to EPSG:27700 |
| Station-to-line mapping | TfL published data | Verify 272 stations, Underground only |

---

## Key Assumptions

1. **Grid centroid representation**: Each 500m × 500m cell is represented by its centre point for distance calculations.
2. **Euclidean distance × 1.3**: Straight-line distance with correction factor approximates real urban walking distance. This avoids the computational cost of full network routing while remaining empirically grounded.
3. **k = 3 nearest stations**: Three stations provide a more robust picture of local accessibility than a single nearest station, capturing redundancy and alternatives.
4. **Underground only**: DLR, Overground, and Elizabeth line are excluded for scope consistency. Extending to multi-modal rail would be a natural improvement.
5. **Study area scoping**: Peripheral areas beyond reasonable Tube catchment are excluded to prevent boundary effects from inflating scores.

---

## Integration with Multi-Criteria Model

This pipeline produces one of three input layers for the final weighted linear combination:

1. **Travel time reduction potential** (separate pipeline)
2. **Crowding reduction potential** (separate pipeline)
3. **Accessibility gap score** (this pipeline)

All three scores are normalised to 0–1 and combined with user-defined weights to produce the final suitability heatmap. The top-scoring grid cells on the combined heatmap identify candidate zones for the proposed new station.