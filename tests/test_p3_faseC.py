"""Checks da Fase C do plano3: pré-codificação dos desfechos."""

import pandas as pd
import pytest

from src.utils import caminho


@pytest.fixture(scope="module")
def c():
    f = caminho("tables") / "p3_codificacao.csv"
    if not f.exists():
        pytest.skip("Fase C do plano3 não rodada")
    return pd.read_csv(f, keep_default_na=False)


def test_um_codigo_por_episodio(c):
    e = pd.read_csv(caminho("tables") / "p3_episodios.csv")
    assert len(c) == len(e) and c["id"].is_unique
    assert c["codigo_proposto"].isin(["R1", "R2", "P", "D", "C"]).all()


def test_regras_de_revisao(c):
    # o plano exige revisão manual de toda ruptura e todo pacto
    assert (c.loc[c["codigo_proposto"].isin(["R1", "R2", "P"]), "revisar"] == "sim").all()
    assert (c.loc[c["codigo_proposto"].isin(["C", "D"]), "revisar"] == "não").all()
    assert c["codigo"].isin(["R1", "R2", "P", "D", "C"]).all()
    assert (c.loc[c["termino"] == "em curso", "codigo_proposto"] == "C").all()


def test_evidencia_sem_lacuna_silenciosa(c):
    r = c[c["revisar"] == "sim"]
    assert (r["evidencia"].str.len() > 0).all() and (r["quem_assumiu"].str.len() > 0).all()
    assert c["codigo_final"].isin(["", "R1", "R2", "P", "D", "C"]).all()
    assert (c["codigo"] == c["codigo_final"].where(c["codigo_final"] != "", c["codigo_proposto"])).all()


def test_casos_brasil(c):
    b = c.set_index("id")
    assert b.loc["BRA-1960", "codigo_proposto"] in ("R1", "R2") and "Castelo Branco" in b.loc["BRA-1960", "evidencia"]
    assert b.loc["BRA-2016", "codigo_proposto"] == "C"


def test_relatorio_de_revisao():
    t = (caminho("report") / "p3_casos_para_revisao.md").read_text(encoding="utf-8")
    assert "## Brasil" in t and "## Casos de referência do plano" in t and "codigo_final" in t
