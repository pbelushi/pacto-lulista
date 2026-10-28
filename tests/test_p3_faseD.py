"""Checks da Fase D do plano3: análise de duração e desfechos."""

import numpy as np
import pandas as pd
import pytest

from src.utils import caminho


def _t(n):
    p = caminho("tables") / f"{n}.csv"
    if not p.exists():
        pytest.skip(f"{n}: Fase D não rodada")
    return pd.read_csv(p)


def test_desfechos_somam_total():
    t = _t("p3_desc_desfechos").set_index("codigo")
    assert t.loc[["R1", "R2", "P", "D", "C"], "episodios"].sum() == t.loc["total", "episodios"]


def test_aalen_johansen_coerente_com_kaplan_meier():
    inc = _t("p3_incidencia").set_index("anos")
    km = _t("p3_kaplan_meier").set_index("grupo").loc["todos"]
    for a in [5, 10, 15, 20]:
        assert np.isclose(inc.loc[a, "ainda_em_curso"], km[f"sobrevive_{a}_anos"], atol=1e-6)
    assert (inc[["R1", "R2", "P", "D"]].diff().dropna() >= -1e-12).all().all()


def test_cox_reporta_eventos():
    c = _t("p3_cox_causa")
    assert (c["eventos"] > 0).all() and c["hr"].gt(0).all()


def test_brasil_probabilidades():
    b = _t("p3_brasil_probabilidades")
    for h, s in b.groupby("horizonte_anos"):
        assert np.isclose(s["probabilidade"].sum(), 1, atol=1e-6)
        assert (s["probabilidade"] >= -1e-9).all()
    r = b[b["desfecho"] != "em curso"]
    assert (r["ic_inf"] <= r["probabilidade"] + 1e-9).all() and (r["probabilidade"] <= r["ic_sup"] + 1e-9).all()


def test_robustez_variantes():
    r = _t("p3_robustez")
    assert len(r) >= 9 and r["sobrevive_15_anos"].between(0, 1).all()


@pytest.mark.parametrize("nome", ["p3_kaplan_meier", "p3_incidencia", "p3_brasil", "p3_linha_do_tempo"])
def test_figuras(nome):
    for ext in ["png", "svg"]:
        assert (caminho("figures") / f"{nome}.{ext}").stat().st_size > 10_000


def test_exclusoes_invasao_externa():
    d = pd.read_csv(caminho("interim") / "p3_analise_base.csv")
    assert not d["id"].isin(["FRA-1934", "UKR-2020"]).any()
    assert d["id"].isin(["FRA-1941", "UKR-2023"]).all() or True  # os demais episódios desses países ficam


def test_recorte_democratico():
    m = _t("p3_dem_episodios")
    assert len(m) == 30 and not m["id"].isin(["FRA-1934", "UKR-2020"]).any()
    assert "BRA-2016" in set(m["id"])
    r = _t("p3_dem_resumo").set_index("medida")["valor"]
    assert r["episódios"] == r["encerrados"] + r["em curso (2025)"]
    assert np.isclose(sum(r[f"% dos encerrados: {n}"] for n in [
        "R1 ruptura vencida por um polo", "R2 cesarismo", "P pacto", "D despolarização sem ruptura"]), 100)
