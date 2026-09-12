import pickle
from pathlib import Path
import json
from shapely.geometry import MultiPoint, Polygon

AQUI = Path(__file__).parent
datos = pickle.loads((AQUI / "data" / "matriz.pkl").read_bytes())
nodos = datos["nodos"]

puntos_por_zona = {}
for i, lat, lon, id, zona in nodos:
    if zona not in puntos_por_zona:
        puntos_por_zona[zona] = []
    puntos_por_zona[zona].append((lon, lat))  # X, Y para shapely

resultados = {}
for zona, puntos in puntos_por_zona.items():
    if len(puntos) >= 3:
        # Liga elastica (convex hull) + margen (buffer) de ~200 metros (0.002 grados)
        poly = MultiPoint(puntos).convex_hull.buffer(0.002, resolution=4)
        resultados[zona] = poly.geom_type
    else:
        resultados[zona] = "Muy pocos puntos"

print(json.dumps(resultados, indent=2))
