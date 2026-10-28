"""Checks da Fase 6 — modelos (PLANO.md, seção 5)."""

import numpy as np
import pandas as pd

from src.utils import caminho, config


def _t(nome):
    return pd.read_csv(caminho("tables") / f"{nome}.csv")


def test_saidas_existem():
    for t in ["fase6_betas_por_eleicao", "fase6_teste_igualdade_betas", "fase6_diferencas_longas",
              "fase6_diferencas_longas_r2", "fase6_logit_grupos_swing_ame", "fase6_oaxaca_resumo",
              "fase6_oaxaca_detalhe", "fase6_logit_proporcional_ame"]:
        assert (caminho("tables") / f"{t}.csv").exists(), t
    for f in ["fase6_betas_s_pt", "fase6_betas_presidencial_x_camara", "fase6_betas_hiato", "fase6_oaxaca"]:
        assert (caminho("figures") / f"{f}.png").exists(), f


def test_betas_completos():
    t = _t("fase6_betas_por_eleicao")
    anos = config()["anos_eleicao"]
    sem_censo = [a for a in anos if config()["alinhamento"]["censo"][a] is None]
    for y in ["s_pt", "p_PT", "p_ANTI", "hiato_lulista"]:
        a = t[(t["y"] == y) & (t["spec"] == "A")]
        b = t[(t["y"] == y) & (t["spec"] == "B")]
        assert set(a["eleicao"]) == set(anos) - set(sem_censo)
        assert set(b["eleicao"]) == set(anos)
    assert np.isfinite(t[["beta", "ep", "ic_inf", "ic_sup"]]).all().all()
    assert ((t["ic_inf"] <= t["beta"]) & (t["beta"] <= t["ic_sup"])).all()
    # quase toda a amostra entra (Ideb ausente imputado com dummy)
    assert (t["n"] >= 5500).all()


def test_censo_nunca_interpolado_em_regressao():
    t = _t("fase6_betas_por_eleicao")
    assert t[(t["eleicao"] == 2018) & t["variavel"].str.startswith("pct_")].empty


def test_oaxaca_identidade():
    r = _t("fase6_oaxaca_resumo").set_index("componente")["estimativa"]
    assert abs(r["y_final"] - r["y_base"] - r["delta"]) < 1e-9
    for ref in ["ref_base", "ref_final"]:
        assert abs(r[f"explicado_{ref}"] + r[f"nao_explicado_{ref}"] - r["delta"]) < 1e-6, ref
    d = _t("fase6_oaxaca_detalhe")
    assert abs(d["ref_base_2010"].sum() - r["explicado_ref_base"]) < 1e-6
    assert abs(d["ref_final_2026"].sum() - r["explicado_ref_final"]) < 1e-6


def test_oaxaca_ic():
    r = _t("fase6_oaxaca_resumo")
    assert ((r["ic_inf"] <= r["estimativa"]) & (r["estimativa"] <= r["ic_sup"])).all()


def test_logits_preenchidos():
    g = _t("fase6_logit_grupos_swing_ame")
    from src.models import X_A

    assert set(g["resultado"]) == {"G_EST", "G_PT", "G_OP"} and len(g) == 3 * 2 * len(X_A)
    # efeitos marginais somam zero entre as categorias
    assert (g.groupby("termo")["ame"].sum().abs() < 1e-6).all()
    p = _t("fase6_logit_proporcional_ame")
    assert set(p["eleicao"]) == set(config()["anos_eleicao"])
    assert (p.groupby(["eleicao", "termo"])["ame"].sum().abs() < 1e-6).all()


def test_diferencas_longas_r2():
    r = _t("fase6_diferencas_longas_r2").iloc[0]
    assert r["so_EF_UF"] <= r["EF_UF+niveis"] <= r["completo"] + 1e-9
    assert r["so_EF_UF"] <= r["EF_UF+mudancas"] <= r["completo"] + 1e-9
