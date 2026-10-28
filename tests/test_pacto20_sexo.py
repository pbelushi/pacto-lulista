"""Checks do extra de comparecimento por sexo (pacto 2.0)."""

import numpy as np
import pandas as pd
import pytest

from src.utils import caminho


def _t(n):
    p = caminho("tables") / f"pacto20_extra_sexo_{n}.csv"
    if not p.exists():
        pytest.skip(f"{n}: não rodado")
    return pd.read_csv(p)


def test_verdade_coerente_com_total_nacional():
    v = _t("comparecimento")
    t = v[v["faixa"] == "todas"]
    assert t["comp_t1"].between(70, 90).all()
    # 2026, 1º turno: abstenção nacional sem exterior de 20,84% → comparecimento ~79,2% entre os dois sexos
    c = t[t["ano"] == 2026].set_index("sexo")["comp_t1"]
    assert c["homens"] < 79.16 < c["mulheres"]


def test_validacao_presente_onde_ha_dado_direto():
    e = _t("ecologico")
    assert e.loc[e["ano"].isin([2018, 2022]), "dif_mulheres_menos_homens_real"].notna().all()
    assert np.isfinite(e["dif_mulheres_menos_homens_est"]).all() and (e["ep"] > 0).all()
    # decomposição: média = f̄·Δmulheres + (1 − f̄)·Δhomens, com f̄ entre 0,4 e 0,6
    fb = (e["delta_medio"] - e["delta_homens_est"]) / (e["delta_mulheres_est"] - e["delta_homens_est"])
    assert fb.between(0.4, 0.6).all()
