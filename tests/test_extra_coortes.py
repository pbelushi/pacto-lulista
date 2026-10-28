"""Checks do teste extra de coortes etárias (src/ingest/ibge_idade.py, src/coortes.py)."""

import numpy as np
import pandas as pd

from src.utils import caminho


def test_coortes_somam_100_e_cobertura():
    d = pd.read_parquet(caminho("interim") / "ibge_idade.parquet")
    s = d[["pct_coorte_1991", "pct_coorte_1970_1990", "pct_coorte_ate1969"]].sum(axis=1)
    assert np.allclose(s, 100)
    assert (d.groupby("ano")["id_municipio"].nunique() >= 5565).all()


def test_adultos_nacional_plausivel():
    """18+ nos Censos: ~134,5 mi (2010) e ~154,3 mi (2022); eleitorado apto 2010/2022 = 135,5 / 155,8 mi."""
    t = pd.read_parquet(caminho("interim") / "ibge_idade.parquet").groupby("ano")["pop_18mais"].sum()
    assert 130e6 < t[2010] < 140e6 and 150e6 < t[2022] < 160e6


def test_saidas_coortes():
    for t in ["por_grupo", "por_quintil", "por_perfil", "regressoes", "diferencas_longas"]:
        assert (caminho("tables") / f"extra_coortes_{t}.csv").exists(), t
    for f in ["extra_coortes_perfis", "extra_coortes_betas"]:
        assert (caminho("figures") / f"{f}.png").exists() and (caminho("figures") / f"{f}.svg").exists()
    r = pd.read_csv(caminho("tables") / "extra_coortes_regressoes.csv")
    assert np.isfinite(r[["beta_pp", "ep"]]).all().all()
    assert set(r["eleicao"]) == {2006, 2010, 2014, 2022, 2026}


def test_tse_perfil_bate_com_aptos():
    """Eleitorado do perfil (sem exterior) ≈ aptos da eleição (detalhe_votacao_munzona), dentro de 0,5%."""
    p = pd.read_parquet(caminho("interim") / "tse_perfil_idade.parquet")
    s = p.groupby("ano")["eleitores"].sum()
    aptos = pd.read_parquet(caminho("processed") / "painel_eleicoes.parquet").groupby("eleicao")["aptos"].sum()
    for ano in s.index:
        assert abs(s[ano] / aptos[ano] - 1) < 0.005, (ano, s[ano], aptos[ano])
    cols = ["pct_coorte_1991", "pct_coorte_1970_1990", "pct_coorte_ate1969"]
    assert np.allclose(p[cols].sum(axis=1), 100)


def test_tse_coortes_saidas_e_censo():
    for t in ["nacional", "quintis_1991", "q5_menos_q1", "regressoes", "vs_censo"]:
        assert (caminho("tables") / f"extra_tse_coortes_{t}.csv").exists(), t
    c = pd.read_csv(caminho("tables") / "extra_tse_coortes_vs_censo.csv")
    assert (c["corr"] > 0.7).all(), c
    n = pd.read_csv(caminho("tables") / "extra_tse_coortes_nacional.csv")
    assert n["% nascidos 1991+"].is_monotonic_increasing
