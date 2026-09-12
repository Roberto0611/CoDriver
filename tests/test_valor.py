"""La tabla de valor: monotona, interpolada, acotada. Y se puede reconstruir."""

import valor


def test_v_json_empieza_en_cero_y_es_monotona():
    V = valor.cargar()
    assert V[0] == 0
    llaves = sorted(V)
    assert llaves[0] == 0
    for a, b in zip(llaves, llaves[1:], strict=False):
        assert b - a == valor.CUBETA
        assert V[b] >= V[a], "mas minutos nunca valen menos"


def test_interpola_linealmente_entre_cubetas():
    V = valor.cargar()
    assert valor.de(10) == V[10]
    assert valor.de(20) == V[20]
    assert abs(valor.de(15) - (V[10] + V[20]) / 2) < 1e-9


def test_se_acota_fuera_del_rango():
    V = valor.cargar()
    assert valor.de(-5) == 0
    assert valor.de(10_000) == V[max(V)]


def test_precio_del_tiempo_es_la_diferencia_y_nunca_negativo():
    assert abs(valor.precio_del_tiempo(90, 25) - (valor.de(90) - valor.de(65))) < 1e-9
    for restante in range(0, 121, 7):
        for minutos in (0, 5, 30, 200):
            assert valor.precio_del_tiempo(restante, minutos) >= 0


def test_construir_produce_una_tabla_completa():
    V = valor.construir(n=3, duracion=60)
    assert sorted(V) == list(range(0, 61, valor.CUBETA))
    assert V[0] == 0
    assert V[60] >= V[30] >= V[0]
