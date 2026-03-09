# London Station Demand Prediction Model (Gravity Model)

This module estimates the **potential passenger demand** for a new transport station in London using a spatial **gravity model**.

The model evaluates how population surrounding a potential station location contributes to expected demand, with influence decreasing as distance increases.

The output is a **demand score** that can later be integrated with other metrics (e.g. congestion relief, connectivity, accessibility) in the team’s final scoring system.

---

# Overview

The workflow consists of two stages:

## Data preparation

- Load population data for London Output Areas
- Load geographic coordinates for each area
- Load existing London rail station locations
- Merge population and coordinate datasets

## Gravity demand model

- Generate candidate station locations
- Remove locations too close to existing stations
- Estimate population-based demand using a gravity model
- Apply a log transformation
- Rank candidate locations by predicted demand

---

# Data Sources

The model combines several datasets.

## Population data

Population counts for each **Output Area (OA)** in London.

Fields used:

- Area code (`OA11CD`)
- Total population (`All Ages`)

## Geographic coordinates

Latitude and longitude coordinates for each Output Area centroid.

Fields used:

- Latitude
- Longitude

## Existing transport stations

Combined dataset containing locations of London rail stations including:

- Underground
- Overground
- DLR
- Elizabeth Line

Fields used:

- Station latitude
- Station longitude

These datasets are merged to create a **geospatial population dataset** used for demand estimation.

---

# Methodology

## Spatial data preparation

Population locations and station locations are converted into a **GeoDataFrame** and reprojected to the **British National Grid (EPSG:27700)** coordinate system.

This projection allows distance calculations in **meters**, improving spatial accuracy.

---

# Candidate station locations

Potential station locations are generated using a **regular spatial grid** covering the London study area.

Grid resolution:

**1 km × 1 km spacing**

The grid is generated using the spatial bounds of the population dataset.

Each grid point represents a **possible new station location**.

---

# Station placement constraint

To prevent unrealistic station placement, candidate locations that are too close to existing stations are removed.

Constraint:

**minimum distance to existing station = 800 meters**

Candidate points within this radius are excluded from the analysis.

This ensures that the model identifies **new coverage areas rather than duplicating existing stations**.

---

# Distance calculation

Distances between candidate locations and nearby population centres are computed using Euclidean distance in projected coordinates.

To improve computational performance, the model uses a **BallTree spatial index**, which allows efficient spatial queries.

Search radius:

**2.5 km**

Only population centres within this distance influence the demand score.

---

# Gravity demand model

Passenger demand at each candidate station location is estimated using a **gravity model**.

The model assumes that demand increases with nearby population but decreases with distance.

The demand contribution from each population area is calculated as:

G_c = Σ (P_i / d_ic^β)

Where:

- **G_c** = gravity demand score for candidate location c  
- **P_i** = population of area i  
- **d_ic** = distance between area i and candidate location c  
- **β** = distance decay parameter  

Model parameter:

β = **1.5**

This parameter controls how quickly demand decreases as distance increases.

Population closer to a candidate station therefore contributes **more strongly** to the predicted demand.

---

# Log transformation

Gravity scores can vary significantly across locations.

To reduce extreme values and improve comparability, a **log transformation** is applied:

G_log = log(1 + G_c)

This transformation:

- compresses large values
- improves visualization
- stabilizes the distribution of scores

The transformed value is used for ranking candidate station locations.

---

# Output

The model outputs a dataset containing predicted demand for all candidate locations.

Key fields include:

| Column | Description |
|------|------|
| lat | candidate location latitude |
| lon | candidate location longitude |
| gravity_score | raw gravity demand score |
| gravity_log | log-transformed demand score |

---

# Key Results

The model identifies locations with **high potential passenger demand**, typically corresponding to densely populated areas that are relatively far from existing stations.

These areas represent promising candidates for new station development.

The highest-ranked candidate locations are determined by sorting grid points based on their **gravity demand score**.

---

# Limitations

This gravity model provides a **simplified estimate of potential demand**.

Limitations include:

- demand is estimated using population only
- employment density and commuting flows are not included
- transport network structure is not explicitly modeled
- travel times and service frequency are not considered

Despite these simplifications, the model provides a useful indicator of **population-driven demand for new transport infrastructure**.
