"""Fase 4 — painéis (PLANO.md, seção 5).

Entradas: data/interim/*.parquet das Fases 1, 1B e 3 e data/processed/grupos_*.parquet da Fase 2.
Fontes incluídas: IBGE (população, Censos, PIB), INEP (Ideb), MDS via Ipeadata (beneficiários do Bolsa
Família), Comex Stat (comércio exterior) e Atlas DH via Ipeadata (IDHM 2010, só como nível inicial).
Fora (ver outputs/pendencias.md): DATASUS, % de cadastrados no CadÚnico, RAIS, IDHM pós-2010.

Saídas:
- data/processed/painel_municipal.parquet: município × ano (2000–2026), indicadores como ingeridos.
- data/processed/painel_amc_anual.parquet: AMC × ano, indicadores agregados em AMC:
    pop, PIB e VABs somados (participações e per capita recalculados);
    percentuais do Censo ponderados pela população do ano do Censo;
    Ideb e IDHM ponderados pela população do ano (aproximação: o ideal seria pela matrícula / pelos
      componentes);
    Bolsa Família somado (benefícios e valor em dezembro), por 100 habitantes e per capita real;
    Comex da tabela já agregada em AMC (src/ingest/comex.py, HHI recalculado), zero para AMC sem
    comércio no ano (2003–2025); per capita real em R$ de dez/2025.
- data/processed/painel_eleicoes.parquet: AMC × eleição, com votação (presidencial e Câmara),
  grupos da Fase 2 e covariáveis alinhadas conforme config.yaml (`alinhamento`):
    anuais → último ano com dado ≤ eleição − 1 (colunas ano_ref_*);
    população → ano da eleição;
    Censo → 2010 para 2006–2014, 2022 para 2022–2026; 2018 sem valor nas colunas principais,
      com *_interp (interpolação linear 2010–2022) só para descritivas.
- outputs/tables/dicionario.csv (e .md): variáveis do painel de eleições.
"""

from __future__ import annotations

import json
import logging

import numpy as np
import pandas as pd

from src.ingest.tse import tse_para_amc
from src.ingest.tse_portal import pasta as pasta_portal
from src.utils import caminho, config

log = logging.getLogger("build_panel")

CENSO = ["pct_branca", "pct_preta", "pct_parda", "pct_amarela", "pct_indigena", "pct_negra",
         "pct_catolica", "pct_evangelica", "pct_pentecostal", "pct_sem_religiao", "pct_outras_religioes",
         "taxa_desocupacao", "pct_informal", "pct_conta_propria"]
SOMAS_PIB = ["pib", "vab", "vab_agro", "vab_industria", "vab_servicos", "vab_adm_publica"]
PIB_DERIV = ["part_vab_agro", "part_vab_industria", "part_vab_servicos", "part_vab_adm_publica",
             "pib_pc_real", "vab_agro_pc_real"]
# grupo de covariável anual → (colunas, coluna que define disponibilidade)
ANUAIS = {
    "pib": (["pib_pc_real"], "pib_pc_real"),
    "vab": (["part_vab_agro", "part_vab_industria", "part_vab_servicos", "part_vab_adm_publica",
             "vab_agro_pc_real"], "part_vab_agro"),
    "ideb": (["ideb_ai_publica"], "ideb_ai_publica"),
    "pbf": (["pbf_100hab", "valor_pbf_pc_real"], "pbf_100hab"),
    "comex": (["export_pc_real", "log_export_commod_pc", "saldo_pc_real", "pct_commodities", "hhi_exp"],
              "export_pc_real"),
}
IDHM = ["idhm", "idhm_e", "idhm_l", "idhm_r"]
COMEX_SOMAS = ["exportacao_real_brl", "exp_commod_real_brl", "importacao_real_brl", "saldo_real_brl"]


def _amc_map() -> pd.Series:
    amc = {int(k): int(v) for k, v in config()["amc"].items()}
    return lambda c: amc.get(c, c)


def painel_municipal() -> pd.DataFrame:
    i = caminho("interim")
    pop = pd.read_parquet(i / "ibge_pop.parquet")
    pib = pd.read_parquet(i / "ibge_pib.parquet")
    cen = pd.read_parquet(i / "ibge_censo.parquet")
    ide = pd.read_parquet(i / "inep_ideb.parquet")
    pbf = pd.read_parquet(i / "mds_pbf.parquet")
    idh = pd.read_parquet(i / "atlas_idhm.parquet")
    cx = pd.read_parquet(i / "comex.parquet")[["id_municipio", "ano", "exportacao_usd", "importacao_usd",
                                                 "pct_commodities", "hhi_exp"] + COMEX_SOMAS]
    df = pop
    for outro in [pib, cen, ide, pbf, idh, cx]:
        df = df.merge(outro, on=["id_municipio", "ano"], how="outer")
    df["id_amc"] = df["id_municipio"].map(_amc_map())
    return df.sort_values(["id_municipio", "ano"]).reset_index(drop=True)


def _media_ponderada(df: pd.DataFrame, cols: list[str], peso: str) -> pd.DataFrame:
    out = {}
    for c in cols:
        ok = df[c].notna() & df[peso].notna()
        num = (df[c] * df[peso]).where(ok).groupby([df["id_amc"], df["ano"]]).sum(min_count=1)
        den = df[peso].where(ok).groupby([df["id_amc"], df["ano"]]).sum(min_count=1)
        out[c] = num / den
    return pd.DataFrame(out)


def painel_amc_anual(mun: pd.DataFrame) -> pd.DataFrame:
    g = mun.groupby(["id_amc", "ano"])
    out = g[["pop"] + SOMAS_PIB].sum(min_count=1)
    out["n_municipios"] = g["id_municipio"].nunique()
    for c in ["agro", "industria", "servicos", "adm_publica"]:
        out[f"part_vab_{c}"] = 100 * out[f"vab_{c}"] / out["vab"]
    ipca = pd.read_parquet(caminho("interim") / "ipca.parquet").set_index("ano")["fator_anual"]
    fator = out.index.get_level_values("ano").map(ipca)
    out["pib_pc_real"] = out["pib"] * fator / out["pop"]
    out["vab_agro_pc_real"] = out["vab_agro"] * fator / out["pop"]
    # Censo: peso = população do ano do Censo; Ideb e IDHM: peso = população do ano
    out = out.join(_media_ponderada(mun, CENSO + ["ideb_ai_publica"] + IDHM, "pop"))
    # Bolsa Família (dezembro de cada ano)
    out = out.join(g[["beneficios_pbf", "valor_pbf_dez"]].sum(min_count=1))
    ipca_dez = pd.read_parquet(caminho("interim") / "ipca.parquet").set_index("ano")["fator_dez"]
    out["pbf_100hab"] = 100 * out["beneficios_pbf"] / out["pop"]
    out["valor_pbf_pc_real"] = out["valor_pbf_dez"] * out.index.get_level_values("ano").map(ipca_dez) / out["pop"]
    # Comex (já em AMC); AMC sem comércio no ano = 0 dentro do período coberto
    cx = pd.read_parquet(caminho("interim") / "comex_amc.parquet").set_index(["id_amc", "ano"])
    out = out.join(cx[COMEX_SOMAS + ["pct_commodities", "hhi_exp"]])
    periodo = out.index.get_level_values("ano").isin(range(cx.index.get_level_values("ano").min(),
                                                           cx.index.get_level_values("ano").max() + 1))
    out.loc[periodo, COMEX_SOMAS] = out.loc[periodo, COMEX_SOMAS].fillna(0)
    out["export_pc_real"] = out["exportacao_real_brl"] / out["pop"]
    out["saldo_pc_real"] = out["saldo_real_brl"] / out["pop"]
    out["log_export_commod_pc"] = np.log1p(out["exp_commod_real_brl"] / out["pop"])
    return out.reset_index()


def _ultimo_ate(amc: pd.DataFrame, cols: list[str], chave: str, limite: int) -> pd.DataFrame:
    """Por AMC, valores do último ano ≤ limite em que `chave` não é nula."""
    sub = amc[(amc["ano"] <= limite) & amc[chave].notna()].sort_values("ano")
    ult = sub.groupby("id_amc").tail(1).set_index("id_amc")
    return ult[cols].assign(ano_ref=ult["ano"])


def covariaveis_eleicao(amc: pd.DataFrame) -> pd.DataFrame:
    cfg = config()
    al = cfg["alinhamento"]
    partes = []
    for t in cfg["anos_eleicao"]:
        base = amc[amc["ano"] == t - al["defasagem_pop"]].set_index("id_amc")[["pop"]]
        for nome, (cols, chave) in ANUAIS.items():
            u = _ultimo_ate(amc, cols, chave, t - al["defasagem_anual"])
            base = base.join(u.rename(columns={"ano_ref": f"ano_ref_{nome}"}))
        ref = al["censo"][t]
        c10 = amc[amc["ano"] == 2010].set_index("id_amc")[CENSO]
        c22 = amc[amc["ano"] == 2022].set_index("id_amc")[CENSO]
        if ref is None:
            principal = pd.DataFrame(np.nan, index=base.index, columns=CENSO)
            w = (t - 2010) / (2022 - 2010)
            interp = (1 - w) * c10 + w * c22  # pentecostal (só 2010) fica NaN
        else:
            principal = amc[amc["ano"] == ref].set_index("id_amc")[CENSO]
            interp = principal
        base = base.join(principal).join(interp.add_suffix("_interp"))
        base["ano_ref_censo"] = ref if ref is not None else np.nan
        partes.append(base.assign(ano=t).reset_index())
    return pd.concat(partes, ignore_index=True)


def capitais() -> set[int]:
    cm = json.loads((pasta_portal() / "mun-cm.json").read_text(encoding="utf-8"))
    return {int(m["cdi"]) for uf in cm["abr"] for m in uf["mu"] if m["c"] == "s"}


def painel_eleicoes(cov: pd.DataFrame) -> pd.DataFrame:
    i, p = caminho("interim"), caminho("processed")
    pres = pd.read_parquet(i / "tse_presidencial.parquet").drop(columns=["fonte", "validos_tse"])
    prop = pd.read_parquet(i / "tse_proporcional.parquet")
    manter = ["validos", "votos_PT", "votos_ANTI", "p_PT", "p_ANTI", "leg_PT", "leg_ANTI", "rank_PT", "rank_ANTI",
              "margem_PT", "margem_ANTI", "nep", "lider", "empate_lider", "frac_puxador_PT", "frac_puxador_ANTI",
              "dependencia_puxador_PT", "dependencia_puxador_ANTI", "hiato_lulista", "hiato_anti"]
    pp = prop[prop["versao"] == "partido"][["ano", "id_amc"] + manter].rename(
        columns={"validos": "validos_camara", "lider": "lider_camara"})
    pf = prop[prop["versao"] == "federacao"][["ano", "id_amc", "p_PT", "p_ANTI", "nep", "hiato_lulista"]]
    pf = pf.rename(columns={c: f"{c}_fed" for c in ["p_PT", "p_ANTI", "nep", "hiato_lulista"]})
    gprop = pd.read_parquet(p / "grupos_proporcionais.parquet")
    gprop = gprop[gprop["versao"] == "partido"][["ano", "id_amc", "g_prop", "g_prop_margem",
                                                  "destaque_p80_PT", "destaque_p80_ANTI"]]
    gpres = pd.read_parquet(p / "grupos_presidenciais.parquet")
    fixos = ["id_amc", "regiao", "swing", "g_swing", "g_swing_dp05", "g_swing_q5", "g_swing_t3", "tipo_2x2",
             "tipo_2x2_rel", "cluster_nivel", "cluster_forma", "cluster_forma_rotulo", "traj_prop"]
    df = (pres.merge(pp, on=["ano", "id_amc"], how="left").merge(pf, on=["ano", "id_amc"], how="left")
          .merge(gprop, on=["ano", "id_amc"], how="left").merge(gpres[fixos], on="id_amc", how="left")
          .merge(cov, on=["ano", "id_amc"], how="left"))
    # IDHM: só 2010, como nível inicial fixo por AMC (decisão do usuário; não há IDHM municipal pós-2010)
    amc = pd.read_parquet(p / "painel_amc_anual.parquet")
    idh = amc[amc["ano"] == 2010].set_index("id_amc")[IDHM].add_suffix("_2010")
    df = df.merge(idh, left_on="id_amc", right_index=True, how="left")
    df["capital"] = df["id_amc"].isin(capitais())
    df = df.rename(columns={"ano": "eleicao"})
    return df.sort_values(["eleicao", "id_amc"]).reset_index(drop=True)


DESCRICOES = {
    "eleicao": ("Ano da eleição", "—", "ano"),
    "id_amc": ("Código IBGE da AMC (município-mãe para os instalados após 2010)", "config.yaml", "código"),
    "sg_uf": ("UF", "TSE", "sigla"), "regiao": ("Grande região", "IBGE (geobr)", "nome"),
    "capital": ("AMC é capital de UF", "TSE (config Portal Resultados)", "booleano"),
    "n_municipios_agregados": ("Nº de municípios TSE somados na AMC", "TSE", "contagem"),
    "votos_pt": ("Votos do candidato do PT no 2º turno presidencial", "TSE", "votos"),
    "votos_op": ("Votos do candidato opositor no 2º turno presidencial", "TSE", "votos"),
    "validos": ("Votos válidos no 2º turno presidencial", "TSE", "votos"),
    "aptos": ("Eleitorado apto", "TSE", "eleitores"),
    "comparecimento": ("Comparecimento", "TSE", "eleitores"), "abstencoes": ("Abstenções", "TSE", "eleitores"),
    "brancos": ("Votos brancos (2º turno presidencial)", "TSE", "votos"),
    "nulos": ("Votos nulos (2º turno presidencial)", "TSE", "votos"),
    "s_pt": ("% do PT nos válidos, 2º turno presidencial", "TSE", "%"),
    "e_pt": ("Votos do PT / eleitorado apto", "TSE", "%"), "e_op": ("Votos do opositor / eleitorado apto", "TSE", "%"),
    "tx_abstencao": ("Abstenção / aptos", "TSE", "%"),
    "tx_brancos_nulos": ("(Brancos + nulos) / comparecimento", "TSE", "%"),
    "validos_camara": ("Votos válidos para deputado federal (nominais + legenda)", "TSE", "votos"),
    "votos_PT": ("Votos do PT para a Câmara (nominais + legenda)", "TSE", "votos"),
    "votos_ANTI": ("Votos do partido antipetista do ano para a Câmara", "TSE", "votos"),
    "p_PT": ("% do PT nos válidos para a Câmara (versão partido)", "TSE", "%"),
    "p_ANTI": ("% do antipetista nos válidos para a Câmara", "TSE", "%"),
    "leg_PT": ("% de voto de legenda do PT nos válidos para a Câmara", "TSE", "%"),
    "leg_ANTI": ("% de voto de legenda do antipetista", "TSE", "%"),
    "rank_PT": ("Posição do PT na Câmara no município", "TSE", "posição"),
    "rank_ANTI": ("Posição do antipetista", "TSE", "posição"),
    "margem_PT": ("p_PT − maior p entre os demais partidos", "TSE", "p.p."),
    "margem_ANTI": ("p_ANTI − maior p entre os demais partidos", "TSE", "p.p."),
    "nep": ("Número efetivo de partidos (Laakso-Taagepera), Câmara", "TSE", "índice"),
    "lider_camara": ("Partido mais votado para a Câmara (P<número>)", "TSE", "código"),
    "empate_lider": ("Empate exato no 1º lugar da Câmara", "TSE", "booleano"),
    "frac_puxador_PT": ("Fração dos votos do PT concentrada no candidato mais votado", "TSE", "fração"),
    "frac_puxador_ANTI": ("Idem, antipetista", "TSE", "fração"),
    "dependencia_puxador_PT": ("frac_puxador_PT ≥ 0,5", "TSE", "booleano"),
    "dependencia_puxador_ANTI": ("frac_puxador_ANTI ≥ 0,5", "TSE", "booleano"),
    "hiato_lulista": ("s_pt − p_PT", "TSE", "p.p."), "hiato_anti": ("(100 − s_pt) − p_ANTI", "TSE", "p.p."),
    "p_PT_fed": ("p_PT na versão federação (PT/PCdoB/PV a partir de 2022)", "TSE", "%"),
    "p_ANTI_fed": ("p_ANTI na versão federação", "TSE", "%"),
    "nep_fed": ("NEP na versão federação", "TSE", "índice"), "hiato_lulista_fed": ("s_pt − p_PT_fed", "TSE", "p.p."),
    "g_prop": ("Grupo proporcional: P_PT / P_ANTI / P_OUTRO (NA = empate)", "Fase 2", "categoria"),
    "g_prop_margem": ("Grupo proporcional com margem ≥ 5 p.p. (P_NENHUM caso contrário)", "Fase 2", "categoria"),
    "destaque_p80_PT": ("p_PT ≥ percentil 80 municipal do ano", "Fase 2", "booleano"),
    "destaque_p80_ANTI": ("p_ANTI ≥ percentil 80 municipal do ano", "Fase 2", "booleano"),
    "swing": ("Swing relativo do PT 2010→2026 (fixo por AMC)", "Fase 2", "p.p."),
    "g_swing": ("G_PT / G_EST / G_OP, ±1 DP (fixo por AMC)", "Fase 2", "categoria"),
    "tipo_2x2": ("Tipologia 2×2 sobre aptos 2010→2026", "Fase 2", "categoria"),
    "tipo_2x2_rel": ("Tipologia 2×2 descontada a variação nacional", "Fase 2", "categoria"),
    "g_swing_dp05": ("Grupos de swing, ±0,5 DP", "Fase 2", "categoria"),
    "g_swing_q5": ("Grupos de swing por quintis", "Fase 2", "categoria"),
    "g_swing_t3": ("Grupos de swing por tercis", "Fase 2", "categoria"),
    "cluster_forma_rotulo": ("Rótulo interpretativo do cluster de forma", "Fase 2 (config.yaml)", "texto"),
    "cluster_forma": ("Cluster de trajetória por forma (k=4)", "Fase 2", "categoria"),
    "cluster_nivel": ("Cluster de trajetória por nível (k=3)", "Fase 2", "categoria"),
    "traj_prop": ("Trajetória proporcional 2006–2026", "Fase 2", "categoria"),
    "pop": ("População no ano da eleição (série coerente na base dos Censos)", "IBGE (Censos + estimativas)", "pessoas"),
    "pib_pc_real": ("PIB per capita, R$ de dez/2025 (IPCA)", "IBGE PIB dos Municípios", "R$"),
    "part_vab_agro": ("% do VAB na agropecuária", "IBGE PIB dos Municípios", "%"),
    "part_vab_industria": ("% do VAB na indústria", "IBGE PIB dos Municípios", "%"),
    "part_vab_servicos": ("% do VAB em serviços exceto adm. pública", "IBGE PIB dos Municípios", "%"),
    "part_vab_adm_publica": ("% do VAB em adm., defesa, educação e saúde públicas", "IBGE PIB dos Municípios", "%"),
    "vab_agro_pc_real": ("VAB agropecuário per capita, R$ de dez/2025", "IBGE PIB dos Municípios", "R$"),
    "ideb_ai_publica": ("Ideb, anos iniciais, rede pública", "INEP", "índice 0–10"),
    "pbf_100hab": ("Benefícios do Bolsa Família (Auxílio Brasil 2021–23) em dezembro por 100 habitantes",
                   "MDS via Ipeadata (FAM_PBF)", "por 100 hab."),
    "valor_pbf_pc_real": ("Valor do Bolsa Família pago em dezembro por habitante, R$ de dez/2025",
                          "MDS via Ipeadata (VAL_PBF)", "R$"),
    "export_pc_real": ("Exportações por habitante, R$ de dez/2025 (câmbio BCB × IPCA)", "Comex Stat (MDIC/SECEX)", "R$"),
    "log_export_commod_pc": ("log(1 + exportações de commodities SH 01–27 por habitante, R$ dez/2025)",
                             "Comex Stat (MDIC/SECEX)", "log R$"),
    "saldo_pc_real": ("Saldo comercial por habitante, R$ de dez/2025", "Comex Stat (MDIC/SECEX)", "R$"),
    "pct_commodities": ("% commodities (SH 01–27) nas exportações; NaN se não exporta", "Comex Stat", "%"),
    "hhi_exp": ("Concentração da pauta exportadora (HHI sobre SH4); NaN se não exporta", "Comex Stat", "0–1"),
    "ano_ref_pbf": ("Ano (dezembro) do Bolsa Família usado", "—", "ano"),
    "ano_ref_comex": ("Ano do Comex usado", "—", "ano"),
    "idhm_2010": ("IDHM 2010 (fixo por AMC; nível inicial)", "Atlas DH (PNUD/Ipea/FJP) via Ipeadata", "0–1"),
    "idhm_e_2010": ("IDHM Educação 2010", "Atlas DH via Ipeadata", "0–1"),
    "idhm_l_2010": ("IDHM Longevidade 2010", "Atlas DH via Ipeadata", "0–1"),
    "idhm_r_2010": ("IDHM Renda 2010", "Atlas DH via Ipeadata", "0–1"),
    "ano_ref_pib": ("Ano do PIB per capita usado", "—", "ano"), "ano_ref_vab": ("Ano do VAB usado", "—", "ano"),
    "ano_ref_ideb": ("Ano do Ideb usado", "—", "ano"), "ano_ref_censo": ("Ano do Censo usado (NaN em 2018)", "—", "ano"),
}
DESC_CENSO = {"pct_branca": "% branca", "pct_preta": "% preta", "pct_parda": "% parda", "pct_amarela": "% amarela",
              "pct_indigena": "% indígena", "pct_negra": "% preta + parda",
              "pct_catolica": "% católica apostólica romana (10 anos ou mais)",
              "pct_evangelica": "% evangélica (10 anos ou mais)",
              "pct_pentecostal": "% evangélica de origem pentecostal (10+; só Censo 2010)",
              "pct_sem_religiao": "% sem religião (10 anos ou mais)",
              "pct_outras_religioes": "% outras religiões e sem declaração (resíduo, 10+)",
              "taxa_desocupacao": "Taxa de desocupação, 14 anos ou mais (amostra do Censo)",
              "pct_informal": "% de ocupados informais: sem carteira + conta própria + não remunerados (2010: 10+; 2022: 14+)",
              "pct_conta_propria": "% de ocupados por conta própria (2010: 10+; 2022: 14+)"}


def dicionario(df: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    for c in df.columns:
        base = c.removesuffix("_interp")
        if base in DESC_CENSO:
            desc = DESC_CENSO[base] + (" — interpolação linear 2010–2022, só para descritivas" if c.endswith("_interp") else "")
            d = (desc, "IBGE Censos 2010/2022 (SIDRA 9605, 2103, 9537; trabalho: 1572, 1577, 6580, 10261)", "%")
        else:
            d = DESCRICOES.get(c, ("(ver código-fonte)", "—", "—"))
        linhas.append({"variavel": c, "descricao": d[0], "fonte": d[1], "unidade": d[2],
                       "pct_missing": round(100 * df[c].isna().mean(), 1)})
    return pd.DataFrame(linhas)


def main() -> None:
    mun = painel_municipal()
    mun.to_parquet(caminho("processed") / "painel_municipal.parquet", index=False)
    amc = painel_amc_anual(mun)
    amc.to_parquet(caminho("processed") / "painel_amc_anual.parquet", index=False)
    cov = covariaveis_eleicao(amc)
    ele = painel_eleicoes(cov)
    ele.to_parquet(caminho("processed") / "painel_eleicoes.parquet", index=False)
    dic = dicionario(ele)
    dic.to_csv(caminho("tables") / "dicionario.csv", index=False, encoding="utf-8")
    (caminho("tables") / "dicionario.md").write_text(dic.to_markdown(index=False), encoding="utf-8")
    log.info("painel_municipal: %d linhas; painel_amc_anual: %d; painel_eleicoes: %d (%d AMCs × %d eleições)",
             len(mun), len(amc), len(ele), ele["id_amc"].nunique(), ele["eleicao"].nunique())
    refs = ele.groupby("eleicao")[["ano_ref_pib", "ano_ref_vab", "ano_ref_ideb", "ano_ref_censo"]].agg(
        lambda s: s.mode().iloc[0] if s.notna().any() else np.nan)
    log.info("anos de referência (moda):\n%s", refs.to_string())


if __name__ == "__main__":
    main()
