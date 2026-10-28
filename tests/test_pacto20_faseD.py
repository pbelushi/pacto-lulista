"""Checks da Fase D do pacto 2.0 (docs/planos/plano2.md): robustez."""

import numpy as np
import pandas as pd
import pytest

from src.utils import caminho


def _t(n):
    p = caminho("tables") / f"pacto20_faseD_{n}.csv"
    if not p.exists():
        pytest.skip(f"{n}: Fase D não rodada")
    return pd.read_csv(p)


def test_variantes_completas():
    b = _t("variantes_betas")
    assert b["amostra"].nunique() == 5 and b[["beta", "ep"]].notna().all().all()


def test_referencia_reproduz_fase_c():
    b = _t("variantes_betas")
    c = pd.read_csv(caminho("tables") / "pacto20_faseC_c2_betas.csv")
    r = b[b["amostra"].str.startswith("referência")].set_index(["variavel", "ano"])["beta"]
    c = c[c["amostra"] == "todos os locais"].set_index(["variavel", "ano"])["beta"]
    assert np.allclose(r.sort_index(), c.sort_index())


def test_conley_cresce_com_raio():
    c = _t("conley")
    p = c.pivot_table(index=["ano", "variavel"], columns="tipo_ep", values="ep")
    assert (p["Conley 5 km"] >= p["Conley 2 km"] - 1e-9).all()
    assert (p["Conley 2 km"] >= p["robusto (HC0)"] - 1e-9).all()


def test_moran_reportado():
    m = _t("moran")
    assert m["moran_i"].between(-1, 1).all() and len(m) == 6


def test_placebo():
    p = _t("placebo_betas")
    assert {2010, 2014} <= set(p["ano"]) and p[["beta", "ep"]].notna().all().all()
    chk = _t("placebo_check_municipal")
    assert len(chk) > 0
