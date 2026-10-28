"""Checks da Fase E do plano3: indicadores brasileiros de esgotamento × conflito."""

import numpy as np
import pandas as pd
import pytest

from src.utils import caminho


@pytest.fixture(scope="module")
def n():
    f = caminho("tables") / "p3_e_nacional.csv"
    if not f.exists():
        pytest.skip("Fase E do plano3 não rodada")
    return pd.read_csv(f).set_index("ano")


def test_serie_completa(n):
    assert list(n.index) == [1994, 1998, 2002, 2006, 2010, 2014, 2018, 2022, 2026]
    assert n.loc[[1994, 1998], "abstencao_t2"].isna().all() and n.loc[2002:, "abstencao_t2"].notna().all()


def test_bate_com_referencias(n):
    # abstenção 2026 sem exterior (referência do usuário): 20,84% e 18,99%
    assert abs(n.loc[2026, "abstencao_t1"] - 20.84) < 0.05 and abs(n.loc[2026, "abstencao_t2"] - 18.99) < 0.05
    # s_PT do 2º turno de 2006–2026 coerente com o painel do projeto
    p = pd.read_parquet(caminho("processed") / "painel_eleicoes.parquet")
    for a in [2006, 2014, 2022]:
        s = p[p["eleicao"] == a]
        assert abs(100 * s["votos_pt"].sum() / s["validos"].sum() - n.loc[a, "s_pt_t2"]) < 0.3


def test_faixas(n):
    assert n[["r2_estrutura_social_t1", "moran_i_t1"]].apply(lambda s: s.between(0, 1)).all().all()
    assert (n["n_efetivo_candidatos_t1"] >= 1).all() and n["terceiros_t1"].between(0, 100).all()


def test_uf():
    u = pd.read_csv(caminho("tables") / "p3_e_uf.csv")
    assert u.groupby("ano")["SG_UF"].nunique().eq(27).all()
    assert u.loc[u["ano"] == 2026, "abstencao_t2"].notna().all()
