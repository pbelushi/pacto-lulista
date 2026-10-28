"""Checks da Fase 3 — ingestão dos indicadores (docs/planos/PLANO.md, seções 3 e 5).

Cada fonte é testada só se o arquivo intermediário existir (fontes pendentes ficam em
outputs/pendencias.md); a ausência das fontes já implementadas é falha.
"""

import pandas as pd
import pytest

from src.utils import caminho

PRONTAS = ["ibge_pop", "ibge_censo", "ipca", "ibge_pib", "inep_ideb"]
# fontes com script pronto mas download bloqueado/indisponível (outputs/pendencias.md): testadas se existirem
PENDENTES = ["datasus"]


def _ler(nome):
    p = caminho("interim") / f"{nome}.parquet"
    if not p.exists():
        if nome in PENDENTES:
            pytest.skip(f"{nome}: fonte pendente (outputs/pendencias.md)")
        pytest.fail(f"{nome}.parquet ausente")
    return pd.read_parquet(p)


@pytest.mark.parametrize("nome", [n for n in PRONTAS if n != "ipca"])
def test_chave_unica(nome):
    df = _ler(nome)
    assert not df.duplicated(["id_municipio", "ano"]).any()
    assert df["id_municipio"].between(1_100_000, 5_399_999).all()


def test_pop_censos_batem_com_ibge():
    """Totais nacionais dos Censos (IBGE): 2000 = 169.799.170; 2010 = 190.755.799; 2022 = 203.080.756."""
    p = _ler("ibge_pop").groupby("ano")["pop"].sum()
    for ano, ref in {2000: 169_799_170, 2010: 190_755_799, 2022: 203_080_756}.items():
        assert abs(p[ano] / ref - 1) < 1e-4, (ano, p[ano])


def test_pop_serie_sem_saltos():
    p = _ler("ibge_pop").groupby("ano")["pop"].sum()
    cresc = p.loc[2001:2026].pct_change().dropna()
    assert cresc.between(-0.005, 0.02).all(), cresc[~cresc.between(-0.005, 0.02)]


def test_pop_cobertura():
    p = _ler("ibge_pop")
    for ano in [2006, 2010, 2014, 2018, 2022, 2026]:
        assert p.loc[p["ano"] == ano, "pop"].notna().sum() >= 5560


def test_censo_percentuais():
    c = _ler("ibge_censo")
    pct = [x for x in c.columns if x.startswith("pct_")]
    v = c[pct].stack().dropna()
    assert v.between(-1e-6, 100 + 1e-6).all()
    assert c.loc[c["ano"] == 2022, "pct_evangelica"].median() > c.loc[c["ano"] == 2010, "pct_evangelica"].median()
    soma_raca = c[["pct_branca", "pct_preta", "pct_parda", "pct_amarela", "pct_indigena"]].sum(axis=1, min_count=5).dropna()
    # resto = "sem declaração"; chega a ~4% em poucos municípios do Norte em 2022
    assert (soma_raca <= 100 + 1e-6).all() and (soma_raca > 95).all(), soma_raca.min()


def test_censo_trabalho():
    """Desocupação e informalidade (amostra): cobertura completa, faixas plausíveis, informalidade estável
    entre os Censos (nacional SIDRA: desocupação 14+ = 7,6% em 2010 e 5,7% em 2022)."""
    c = _ler("ibge_censo")
    t = c.dropna(subset=["pct_informal"])
    assert (t.groupby("ano")["id_municipio"].nunique() >= 5565).all()
    assert t[["taxa_desocupacao", "pct_informal", "pct_conta_propria"]].notna().all().all()
    assert (t["pct_conta_propria"] <= t["pct_informal"] + 1e-9).all()
    med = t.groupby("ano")["taxa_desocupacao"].median()
    assert med.between(2, 12).all(), med
    w = t.pivot(index="id_municipio", columns="ano", values="pct_informal").dropna()
    assert w[2010].corr(w[2022]) > 0.8


def test_ipca():
    i = _ler("ipca").set_index("ano")
    assert abs(i.loc[2025, "fator_dez"] - 1) < 1e-9
    assert (i["fator_anual"].diff().dropna() < 0).all()  # inflação positiva em todos os anos


def test_pib_nacional():
    """Soma municipal ≈ PIB Brasil divulgado pelo IBGE (2010: R$ 3,886 tri; 2021: R$ 9,012 tri)."""
    p = _ler("ibge_pib").groupby("ano")["pib"].sum() / 1e12
    assert abs(p[2010] / 3.886 - 1) < 0.01, p[2010]
    assert abs(p[2021] / 9.012 - 1) < 0.01, p[2021]


def test_pib_ftp_igual_sidra():
    """Base do FTP (fonte usada) = tabela SIDRA 5938 v37 (PIB), município a município, 2002–2023."""
    import json

    pasta = caminho("raw") / "sidra" / "5938"
    if not any(pasta.glob("v37_*.json")):
        pytest.skip("cache SIDRA 5938 ausente")
    linhas = []
    for f in pasta.glob("v37_*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        linhas += [(int(r["D1C"]), int(r["D3C"]), float(r["V"])) for r in d[1:] if r["V"].replace(".", "").isdigit()]
    s = pd.DataFrame(linhas, columns=["id_municipio", "ano", "pib_sidra"])
    m = _ler("ibge_pib").merge(s, on=["id_municipio", "ano"])
    assert len(m) > 120_000
    assert ((m["pib"] / 1000 - m["pib_sidra"]).abs() < 1.5).all()


def test_pib_participacoes():
    p = _ler("ibge_pib")
    # VAB setorial não divulgado para 2022–2023 (outputs/pendencias.md)
    assert p.loc[p["ano"] >= 2022, "part_vab_agro"].isna().all()
    p = p[p["ano"] <= 2021]
    soma = p[["part_vab_agro", "part_vab_industria", "part_vab_servicos", "part_vab_adm_publica"]].sum(axis=1)
    assert ((soma - 100).abs() < 0.01).all()
    # PIB negativo existe nos dados do IBGE (ex.: Guamaré/RN 2012, VAB industrial negativo); tolera-se raros casos
    assert (p["pib_pc_real"].dropna() <= 0).sum() <= 5


def test_ideb():
    i = _ler("inep_ideb")
    assert i["ideb_ai_publica"].dropna().between(0, 10).all()
    assert set(i["ano"]) == set(range(2005, 2026, 2))


def test_datasus():
    d = _ler("datasus")
    nac = d.groupby("ano")[["obitos_infantis", "nascidos_vivos"]].sum()
    tmi = 1000 * nac["obitos_infantis"] / nac["nascidos_vivos"]
    # TMI Brasil (SIM/SINASC, sem correção de sub-registro) entre ~11 e ~16 por mil no período
    assert tmi.loc[2005:2023].between(10, 17).all(), tmi
    assert (d["tmi_trienal_eb"].dropna() >= 0).all()
    # EB reduz a dispersão em relação à taxa bruta
    g = d[d["ano"] == 2022]
    assert g["tmi_trienal_eb"].std() < g["tmi_trienal"].std()
