import pytest

from src.estadisticas import recomendar_capacidad

PROM = {1: 7.5, 2: 2.0, 3: 0.5}


def test_p2_regla_aislada_acepta_igualdad():
    assert recomendar_capacidad(PROM, 2) == 2     # 2 <= 2
    assert recomendar_capacidad(PROM, 8) == 1


def test_p3_ninguna_cumple():
    assert recomendar_capacidad(PROM, 0.25) is None


def test_meta_cero_y_exacta():
    assert recomendar_capacidad({1: 0.0, 2: 0.0, 3: 0.0}, 0) == 1
    assert recomendar_capacidad(PROM, 0.5) == 3


@pytest.mark.parametrize("meta", [-1, float("nan"), float("inf"), True, "1"])
def test_meta_invalida(meta):
    with pytest.raises(ValueError):
        recomendar_capacidad(PROM, meta)
