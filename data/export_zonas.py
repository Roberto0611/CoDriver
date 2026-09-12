"""Exporta las zonas y los puntos de interes a GeoJSON, para pintarlos en el mapa.

Genera en frontend/public/:
  - zonas.json    poligono por zona, con su riesgo de dia y de noche
  - puntos.json   los 210 puntos que el simulador usa como pickups y dropoffs

Son chicos (~100 KB) y SI van al repo: asi el front no necesita Python ni el grafo.

Uso:  python data/export_zonas.py
"""

import json
import math
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from mundo import RIESGO_BASE, UMBRAL_RIESGO, ZONAS, es_segura, riesgo  # noqa: E402

AQUI = Path(__file__).parent
PUBLIC = AQUI.parent / "frontend" / "public"

LADOS = 64   # un circulo de 64 lados se ve redondo a cualquier zoom del demo


def circulo(lat, lon, radio_m, lados=LADOS):
    """Poligono GeoJSON aproximando el radio de la zona.

    Un grado de latitud son ~111 km; uno de longitud se encoge con cos(lat),
    si no se corrige el circulo sale ovalado.
    """
    dlat = radio_m / 111_320
    dlon = radio_m / (111_320 * math.cos(math.radians(lat)))
    anillo = [
        [round(lon + dlon * math.cos(2 * math.pi * i / lados), 5),
         round(lat + dlat * math.sin(2 * math.pi * i / lados), 5)]
        for i in range(lados + 1)   # el ultimo punto cierra el anillo
    ]
    return {"type": "Polygon", "coordinates": [anillo]}


def zonas_geojson():
    feats = []
    for zona, (lat, lon, radio) in ZONAS.items():
        feats.append({
            "type": "Feature",
            "geometry": circulo(lat, lon, radio),
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
        })
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
        print(f"{nombre:<14} {len(gj['features']):>4} features  {salida.stat().st_size / 1e3:>6.1f} KB")

    z = zonas_geojson()
    assert len(z["features"]) == len(ZONAS)
    anillo = z["features"][0]["geometry"]["coordinates"][0]
    assert anillo[0] == anillo[-1], "el poligono debe cerrar"
    bloqueadas = [f["properties"]["zona"] for f in z["features"] if f["properties"]["bloqueada_noche"]]
    print(f"\nbloqueadas a las 23h: {', '.join(bloqueadas)}")


if __name__ == "__main__":
    main()
