# Tube Accessibility Gap Scoring Pipeline

## Overview

This pipeline computes a per-grid-cell **accessibility gap score** across London, quantifying how underserved each area is by the existing Tube network. The score combines two components: **physical distance** to nearby stations (adjusted for real-world walking) and **line diversity** of those stations. High scores indicate areas that are both far from the Tube and lack variety in the lines available — making them strong candidates for a new station.



---

## Pipeline Stages



---

### Stage 1 — Station Data Preparation

Used Arcgis API to download london underground station location in geojson format.


**Robustness notes:**
- Verify completeness — the Underground network has 272 stations; 
- Decide upfront whether to include Elizabeth line, DLR, or Overground and document the decision; **recommendation is Underground only** for consistency with the datathon brief
- Station coordinates are in lon and lat

---

### Stage 2 — K-Nearest Station Distance Computation

For each grid cell centroid, find the 3 nearest Tube stations and compute adjusted walking distances.

**Input:** Grid centroids from Stage 1, station locations from Stage 2.

**Output:** For each grid cell: indices and adjusted distances to the 3 nearest stations (`d₁`, `d₂`, `d₃`).

**Method:**
1. Use  KD-tree to query the 3 nearest stations for every centroid in a single batch operation
2. Multiply each Euclidean distance by a **correction factor of 1.3** to approximate real walking distance along London's street network

**Parameters:**
- k = **3** nearest stations
- Correction factor = **1.3** (standard urban walking adjustment from transport literature)

**Robustness notes:**
- The correction factor of 1.3 is an empirical approximation; values between 1.2–1.4 are common in the literature — note this assumption in the report
- If computational resources allow, consider validating a sample of corrected distances against actual walking distances from OpenStreetMap routing to confirm the factor is reasonable for London

---

### Stage 3 — Line Diversity 

Assess how varied the Tube line coverage is around each grid cell, based on the lines serving its 3 nearest stations.

**Input:** The 3 nearest stations per grid cell (from Stage 3), station-to-line mapping (from Stage 2).

**Output:** For each grid cell, collect unique lines from the 3 stations, then quantify as count

**Method:**
1. For each grid cell, pool all line-station connections across its 3 nearest stations

Implementation note: `find_line_diversity` builds a station-to-lines lookup from `NAME`/`LINES`, parses comma-separated `LINES`, pools lines from `nearest_station_1..k` per row, computes `line_unique_count`, then min-max scales it to `line_unique_count_norm`.

2. Count number of unique lines
3. Normalize, then `1 − line_unique_count_norm`, since we are assessing connectivity **gap**


---

### Stage 4 — Combination

Combine distance and diversity into a single accessibility gap score per grid cell.

**Input:** Distances (`d₁`, `d₂`, `d₃`) and diversity penalty per cell from Stages 3–4.

**Output:** A single normalised accessibility gap score (0–1) per grid cell.

**Method:**
1. Compute **Harmonic mean** adjusted distance per cell: `D = 3 / (1/adj_d1 + 1/adj_d2 + 1/adj_d3) `
2. Apply **min-max normalisation** to D across all cells: `D_norm = (D − D_min) / (D_max − D_min)`
3. Combine using weighted addition: `Connectivity  Score = α × D_norm + β × Diversity_Penalty` where α + β = 1

**weights:** α = 0.5 (distance), β = 0.5 (diversity). 
For sensitivity analysis:
Physical proximity could be weighted more heavily because it is the primary determinant of whether someone can realistically walk to a station.

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
## Leave out Bus Stops

---

## Sensitivity Analysis
1. k nearest neighbors
2. α, β
3. 

## Integration with Multi-Criteria Model

This pipeline produces one of three input layers for the final weighted linear combination:

1. **Travel time reduction potential** (separate pipeline)
2. **Crowding reduction potential** (separate pipeline)
3. **Accessibility gap score** (this pipeline)

All three scores are normalised to 0–1 and combined with user-defined weights to produce the final suitability heatmap. The top-scoring grid cells on the combined heatmap identify candidate zones for the proposed new station.