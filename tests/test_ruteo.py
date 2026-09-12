"""La velocidad cambia viajes, no la espera, y nunca mueve la parada en curso."""

import pytest

import ruteo
import seguridad
from sim import Parada


def test_duracion_usa_vehiculo_y_hora_de_cada_tramo(monkeypatch):
    horas = []

    def viaje(i, j, hora, vehiculo="moto"):
        horas.append(hora)
        return 10 * seguridad.VEHICULOS[vehiculo].velocidad

    monkeypatch.setattr(ruteo.rutas, "minutos", viaje)
    orden = [Parada("pickup", 1, "a", listo_en=70), Parada("dropoff", 2, "a")]
    # Sale a 14:50; el restaurante esta listo a 15:10. La espera no se multiplica.
    assert ruteo.duracion(0, orden, 14, t0=50, vehiculo="bike") == 38
    assert horas == [14, 15]


@pytest.mark.parametrize("cantidad", (4, 9))
def test_primera_parada_fija_en_enumeracion_e_insercion(monkeypatch, cantidad):
    monkeypatch.setattr(ruteo.rutas, "minutos", lambda i, j, hora, vehiculo="moto": abs(i - j))
    paradas = [Parada("dropoff", i, str(i)) for i in range(cantidad, 0, -1)]
    orden, minutos = ruteo.mejor_ruta(0, paradas, 3, vehiculo="car")
    assert orden[0] == paradas[0]
    assert set(orden) == set(paradas)
    assert minutos == ruteo.duracion(0, orden, 3, vehiculo="car")
