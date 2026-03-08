import pandas as pd
import geopandas as gpd
import numpy as np
import matplotlib.pyplot as plt
from shapely.geometry import Point
from sklearn.neighbors import BallTree

#Data
population = pd.read_csv(r"Population.csv", sep=";", usecols=[0,2])
population = population.rename(columns={'All Ages': 'Population', 'OA11CD':'Area'})

coordinate = pd.read_csv(r"Coordinate_filter.csv", sep=",")

data = pd.merge(population, coordinate, on='Area')

#Coordinate for spatial 
geometry = [Point(xy) for xy in zip(data['LONG'], data['LAT'])]

gdf = gpd.GeoDataFrame(data, geometry=geometry, crs="EPSG:4326")

#Convert to UK metric CRS (meters)
gdf = gdf.to_crs(epsg=27700)

#Creating candidate grid across London
xmin, ymin, xmax, ymax = gdf.total_bounds
step = 1000
grid_points = [Point(x, y) for x in np.arange(xmin, xmax, step)
                        for y in np.arange(ymin, ymax, step)]
grid = gpd.GeoDataFrame(geometry=grid_points, crs=gdf.crs)

#Compute Gravity Model Value

#Convert coordinates to meters if not already
coords = np.array([[pt.x, pt.y] for pt in gdf.geometry])
pop = gdf['Population'].values

grid_coords = np.array([[pt.x, pt.y] for pt in grid.geometry])

#Build spatial index
tree = BallTree(coords, leaf_size=50, metric='euclidean')

radius = 2500  
#Beta controls how quickly a population’s influence decreases with distance, balancing local density and nearby neighborhoods in the gravity score.
beta = 1.5
idxs_list, dists_list = tree.query_radius(grid_coords, r=radius, return_distance=True)

gravity_scores = []

for idxs, d in zip(idxs_list, dists_list):
    idxs = np.array(idxs, dtype=int)
    d = np.array(d)

    if len(idxs) == 0:
        gravity_scores.append(0)
        continue

    d = np.where(d == 0, 1e-6, d)
    score = (pop[idxs] / (d ** beta)).sum()
    gravity_scores.append(score)

gravity_scores = np.array(gravity_scores)
grid['gravity_score'] = gravity_scores

#Normalising

#Log transformation
grid['gravity_log'] = np.log1p(grid['gravity_score'])

skewness = grid['gravity_log'].skew()

#Don't really have to show
print(skewness)
plt.hist(grid['gravity_log'], bins=1000)
plt.title("Distribution of Gravity Scores")
plt.xlabel("Gravity Score (Log Transformed)")
plt.ylim(0, 200) 
plt.ylabel("Count")
plt.show()

# Convert entire grid to lat/lon
grid_latlon = grid.to_crs(epsg=4326)

grid_latlon['lat'] = grid_latlon.geometry.y
grid_latlon['lon'] = grid_latlon.geometry.x

print(grid_latlon)

#Top 10 locations
top10 = grid_latlon.sort_values(by='gravity_log', ascending=False).head(10)

print(top10[['lat','lon','gravity_log']])

grid_latlon[['lat', 'lon', 'gravity_score', 'gravity_log']].to_csv("sorted_grid.csv", index=False)
print("Saved sorted_grid.csv")