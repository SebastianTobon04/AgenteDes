import csv
import statistics

import pytest

from src.simulador import ejecutar_simulacion, generar_muestras_replica, simular_capacidad
from src.validaciones import validar_escenario

TOL = 1e-9
BASE = dict(n_personas=20, llegadas={"distribucion": "exponencial", "media": 2},
            servicio={"distribucion": "triangular", "minimo": 1, "moda": 3, "maximo": 5}, replicas=30, semilla_base=2026)


def esc(**kw):
    return validar_escenario({**BASE, **kw})


def test_p13_regresion_determinista():
    ll, sv = [0, 1, 2, 3, 4, 5], [4] * 6
    ref = {1: ([0, 3, 6, 9, 12, 15], 7.5, 24), 2: ([0, 0, 2, 2, 4, 4], 2.0, 13), 3: ([0, 0, 0, 1, 1, 1], 0.5, 10)}
    for c, (esperas, prom, salida) in ref.items():
        r = simular_capacidad(ll, sv, c)
        assert r["esperas"] == pytest.approx(esperas, abs=TOL)
        assert r["espera_promedio"] == pytest.approx(prom, abs=TOL)
        assert r["salida_ultima"] == pytest.approx(salida, abs=TOL)


def test_p1_estructura_y_agregados_verificables():
    r = ejecutar_simulacion(esc())
    for c in ("1", "2", "3"):
        filas = r["por_replica"][c]
        assert len(filas) == 30
        esperas = [f["espera_promedio"] for f in filas]
        ag = r["agregados"][c]
        assert ag["espera_promedio_media"] == pytest.approx(sum(esperas) / 30, abs=TOL)
        assert ag["espera_desviacion_muestral"] == pytest.approx(statistics.stdev(esperas), abs=TOL)  # R-1
        assert ag["salida_ultima_media"] == pytest.approx(sum(f["salida_ultima"] for f in filas) / 30, abs=TOL)


def test_mas_puestos_nunca_aumentan_la_espera_en_la_misma_replica():
    r = ejecutar_simulacion(esc())
    for i in range(30):
        e = [r["por_replica"][c][i]["espera_promedio"] for c in ("1", "2", "3")]
        assert e[0] >= e[1] - TOL >= e[2] - 2 * TOL


def test_semillas_y_primera_llegada():
    m = generar_muestras_replica(esc(semilla_base=100), 3)
    assert (m["semilla_llegadas"], m["semilla_servicios"]) == (106, 107)
    assert m["llegadas"][0] == 0.0 and len(m["llegadas"]) == 20 and len(m["servicios"]) == 20
    assert len(set(m["intervalos"])) > 1


def test_p14_reproducibilidad_y_independencia_entre_replicas():
    a, b = ejecutar_simulacion(esc()), ejecutar_simulacion(esc())
    assert a["por_replica"] == b["por_replica"] and a["muestras"] == b["muestras"]
    c = ejecutar_simulacion(esc(semilla_base=2027))
    assert c["muestras"][0]["servicios"] != a["muestras"][0]["servicios"]
    assert c["muestras"][0]["intervalos"] != a["muestras"][0]["intervalos"]
    # réplicas distintas -> muestras nuevas
    assert a["muestras"][0]["servicios"] != a["muestras"][1]["servicios"]
    assert a["muestras"][0]["llegadas"] != a["muestras"][1]["llegadas"]
    # muestras compartidas entre capacidades: re-simular con las mismas muestras reproduce cada capacidad
    for r in (0, 1):
        for cap in (1, 2, 3):
            s = simular_capacidad(a["muestras"][r]["llegadas"], a["muestras"][r]["servicios"], cap)
            assert s["espera_promedio"] == pytest.approx(a["por_replica"][str(cap)][r]["espera_promedio"], abs=TOL)


def test_p4_cambio_a_uniforme_conserva_llegadas_y_cambia_servicios():
    a = ejecutar_simulacion(esc())
    u = ejecutar_simulacion(esc(servicio={"distribucion": "uniforme", "minimo": 1, "maximo": 3}))
    for r in range(30):
        assert a["muestras"][r]["llegadas"] == u["muestras"][r]["llegadas"]
        assert a["muestras"][r]["servicios"] != u["muestras"][r]["servicios"]
        assert all(1 <= x <= 3 for x in u["muestras"][r]["servicios"])
    assert a["por_replica"] != u["por_replica"]


def test_una_persona():
    r = ejecutar_simulacion(esc(n_personas=1))
    assert r["muestras"][0]["intervalos"] == [] and r["por_replica"]["1"][0]["espera_promedio"] == 0
