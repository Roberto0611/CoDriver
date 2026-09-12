"""Convierte mty_graph.pkl a GeoJSON para el frontend con MapLibre.

Uso:  python data/export_geojson.py

Genera dos archivos en frontend/public/:
  - mty_edges.json   → red vial completa (aristas con tipo de vía)
  - mty_route.json   → ruta de ejemplo Macroplaza → Valle
"""

import json
import pickle
import sys
from pathlib import Path

import networkx as nx
import osmnx as ox

AQUI = Path(__file__).parent
sys.path.insert(0, str(AQUI.parent))
from mundo import ZONAS  # noqa: E402

FRONTEND_PUBLIC = AQUI.parent / "frontend" / "public"

# Puntos de ejemplo para la ruta demo
ORIGEN = (25.6714, -100.3090)  # Macroplaza
DESTINO = (25.6510, -100.3590)  # Valle, San Pedro

# Las calles locales son el 83.6% de las aristas (224k de 268k) y a zoom 11-14
# -el zoom del demo- se ven como un manchon gris. Filtrarlas baja el archivo de
# 66 MB a ~11 MB y deja el esqueleto de la ciudad, que es lo que el juez reconoce.
# Ponlo en True si alguna vez hace falta el detalle a zoom 17.
INCLUIR_LOCALES = True

DECIMALES = 5  # ~1 metro de precision; el sexto decimal solo pesa


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


def edges_to_geojson_chunked(G):
    """Convierte aristas del grafo a múltiples GeoJSON agrupados por zona más cercana."""
    _, edges = ox.graph_to_gdfs(G)

    zonas_centers = {name: (lat, lon) for name, (lat, lon, _) in ZONAS.items()}
    chunks: dict[str, list[dict]] = {name: [] for name in ZONAS}

    omitidas = 0
    for _, row in edges.iterrows():
        geom = row.geometry
        highway_class = classify_highway(row.get("highway", ""))

        if highway_class == "local" and not INCLUIR_LOCALES:
            omitidas += 1
            continue

        coords = list(geom.coords)
        centroid = geom.centroid
        c_lon, c_lat = centroid.x, centroid.y

        nearest_zona = None
        min_dist = float('inf')
        for name, (z_lat, z_lon) in zonas_centers.items():
            dist = (c_lat - z_lat) ** 2 + (c_lon - z_lon) ** 2
            if dist < min_dist:
                min_dist = dist
                nearest_zona = name

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [[round(c[0], DECIMALES), round(c[1], DECIMALES)] for c in coords],
            },
            "properties": {
                "class": highway_class,
                "speed": round(row.get("speed_kph", 0), 1),
                "tt": round(row.get("travel_time", 0), 1),
                "name": row.get("name", "") if isinstance(row.get("name", ""), str) else "",
            },
        }
        chunks[str(nearest_zona)].append(feature)

    if omitidas:
        print(f"  calles locales omitidas: {omitidas:,} (INCLUIR_LOCALES=False)")

    return {
        name: {"type": "FeatureCollection", "features": feats} for name, feats in chunks.items()
    }


def route_to_geojson(G, origen, destino, weight="travel_time"):
    """Genera GeoJSON de la ruta más rápida entre dos puntos."""
    o_node = ox.nearest_nodes(G, origen[1], origen[0])
    d_node = ox.nearest_nodes(G, destino[1], destino[0])
    ruta = nx.shortest_path(G, o_node, d_node, weight=weight)

    # Extraer coordenadas de cada nodo en la ruta
    coords = []
    for node in ruta:
        data = G.nodes[node]
        coords.append([round(data["x"], 6), round(data["y"], 6)])

    # Calcular stats
    length_m = nx.shortest_path_length(G, o_node, d_node, weight="length")
    try:
        time_s = nx.shortest_path_length(G, o_node, d_node, weight=weight)
    except Exception:
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
    print("Convirtiendo 268,318 aristas a GeoJSON por zonas...")
    chunks = edges_to_geojson_chunked(G)

    for zona, geojson_data in chunks.items():
        out_path = FRONTEND_PUBLIC / f"mty_edges_{zona}.json"
        out_path.write_text(json.dumps(geojson_data), encoding="utf-8")
        size_mb = out_path.stat().st_size / (1024 * 1024)
        print(
            f"  -> {out_path.name} ({size_mb:.1f} MB, {len(geojson_data['features']):,} features)"
        )

    # 2. Ruta de ejemplo
    print("Calculando ruta Macroplaza -> Valle...")
    route_gj = route_to_geojson(G, ORIGEN, DESTINO)
    out_route = FRONTEND_PUBLIC / "mty_route.json"
    out_route.write_text(json.dumps(route_gj), encoding="utf-8")
    props = route_gj["features"][0]["properties"]
    print(
        f"  -> {out_route.name} ({props['length_km']} km, {props['time_min']} min, "
        f"{props['nodes']} nodos)"
    )

    print("\nListo. Arranca el frontend con: cd frontend && npm run dev")


if __name__ == "__main__":
    main()
