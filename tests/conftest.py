"""Reglas para toda la suite.

Los tests NO hablan con Gemini. Ahora que `.env` trae la credencial, el hilo de la
capa de estrategia la usaria de verdad en cada test que levante un turno: lento,
dependiente de la red, y distinto segun quien lo corra. En CI ni siquiera hay llave.

El test que si tiene que probar el camino real de la credencial se salta esto a
mano con `monkeypatch` (ver `tests/test_estrategia.py`).
"""

import pytest


@pytest.fixture(autouse=True)
def sin_modelo_de_verdad(monkeypatch):
    monkeypatch.setenv("NUEZ_MODELO", "falso")
