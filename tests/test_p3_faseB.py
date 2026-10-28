"""Checks da Fase B do plano3: episódios de polarização."""

import pandas as pd
import pytest

from src.utils import caminho


@pytest.fixture(scope="module")
def e():
    f = caminho("tables") / "p3_episodios.csv"
    if not f.exists():
        pytest.skip("Fase B do plano3 não rodada")
    return pd.read_csv(f)


def test_estrutura(e, ):
    assert (e["duracao"] >= 3).all() and (e["fim"] >= e["inicio"]).all()
    assert (e["duracao"] == e["fim"] - e["inicio"] + 1).all()
    assert e["termino"].isin(["ruptura", "despolarização", "em curso", "fim da série"]).all()
    assert (e["censurado"] == e["termino"].isin(["em curso", "fim da série"])).all()
    assert (e.loc[e["termino"] == "em curso", "fim"] == 2025).all()


def test_sem_sobreposicao(e):
    for _, s in e.sort_values("inicio").groupby("iso"):
        assert (s["inicio"].values[1:] > s["fim"].values[:-1]).all()


def test_ruptura_tem_evento(e):
    r = e[e["termino"] == "ruptura"]
    assert r["eventos_termino"].notna().all() and (r["eventos_termino"].str.len() > 0).all()
    assert not r["eventos_termino"].str.contains("guerra civil").any()


def test_referencias(e):
    v = pd.read_csv(caminho("tables") / "p3_faseB_referencia.csv").set_index("caso")["capturado"]
    assert v.sum() >= 9
    for c in ["Brasil 1954–1964", "Brasil pós-2014", "Chile 1970–1973", "Alemanha 1919–1933"]:
        assert v[c]
    b = e[(e["iso"] == "BRA") & (e["fim"] == 1964)]
    assert len(b) == 1 and "golpe" in b["eventos_termino"].iat[0]


def test_robustez(e):
    r = pd.read_csv(caminho("tables") / "p3_faseB_robustez.csv")
    assert len(r) == 6 and (r["episodios"] > 50).all()
    assert r.loc[r["variante"].str.startswith("limiar p75"), "episodios"].iat[0] > r.loc[r["variante"].str.startswith("principal"), "episodios"].iat[0]
