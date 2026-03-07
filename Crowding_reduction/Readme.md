# London Station Crowding Relief Model

This module estimates how much congestion a **new transport station** could relieve in the London rail network.

The model uses **Transport for London (TfL) station usage data** to estimate how passenger demand may redistribute if a new station is built at a candidate location.

The output is a **normalized crowding score** that can be combined with other metrics (e.g. accessibility, population demand) in the team's final scoring system.

---

# Overview

The workflow consists of two stages:

1. **Data preparation**
   - Clean station location datasets
   - Merge with annual passenger flows

2. **Crowding relief model**
   - Generate candidate station locations
   - Estimate passenger diversion from nearby stations
   - Compute a crowding relief score for each candidate location
   - Normalize the score for use in the final team model

---

# Data Sources

Transport for London (TfL):

- Underground station locations
- Overground station locations
- DLR station locations
- Elizabeth line station locations
- Annualised station entry/exit counts

These datasets are combined to produce a cleaned station dataset used by the model.

---

# Methodology

## Candidate station locations

Candidate station locations are generated using a regular spatial grid covering Greater London.

Grid bounds:

Latitude:  51.35 → 51.65  
Longitude: -0.35 → 0.20  

This produces a **70 × 70 grid (4900 candidate locations)**.

Each grid point represents a possible new station location.

---

# Distance calculation

Distances between candidate locations and existing stations are computed using the **Haversine great-circle formula**.

d = 2R * arcsin( sqrt( sin²(Δφ / 2) + cos(φ1) * cos(φ2) * sin²(Δλ / 2) ) )

Where:

- R = 6371 km (Earth radius)
- φ = latitude
- λ = longitude

Distances are measured in **kilometres**.

---

# Passenger diversion model

For each nearby station i, the number of passengers that could shift to the candidate location is estimated using a **distance-decay function**:

D_i = α * F_i * exp(-β * d_i)

Where:

- D_i = diverted passenger flow from station i
- F_i = annual passenger flow at station i
- d_i = distance from candidate location to station i
- α = maximum share of passengers who may shift
- β = distance decay parameter

Model parameters:

α = 0.25  
β = 1.5  

This means:

- up to **25% of passengers** could potentially shift
- influence decreases exponentially with distance

---

# Crowding relief score

For each candidate location c, the total crowding relief score is the sum of diverted passengers from nearby stations.

Only stations within a **2 km radius** contribute.

S_c = Σ D_i

Where:

- S_c = crowding relief score for candidate location c
- the sum is taken over all stations within 2 km

Higher values indicate **greater potential congestion relief**.

---

# Station placement constraint

To avoid placing stations unrealistically close together, candidate locations are rejected if they are too close to an existing station.

Constraint:

minimum distance to existing station = 0.8 km

Candidates closer than this are excluded from scoring.

---

# Normalized crowding score

To allow integration with other scoring components, the crowding score is normalized to the range **0–1**.

S_norm = (S_c - S_min) / (S_max - S_min)

Where:

- S_max = maximum crowding score across all candidate locations
- S_min = minimum crowding score

The normalized score (`crowding_score_norm`) is the value used by the team.

---

# Output

The main output file is:

team_crowding_scores.csv

Columns:

| Column | Description |
|------|------|
| lat | candidate location latitude |
| lon | candidate location longitude |
| crowding_score | estimated passenger diversion |
| crowding_score_norm | normalized crowding score (0–1) |
| min_distance_to_station_km | distance to nearest existing station |
| top_relieved_stations | stations contributing most to relief |

The normalized score can be combined with other metrics in the final scoring system.
---

# Scripts

## data_prep.py

Loads and cleans station datasets and merges them with TfL passenger flow data.

Output files:

combined_stations.geojson  
combined_stations.csv  

---

## model.py

Runs the crowding relief model.

Steps:

1. Load cleaned station dataset
2. Generate candidate station locations
3. Compute distances to existing stations
4. Estimate passenger diversion
5. Calculate crowding scores
6. Normalize scores
7. Export results

Output:

team_crowding_scores.csv

---

# Key Results

The model identifies several major congestion-relief hotspots in London, including:

- King's Cross / Camden
- Stratford / East London
- South Kensington
- Finsbury Park / Highbury

These areas correspond to major passenger demand centres in the London rail network.

---

# Limitations

This model provides a **simplified estimate** of congestion relief.

Limitations include:

- passenger behaviour is approximated using a distance-decay function
- network structure and travel times are not explicitly modelled
- population density and accessibility are handled by other components of the team model

Despite these simplifications, the model provides a **useful indicator of potential congestion relief**.

---

# Repository Structure

project/

data_prep.py  
model.py  

combined_stations.geojson  
team_crowding_scores.csv  

README.md

---

# Usage

Run the data preparation step:

python data_prep.py

Then run the crowding model:

python model.py

The final scoring dataset will be generated as:

team_crowding_scores.csv

This file can then be merged with other scoring components.
