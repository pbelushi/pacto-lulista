"""Checks da Fase 1 — votação do 2º turno presidencial (PLANO.md, seção 5)."""

import json

import pandas as pd
import pytest

from src.ingest.tse_portal import pasta as pasta_portal
from src.utils import caminho, config

# Resultado oficial do 2º turno (TSE, votos nominais totais, incluindo exterior e trânsito).
# 2006–2022: divulgação oficial do TSE; 2026: total Brasil do Portal Resultados (br.json).
OFICIAL = {
    2006: (58_295_042, 37_543_178),
    2010: (55_752_529, 43_711_388),
    2014: (54_501_118, 51_041_155),
    2018: (47_040_906, 57_797_847),
    2022: (60_345_999, 58_206_354),
}


def _oficial(ano):
    if ano in OFICIAL:
        return OFICIAL[ano]
    d = json.loads((pasta_portal() / "br.json").read_text(encoding="utf-8"))
    pres = config()["presidencial"][ano]
    cand = {int(c["n"]): int(c["vap"]) for a in d["carg"][0]["agr"] for p in a["par"] for c in p["cand"]}
    return cand[pres["pt"]], cand[pres["op"]]


@pytest.fixture(scope="module")
def amc():
    return pd.read_parquet(caminho("interim") / "tse_presidencial.parquet")


@pytest.fixture(scope="module")
def mun():
    return pd.read_parquet(caminho("interim") / "tse_presidencial_municipio.parquet")


ANOS = config()["anos_eleicao"]


def test_todos_os_anos(amc):
    assert sorted(amc["ano"].unique()) == ANOS


@pytest.fixture(scope="module")
def totais():
    return pd.read_parquet(caminho("interim") / "tse_presidencial_totais_br.parquet").set_index("ano")


@pytest.mark.parametrize("ano", ANOS)
def test_share_nacional_bate_com_tse(totais, ano):
    """Totais com exterior e trânsito: s_PT dentro de 0,01 p.p. do oficial (PLANO.md, Fase 1)."""
    pt, op = _oficial(ano)
    t = totais.loc[ano]
    s_ofic = 100 * pt / (pt + op)
    s_dados = 100 * t["votos_pt"] / (t["votos_pt"] + t["votos_op"])
    assert abs(s_ofic - s_dados) < config()["checks"]["tolerancia_pp"], (s_ofic, s_dados)


@pytest.mark.parametrize("ano", ANOS)
def test_exclusao_exterior_transito_pequena(amc, ano):
    """Sem exterior e trânsito, o s_PT nacional muda menos de 0,5 p.p."""
    pt, op = _oficial(ano)
    g = amc[amc["ano"] == ano]
    s_ofic = 100 * pt / (pt + op)
    s_dados = 100 * g["votos_pt"].sum() / g["validos"].sum()
    assert abs(s_ofic - s_dados) < 0.5, (s_ofic, s_dados)


@pytest.mark.parametrize("ano", ANOS)
def test_votos_nacionais_cobertura(amc, ano):
    """Votos nos municípios ≤ oficial e cobrem ≥ 98% dele (o resto é exterior + trânsito)."""
    pt, op = _oficial(ano)
    g = amc[amc["ano"] == ano]
    for dados, ofic in [(g["votos_pt"].sum(), pt), (g["votos_op"].sum(), op)]:
        assert dados <= ofic
        assert dados / ofic > 0.98


@pytest.mark.parametrize("ano", ANOS)
def test_validos_batem_com_detalhe(amc, ano):
    """PT + opositor = total de válidos do arquivo de detalhe, município a município."""
    g = amc[amc["ano"] == ano]
    assert (g["validos"] == g["validos_tse"]).all()


@pytest.mark.parametrize("ano", ANOS)
def test_n_municipios(mun, amc, ano):
    n_amc_esperado = 5571 - len(config()["amc"])
    assert amc[amc["ano"] == ano]["id_amc"].nunique() == n_amc_esperado
    n_mun = mun[mun["ano"] == ano]["id_municipio"].nunique()
    assert 5564 <= n_mun <= 5571


def test_sem_duplicatas(amc, mun):
    assert not amc.duplicated(["ano", "id_amc"]).any()
    assert not mun.duplicated(["ano", "id_municipio"]).any()


def test_identidades_contabeis(amc):
    assert (amc["comparecimento"] == amc["validos"] + amc["brancos"] + amc["nulos"]).all()
    assert (amc["comparecimento"] + amc["abstencoes"] <= amc["aptos"]).all()
    assert amc["s_pt"].between(0, 100).all()
    assert amc[["s_pt", "e_pt", "e_op", "tx_abstencao", "tx_brancos_nulos"]].notna().all().all()
