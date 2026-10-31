"""Checks do perfil dos lugares em que Lula mais cresceu entre os turnos de 2026."""

import pandas as pd
import pytest

from src.extra_entre_turnos import _decil
from src.utils import caminho


@pytest.fixture(scope="module")
def perfil():
    f = caminho("tables") / "extra_turnos_perfil.csv"
    if not f.exists():
        pytest.skip("extra entre turnos não rodado")
    return pd.read_csv(f)


def test_decil_soma_dez_por_cento():
    s = pd.Series([5.0, 4, 3, 2, 1, 0, -1, -2, -3, -4])
    w = pd.Series([1.0] * 10)
    assert _decil(s, w).tolist() == [True] + [False] * 9


def test_media_bate_com_criterio4():
    # Δ voto PT nacional do Critério 4 (pacto20.md): +6,7 p.p. dos aptos
    r = pd.read_csv(caminho("tables") / "extra_turnos_resumo.csv").set_index("recorte")
    assert abs(r.loc["locais", "d_lula_media"] - 6.7) < 0.05
    assert (r["d_lula_topo"] > r["d_lula_media"]).all() and (r["d_lula_demais"] < r["d_lula_media"]).all()


def test_recortes(perfil):
    assert perfil["recorte"].nunique() == 8
    x = perfil[perfil["variavel"] == "Taxa de captura"]
    assert (x["maior_crescimento"] > x["demais"]).all() and x["maior_crescimento"].between(0, 1).all()


def test_perfil_central_resiste_aos_recortes(perfil):
    n = perfil[perfil["variavel"].str.startswith("% negra")]
    assert (n["diferenca_dp"] > 0).all()
    c = perfil[perfil["variavel"].str.startswith("Δ comparecimento")]
    assert (c["maior_crescimento"] > c["demais"]).all()


def test_modelo():
    m = pd.read_csv(caminho("tables") / "extra_turnos_amc_modelo.csv")
    assert set(m["ano"]) == {2022, 2026} and (m["n"] == 5565).all()
    b = m[(m["modelo"] == "com voto disponível") & (m["variavel"] == "pct_negra")].set_index("ano")
    assert b.loc[2026, "p"] < 0.01 and b.loc[2022, "p"] > 0.10
