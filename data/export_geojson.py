"""Convierte mty_graph.pkl a GeoJSON para el frontend con MapLibre.

Uso:  python data/export_geojson.py

Genera dos archivos en frontend/public/:
  - mty_edges.json   → red vial completa (aristas con tipo de vía)
  - mty_route.json   → ruta de ejemplo Macroplaza → Valle
"""

import json
import pickle
from pathlib import Path

import networkx as nx
import osmnx as ox

AQUI = Path(__file__).parent
FRONTEND_PUBLIC = AQUI.parent / "frontend" / "public"

# Puntos de ejemplo para la ruta demo
ORIGEN = (25.6714, -100.3090)   # Macroplaza
DESTINO = (25.6510, -100.3590)  # Valle, San Pedro


def classify_highway(highway):
    """Clasifica el tipo de vía para estilizar en el mapa."""
    if isinstance(highway, list):
        highway = highway[0]
    if highway in ("motorway", "motorway_link", "trunk", "trunk_link"):
        return "highway"
    if highway in ("primary", "primary_link"):
        return "primary"
    if highway in ("secondary", "secondary_link"):
        return "secondary"
    if highway in ("tertiary", "tertiary_link"):
        return "tertiary"
    return "local"


def edges_to_geojson(G):
    """Convierte aristas del grafo a GeoJSON FeatureCollection."""
    _, edges = ox.graph_to_gdfs(G)

    features = []
    for _, row in edges.iterrows():
        geom = row.geometry
        highway_class = classify_highway(row.get("highway", ""))

        # Solo incluir coordenadas (lon, lat) de la geometría
        coords = list(geom.coords)

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [[round(c[0], 6), round(c[1], 6)] for c in coords],
            },
            "properties": {
                "class": highway_class,
                "speed": round(row.get("speed_kph", 0), 1),
                "tt": round(row.get("travel_time", 0), 1),
                "name": row.get("name", "") if isinstance(row.get("name", ""), str) else "",
            },
        }
        features.append(feature)

    return {"type": "FeatureCollection", "features": features}


def route_to_geojson(G, origen, destino):
    """Genera GeoJSON de la ruta más rápida entre dos puntos."""
    o_node = ox.nearest_nodes(G, origen[1], origen[0])
    d_node = ox.nearest_nodes(G, destino[1], destino[0])
    ruta = nx.shortest_path(G, o_node, d_node, weight="travel_time")

    # Extraer coordenadas de cada nodo en la ruta
    coords = []
    for node in ruta:
        data = G.nodes[node]
        coords.append([round(data["x"], 6), round(data["y"], 6)])

    # Calcular stats
    length_m = nx.shortest_path_length(G, o_node, d_node, weight="length")
    time_s = nx.shortest_path_length(G, o_node, d_node, weight="travel_time")

    feature = {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": coords},
        "properties": {
            "from": "Macroplaza",
            "to": "Valle, San Pedro",
            "length_km": round(length_m / 1000, 2),
            "time_min": round(time_s / 60, 1),
            "nodes": len(ruta),
        },
    }
    return {"type": "FeatureCollection", "features": [feature]}


def main():
    print("Cargando grafo...")
    G = pickle.loads((AQUI / "mty_graph.pkl").read_bytes())

    FRONTEND_PUBLIC.mkdir(parents=True, exist_ok=True)

    # 1. Red vial completa
    print(f"Convirtiendo {G.number_of_edges():,} aristas a GeoJSON...")
    edges_gj = edges_to_geojson(G)
    out_edges = FRONTEND_PUBLIC / "mty_edges.json"
    out_edges.write_text(json.dumps(edges_gj), encoding="utf-8")
    print(f"  -> {out_edges.name} ({out_edges.stat().st_size / 1e6:.1f} MB, {len(edges_gj['features']):,} features)")

    # 2. Ruta de ejemplo
    print("Calculando ruta Macroplaza -> Valle...")
    route_gj = route_to_geojson(G, ORIGEN, DESTINO)
    out_route = FRONTEND_PUBLIC / "mty_route.json"
    out_route.write_text(json.dumps(route_gj), encoding="utf-8")
    props = route_gj["features"][0]["properties"]
    print(f"  -> {out_route.name} ({props['length_km']} km, {props['time_min']} min, {props['nodes']} nodos)")

    print("\nListo. Arranca el frontend con: cd frontend && npm run dev")


if __name__ == "__main__":
    main()
