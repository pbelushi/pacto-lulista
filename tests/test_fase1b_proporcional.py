"""Checks da Fase 1B — voto proporcional para deputado federal (docs/planos/PLANO.md, seção 1A)."""

import json

import pandas as pd
import pytest

from src.ingest.tse_portal import pasta as pasta_portal
from src.utils import caminho, config

ANOS = config()["anos_eleicao"]
N_AMC = 5571 - len(config()["amc"])

# Divergências conhecidas entre arquivo de detalhe (válidos) e arquivo de partido (outputs/pendencias.md)
DIF_CONHECIDA = {2006: 154_179, 2018: -7_048}


@pytest.fixture(scope="module")
def prop():
    return pd.read_parquet(caminho("interim") / "tse_proporcional.parquet")


@pytest.fixture(scope="module")
def part(prop):
    return prop[prop["versao"] == "partido"]


def test_estrutura(prop):
    assert sorted(prop["ano"].unique()) == ANOS
    assert set(prop["versao"]) == {"partido", "federacao"}
    assert not prop.duplicated(["ano", "versao", "id_amc"]).any()
    assert (prop.groupby(["ano", "versao"]).size() == N_AMC).all()


@pytest.mark.parametrize("ano", ANOS)
def test_nominal_mais_legenda_igual_validos(part, ano):
    """Soma de nominais + legenda de todos os partidos = válidos, em cada município."""
    g = part[part["ano"] == ano]
    dif = g["validos"] - g["votos_partidos"]
    assert dif.sum() == DIF_CONHECIDA.get(ano, 0)
    if ano in DIF_CONHECIDA:
        # divergência pequena: ≤ 4% dos válidos em qualquer AMC e ≤ 0,2% no total
        assert (dif.abs() / g["validos"]).max() < 0.04
        assert abs(dif.sum()) / g["validos"].sum() < 0.002
    else:
        assert (dif == 0).all()


@pytest.mark.parametrize("ano", ANOS)
def test_nominais_partido_igual_soma_candidatos(ano):
    chk = pd.read_parquet(caminho("interim") / f"_check_partido_candidato_{ano}.parquet")
    assert (chk["dif_nominal_partido_cand"] == 0).all()


def test_2026_bate_com_portal_por_uf(part):
    """2026: válidos, PT e PL por UF iguais aos do Portal Resultados (fonte independente do CDN)."""
    pres = pd.read_parquet(caminho("interim") / "tse_presidencial.parquet")[["id_amc", "sg_uf"]].drop_duplicates()
    g = part[part["ano"] == 2026].merge(pres, on="id_amc").groupby("sg_uf")[["validos", "votos_PT", "votos_ANTI"]].sum()
    anti = config()["partido_anti"][2026]
    for f in (pasta_portal() / "dep_federal").glob("*.json"):
        j = json.loads(f.read_text(encoding="utf-8"))
        uf = j["cdabr"].upper()
        par = {int(p["n"]): int(p["tvtn"]) + int(p["tval"]) for a in j["carg"][0]["agr"] for p in a["par"]}
        assert g.loc[uf, "validos"] == int(j["v"]["vv"]), uf
        assert g.loc[uf, "votos_PT"] == par[13], uf
        assert g.loc[uf, "votos_ANTI"] == par[anti], uf


# Votação nacional para a Câmara divulgada pelo TSE (% dos válidos, arredondado a 0,1 p.p.).
# Referência aproximada: confere ordem de grandeza e identidade do partido antipetista.
REFERENCIA_PT = {2006: 15.0, 2010: 16.9, 2014: 14.0, 2018: 10.3}


@pytest.mark.parametrize("ano", list(REFERENCIA_PT))
def test_p_pt_nacional_referencia(part, ano):
    g = part[part["ano"] == ano]
    p = 100 * g["votos_PT"].sum() / g["validos"].sum()
    assert abs(p - REFERENCIA_PT[ano]) < 0.15, p


def test_intervalos(prop):
    for c in ["p_PT", "p_ANTI", "leg_PT", "leg_ANTI", "p_lider"]:
        assert prop[c].between(0, 100).all(), c
    assert (prop["leg_PT"] <= prop["p_PT"] + 1e-9).all()
    assert (prop["nep"] >= 1).all()
    assert (prop["rank_PT"] >= 1).all() and (prop["rank_ANTI"] >= 1).all()
    assert ((prop["rank_PT"] == 1) == (prop["margem_PT"] >= 0)).all()
    assert prop[["s_pt", "hiato_lulista", "hiato_anti"]].notna().all().all()
    fr = prop["frac_puxador_PT"].dropna()
    assert fr.between(0, 1).all()


def test_federacao_igual_partido_antes_de_2022(prop):
    cols = ["p_PT", "p_ANTI", "nep", "rank_PT", "rank_ANTI"]
    a = prop[(prop["versao"] == "partido") & (prop["ano"] < 2022)].set_index(["ano", "id_amc"])[cols]
    b = prop[(prop["versao"] == "federacao") & (prop["ano"] < 2022)].set_index(["ano", "id_amc"])[cols]
    pd.testing.assert_frame_equal(a.sort_index(), b.sort_index())


def test_federacao_pt_maior_ou_igual(prop):
    a = prop[prop["versao"] == "partido"].set_index(["ano", "id_amc"])["p_PT"]
    b = prop[prop["versao"] == "federacao"].set_index(["ano", "id_amc"])["p_PT"]
    assert (b.loc[a.index] >= a - 1e-9).all()
