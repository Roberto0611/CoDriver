"""La matriz de tiempos: consulta O(1), consistente con el trafico y las zonas."""

import rutas
import seguridad
from mundo import ZONAS


def test_matriz_cuadrada_y_alineada_con_los_puntos():
    n = len(rutas.PUNTOS)
    assert n == len(rutas.ZONA_DE) == len(rutas.COORD_DE)
    assert rutas._M.shape == (n, n)


def test_de_un_punto_a_si_mismo_son_cero_minutos():
    assert rutas.minutos(0, 0, hora=12) == 0.0
    assert rutas.km(0, 0) == 0.0


def test_hora_pico_duele():
    centro = rutas.puntos_de("Centro")[0]
    valle = rutas.puntos_de("Valle")[0]
    libre = rutas.minutos(centro, valle, hora=3)
    pico = rutas.minutos(centro, valle, hora=18)
    assert libre > 0
    assert pico > libre * 2


def test_km_no_depende_del_trafico():
    centro = rutas.puntos_de("Centro")[0]
    valle = rutas.puntos_de("Valle")[0]
    assert rutas.km(centro, valle) > 0
    # km sale de la matriz de flujo libre; minutos a las 3 AM es flujo libre x1.0
    assert abs(rutas.km(centro, valle) - rutas.minutos(centro, valle, 3) / 60 * 30) < 1e-6


def test_cada_zona_tiene_puntos_y_todos_estan_en_una_zona():
    for zona in ZONAS:
        assert len(rutas.puntos_de(zona)) > 0
    assert set(rutas.ZONA_DE) <= set(ZONAS)
    assert len(rutas.puntos_de("Tec")) == 15


def test_indice_mas_cercano_resuelve_el_ancla_a_su_zona():
    lat, lon = ZONAS["Tec"][0], ZONAS["Tec"][1]
    i = rutas.indice_mas_cercano(lat, lon)
    assert rutas.ZONA_DE[i] == "Tec"
    # Un punto exacto se resuelve a si mismo.
    j = rutas.puntos_de("Valle")[0]
    assert rutas.indice_mas_cercano(*rutas.COORD_DE[j]) == j


def test_velocidad_por_vehiculo_y_trafico_al_cruzar_medianoche():
    origen, destino = rutas.puntos_de("Tec")[:2]
    for vehiculo, perfil in seguridad.VEHICULOS.items():
        for hora in (3, 14, 18, 25):
            assert rutas.minutos(origen, destino, hora, vehiculo) == (
                rutas.minutos(origen, destino, hora % 24) * perfil.velocidad
            )
