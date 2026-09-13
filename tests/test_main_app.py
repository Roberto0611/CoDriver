"""La app que se levanta con uvicorn expone el protocolo Courier.

Los demas tests arman su propia FastAPI con el router, asi que un merge que borre
`include_router(courier_api.router)` de main.py pasaba en verde y el juez recibia 404.
"""

from fastapi.testclient import TestClient

from backendruta.main import app

RUTAS_DEL_PROTOCOLO = {
    ("GET", "/zones"),
    ("POST", "/shift/start"),
    ("POST", "/decide"),
    ("POST", "/shift/end"),
    ("GET", "/shift/status"),
    ("GET", "/explain/{order_id}"),
    ("GET", "/explain_decision/{order_id}"),
    ("POST", "/shock"),
}


def test_main_monta_el_protocolo_courier():
    # FastAPI 0.141 guarda los routers incluidos sin aplanar en app.routes; el esquema
    # OpenAPI es la vista publica de lo que realmente queda montado.
    montadas = {
        (metodo.upper(), ruta)
        for ruta, operaciones in app.openapi()["paths"].items()
        for metodo in operaciones
    }
    faltan = RUTAS_DEL_PROTOCOLO - montadas
    assert not faltan, f"main.py no monta estas rutas del protocolo: {sorted(faltan)}"


def test_main_responde_zones_sin_levantar_nada():
    # Sin context manager: no corre el startup (TigerData), igual que un probe frio.
    respuesta = TestClient(app).get("/zones")
    assert respuesta.status_code == 200, respuesta.text
