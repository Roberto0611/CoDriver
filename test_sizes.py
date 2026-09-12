import osmnx as ox
import json
import warnings
warnings.filterwarnings('ignore')

zonas_queries = {
    "Centro": "Centro, Monterrey, Nuevo León, Mexico",
    "Obispado": "Obispado, Monterrey, Nuevo León, Mexico",
    "Valle": "San Pedro Garza García, Nuevo León, Mexico",
    "Contry": "Contry, Monterrey, Nuevo León, Mexico",
    "Tec": "Tecnológico, Monterrey, Nuevo León, Mexico",
    "Fundidora": "Parque Fundidora, Monterrey, Nuevo León, Mexico",
    "Guadalupe": "Guadalupe, Nuevo León, Mexico",
    "LindaVista": "Linda Vista, Guadalupe, Nuevo León, Mexico",
    "SanNicolas": "San Nicolás de los Garza, Nuevo León, Mexico",
    "Cumbres": "Cumbres, Monterrey, Nuevo León, Mexico",
    "Mitras": "Mitras, Monterrey, Nuevo León, Mexico",
    "Escobedo": "General Escobedo, Nuevo León, Mexico",
    "SantaCatarina": "Santa Catarina, Nuevo León, Mexico",
    "Apodaca": "Apodaca, Nuevo León, Mexico"
}

results = {}
for zona, query in zonas_queries.items():
    try:
        gdf = ox.geocode_to_gdf(query)
        geom = gdf.geometry.iloc[0]
        # Calculate approximate area in sq degrees (just for relative comparison)
        area = geom.area
        # Get bounding box width/height in degrees
        minx, miny, maxx, maxy = geom.bounds
        width = maxx - minx
        height = maxy - miny
        
        results[zona] = {
            "type": geom.geom_type,
            "width_deg": round(width, 4),
            "height_deg": round(height, 4)
        }
    except Exception as e:
        pass

print(json.dumps(results, indent=2))
