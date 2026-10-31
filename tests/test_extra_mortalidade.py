"""Checks do SIM e do extra de mortalidade e voto."""

import pandas as pd
import pytest

from src.utils import caminho, config


@pytest.fixture(scope="module")
def sim():
    f = caminho("interim") / "sim.parquet"
    if not f.exists():
        pytest.skip("microdados do SIM não ingeridos")
    return pd.read_parquet(f)


def test_validacao_tabnet(sim):
    # consulta ao TabNet registrada em outputs/pendencias.md
    assert sim.loc[sim["ano"] == 2022, "obitos_infantis"].sum() == 32_238


def test_mortalidade_infantil_sem_2015():
    e = pd.read_parquet(caminho("processed") / "painel_eleicoes.parquet")
    if "tmi_trienal" not in e:
        pytest.skip("painel sem SINASC")
    n = e.groupby("eleicao")["tmi_trienal"].count()
    assert n[2018] == 0 and (n.drop(2018) >= 5560).all()
    # janelas com 2015 ficam vazias
    a = pd.read_parquet(caminho("processed") / "painel_amc_anual.parquet")
    assert a.loc[a["ano"].between(2015, 2017), "tmi_trienal"].isna().all()
    assert a.loc[a["ano"] == 2014, "tmi_trienal"].notna().sum() > 5500 and a.loc[a["ano"] == 2018, "tmi_trienal"].notna().sum() > 5500


def test_chave_unica(sim):
    assert not sim.duplicated(["id_municipio", "ano"]).any()


def test_anos_incompletos_fora(sim):
    fim = config()["sim"]["ultimo_ano_completo"]
    assert fim == 2024 and sim.loc[sim["ano"] > fim, "ano_completo"].eq(False).all()
    a = pd.read_parquet(caminho("processed") / "painel_amc_anual.parquet")
    assert a.loc[a["ano"] > fim, "tx_homicidio_trienal"].isna().all()
    assert a.loc[a["ano"] < 2005, "tx_homicidio_trienal"].isna().all()


def test_alinhamento_no_painel():
    e = pd.read_parquet(caminho("processed") / "painel_eleicoes.parquet")
    if "ano_ref_sim" not in e:
        pytest.skip("painel sem SIM")
    ref = e.groupby("eleicao")["ano_ref_sim"].max()
    assert ref.to_dict() == {2006: 2005, 2010: 2009, 2014: 2013, 2018: 2017, 2022: 2021, 2026: 2024}
    assert e["tx_homicidio_trienal"].dropna().ge(0).all()


def test_mes_de_2025_e_2026():
    m = pd.read_parquet(caminho("interim") / "sim_mensal.parquet")
    assert m.loc[m["ano"] == 2025, "mes"].max() == 9 and m.loc[m["ano"] == 2026, "mes"].max() == 8


def test_tabelas():
    f = caminho("tables") / "extra_sim_covid_voto.csv"
    if not f.exists():
        pytest.skip("extra de mortalidade não rodado")
    r = pd.read_csv(f)
    assert len(r) == 45 and r["n"].ge(5500).all() and (r["ic_inf"] <= r["ic_sup"]).all()
    assert set(r["desfecho"]) == {"2018→2022", "2022→2026", "placebo 2014→2018"}
    t = pd.read_csv(caminho("tables") / "extra_sim_homicidio_teste.csv")
    assert len(t) == 3
    assert len(pd.read_csv(caminho("tables") / "extra_sim_tmi_teste.csv")) == 3
    s = pd.read_csv(caminho("tables") / "extra_sim_tmi_simples.csv")
    assert "2018" not in set(s["modelo"].astype(str)) and "2026 − 2010" in set(s["modelo"])
