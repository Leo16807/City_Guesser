# Importiert Geometriedaten der Länder und exportiert eine csv Datei.
# Quelle: Natural Earth 1:110m Cultural Vectors. Admin o - Countries. Link: https://www.naturalearthdata.com/downloads/110m-cultural-vectors/. 

import geopandas as gpd

# Natural Earth Shapefile laden 
gdf = gpd.read_file('get_country_data/world_borders/ne_110m_admin_0_countries.shp')

# Geometriedaten und Ländernamen filtern
gdf['wkt_geom'] = gdf['geometry'].apply(lambda x: x.wkt)
export_data = gdf[['NAME', 'wkt_geom']]

# Als CSV speichern
export_data.to_csv('get_country_data/countries_import.csv', index=False, sep=';')