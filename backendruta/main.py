import asyncio
import json
import pickle
import sys
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# Configurar path para importar desde el directorio raíz
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import contrato  # noqa: E402
from data.export_geojson import route_to_geojson  # noqa: E402
from mundo import ZONAS  # noqa: E402

app = FastAPI(
    title="Nuez Copiloto API", description="API para el simulador y motor del repartidor Nuez"
)

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


@app.get("/")
def read_root():
    return {"message": "Nuez Copiloto Backend"}


@app.get("/api/route")
def get_route(origen: str, destino: str):
    if not G:
        raise HTTPException(status_code=500, detail="Grafo no cargado en el backend")

    if origen not in ZONAS or destino not in ZONAS:
        raise HTTPException(status_code=400, detail="Zona de origen o destino inválida")

    # mundo.ZONAS tiene el formato (lat, lon, radio)
    coord_origen = (ZONAS[origen][0], ZONAS[origen][1])
    coord_destino = (ZONAS[destino][0], ZONAS[destino][1])

    # route_to_geojson usa origen y destino como (lat, lon)
    try:
        geojson_data = route_to_geojson(G, coord_origen, coord_destino)
        # Ajustamos los nombres de los endpoints en las propiedades
        geojson_data["features"][0]["properties"]["from"] = origen
        geojson_data["features"][0]["properties"]["to"] = destino
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
