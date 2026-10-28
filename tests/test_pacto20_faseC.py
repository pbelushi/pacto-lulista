"""Checks da Fase C do pacto 2.0 (plano2.md): modelos por local com EF de município."""

import numpy as np
import pandas as pd
import pytest

from src.utils import caminho


def _t(n):
    p = caminho("tables") / f"pacto20_faseC_{n}.csv"
    if not p.exists():
        pytest.skip(f"{n}: Fase C não rodada")
    return pd.read_csv(p)


def test_amostra_cobre_escopo():
    a = _t("amostra")
    assert (a["municipios"] > 2400).all() and (a["locais"] > 70000).all()
    # s_PT ponderado coerente com o resultado nacional do 2º turno (amostra urbana, ~87% do eleitorado)
    assert a["s_pt_media_pond"].between(35, 65).all()


def test_c1_coeficientes_finitos():
    c = _t("c1_coef")
    assert c[["coef", "ep"]].notna().all().all() and (c["ep"] > 0).all()
    assert set(c["ano"]) == {2018, 2022, 2026}


def test_c1_tercis_completos():
    t = _t("c1_tercis")
    assert len(t) == 3 * 2 * 4 and t["ep"].gt(0).all()


def test_c2_delta_consistente_com_betas():
    b, d = _t("c2_betas"), _t("c2_delta")
    for (am, v), g in b.groupby(["amostra", "variavel"]):
        if v not in ("jovens", "negros"):
            continue
        beta = g.set_index("ano")["beta"]
        dd = d[(d["amostra"] == am) & (d["variavel"] == v)].set_index("contraste")["delta_beta"]
        assert np.isclose(dd["2026−2018"], beta[2026] - beta[2018])
        assert np.isclose(dd["2026−2022"], beta[2026] - beta[2022])


def test_c4_media_bate_com_nacional_2026():
    c = _t("c4_turnos")
    m = c[(c["ano"] == 2026) & (c["resultado"] == "Δ comparecimento")]["media_pond"].iat[0]
    # abstenção nacional sem exterior: 20,84% (1º) e 18,99% (2º) → +1,85 p.p. de comparecimento
    assert abs(m - 1.85) < 0.3


def test_c4_idade_publicada():
    i = _t("c4_idade")
    assert i["comp_t1"].between(40, 100).all()
    assert i.loc[i["ano"] == 2022, "comp_t2"].notna().all()


def test_c4_ei_proporcoes():
    e = _t("c4_ei")
    s = e.groupby(["municipio", "origem_1t"])["proporcao"].sum()
    assert np.allclose(s, 1, atol=0.01)


def test_c5_grupos():
    h = _t("c5_heterogeneidade")
    assert {"capital", "RM (exceto capital)", "interior"} <= set(h["grupo"])


def test_c4_goodman_linhas_somam_um():
    g = _t("c4_goodman")
    s = g.groupby(["municipio", "origem_1t"])["proporcao"].sum()
    assert np.allclose(s, 1, atol=1e-4) and g["proporcao"].between(-1e-6, 1 + 1e-6).all()
