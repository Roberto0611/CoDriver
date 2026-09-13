"""Lo que el review del PR #14 encontro en /live: limites, ids, candados y fallas a medias."""

import threading

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import valor
from backendruta import live_api, zonas
from backendruta.live_demo import AGENTES, SEED_ENSAYADO, LiveDemoSession
from backendruta.live_geometry import linea_recta
from contrato import ConfigTurno

CIERRE = {"shock_type": "closure", "zone": 0, "duration_min": 40, "road": "Constitución"}


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(live_api, "registry", live_api.LiveRegistry(tmp_path, linea_recta))
    app = FastAPI()
    app.include_router(live_api.router)
    return TestClient(app)


def start(api, **body):
    r = api.post("/live/start", json={"seed": 2000, **body})
    assert r.status_code == 200, r.text
    return r.json()["session_id"]


def sesion(tmp_path, geometria=linea_recta) -> LiveDemoSession:
    cfg = ConfigTurno(duracion_min=120, ancla=zonas.punto(4), seed=SEED_ENSAYADO)
    return LiveDemoSession("s", cfg, tmp_path / "s.jsonl", geometria=geometria)


# --- limites del request ----------------------------------------------------------


def test_un_seed_enorme_es_422_y_no_500(api):
    """El seed va en el nombre del JSONL: uno de 400 digitos tronaba el filesystem."""
    assert api.post("/live/start", json={"seed": 2**31}).status_code == 422
    assert api.post("/live/start", json={"seed": 10**400}).status_code == 422
    assert api.post("/live/start", json={"seed": 2**31 - 1}).status_code == 200


def test_road_de_mas_de_60_es_422(api):
    sid = start(api)
    largo = api.post("/live/shock", json={"session_id": sid, **CIERRE, "road": "x" * 61})
    assert largo.status_code == 422
    justo = api.post("/live/shock", json={"session_id": sid, **CIERRE, "road": "x" * 60})
    assert justo.status_code == 200, justo.text


def test_duracion_que_ninguna_tabla_cubre_es_422(api, monkeypatch):
    # Sin las tablas de 8 y 8.5 h, 480 min no tiene costo de oportunidad con que decidir.
    monkeypatch.setattr(valor, "ARCHIVO_LARGO", valor.ARCHIVO)
    monkeypatch.setattr(valor, "ARCHIVO_510", valor.ARCHIVO)
    r = api.post("/live/start", json={"seed": 2000, "duracion_min": 480})
    assert r.status_code == 422
    assert "la tabla cubre" in r.json()["detail"]
    # Arriba de la jornada de 8.5 h (MAX_TURNO_MIN) ya lo rechaza pydantic.
    assert api.post("/live/start", json={"seed": 2000, "duracion_min": 511}).status_code == 422


# --- el registro -------------------------------------------------------------------


def test_404_en_status_shock_y_end(api):
    assert api.get("/live/status/nope").status_code == 404
    assert api.post("/live/shock", json={"session_id": "nope", **CIERRE}).status_code == 404
    assert api.post("/live/end", json={"session_id": "nope"}).status_code == 404


def test_un_segundo_end_es_409(api):
    sid = start(api)
    assert api.post("/live/end", json={"session_id": sid}).status_code == 200
    assert api.post("/live/end", json={"session_id": sid}).status_code == 409


def test_la_novena_sesion_saca_a_la_mas_vieja(api):
    ids = [start(api, seed=2000)]
    primera = live_api.registry.obtener(ids[0])
    assert primera.estrategia.en_marcha
    ids += [start(api, seed=2001 + i) for i in range(live_api.MAX_SESIONES)]
    assert api.get(f"/live/status/{ids[0]}").status_code == 404
    for sid in ids[1:]:
        assert api.get(f"/live/status/{sid}").status_code == 200
    # Nadie le va a mandar /live/end a la que salio: su hilo de Gemini se para solo.
    parada = threading.Event()
    for _ in range(40):
        if not primera.estrategia.en_marcha:
            parada.set()
            break
        parada.wait(0.05)
    assert parada.is_set(), "la sesion desalojada siguio consultando a Gemini"


def test_un_start_que_truena_no_saca_a_nadie(api, tmp_path):
    ids = [start(api, seed=2000 + i) for i in range(live_api.MAX_SESIONES)]
    # Un log_dir que es un archivo: la sesion no se puede construir (no hay donde escribir).
    archivo = tmp_path / "no-es-carpeta"
    archivo.write_text("", encoding="utf-8")
    live_api.registry.log_dir = archivo
    with pytest.raises(OSError):
        api.post("/live/start", json={"seed": 3000})
    for sid in ids:
        assert api.get(f"/live/status/{sid}").status_code == 200, "desalojo por un start fallido"


def test_un_id_repetido_se_vuelve_a_sortear(api, monkeypatch):
    sorteos = iter(["aaaaaa", "aaaaaa", "bbbbbb"])
    monkeypatch.setattr(live_api.secrets, "token_hex", lambda _n: next(sorteos))
    primera, segunda = start(api), start(api)
    assert primera == "live-2000-aaaaaa" and segunda == "live-2000-bbbbbb"
    assert api.post("/live/tick", json={"session_id": primera}).json()["minute"] == 1
    assert api.get(f"/live/status/{segunda}").json()["minute"] == 0, "la segunda piso a la primera"


# --- fallas a medias dentro de la sesion ----------------------------------------------


@pytest.mark.parametrize("falla_en", [1, 2, 3])
def test_si_la_geometria_truena_los_tramos_no_se_pierden(tmp_path, falla_en):
    """Los cursores de tramos avanzan solo si la geometria de LOS DOS agentes salio: si
    truena la de Nuez, lo de Greedy tampoco llego al front. El siguiente tick los manda."""
    llamadas = {"n": 0}

    def geometria(tramos):
        llamadas["n"] += 1
        if llamadas["n"] == falla_en:
            raise RuntimeError("el grafo no contesto")
        return linea_recta(tramos)

    s = sesion(tmp_path, geometria)
    mandados: dict[str, list] = {"greedy": [], "nuez": []}
    tronó = False
    while s.minute < 60:
        try:
            snap = s.tick()
        except RuntimeError:
            tronó = True
            continue
        for a in mandados:
            mandados[a] += [(x["t_salida"], x["clave"]) for x in snap[a]["new_legs"]]
    assert tronó
    for a in AGENTES:
        turno = s.turnos[a]
        assert mandados[a] == [(x[0], f"{x[2]}-{x[3]}") for x in turno.res.tramos], a


def test_si_el_log_del_shock_truena_el_shock_no_se_inyecta(tmp_path, monkeypatch):
    s = sesion(tmp_path)
    for _ in range(10):
        s.tick()
    antes = s.log.path.read_bytes()
    escribir = s.log.append

    def disco_lleno(evento):
        if evento["event"] == "shock":
            raise OSError("no space left on device")
        escribir(evento)

    monkeypatch.setattr(s.log, "append", disco_lleno)
    with pytest.raises(OSError):
        s.shock("closure", 40, zona=0, calle="Constitución")
    assert s.shocks == [] and s.snapshot()["active_shocks"] == []
    assert all(t.disrupciones == () for t in s.turnos.values())
    assert s.log.path.read_bytes() == antes


def test_end_no_detiene_al_registro_ni_deja_tocar_la_sesion(api):
    """/live/end adelanta el turno completo. Mientras lo hace, las demas sesiones
    contestan, y un tick sobre la misma espera y despues ve que ya termino."""
    sid, otra = start(api), start(api, seed=2001)
    s = live_api.registry.obtener(sid)
    entro, soltar = threading.Event(), threading.Event()
    minuto = s._minuto

    def lento(frames):
        entro.set()
        assert soltar.wait(5)
        return minuto(frames)

    s._minuto = lento  # type: ignore[method-assign]
    fin = threading.Thread(target=live_api.end, args=(live_api.SessionRequest(session_id=sid),))
    fin.start()
    resultado: dict[str, object] = {}

    def tick_misma():
        try:
            live_api.tick(live_api.TickRequest(session_id=sid))
        except HTTPException as exc:
            resultado["status"] = exc.status_code

    hilo_tick = threading.Thread(target=tick_misma)
    try:
        assert entro.wait(5)
        listo = threading.Event()

        def status_otra():
            live_api.status(otra)
            listo.set()

        threading.Thread(target=status_otra, daemon=True).start()
        assert listo.wait(2), "status de otra sesion espero al end"

        hilo_tick.start()
        hilo_tick.join(0.3)
        assert hilo_tick.is_alive(), "un tick corrio sobre la sesion a media fast-forward"
    finally:
        soltar.set()
        fin.join(10)
        hilo_tick.join(10)
    assert resultado == {"status": 409}
