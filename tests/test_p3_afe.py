"""Checks do extra do plano3: análise fatorial exploratória das variáveis de polarização do V-Dem."""

import pandas as pd
import pytest

from src.utils import caminho


@pytest.fixture(scope="module")
def tabs():
    f = caminho("tables") / "p3_afe_amostras.csv"
    if not f.exists():
        pytest.skip("AFE do plano3 não rodada")
    return pd.read_csv(f), pd.read_csv(caminho("tables") / "p3_afe_polarizacao.csv")


def test_adequacao(tabs):
    a, _ = tabs
    assert set(a["amostra"]) == {"1900–2025", "2000–2025"}
    assert (a["kmo"].dropna() > 0.8).all()
    assert (a["pais_anos"] > 3000).all() and (a["variaveis"] > 100).all()


def test_ancora_no_fator(tabs):
    a, p = tabs
    princ = a[a["especificacao"] == "principal"]
    assert (princ["carga_v2cacamps"] >= 0.40).all() and (princ["pertinentes"] >= 3).all()
    # a carga da âncora está alinhada para > 0 em todas as especificações com fator definido
    assert (a["carga_v2cacamps"].dropna() >= 0.40).all()
    assert (p.loc[p["variavel"] == "v2cacamps", "carga principal"] > 0).all()


def test_coerencia(tabs):
    a, p = tabs
    assert p["carga principal"].abs().le(1.05).all() and p["h2"].between(0, 1.05).all()
    assert not p.duplicated(["amostra", "variavel"]).any()
    # contagem de especificações bate com as cargas
    cargas = p.filter(like="carga ")
    assert (cargas.abs().ge(0.40).sum(axis=1) == p["especificacoes_ge_040"]).all()
    # v2smpolsoc (escala invertida: 0 = polarização grave) entra no recorte 2000–2025 com sinal negativo
    s = p[(p["amostra"] == "2000–2025") & (p["variavel"] == "v2smpolsoc")]
    assert len(s) == 1 and s["carga principal"].iloc[0] < 0
