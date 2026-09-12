"""Exporta las zonas y los puntos de interes a GeoJSON, para pintarlos en el mapa.

Genera en frontend/public/:
  - zonas.json    poligono por zona, con su riesgo de dia y de noche
  - puntos.json   los 210 puntos que el simulador usa como pickups y dropoffs

Son chicos (~100 KB) y SI van al repo: asi el front no necesita Python ni el grafo.

Uso:  python data/export_zonas.py
"""

import json
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from mundo import RIESGO_BASE, UMBRAL_RIESGO, ZONAS, es_segura, riesgo  # noqa: E402

AQUI = Path(__file__).parent
PUBLIC = AQUI.parent / "frontend" / "public"

from shapely.geometry import MultiPoint  # noqa: E402


def zonas_geojson():
    # Leer los puntos del simulador para saber exactamente dónde ocurren las cosas
    datos = pickle.loads((AQUI / "matriz.pkl").read_bytes())

    # Agrupar coordenadas (lon, lat) por cada zona
    puntos_por_zona: dict[str, list[tuple[float, float]]] = {}
    for zona, _node, lat, lon in datos["puntos"]:
        if zona not in puntos_por_zona:
            puntos_por_zona[zona] = []
        puntos_por_zona[zona].append((lon, lat))

    feats = []
    for zona, (lat, lon, radio) in ZONAS.items():
        puntos = puntos_por_zona.get(zona, [])

        # Si la zona tiene al menos 3 puntos, le ponemos nuestra "liga elástica" (Convex Hull)
        if len(puntos) >= 3:
            # 1. Envuelve los puntos matemáticamente
            # 2. Le da un "buffer" (margen) de ~300 m (0.003 grados) para que no quede puntiagudo
            poly = MultiPoint(puntos).convex_hull.buffer(0.003, resolution=4)
            geom = poly.__geo_interface__
        else:
            # Fallback a un cuadrito simple si por alguna razón no hay puntos
            d = 0.01
            anillo = [
                [lon - d, lat - d],
                [lon + d, lat - d],
                [lon + d, lat + d],
                [lon - d, lat + d],
                [lon - d, lat - d],
            ]
            geom = {"type": "Polygon", "coordinates": [anillo]}

        feats.append(
            {
                "type": "Feature",
                "geometry": geom,
                "properties": {
                    "zona": zona,
                    "centro": [round(lon, 5), round(lat, 5)],
                    "radio_m": radio,
                    "riesgo_base": RIESGO_BASE[zona],
                    "riesgo_dia": round(riesgo(zona, 14), 2),
                    "riesgo_noche": round(riesgo(zona, 23), 2),
                    "bloqueada_noche": not es_segura(zona, 23),
                    "umbral": UMBRAL_RIESGO,
                },
            }
        )
    return {"type": "FeatureCollection", "features": feats}


def puntos_geojson():
    """Los puntos que el simulador usa. Salen de matriz.pkl para que el indice
    del front sea EL MISMO que el del motor: punto i aqui = columna i en la matriz."""
    datos = pickle.loads((AQUI / "matriz.pkl").read_bytes())
    feats = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(lon, 5), round(lat, 5)]},
            "properties": {"i": i, "zona": zona, "node_id": node},
        }
        for i, (zona, node, lat, lon) in enumerate(datos["puntos"])
    ]
    return {"type": "FeatureCollection", "features": feats}


def main():
    PUBLIC.mkdir(parents=True, exist_ok=True)

    for nombre, gj in (("zonas.json", zonas_geojson()), ("puntos.json", puntos_geojson())):
        salida = PUBLIC / nombre
        salida.write_text(json.dumps(gj), encoding="utf-8")
        kb = salida.stat().st_size / 1e3
        print(f"{nombre:<14} {len(gj['features']):>4} features  {kb:>6.1f} KB")

    z = zonas_geojson()
    assert len(z["features"]) == len(ZONAS)
    anillo = z["features"][0]["geometry"]["coordinates"][0]
    assert anillo[0] == anillo[-1], "el poligono debe cerrar"
    bloqueadas = [
        f["properties"]["zona"] for f in z["features"] if f["properties"]["bloqueada_noche"]
    ]
    print(f"\nbloqueadas a las 23h: {', '.join(bloqueadas)}")


if __name__ == "__main__":
    main()
