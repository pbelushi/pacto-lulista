"""Checks da Fase A do pacto 2.0 (docs/planos/plano2.md): base por local de votação 2018, 2022, 2026."""

import numpy as np
import pandas as pd
import pytest

from src.utils import caminho

ANOS = [2018, 2022, 2026]


def _t(n):
    p = caminho("tables") / f"pacto20_faseA_{n}.csv"
    if not p.exists():
        pytest.skip(f"{n}: Fase A não rodada")
    return pd.read_csv(p)


def test_bases_existem():
    for a in ANOS:
        b = pd.read_parquet(caminho("interim") / f"pacto20_locais_{a}.parquet")
        assert len(b) > 80_000 and b["aptos_t2"].sum() > 140e6


def test_sem_duplicidade():
    d = _t("duplicidades")
    cols = [c for c in d.columns if "duplicad" in c]
    assert (d[cols] == 0).all().all(), d


def test_totais_municipais_batem_com_painel():
    """Presidente, 2º turno: votos do PT, do opositor, válidos e aptos por AMC, tolerância de 0,1%."""
    c = _t("check_municipal")
    for col in ["dif_pt", "dif_op", "dif_validos", "dif_aptos"]:
        ruins = c[c[col].abs() > 0.001]
        assert len(ruins) == 0, (col, ruins.head(10).to_dict("records"))


def test_coordenadas_dentro_do_municipio():
    c = _t("coordenadas")
    assert (c["pct_com_coord_ate_500m_do_municipio"] >= 95).all(), c


def test_match_reportado():
    m = _t("match")
    tot = m[m["metodo"] == "total"]
    assert set(zip(tot["ano"], tot["referencia"])) >= {(2018, 2026), (2022, 2026), (2018, 2022)}
    assert np.isfinite(tot["pct_eleitorado"]).all()
