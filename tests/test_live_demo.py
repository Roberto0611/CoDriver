"""El demo en vivo: el mismo motor, dos agentes, un solo stream de ofertas."""

import json
from dataclasses import asdict
from functools import partial

import pytest

import rutas
import valor
from backendruta.live_demo import SEED_ENSAYADO, LiveDemoSession, SesionTerminada
from backendruta.live_geometry import linea_recta, por_calles
from contrato import ConfigTurno, Punto
from nuez import politica_nuez
from sim import politica_greedy, simular


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


def test_sin_shocks_el_final_es_el_de_simular(tmp_path):
    s = sesion(tmp_path)
    fin = s.end()
    assert fin["greedy"]["earnings_mxn"] == simular(cfg(), politica_greedy).ganado
    nuez = partial(politica_nuez, tabla=valor.para_turno(120))
    assert fin["nuez"]["earnings_mxn"] == simular(cfg(), nuez).ganado


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


def test_el_shock_queda_en_el_jsonl(tmp_path):
    s = sesion(tmp_path)
    correr(s, 30)
    s.shock("closure", 40, zona=0, calle="Constitución")
    correr(s, 31)
    s.end()
    eventos = [json.loads(linea) for linea in s.log.path.read_text(encoding="utf-8").splitlines()]
    tipos = [e["event"] for e in eventos]
    assert tipos[0] == "shift_start" and tipos[-1] == "shift_end"
    i = tipos.index("shock")
    assert eventos[i]["minute"] == 30 and eventos[i]["zone"] == 0
    despues = [e for e in eventos[i:] if e["event"] == "decision"]
    assert {e["agent"] for e in despues} == {"greedy", "nuez"}


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
    fin = s.end()
    assert fin["status"] == "ended" and fin["event_log"] == str(s.log.path)


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
