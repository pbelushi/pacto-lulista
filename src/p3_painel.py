"""Fase A do plano3: painel país-ano 1900–2025 (V-Dem v16 + ERT v16 + UCDP/PRIO 25.1 + Archigos 4.1).

Variáveis do V-Dem (nome, cobertura e escala conferidos no codebook v16, data/raw/p3/vdem_codebook.RData):
- v2cacamps "Political polarization", 1900–2025. Pergunta: "Is society polarized into antagonistic, political
  camps?" Ordinal 0–4 convertida em intervalo pelo modelo de medida (maior = mais polarizado). _ord: categoria
  ordinal mais provável (0–4); _osp: escala linearizada 0–4. 3 = "supporters of opposing camps are more likely
  to interact in a hostile than friendly manner"; 4 = "generally interact in a hostile manner".
- v2smpolsoc "Polarization of society", 2000–2025 (robustez). Na escala original, valores baixos = mais
  polarizado (conferir sinal na Fase B antes de usar).
- v2x_regime (RoW: 0 autocracia fechada, 1 autocracia eleitoral, 2 democracia eleitoral, 3 democracia liberal),
  1900–2025; v2x_polyarchy, v2x_libdem, v2x_jucon, v2xlg_legcon, v2xps_party: índices 0–1, 1789–2025.
- v2x_ex_military "Military dimension index" (0–1, 1789–2025): quanto a nomeação e a destituição do chefe do
  Executivo dependem de força militar. Escolhida como "papel dos militares".
- presidencialismo (derivado): chefe de Estado eleito diretamente (v2ex_elechos = 1) e acumulando a chefia de
  governo (v2exhoshog = 1).
- e_gdppc (PIB per capita, modelo latente, 1789–2019) e e_pop; crescimento = variação % anual de e_gdppc.
  Sem dado de 2020 em diante (registrado em pendencias.md).
- Golpes: e_pt_coup / e_pt_coup_attempts (Powell e Thyne, 1950–2025) e e_coups (golpes bem-sucedidos,
  1789–2008, definição de remoção irregular com força armada). golpe = e_pt_coup a partir de 1950, e_coups antes.
- Guerra civil: e_civil_war (≥ 1.000 mortes em combate, 1816–2006); e_miinterc (conflito armado interno, Brecke,
  1789–2000); UCDP/PRIO (conflitos internos, tipos 3 e 4, 1946–2024; intensidade 2 = guerra, ≥ 1.000 mortes/ano).
- v2svindep "Independent states" (0/1, Gleditsch e Ward): exclui colônias e territórios dependentes.
- Evidência para a Fase C: v2exnamhos/v2exnamhog (nomes do chefe de Estado e de governo, texto, 1789–2025);
  v2expathhs/v2expathhg (como chegou ao cargo: 0 força, 1 potência estrangeira, 2 partido único, 3 conselho real,
  4 hereditário, 5 nomeado pelos militares, 6 legislativo [HOG: 6 = pelo chefe de Estado, 7 = legislativo],
  7 eleição direta [HOG: 8], 8 outro [HOG: 9]); v2exparhos (partido do chefe de Estado, 1900–2025);
  v2caviol "Political violence" (violência política de atores não estatais; ordinal 0 "not at all" a 4 "often",
  1900–2025; _ord = categoria).
ERT v16: um registro por país-ano com episódios de democratização (dem_ep) e autocratização (aut_ep) e desfechos.
Archigos 4.1 (1875–2015): entradas e saídas irregulares do chefe do Executivo, por ano de início/fim.

Saídas: data/interim/p3_painel.parquet; outputs/tables/p3_faseA_{cobertura,referencia}.

Uso: python -m src.p3_painel
"""

from __future__ import annotations

import logging
import zipfile

import numpy as np
import pandas as pd
import pyreadr

from src.utils import caminho

log = logging.getLogger("p3_painel")
ANO0 = 1900
VDEM = ["country_name", "country_text_id", "country_id", "COWcode", "year", "e_regionpol_6C", "v2svindep",
        "v2cacamps", "v2cacamps_codelow", "v2cacamps_codehigh", "v2cacamps_ord", "v2cacamps_osp",
        "v2smpolsoc", "v2smpolsoc_ord", "v2x_regime", "v2x_polyarchy", "v2x_libdem", "v2x_jucon",
        "v2xlg_legcon", "v2xps_party", "v2x_ex_military", "v2ex_elechos", "v2exhoshog", "e_gdppc", "e_pop",
        "e_pt_coup", "e_pt_coup_attempts", "e_coups", "e_civil_war", "e_miinterc", "e_miinteco",
        "v2exnamhos", "v2exnamhog", "v2expathhs", "v2expathhg", "v2exparhos", "v2caviol", "v2caviol_ord"]
ERT = ["country_id", "year", "reg_trans", "row_regch_event", "dem_ep", "dem_ep_id", "dem_ep_start_year",
       "dem_ep_end_year", "dem_ep_outcome", "dem_ep_outcome_agg", "aut_ep", "aut_ep_id", "aut_ep_start_year",
       "aut_ep_end_year", "aut_ep_outcome", "aut_ep_outcome_agg"]
REGIAO = {1: "Europa Oriental e Ásia Central", 2: "América Latina e Caribe", 3: "Oriente Médio e Norte da África",
          4: "África Subsaariana", 5: "Europa Ocidental e América do Norte", 6: "Ásia e Pacífico"}
# Gleditsch-Ward → Correlates of War, onde diferem (só os casos que aparecem no UCDP)
GW_COW = {340: 345, 678: 679}

# casos de referência do plano3 (anos esperados do episódio)
REFERENCIA = [("Rússia 1917", "RUS", 1917, 1917), ("França 1789–1799", "FRA", 1789, 1799),
              ("Itália 1919–1922", "ITA", 1919, 1922), ("Alemanha 1919–1933", "DEU", 1919, 1933),
              ("Espanha 1931–1936", "ESP", 1931, 1936), ("Chile 1970–1973", "CHL", 1970, 1973),
              ("Argentina 1945–1976", "ARG", 1945, 1976), ("Colômbia 1946–1958", "COL", 1946, 1958),
              ("Brasil 1954–1964", "BRA", 1954, 1964), ("Venezuela pós-1999", "VEN", 1999, 2025),
              ("EUA pós-1990", "USA", 1990, 2025), ("Brasil pós-2014", "BRA", 2014, 2025)]


def raw():
    return caminho("raw") / "p3"


def vdem() -> pd.DataFrame:
    v = pyreadr.read_r(raw() / "vdem.RData")["vdem"][VDEM]
    v = v[v["year"] >= ANO0].copy()
    for c in ["year", "country_id", "COWcode"]:
        v[c] = v[c].astype("Int64")
    v = v.sort_values(["country_id", "year"])
    v["crescimento_pib"] = 100 * v.groupby("country_id")["e_gdppc"].pct_change(fill_method=None)
    v["presidencialismo"] = ((v["v2ex_elechos"] == 1) & (v["v2exhoshog"] == 1)).astype(float)
    v.loc[v["v2ex_elechos"].isna() | v["v2exhoshog"].isna(), "presidencialismo"] = np.nan
    v["golpe"] = np.where(v["year"] >= 1950, v["e_pt_coup"], v["e_coups"])
    v["regiao"] = v["e_regionpol_6C"].map(REGIAO)
    return v


def ert() -> pd.DataFrame:
    e = pyreadr.read_r(raw() / "ert_episodes.rda")["episodes"][ERT].copy()
    for c in ["country_id", "year"]:
        e[c] = e[c].astype("Int64")
    return e


def ucdp() -> pd.DataFrame:
    """País-ano com conflito armado interno (tipos 3 e 4) e com guerra interna (intensidade 2)."""
    z = zipfile.ZipFile(raw() / "ucdp_prio_acd_251_csv.zip")
    u = pd.read_csv(z.open(z.namelist()[0]))
    u = u[u["type_of_conflict"].isin([3, 4])].copy()
    u["gw"] = u["gwno_a"].astype(str).str.split(",")
    u = u.explode("gw")
    u["COWcode"] = u["gw"].str.strip().astype(int).replace(GW_COW)
    g = u.groupby(["COWcode", "year"]).agg(ucdp_conflito_interno=("conflict_id", "nunique"),
                                            ucdp_guerra_interna=("intensity_level", lambda s: int((s == 2).any())))
    g["ucdp_conflito_interno"] = 1
    return g.reset_index().astype({"COWcode": "Int64", "year": "Int64"})


def archigos() -> pd.DataFrame:
    a = pd.read_stata(raw() / "Archigos_4.1_stata14.dta")
    a["ano_entrada"] = pd.to_datetime(a["startdate"], errors="coerce").dt.year
    a["ano_saida"] = pd.to_datetime(a["enddate"], errors="coerce").dt.year
    ent = a[a["entry"].isin(["Irregular", "Foreign Imposition"])].groupby(["ccode", "ano_entrada"]).agg(
        arch_entrada_irregular=("leader", "size"), arch_lider_irregular=("leader", lambda s: "; ".join(s)))
    sai = a[a["exit"].isin(["Irregular", "Foreign"])].groupby(["ccode", "ano_saida"]).size().rename("arch_saida_irregular")
    ent.index.names = sai.index.names = ["COWcode", "year"]
    out = ent.join(sai, how="outer").reset_index()
    return out.astype({"COWcode": "Int64", "year": "Int64"})


def painel() -> pd.DataFrame:
    v = vdem()
    p = v.merge(ert(), on=["country_id", "year"], how="left")
    p = p.merge(ucdp(), on=["COWcode", "year"], how="left")
    p = p.merge(archigos(), on=["COWcode", "year"], how="left")
    cobertos = p["year"].between(1946, 2024)
    for c in ["ucdp_conflito_interno", "ucdp_guerra_interna"]:
        p.loc[cobertos & p["COWcode"].notna(), c] = p.loc[cobertos & p["COWcode"].notna(), c].fillna(0)
    arch = p["year"].between(1875, 2015) & p["COWcode"].notna()
    for c in ["arch_entrada_irregular", "arch_saida_irregular"]:
        p.loc[arch, c] = p.loc[arch, c].fillna(0)
    # guerra civil combinada: e_civil_war até 2006; UCDP guerra interna depois
    p["guerra_civil"] = np.where(p["year"] <= 2006, p["e_civil_war"], p["ucdp_guerra_interna"])
    return p


def checks(p: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    p = p.assign(decada=(p["year"] // 10 * 10).astype(int))
    vars_ = ["v2cacamps", "v2smpolsoc", "v2x_regime", "v2x_polyarchy", "v2x_jucon", "v2xlg_legcon", "v2xps_party",
             "v2x_ex_military", "presidencialismo", "crescimento_pib", "golpe", "guerra_civil", "reg_trans",
             "arch_entrada_irregular"]
    cob = p.groupby("decada").agg(paises=("country_id", "nunique"), pais_anos=("year", "size"),
                                  **{v: (v, lambda s: round(100 * s.notna().mean(), 1)) for v in vars_}).reset_index()
    ref = []
    for nome, iso, a0, a1 in REFERENCIA:
        s = p[(p["country_text_id"] == iso) & p["year"].between(a0, a1)]
        ref.append({"caso": nome, "pais": iso, "anos_esperados": f"{a0}–{a1}", "anos_no_vdem": len(s),
                    "primeiro_ano_vdem": int(p.loc[p["country_text_id"] == iso, "year"].min()),
                    "v2cacamps_media": s["v2cacamps"].mean(), "v2cacamps_max": s["v2cacamps"].max(),
                    "ord_max": s["v2cacamps_ord"].max(),
                    "anos_ord_4": int((s["v2cacamps_ord"] == 4).sum()), "golpes": s["golpe"].sum(),
                    "anos_guerra_civil": s["guerra_civil"].sum()})
    return cob, pd.DataFrame(ref)


def _salvar(df: pd.DataFrame, nome: str) -> None:
    df.to_csv(caminho("tables") / f"{nome}.csv", index=False, encoding="utf-8")
    (caminho("tables") / f"{nome}.md").write_text(df.to_markdown(index=False, floatfmt=".3g"), encoding="utf-8")


def main() -> None:
    p = painel()
    dup = int(p.duplicated(["country_id", "year"]).sum())
    log.info("painel: %d país-anos, %d países, %d–%d; duplicatas: %d", len(p), p["country_id"].nunique(),
             p["year"].min(), p["year"].max(), dup)
    p.to_parquet(caminho("interim") / "p3_painel.parquet", index=False)
    cob, ref = checks(p)
    _salvar(cob, "p3_faseA_cobertura")
    _salvar(ref, "p3_faseA_referencia")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    main()
