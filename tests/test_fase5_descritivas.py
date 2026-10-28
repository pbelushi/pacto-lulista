"""Checks da Fase 5 — descritivas (PLANO.md, seção 5)."""

import pandas as pd
import pytest

from src.utils import caminho, config


def _t(nome):
    return pd.read_csv(caminho("tables") / f"{nome}.csv")


def test_saidas_existem():
    for t in ["fase5_trajetorias_mediana_iqr", "fase5_deltas_bootstrap", "fase5_perfil_inicial_final",
              "fase5_grupos_por_regiao", "fase5_perfil_proporcional_z", "fase5_distancias_perfis",
              "fase5_perfil_celulas"]:
        assert (caminho("tables") / f"{t}.csv").exists() and (caminho("tables") / f"{t}.md").exists(), t
    for f in ["fase5_trajetorias_g_swing", "fase5_trajetorias_cluster_forma", "fase5_deltas_gpt_menos_gop",
              "fase5_perfil_proporcional", f"fase5_perfil_celulas_{config()['ano_final']}"]:
        for ext in ["png", "svg"]:
            assert (caminho("figures") / f"{f}.{ext}").exists(), f


def test_trajetorias_quantis_ordenados():
    t = _t("fase5_trajetorias_mediana_iqr")
    assert ((t["q25"] <= t["mediana"] + 1e-9) & (t["mediana"] <= t["q75"] + 1e-9)).all()
    assert set(t.loc[t["esquema"] == "g_swing", "grupo"]) == {"G_PT", "G_EST", "G_OP"}


def test_bootstrap_ic_contem_estimativa():
    d = _t("fase5_deltas_bootstrap").dropna(subset=["dif_medianas"])
    assert len(d) > 300
    assert ((d["ic95_inf"] <= d["dif_medianas"] + 1e-9) & (d["dif_medianas"] <= d["ic95_sup"] + 1e-9)).all()
    assert d["p_bootstrap"].between(0, 1).all()
    assert set(d["regiao"]) == {"Brasil", "Norte", "Nordeste", "Sudeste", "Sul", "Centro-Oeste"}


def test_ideb_delta_parte_de_2009():
    d = _t("fase5_deltas_bootstrap")
    assert (d.loc[d["indicador"] == "ideb_ai_publica", "periodo"] == "2009→2025").all()


def test_perfil_proporcional_completo():
    p = _t("fase5_perfil_proporcional_z")
    assert (p.groupby("eleicao").size() == 3).all()
    assert len(p) == 3 * len(config()["anos_eleicao"])
    # z-score dentro da eleição: a média ponderada pelo n dos três grupos é ~0 (só empates ficam de fora)
    for var in ["pib_pc_real", "part_vab_agro"]:
        m = p.groupby("eleicao").apply(lambda g: (g[var] * g["n"]).sum() / g["n"].sum(), include_groups=False)
        assert m.abs().max() < 0.01, var


def test_celulas_somam_amcs():
    c = _t("fase5_perfil_celulas")
    n = c.groupby("eleicao")["n"].sum()
    assert (n >= 5555).all() and (n <= 5565).all()
    assert (c.groupby("eleicao")["pct_eleitorado"].sum().sub(100).abs() < 1e-6).all()


def test_distancias():
    d = _t("fase5_distancias_perfis")
    assert (d["distancia"] >= 0).all()
