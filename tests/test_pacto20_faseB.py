"""Checks da Fase B do pacto 2.0 (docs/planos/plano2.md): entorno censitário dos locais de votação."""

import numpy as np
import pandas as pd
import pytest

from src.utils import caminho


def _t(n):
    p = caminho("tables") / f"pacto20_faseB_{n}.csv"
    if not p.exists():
        pytest.skip(f"{n}: Fase B não rodada")
    return pd.read_csv(p)


def test_escopo_reportado():
    e = _t("escopo")
    assert (e["municipios_escopo"] > 2000).all() and (e["pct_eleitorado_escopo"] > 80).all()


def test_cobertura_entorno():
    c = _t("cobertura")
    assert (c["pct_eleitorado_com_entorno"] >= 95).all(), c


def test_voronoi_particiona_municipio():
    c = _t("check_pop_voronoi")
    assert (c["pct_dentro_5pct"] >= 95).all(), c


def test_faixas_plausiveis():
    for a in [2018, 2022, 2026]:
        e = pd.read_parquet(caminho("interim") / f"pacto20_entorno_{a}.parquet")
        for suf in ["_vor", "_buf"]:
            assert e[f"pct_negra{suf}"].dropna().between(0, 100 + 1e-6).all()
            assert e[f"pct_urbana{suf}"].dropna().between(0, 100 + 1e-6).all()
            assert (e[f"renda_media{suf}"].dropna() > 0).all()
    v = _t("vor_x_buf")
    assert (v.loc[v["variavel"].isin(["pct_negra", "renda_media"]), "corr_vor_buf"] > 0.8).all(), v
