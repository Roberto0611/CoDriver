import asyncio
import json
import pickle
import sys
from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Configurar path para importar desde el directorio raíz
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import contrato  # noqa: E402
from backendruta import database, seed_traffic  # noqa: E402
from data.export_geojson import route_to_geojson  # noqa: E402
from mundo import ZONAS  # noqa: E402

app = FastAPI(
    title="Nuez Copiloto API",
    description="API para el simulador y motor del repartidor Nuez",
)


class IncidenteInput(BaseModel):
    id: str
    inicio_hora: str  # formato HH:MM
    fin_hora: str  # formato HH:MM
    calle: str
    tipo: str = "CIERRE_TOTAL"
    factor_penalizacion: float = 99999.0
    motivo: str = ""
    alerta_voz: str = ""
    coords: list[list[float]] = []


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cargar el grafo globalmente al inicio (puede tardar ~1-2 segundos)
print("Cargando grafo OSMnx...")
try:
    G = pickle.loads((BASE_DIR / "data" / "mty_graph.pkl").read_bytes())
    print("Grafo cargado exitosamente.")
except Exception as e:
    print(f"Error al cargar el grafo: {e}")
    G = None


@app.on_event("startup")
def startup_event():
    print("Inicializando TigerData (TimescaleDB) / almacén de series de tiempo...")
    database.init_db()
    print("Poblando catálogo de simulación de tráfico (14:00 - 16:00)...")
    seed_traffic.generar_datos_simulacion()


@app.get("/")
def read_root():
    return {
        "message": "Nuez Copiloto Backend",
        "tigerdata_connected": database.is_connected(),
    }


@app.get("/api/traffic")
def get_traffic(hora: str | None = "14:00"):
    """Devuelve las calles congestionadas y los incidentes activos en una hora dada."""
    hora = hora or "14:00"
    traffic_records = database.get_traffic_at_time(hora)
    incidents = database.get_active_incidents(hora)

    features = []
    for t in traffic_records:
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": t.get("coords", [])},
                "properties": {
                    "calle": t.get("calle_nombre"),
                    "factor_retraso": t.get("factor_retraso"),
                    "delay_segundos": t.get("delay_segundos"),
                    "velocidad_kmh": t.get("velocidad_kmh"),
                    "motivo": t.get("motivo"),
                    "tipo": "TRAFICO",
                },
            }
        )

    for inc in incidents:
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": inc.get("coords", [])},
                "properties": {
                    "calle": inc.get("calle"),
                    "factor_penalizacion": inc.get("factor_penalizacion"),
                    "motivo": inc.get("motivo"),
                    "alerta_voz": inc.get("alerta_voz"),
                    "tipo": inc.get("tipo", "CIERRE_TOTAL"),
                },
            }
        )

    return {
        "hora": hora,
        "tigerdata_connected": database.is_connected(),
        "total_incidentes": len(incidents),
        "alertas": [inc.get("alerta_voz") for inc in incidents if inc.get("alerta_voz")],
        "geojson": {"type": "FeatureCollection", "features": features},
    }


@app.post("/api/incidents")
def create_incident(inc: IncidenteInput):
    """Inyecta un cierre vial o incidente de manera manual."""
    from datetime import date, time

    hoy = date.today()

    try:
        h_ini, m_ini = map(int, inc.inicio_hora.split(":"))
        h_fin, m_fin = map(int, inc.fin_hora.split(":"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de hora inválido. Usa HH:MM") from None

    inc_dict = {
        "id": inc.id,
        "inicio": datetime.combine(hoy, time(h_ini, m_ini)),
        "fin": datetime.combine(hoy, time(h_fin, m_fin)),
        "calle": inc.calle,
        "tipo": inc.tipo,
        "factor_penalizacion": inc.factor_penalizacion,
        "motivo": inc.motivo,
        "alerta_voz": inc.alerta_voz,
        "coords": inc.coords,
    }
    database.save_incident(inc_dict)
    return {"status": "success", "message": f"Incidente {inc.id} registrado correctamente"}


@app.get("/api/route")
def get_route(origen: str, destino: str, hora: str | None = None):
    if not G:
        raise HTTPException(status_code=500, detail="Grafo no cargado en el backend")

    if origen not in ZONAS or destino not in ZONAS:
        raise HTTPException(status_code=400, detail="Zona de origen o destino inválida")

    # mundo.ZONAS tiene el formato (lat, lon, radio)
    coord_origen = (ZONAS[origen][0], ZONAS[origen][1])
    coord_destino = (ZONAS[destino][0], ZONAS[destino][1])

    active_incidents = database.get_active_incidents(hora) if hora else []

    weight_param: str | Callable[[Any, Any, Any], float] = "travel_time"
    if active_incidents:
        penalizaciones = {}
        for inc in active_incidents:
            calle_key = inc["calle"].lower()
            penalizaciones[calle_key] = inc.get("factor_penalizacion", 1000.0)

        def dynamic_weight(u, v, edges_dict):
            best_weight = float("inf")
            for _key, edge_data in edges_dict.items():
                base_time = edge_data.get("travel_time", 1.0)
                name = str(edge_data.get("name", "")).lower()
                mult = 1.0
                for p_calle, penalty in penalizaciones.items():
                    palabras = [
                        p for p in p_calle.split() if len(p) > 3 and p not in ("avenida", "calle")
                    ]
                    if p_calle in name or (palabras and all(p in name for p in palabras)):
                        mult = max(mult, penalty)
                w = base_time * mult
                if w < best_weight:
                    best_weight = w
            return best_weight

        weight_param = dynamic_weight

    try:
        geojson_data = route_to_geojson(G, coord_origen, coord_destino, weight=weight_param)
        geojson_data["features"][0]["properties"]["from"] = origen
        geojson_data["features"][0]["properties"]["to"] = destino
        geojson_data["features"][0]["properties"]["hora"] = hora
        geojson_data["features"][0]["properties"]["incidente_activo"] = bool(active_incidents)
        if active_incidents:
            geojson_data["features"][0]["properties"]["alerta_voz"] = active_incidents[0].get(
                "alerta_voz"
            )
        return geojson_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    try:
        t_actual = 14 * 60

        while True:
            estado = contrato.EstadoRepartidor(
                t=t_actual,
                t_restante=120 - (t_actual - 840),
                pos=contrato.Punto("Tec", 25.651, -100.289),
                mochila=[],
                ganado=120.5,
                fatiga=0.1,
            )
            await websocket.send_text(json.dumps({"type": "estado", "data": asdict(estado)}))

            if t_actual % 10 == 0:
                oferta = contrato.Oferta(
                    id=f"o_{t_actual}",
                    plataforma="rappi",
                    pago=55.0,
                    surge=1.2,
                    t_aparece=t_actual,
                    t_prep=5,
                    pickup=contrato.Punto("Contry", 25.66, -100.28),
                    dropoff=contrato.Punto("Valle", 25.65, -100.36),
                )
                await websocket.send_text(json.dumps({"type": "oferta", "data": asdict(oferta)}))

                decision = contrato.Decision(
                    t=t_actual,
                    oferta_id=oferta.id,
                    accion="saltar",
                    terminos={"pago_neto": 50.0, "minutos": 40, "precio_tiempo": 70.0},
                    razon=(
                        "Saltar. Son muchos minutos de tráfico hacia Valle "
                        "y no paga lo suficiente a esta hora."
                    ),
                )

                await asyncio.sleep(1)

                await websocket.send_text(
                    json.dumps({"type": "decision", "data": asdict(decision)})
                )

            t_actual += 1
            await asyncio.sleep(2)

    except WebSocketDisconnect:
        print("Cliente desconectado")
