"""Checks da Fase A do plano3: painel país-ano de polarização e rupturas."""

import json

import pandas as pd
import pytest

from src.utils import caminho


@pytest.fixture(scope="module")
def p():
    f = caminho("interim") / "p3_painel.parquet"
    if not f.exists():
        pytest.skip("Fase A do plano3 não rodada")
    return pd.read_parquet(f)


def test_versoes_registradas():
    v = json.loads((caminho("raw") / "p3" / "versoes.json").read_text(encoding="utf-8"))
    assert v["vdemdata"]["versao_pacote"].startswith("16") and v["ERT"]["versao_pacote"].startswith("16")


def test_sem_duplicatas_e_cobertura(p):
    assert not p.duplicated(["country_id", "year"]).any()
    assert p["year"].min() == 1900 and p["year"].max() >= 2025
    assert p["v2cacamps"].notna().mean() > 0.95
    assert p.loc[p["year"] >= 2000, "v2smpolsoc"].notna().mean() > 0.95
    assert p.loc[p["year"] < 2000, "v2smpolsoc"].isna().all()


def test_escala_v2cacamps(p):
    assert p["v2cacamps_ord"].dropna().isin([0, 1, 2, 3, 4]).all()
    # maior = mais polarizado: a categoria ordinal cresce com o valor latente
    assert p[["v2cacamps", "v2cacamps_osp"]].corr().iat[0, 1] > 0.9


def test_casos_de_referencia(p):
    r = pd.read_csv(caminho("tables") / "p3_faseA_referencia.csv")
    cobertos = r[r["caso"] != "França 1789–1799"]
    assert (cobertos["anos_no_vdem"] > 0).all() and (cobertos["ord_max"] == 4).all()
    # eventos conhecidos presentes nas bases
    g = p.set_index(["country_text_id", "year"])["golpe"]
    assert g[("CHL", 1973)] >= 1 and g[("BRA", 1964)] >= 1 and g[("ITA", 1922)] >= 1
    assert p.set_index(["country_text_id", "year"]).loc[("ESP", 1936), "guerra_civil"] == 1
