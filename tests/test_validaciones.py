import copy

import pytest

from src.herramientas import construir_recomendacion
from src.simulador import ejecutar_simulacion
from src.estadisticas import agregar_capacidad
from src.validaciones import ErrorValidacion, validar_escenario, validar_meta, validar_registro

BASE = dict(n_personas=20, llegadas={"distribucion": "exponencial", "media": 2},
            servicio={"distribucion": "triangular", "minimo": 1, "moda": 3, "maximo": 5}, replicas=30, semilla_base=2026)


def _con(**kw):
    d = copy.deepcopy(BASE)
    d.update(kw)
    return d


@pytest.mark.parametrize("datos", [
    _con(n_personas=0), _con(n_personas=101), _con(n_personas=2.5), _con(n_personas=True),
    _con(llegadas={"distribucion": "exponencial", "media": 0}),
    _con(llegadas={"distribucion": "exponencial", "media": -2}),
    _con(servicio={"distribucion": "triangular", "minimo": 1, "moda": 6, "maximo": 5}),
    _con(servicio={"distribucion": "uniforme", "minimo": 3, "maximo": 1}),
    _con(replicas=29), _con(replicas=101), _con(semilla_base=-1), _con(semilla_base=1.5),
    _con(llegadas={"distribucion": "exponencial", "media": float("inf")}),
    _con(capacidades=(1, 4)),
])
def test_p6_datos_invalidos_se_rechazan(datos):
    with pytest.raises(ErrorValidacion):
        validar_escenario(datos)


def test_p6_meta_negativa():
    with pytest.raises(ErrorValidacion):
        validar_meta(-0.1)
    assert validar_meta(0) == 0.0


def test_limites_validos_se_aceptan():
    assert validar_escenario(_con(n_personas=1, replicas=30)).n_personas == 1
    assert validar_escenario(_con(n_personas=100, replicas=100)).replicas == 100


def test_limite_de_personas_del_contexto():
    with pytest.raises(ErrorValidacion):
        validar_escenario(_con(n_personas=60), limite_personas=50)


def _estado(meta=2.0):
    esc = validar_escenario(BASE)
    r = ejecutar_simulacion(esc)
    res = {"huella": esc.huella(), "configuracion": r["configuracion"], "por_replica": r["por_replica"],
           "agregados": {c: agregar_capacidad(f) for c, f in r["por_replica"].items()}, "archivos": {}}
    return {"escenario": esc.como_dict(), "resultados": res, "recomendacion": construir_recomendacion(res, esc, meta)}, res


def test_p11_observador_no_registra_validacion_directa():
    est, _ = _estado(2.0)
    cap = est["recomendacion"]["capacidad"]
    assert validar_registro(est, "operador", 2.0, cap, "nota") == []
    errs = validar_registro(est, "observador", 2.0, cap, "nota")
    assert any("operador" in e for e in errs)


def test_registro_exige_coincidir_con_la_recomendacion_de_python():
    est, _ = _estado(2.0)
    errs = validar_registro(est, "operador", 2.0, 3, "n")
    assert any("no coincide" in e for e in errs)


def test_registro_exige_resultados_completos_y_vigentes():
    est, _ = _estado(2.0)
    cap = est["recomendacion"]["capacidad"]
    assert validar_registro({**est, "resultados": None}, "operador", 2.0, cap)
    incompleto = copy.deepcopy(est)
    incompleto["resultados"]["por_replica"]["3"] = incompleto["resultados"]["por_replica"]["3"][:10]
    assert any("incompletos" in e for e in validar_registro(incompleto, "operador", 2.0, cap))
    viejo = copy.deepcopy(est)
    viejo["escenario"]["n_personas"] = 30
    assert any("escenario vigente" in e for e in validar_registro(viejo, "operador", 2.0, cap))


def test_registro_bloqueado_si_ninguna_cumple_o_meta_cambio():
    est, _ = _estado(2.0)
    assert any("Ninguna capacidad" in e for e in validar_registro(est, "operador", 0.0001, 3))
    cap = est["recomendacion"]["capacidad"]
    assert any("vigentes" in e for e in validar_registro(est, "operador", 8.0, cap))  # recomendación de otra meta
