"""Checks da Fase 4 — painéis (PLANO.md, seção 5)."""

import numpy as np
import pandas as pd
import pytest

from src.utils import caminho, config

N_AMC = 5571 - len(config()["amc"])
ANOS = config()["anos_eleicao"]


@pytest.fixture(scope="module")
def ele():
    return pd.read_parquet(caminho("processed") / "painel_eleicoes.parquet")


@pytest.fixture(scope="module")
def amc():
    return pd.read_parquet(caminho("processed") / "painel_amc_anual.parquet")


@pytest.fixture(scope="module")
def mun():
    return pd.read_parquet(caminho("processed") / "painel_municipal.parquet")


def test_chaves(ele, amc, mun):
    assert not ele.duplicated(["eleicao", "id_amc"]).any()
    assert (ele.groupby("eleicao").size() == N_AMC).all()
    assert sorted(ele["eleicao"].unique()) == ANOS
    assert not amc.duplicated(["id_amc", "ano"]).any()
    assert not mun.duplicated(["id_municipio", "ano"]).any()


def test_votacao_preservada(ele):
    """O painel traz a votação da Fase 1 sem alteração."""
    pres = pd.read_parquet(caminho("interim") / "tse_presidencial.parquet")
    m = ele.merge(pres[["ano", "id_amc", "s_pt"]], left_on=["eleicao", "id_amc"], right_on=["ano", "id_amc"])
    assert len(m) == len(ele) and np.allclose(m["s_pt_x"], m["s_pt_y"])


def test_agregacao_amc_conserva_totais(amc, mun):
    for c in ["pop", "pib"]:
        a = amc.groupby("ano")[c].sum()
        b = mun.groupby("ano")[c].sum()
        assert np.allclose(a.loc[b.index], b, rtol=1e-9), c


def test_alinhamento_temporal(ele):
    for t, g in ele.groupby("eleicao"):
        assert (g["ano_ref_pib"].dropna() <= t - 1).all()
        assert (g["ano_ref_ideb"].dropna() <= t - 1).all()
        assert (g["ano_ref_vab"].dropna() <= t - 1).all()
        ref = config()["alinhamento"]["censo"][t]
        if ref is None:
            assert g["pct_evangelica"].isna().all() and g["pct_evangelica_interp"].notna().mean() > 0.99
        else:
            assert (g["ano_ref_censo"] == ref).all()


def test_interpolacao_2018(ele, amc):
    g = ele[ele["eleicao"] == 2018].set_index("id_amc")["pct_negra_interp"]
    c10 = amc[amc["ano"] == 2010].set_index("id_amc")["pct_negra"]
    c22 = amc[amc["ano"] == 2022].set_index("id_amc")["pct_negra"]
    esperado = c10 + (8 / 12) * (c22 - c10)
    idx = g.dropna().index
    assert np.allclose(g.loc[idx], esperado.loc[idx])


def test_cobertura_covariaveis(ele):
    """Cobertura mínima das covariáveis principais (≥ 97% das AMCs)."""
    for c in ["pop", "pib_pc_real", "part_vab_agro", "ideb_ai_publica"]:
        cob = ele.groupby("eleicao")[c].apply(lambda s: s.notna().mean())
        # Ideb 2005 (1ª edição, usado em 2006) não foi divulgado para ~10% dos municípios
        minimo = pd.Series(0.97, index=cob.index)
        if c == "ideb_ai_publica":
            minimo[2006] = 0.90
        assert (cob > minimo).all(), (c, cob)
    for t in [2010, 2014, 2022, 2026]:
        assert ele.loc[ele["eleicao"] == t, "pct_evangelica"].notna().mean() > 0.99


def test_capitais(ele):
    assert ele.loc[ele["eleicao"] == 2026, "capital"].sum() == 27


def test_dicionario(ele):
    d = pd.read_csv(caminho("tables") / "dicionario.csv")
    assert set(d["variavel"]) == set(ele.columns)
    assert (d["descricao"] != "(ver código-fonte)").mean() > 0.9
