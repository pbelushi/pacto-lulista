"""Checks da Fase 7 — espacial e robustez (docs/planos/PLANO.md, seção 5)."""

import numpy as np
import pandas as pd

from src.utils import caminho


def _t(nome):
    return pd.read_csv(caminho("tables") / f"{nome}.csv")


def test_saidas_existem():
    for t in ["fase7_espacial_moran", "fase7_espacial_lisa_contagem", "fase7_espacial_spreg",
              "fase7_espacial_conley", "fase7_robustez"]:
        assert (caminho("tables") / f"{t}.csv").exists(), t
    for f in ["fase7_lisa_swing", "fase7_robustez"]:
        assert (caminho("figures") / f"{f}.png").exists(), f


def test_moran():
    m = _t("fase7_espacial_moran")
    assert m["moran_I"].between(-1, 1).all()
    assert (m["n"] >= 5560).all()


def test_lisa_cobre_todas_amcs():
    c = _t("fase7_espacial_lisa_contagem")
    assert 5560 <= c["n_amc"].sum() <= 5565
    assert set(c["lisa"]) <= {"HH", "LL", "HL", "LH", "n.s."}


def test_spreg_parametros_espaciais():
    s = _t("fase7_espacial_spreg")
    lam = s[s["variavel"] == "lambda (erro espacial)"]["coef"]
    rho = s[s["variavel"] == "rho (lag espacial)"]["coef"]
    assert len(lam) == 3 and len(rho) == 3
    assert lam.between(-1, 1).all() and rho.between(-1, 1).all()
    assert np.isfinite(s[["coef", "ep"]]).all().all()


def test_conley_coef_igual_fase6():
    c = _t("fase7_espacial_conley")
    b = _t("fase6_betas_por_eleicao")
    b = b[(b["spec"] == "A") & b["y"].isin(["s_pt", "hiato_lulista"])]
    m = c.merge(b, on=["y", "eleicao", "variavel"])
    assert len(m) == len(c)
    assert np.allclose(m["coef"], m["beta"])
    assert np.allclose(m["cluster_microrregiao"], m["ep"])
    assert (c[["conley_100km", "conley_250km"]] > 0).all().all()


def test_robustez_principal_igual_fase6():
    r = _t("fase7_robustez")
    p = r[(r["spec"] == "principal") & (r["familia"] == "E1")].set_index("variavel")["estimativa"]
    f6 = _t("fase6_teste_igualdade_betas")
    f6 = f6[(f6["y"] == "s_pt") & (f6["comparacao"] == "2026 − 2010")].set_index("variavel")["dif_beta"]
    assert np.allclose(p, f6.loc[p.index])


def test_robustez_especificacoes():
    r = _t("fase7_robustez")
    esperadas = {"principal", "(a) ±0,5 DP", "(a) quintis", "(a) tercis", "(b) sem ponderação", "(c) sem capitais",
                 "(d) sem AMCs < 5 mil hab.", "(e) base 2006", "(f) final 2022", "(g) federação",
                 "(h) sem dependência de puxador", "(i) só legenda"}
    assert set(r["spec"]) == esperadas
    assert np.isfinite(r[["estimativa", "ep"]]).all().all()
