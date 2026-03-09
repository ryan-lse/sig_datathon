import pandas as pd
import geopandas as gpd
import numpy as np
import matplotlib.pyplot as plt
from shapely.geometry import Point
from sklearn.neighbors import BallTree

#Data
population = pd.read_csv(r"Data\Population.csv", sep=";", usecols=[0,2])
population = population.rename(columns={'All Ages': 'Population', 'OA11CD':'Area'})
coordinate = pd.read_csv(r"Data\Coordinate_filter.csv", sep=",")
stations = pd.read_csv(r"Data\combined_stations.csv")
data = pd.merge(population, coordinate, on='Area')

#Coordinate for spatial 
geometry = [Point(xy) for xy in zip(data['LONG'], data['LAT'])]
gdf = gpd.GeoDataFrame(data, geometry=geometry, crs="EPSG:4326")
station_geometry = [Point(xy) for xy in zip(stations['lon'], stations['lat'])]
stations_gdf = gpd.GeoDataFrame(stations, geometry=station_geometry, crs="EPSG:4326")

#Convert to UK metric CRS (meters)
gdf = gdf.to_crs(epsg=27700)
stations_gdf = stations_gdf.to_crs(epsg=27700)

#Creating candidate grid across London
xmin, ymin, xmax, ymax = gdf.total_bounds
step = 1000
grid_points = [Point(x, y) for x in np.arange(xmin, xmax, step)
                        for y in np.arange(ymin, ymax, step)]
grid = gpd.GeoDataFrame(geometry=grid_points, crs=gdf.crs)

#Convert coordinates to meters
coords = np.array([[pt.x, pt.y] for pt in gdf.geometry])
pop = gdf['Population'].values
grid_coords = np.array([[pt.x, pt.y] for pt in grid.geometry])
station_coords = np.array([[pt.x, pt.y] for pt in stations_gdf.geometry])

#Build spatial index
tree = BallTree(coords, leaf_size=50, metric='euclidean')
station_tree = BallTree(station_coords, metric='euclidean')

#Grid filtering
idxs = station_tree.query_radius(grid_coords, r=800)
mask = np.array([len(i) == 0 for i in idxs])
grid = grid[mask].reset_index(drop=True)
grid_coords = np.array([[pt.x, pt.y] for pt in grid.geometry])


#Compute Gravity Model Value
radius = 2500  
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

#Log transformation
grid['gravity_log'] = np.log1p(grid['gravity_score'])

# Convert entire grid to lat/lon
grid_latlon = grid.to_crs(epsg=4326)

grid_latlon['lat'] = grid_latlon.geometry.y
grid_latlon['lon'] = grid_latlon.geometry.x

print(grid_latlon)

#Top 10 locations
top10 = grid_latlon.sort_values(by='gravity_log', ascending=False).head(10)
print(top10[['lat','lon','gravity_log']])