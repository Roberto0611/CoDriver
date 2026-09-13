"""El demo en vivo: el mismo motor, dos agentes, un solo stream de ofertas."""

import importlib.util
import json
import threading
from dataclasses import asdict
from functools import partial
from pathlib import Path

import pytest

import rutas
import shocks
import valor
from backendruta import zonas
from backendruta.live_demo import AGENTES, SEED_ENSAYADO, LiveDemoSession, SesionTerminada
from backendruta.live_geometry import linea_recta, por_calles
from baselines import politica_accept_all, politica_highest_pay, politica_nearest_first
from contrato import ConfigTurno, Punto
from nuez import politica_nuez
from sim import indice_de, politica_greedy, simular


def cfg(seed=SEED_ENSAYADO):
    tec = rutas.COORD_DE[rutas.puntos_de("Tec")[0]]
    return ConfigTurno(
        duracion_min=120,
        ancla=Punto("Tec", *tec),
        margen_min=10,
        vehiculo="moto",
        seed=seed,
        hora_inicio=14,
    )


def sesion(tmp_path, seed=SEED_ENSAYADO, name="s"):
    return LiveDemoSession(name, cfg(seed), tmp_path / f"{name}.jsonl")


def correr(s, hasta):
    snaps = []
    while s.snapshot()["minute"] < hasta:
        snaps.append(s.tick())
    return snaps


def decisiones(snaps, agente):
    return [d for snap in snaps for f in snap[agente]["frames"] for d in f["decisiones"]]


def test_greedy_y_nuez_ven_las_mismas_ofertas(tmp_path):
    snaps = correr(sesion(tmp_path), 120)

    def ids(a):
        return [d["oferta_id"] for d in decisiones(snaps, a)]

    assert ids("greedy") == ids("nuez")
    assert len(ids("greedy")) > 50


def test_live_avisa_a_gemini_en_cada_media_hora_simulada(tmp_path):
    """El reloj live, no los cinco minutos de pared, gobierna los refrescos de Gemini."""
    s = sesion(tmp_path)
    s.estrategia.detener()
    llamadas: list[int] = []
    respondio = threading.Event()

    def proveedor(contexto):
        llamadas.append(contexto["elapsed_min"])
        respondio.set()
        return {"margen_mxn": 1.0, "nota": "live refresh"}

    s.estrategia.proveedor = proveedor
    s.estrategia.fuente = "doble"
    s.estrategia.intervalo = 3600
    s.estrategia.arrancar()
    try:
        assert respondio.wait(1)
        respondio.clear()
        s.tick(29)
        assert not respondio.wait(0.05)
        s.tick()
        assert respondio.wait(1)
        assert llamadas == [0, 30]
    finally:
        s.end()


def test_sin_shocks_el_final_es_el_de_simular(tmp_path):
    s = sesion(tmp_path)
    fin = s.end()
    assert fin["greedy"]["earnings_mxn"] == simular(cfg(), politica_greedy).ganado
    nuez = partial(politica_nuez, tabla=valor.para_turno(120))
    assert fin["nuez"]["earnings_mxn"] == simular(cfg(), nuez).ganado


def test_los_tres_benchmarks_corren_el_mismo_turno_sin_meter_tres_rutas_al_mapa(tmp_path):
    s = sesion(tmp_path)
    fin = s.end()
    esperados = {
        "accept_all": politica_accept_all,
        "highest_pay": politica_highest_pay,
        "nearest_first": politica_nearest_first,
    }
    for nombre, politica in esperados.items():
        assert fin["benchmarks"][nombre]["earnings_mxn"] == simular(cfg(), politica).ganado
    # La evidencia oficial sigue siendo el duelo detallado: solo esas dos rutas viajan al front.
    assert set(fin["benchmarks"]) == set(esperados)
    assert {e["agent"] for e in eventos_de(s) if e["event"] == "decision"} == {"greedy", "nuez"}


def test_mismo_seed_mismo_shock_mismas_decisiones(tmp_path):
    def corrida(name):
        s = sesion(tmp_path, name=name)
        antes = correr(s, 30)
        s.shock("closure", 40, zona=0, calle="Constitución")
        return decisiones(antes + correr(s, 120), "nuez")

    assert corrida("a") == corrida("b")


def test_cierre_estira_los_tramos_de_los_dos(tmp_path):
    def tramos(con_cierre):
        s = sesion(tmp_path, name=f"c{con_cierre}")
        correr(s, 30)
        if con_cierre:
            s.shock("closure", 40, zona=0, calle="Constitución")
        snaps = correr(s, 70)
        return {a: [leg for sn in snaps for leg in sn[a]["new_legs"]] for a in ("greedy", "nuez")}

    libre, cerrado = tramos(False), tramos(True)
    for a in ("greedy", "nuez"):
        assert libre[a] != cerrado[a], f"el cierre no cambio las rutas de {a}"


def test_surge_sube_el_pago_de_las_ofertas_de_esa_zona(tmp_path):
    def pagos(con_surge):
        s = sesion(tmp_path, name=f"s{con_surge}")
        correr(s, 30)
        if con_surge:
            s.shock("surge", 30, zona=4, multiplicador=1.8)
        snaps = correr(s, 60)
        return {
            o["order_id"]: o["pay_mxn"]
            for sn in snaps
            for o in sn["offers_this_tick"]
            if o["pickup_zone"] == "Tec"
        }

    base, surge = pagos(False), pagos(True)
    assert base and base.keys() == surge.keys()
    assert all(surge[k] == pytest.approx(base[k] * 1.8, abs=0.2) for k in base)


def eventos_de(s):
    return [json.loads(linea) for linea in s.log.path.read_text(encoding="utf-8").splitlines()]


def validador():
    """El validador oficial tal cual lo mando Infosys. El nombre trae espacios y
    parentesis, asi que no se puede importar como modulo normal."""
    ruta = Path(__file__).resolve().parents[1] / "courier" / "validate_format (2).py"
    spec = importlib.util.spec_from_file_location("validate_format", ruta)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def errores_de_formato(s):
    """Lo que dice el validador oficial, menos el presupuesto de 50 ms.

    `latency_ms` es el tiempo real de pared de cada `paso()`: en un runner cargado un
    solo minuto lento lo pasa, y eso no es un error de FORMATO. El validador lo
    reporta como "...: latency Nms exceeds the 50ms fast-path budget"; se filtra solo
    ese texto y se revisa aparte que la latencia sea un numero no negativo."""
    errs, counts = validador().check_event_log(str(s.log.path))
    latencias = [e["latency_ms"] for e in eventos_de(s) if e["event"] == "decision"]
    assert latencias and all(
        isinstance(x, int | float) and not isinstance(x, bool) and x >= 0 for x in latencias
    )
    return [e for e in errs if "fast-path budget" not in e], counts


def test_el_shock_queda_en_el_jsonl(tmp_path):
    s = sesion(tmp_path)
    correr(s, 30)
    s.shock("closure", 40, zona=0, calle="Constitución")
    correr(s, 31)
    s.end()
    eventos = eventos_de(s)
    tipos = [e["event"] for e in eventos]
    assert tipos[0] == "shift_start" and tipos[-1] == "shift_end"
    i = tipos.index("shock")
    assert eventos[i]["zone"] == 0 and eventos[i]["sim_time"] == "2026-03-21T14:30:00"
    assert eventos[i]["shock_type"] == "closure" and eventos[i]["road"] == "Constitución"
    despues = [e for e in eventos[i:] if e["event"] == "decision"]
    assert {e["agent"] for e in despues} == {"greedy", "nuez"}
    assert {e["agent"] for e in eventos if e["event"] == "shift_end"} == {"greedy", "nuez"}


def test_el_jsonl_en_vivo_pasa_el_validador_oficial(tmp_path):
    s = sesion(tmp_path)
    correr(s, 30)
    s.shock("closure", 40, zona=0, calle="Constitución")
    correr(s, 50)
    s.shock("surge", 30, zona=4, multiplicador=1.8)
    correr(s, 120)  # tick llega al final: finished
    s.end()  # y end() sobre finished no puede volver a escribir shift_end

    formato, counts = errores_de_formato(s)
    assert formato == []
    for tipo in ("order_offered", "decision", "shock", "shift_end", "position_update"):
        assert counts.get(tipo), f"falta {tipo} en {counts}"
    assert counts["shift_start"] == 1 and counts["shock"] == 2 and counts["shift_end"] == 2
    assert counts["decision"] == 2 * counts["order_offered"], "cada oferta la deciden los dos"


def test_el_jsonl_en_vivo_es_ascii_y_aguanta_calles_con_acento(tmp_path):
    """El validador oficial lee con la codificacion del sistema (cp1252 en Windows).
    En UTF-8 la "Á" lleva el byte 0x81, que cp1252 no sabe leer: una calle escrita
    por el juez tumbaria el validador. El log en vivo se escribe en ASCII puro."""
    s = sesion(tmp_path)
    correr(s, 30)
    s.shock("closure", 40, zona=0, calle="Álvaro Obregón")
    s.end()

    crudo = s.log.path.read_bytes()
    assert crudo.isascii()
    assert any(e.get("road") == "Álvaro Obregón" for e in eventos_de(s))  # sin perder el acento
    formato, counts = errores_de_formato(s)
    assert formato == [] and counts["shock"] == 1


def test_un_shock_que_no_se_puede_anotar_no_se_inyecta(tmp_path, monkeypatch):
    """Si armar el evento truena, el shock no puede quedar vivo en los turnos sin
    rastro en el JSONL: el evento se arma antes de tocar nada."""
    s = sesion(tmp_path)
    correr(s, 10)
    antes = s.log.path.read_bytes()

    def truena(*_args, **_kwargs):
        raise ValueError("no se pudo armar el evento")

    monkeypatch.setattr("backendruta.live_demo.live_log.shock", truena)
    with pytest.raises(ValueError, match="no se pudo armar"):
        s.shock("closure", 40, zona=0, calle="Constitución")
    assert s.shocks == [] and s.snapshot()["active_shocks"] == []
    assert all(t.disrupciones == () for t in s.turnos.values())
    assert s.log.path.read_bytes() == antes


def test_la_razon_en_ingles_de_greedy_no_inventa_costo_de_oportunidad(tmp_path):
    """Greedy decide con un umbral fijo de $/min; la razon oficial no puede hablar de
    un costo de oportunidad que nunca calculo. La de Nuez si lo nombra."""
    s = sesion(tmp_path)
    s.end()
    decs = [e for e in eventos_de(s) if e["event"] == "decision"]
    greedy = [e["reason"] for e in decs if e["agent"] == "greedy"]
    nuez = [e["reason"] for e in decs if e["agent"] == "nuez"]
    assert greedy and not any("opportunity cost" in r for r in greedy)
    assert any("per-minute threshold" in r for r in greedy)
    assert any("opportunity cost" in r for r in nuez)


def test_mismo_seed_mismo_shock_mismo_jsonl(tmp_path):
    """Replay: fuera de session_id y latency_ms, el log no depende del reloj de pared."""

    def lineas(name):
        s = sesion(tmp_path, name=name)
        correr(s, 30)
        s.shock("closure", 40, zona=0, calle="Constitución")
        s.end()
        eventos = eventos_de(s)
        for e in eventos:
            e.pop("session_id", None)
            e.pop("latency_ms", None)
        return eventos

    a, b = lineas("a"), lineas("b")
    assert len(a) > 100 and a == b


def test_sesiones_nuevas_no_heredan_nada(tmp_path):
    vieja = sesion(tmp_path, name="vieja")
    correr(vieja, 40)
    vieja.shock("surge", 30, zona=4, multiplicador=1.8)
    nueva = sesion(tmp_path, name="nueva").snapshot()
    assert nueva["minute"] == 0 and nueva["active_shocks"] == []
    for a in ("greedy", "nuez"):
        assert nueva[a]["earnings_mxn"] == 0 and nueva[a]["route"] == []


def test_no_hay_tick_ni_shock_despues_de_terminar(tmp_path):
    s = sesion(tmp_path)
    s.end()
    with pytest.raises(SesionTerminada):
        s.tick()
    with pytest.raises(SesionTerminada):
        s.shock("closure", 40, zona=0)


def test_tick_al_final_marca_finished(tmp_path):
    s = sesion(tmp_path)
    ultimo = correr(s, 120)[-1]
    assert ultimo["status"] == "finished"
    assert ultimo["greedy"]["result"]["ganado"] == ultimo["greedy"]["earnings_mxn"]


# --- lo que Task 3 y el front dan por hecho ------------------------------------


def test_los_frames_son_los_del_replay_grabado(tmp_path):
    """El front reusa los renderers del replay: frame a frame tiene que ser a_frames."""
    export_turno = pytest.importorskip("data.export_turno")  # jala networkx
    s = sesion(tmp_path)
    frames = [f for sn in correr(s, 120) for f in sn["nuez"]["frames"]]
    res = simular(cfg(), partial(politica_nuez, tabla=valor.para_turno(120)))
    grabados = export_turno.a_frames(res, 120)
    assert [f["decisiones"] for f in frames] == [f["decisiones"] for f in grabados]
    assert [f["ofertas"] for f in frames] == [f["ofertas"] for f in grabados]
    assert [f["llegada"] for f in frames] == [f["llegada"] for f in grabados]
    assert frames[0].keys() == grabados[0].keys()
    assert frames[0]["ofertas"] == [asdict(o) for o in res.ofertas if o.t_aparece == 0]
    assert frames[-1]["ganado"] == pytest.approx(res.ganado, abs=0.05)


def test_el_snapshot_viaja_como_json_y_valida_el_shock(tmp_path):
    s = sesion(tmp_path)
    json.dumps(s.tick(5))
    fuera = s.shock("surge", 30, zona=4, multiplicador=1.8)
    json.dumps(fuera)
    assert fuera["shock"]["zone_name"] == "Tec" and fuera["shock"]["ends_at_min"] == 35
    assert fuera["snapshot"]["active_shocks"] == [fuera["shock"]]
    for malo in (
        dict(tipo="tornado", duracion_min=10, zona=0),
        dict(tipo="closure", duracion_min=0, zona=0),
        dict(tipo="closure", duracion_min=241, zona=0),
        dict(tipo="closure", duracion_min=10),
        dict(tipo="surge", duracion_min=10, zona=4, multiplicador=1.0),
        dict(tipo="surge", duracion_min=10, zona=4, multiplicador=3.5),
        dict(tipo="surge", duracion_min=10, zona=99, multiplicador=1.5),
    ):
        with pytest.raises(ValueError):
            s.shock(**malo)
    lluvia = s.shock("rain", 20, zona=0, multiplicador=2.0)["shock"]
    assert lluvia["zone"] is None and lluvia["multiplier"] == 1.0, "la lluvia es en toda la ciudad"
    assert lluvia["order_id"] is None and lluvia["slip_min"] is None, "mismas llaves para todos"
    fin = s.end()
    assert fin["status"] == "ended" and fin["event_log"] == str(s.log.path)


# --- delay: el restaurante se atrasa ------------------------------------------

# En el 20 del seed ensayado el siguiente pedido (o_017) no deja ver nada: los dos
# agentes lo saltan por capacidad y su cola ya llega al restaurante despues de la
# hora atrasada. En el 59 le toca a o_047: la espera sube los minutos de los dos y
# Nuez pasa de aceptarlo a saltarlo. Si se recalibra el mundo, volver a buscarlo.
MINUTO_DELAY = 59


def _nuez():
    return partial(politica_nuez, tabla=valor.para_turno(120))


def test_delay_pega_al_siguiente_pedido_y_se_ve_en_sus_terminos(tmp_path):
    def corrida(con_delay):
        s = sesion(tmp_path, name=f"d{con_delay}")
        correr(s, MINUTO_DELAY)
        fuera = s.shock("delay", retraso_min=15) if con_delay else None
        snaps = correr(s, 70)
        return s, fuera, {a: {d["oferta_id"]: d for d in decisiones(snaps, a)} for a in AGENTES}

    s, fuera, con = corrida(True)
    _, _, sin = corrida(False)

    siguiente = next(o for o in s.ofertas if o.t_aparece >= MINUTO_DELAY)
    objetivo = fuera["shock"]["order_id"]
    assert objetivo == siguiente.id == "o_047"
    zona = rutas.ZONA_DE[indice_de(siguiente.pickup)]
    assert fuera["shock"] == {
        "type": "delay",
        "zone": zonas.ID_POR_NOMBRE[zona],
        "zone_name": zona,
        "road": None,
        "starts_at_min": MINUTO_DELAY,
        "ends_at_min": 120,  # una vez tarde, tarde hasta el final del turno
        "multiplier": 1.0,
        "order_id": objetivo,
        "slip_min": 15,
    }
    assert fuera["snapshot"]["active_shocks"] == [fuera["shock"]]

    # `minutos` es lo que le cuesta ESTE pedido e incluye esperar al restaurante,
    # en las dos politicas. Antes de ese pedido nada cambia, asi que la diferencia
    # es solo la espera.
    for a in AGENTES:
        assert con[a][objetivo]["terminos"]["minutos"] > sin[a][objetivo]["terminos"]["minutos"], a
    assert any(con[a][objetivo]["accion"] != sin[a][objetivo]["accion"] for a in AGENTES)

    choque = next(e for e in eventos_de(s) if e["event"] == "shock")
    assert choque["order_id"] == objetivo and choque["slip_min"] == 15


def test_closure_surge_y_delay_pasan_el_validador_oficial(tmp_path):
    """Los tres shocks del ensayo en una sola sesion: el log sigue siendo del formato
    oficial y el delay lleva los nombres del esquema (order_id, slip_min) sin zona."""
    s = sesion(tmp_path)
    correr(s, 30)
    s.shock("closure", 40, zona=0, calle="Constitución")
    correr(s, 50)
    s.shock("surge", 30, zona=4, multiplicador=1.8)
    correr(s, MINUTO_DELAY)
    objetivo = s.shock("delay", retraso_min=15)["shock"]["order_id"]
    correr(s, 120)
    s.end()

    formato, counts = errores_de_formato(s)
    assert formato == [] and counts["shock"] == 3 and counts["shift_end"] == 2
    choques = [e for e in eventos_de(s) if e["event"] == "shock"]
    assert [e["shock_type"] for e in choques] == ["closure", "surge", "delay"]
    delay = choques[2]
    assert delay["order_id"] == objetivo and delay["slip_min"] == 15
    assert delay.get("zone") is None and delay["sim_time"] == "2026-03-21T14:59:00"


@pytest.mark.parametrize("minuto", [MINUTO_DELAY, 72], ids=["mueve-nuez", "mueve-greedy"])
def test_delay_inyectado_es_el_mismo_que_declarado(tmp_path, minuto):
    s = sesion(tmp_path, name=f"eq{minuto}")
    correr(s, minuto)
    objetivo = s.shock("delay", retraso_min=15)["shock"]["order_id"]
    fin = s.end()

    declarado = (shocks.Shock(minuto, "delay", 120 - minuto, oferta_id=objetivo, retraso_min=15),)
    cambio = False
    for a, politica in (("greedy", politica_greedy), ("nuez", _nuez())):
        res = simular(cfg(), politica, declarado)
        assert fin[a]["earnings_mxn"] == res.ganado, a
        assert fin[a]["result"]["entregas"] == res.entregas, a
        cambio |= res.ganado != simular(cfg(), politica).ganado
    assert cambio, "el delay tiene que mover el final de alguien, si no el test no prueba nada"


def test_delay_con_order_id_explicito(tmp_path):
    s = sesion(tmp_path)
    correr(s, MINUTO_DELAY)
    fuera = s.shock("delay", oferta_id="o_059", retraso_min=10, duracion_min=5)
    assert fuera["shock"]["order_id"] == "o_059" and fuera["shock"]["slip_min"] == 10
    assert fuera["shock"]["ends_at_min"] == 120, "la duracion que manden no aplica a un delay"


def test_delay_invalido_no_toca_la_sesion(tmp_path, monkeypatch):
    s = sesion(tmp_path)
    correr(s, MINUTO_DELAY)
    s.shock("rain", 20)
    antes = (s.minute, list(s.shocks), {a: t.disrupciones for a, t in s.turnos.items()})
    log = s.log.path.read_text(encoding="utf-8")

    def no_se_arma(*_args, **_kwargs):
        raise AssertionError("un delay invalido no llega a armar su evento")

    # La validacion truena antes de armar el evento, y el evento antes de inyectar.
    monkeypatch.setattr("backendruta.live_demo.live_log.shock", no_se_arma)

    for malo in (
        dict(oferta_id="o_000", retraso_min=15),  # ya aparecio
        dict(oferta_id="o_999", retraso_min=15),  # no existe
        dict(retraso_min=0),
        dict(retraso_min=61),
        dict(retraso_min=None),
    ):
        with pytest.raises(ValueError):
            s.shock("delay", **malo)
        assert (s.minute, list(s.shocks), {a: t.disrupciones for a, t in s.turnos.items()}) == antes
        assert s.log.path.read_text(encoding="utf-8") == log
    with pytest.raises(ValueError, match="ya apareci"):
        s.shock("delay", oferta_id="o_000", retraso_min=15)
    with pytest.raises(ValueError):
        s.shock("closure", zona=0)  # los demas tipos siguen necesitando duracion


def test_delay_sin_pedidos_por_venir(tmp_path):
    # El ultimo pedido del seed 2046 aparece en el 117: del 118 al final ya no hay a quien.
    s = sesion(tmp_path, seed=2046)
    assert s.ofertas[-1].t_aparece == 117
    correr(s, 118)
    assert s.snapshot()["status"] == "running"
    with pytest.raises(ValueError):
        s.shock("delay", retraso_min=15)
    assert s.shocks == [] and s.minute == 118


# --- geometria ----------------------------------------------------------------


def test_sin_grafo_la_geometria_es_linea_recta():
    assert por_calles(None) is linea_recta
    (lat_a, lon_a), (lat_b, lon_b) = rutas.COORD_DE[3], rutas.COORD_DE[7]
    geo = linea_recta([(0, 4.5, 3, 7)])
    assert geo == {
        "3-7": [
            [pytest.approx(lon_a, abs=1e-5), pytest.approx(lat_a, abs=1e-5)],
            [pytest.approx(lon_b, abs=1e-5), pytest.approx(lat_b, abs=1e-5)],
        ]
    }


def test_por_calles_usa_el_grafo_que_le_dan_y_cae_a_recta_por_tramo():
    nx = pytest.importorskip("networkx")
    n0, n1 = rutas.PUNTOS[0][1], rutas.PUNTOS[1][1]
    G = nx.MultiDiGraph()
    G.add_node(n0, x=-100.1, y=25.1)
    G.add_node("medio", x=-100.2, y=25.2)
    G.add_node(n1, x=-100.3, y=25.3)
    G.add_edge(n0, "medio", travel_time=1.0)
    G.add_edge("medio", n1, travel_time=1.0)

    geo = por_calles(G)([(0, 3, 0, 1), (3, 6, 1, 0), (6, 9, 0, 2)])
    assert geo["0-1"] == [[-100.1, 25.1], [-100.2, 25.2], [-100.3, 25.3]], "uso el grafo dado"
    # Sin camino de regreso y sin nodo para el punto 2: esos tramos caen a recta, no truenan.
    assert geo["1-0"] == linea_recta([(3, 6, 1, 0)])["1-0"]
    assert geo["0-2"] == linea_recta([(6, 9, 0, 2)])["0-2"]
