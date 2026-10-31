"""Extra do estudo 1: mortalidade (SIM) e voto. Não altera os modelos principais.

1. Série nacional de óbitos, homicídios e Covid (data/interim/sim.parquet).
2. Homicídios e mortalidade infantil (H1 do PLANO), uma de cada vez: betas de s_pt por eleição (specs. A e B da
   Fase 6) acrescentando a taxa trienal suavizada; compara com os mesmos modelos sem ela e mostra o coeficiente da
   própria taxa. Para a mortalidade infantil, também a associação simples (só EF de UF), porque renda e Bolsa
   Família absorvem boa parte dela nos modelos completos.
3. Covid: os municípios mais atingidos votaram diferente? Excesso de mortalidade por AMC, em três janelas:
   2020–2021; 1ª onda (mar–dez/2020, antes da vacina); e jan/2020–set/2022 (tudo o que antecede a eleição).
   Esperado = taxa de 2015–2019 do mesmo mês × população do ano. Razão O/E com suavização Bayesiana empírica;
   excesso em % = 100 × (razão − 1). Sem padronização por idade. Alternativa: óbitos notificados por Covid por
   100 mil hab., 2020–2021, suavizados.
   Modelo: swing relativo = α_UF + β·medida (z) + controles, WLS (aptos da eleição inicial), EP por microrregião.
   Controles: M0 só EF de UF; M1 + s_pt inicial e swing do período anterior; M2 + covariáveis da spec. B na eleição
   inicial e pct_negra, pct_evangelica e pct_sem_religiao do Censo 2010.
   Desfechos: 2018→2022 (principal), 2022→2026 (persistência) e 2014→2018 (placebo: anterior à pandemia; β ≠ 0
   indica que a medida capta tendência prévia, e não efeito da pandemia).

Associação ecológica, não efeito causal: municípios mais bolsonaristas podem ter tido mais mortes.

Saídas: outputs/tables/extra_sim_{serie,homicidio_betas,homicidio_teste,tmi_betas,tmi_teste,tmi_simples,
excesso_resumo,covid_voto}.

Uso: python -m src.extra_mortalidade
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from src import models as M
from src.build_panel import _amc_map
from src.ingest.datasus import bayes_empirico
from src.utils import caminho, config

log = logging.getLogger("extra_mortalidade")
FONTE = "Fonte: DATASUS, SIM (2025 preliminar e 2026 segunda prévia, fora das taxas); TSE; IBGE. Elaboração própria."
HOM = "tx_homicidio_trienal_eb"
TMI = "tmi_trienal_eb"
JANELAS = {"2020–2021": ((2020, 1), (2021, 12)), "1ª onda (mar–dez/2020)": ((2020, 3), (2020, 12)),
           "jan/2020–set/2022": ((2020, 1), (2022, 9))}
DESFECHOS = {"2018→2022": (2018, 2022, 2014), "2022→2026": (2022, 2026, 2018), "placebo 2014→2018": (2014, 2018, 2010)}
CENSO_FIXO = ["pct_negra", "pct_evangelica", "pct_sem_religiao"]


def _salvar(df: pd.DataFrame, nome: str, nota: str = "") -> None:
    df.to_csv(caminho("tables") / f"{nome}.csv", index=False, encoding="utf-8")
    md = df.to_markdown(index=False, floatfmt=".4g") + (f"\n\n{nota}" if nota else "") + f"\n\n{FONTE}\n"
    (caminho("tables") / f"{nome}.md").write_text(md, encoding="utf-8")
    log.info("tabela %s (%d linhas)", nome, len(df))


def serie() -> pd.DataFrame:
    s = pd.read_parquet(caminho("interim") / "sim.parquet")
    pop = pd.read_parquet(caminho("interim") / "ibge_pop.parquet")
    t = s.groupby("ano")[["obitos_total", "obitos_infantis", "homicidios", "mortes_intervencao_legal",
                          "obitos_covid"]].sum()
    t["homicidios_100mil"] = 1e5 * t["homicidios"] / pop.groupby("ano")["pop"].sum().reindex(t.index)
    t["ano_completo"] = s.groupby("ano")["ano_completo"].first()
    t["nascidos_vivos"] = pd.read_parquet(caminho("interim") / "sinasc.parquet").groupby("ano")["nascidos_vivos"].sum()
    t["tmi_por_mil"] = 1000 * t["obitos_infantis"] / t["nascidos_vivos"]
    t.loc[~t["ano_completo"], ["homicidios_100mil", "tmi_por_mil"]] = np.nan
    t.loc[config()["sim"]["nv_anos_truncados"], ["nascidos_vivos", "tmi_por_mil"]] = np.nan
    return t.reset_index()


def betas_com(e: pd.DataFrame, var: str) -> pd.DataFrame:
    z = M.padronizar(e, M.X_A + ["nep", var])
    z = z[z.groupby("eleicao")[var].transform("count") > 0]  # mortalidade infantil não existe em 2018
    com = M.betas_por_eleicao(z, "s_pt", extra=[var])
    # mesma amostra nos dois modelos: AMCs sem a taxa saem também do modelo sem ela
    sem = M.betas_por_eleicao(z[z[var].notna()], "s_pt")
    t = com.merge(sem[["spec", "eleicao", "variavel", "beta"]], on=["spec", "eleicao", "variavel"], how="left",
                  suffixes=("", "_sem_variavel"))
    t["mudanca_beta"] = t["beta"] - t["beta_sem_variavel"]
    return t[["spec", "eleicao", "variavel", "beta", "ep", "p", "beta_sem_variavel", "mudanca_beta", "n"]]


def teste_com(e: pd.DataFrame, var: str) -> pd.DataFrame:
    # mudança do coeficiente entre eleições, no modelo empilhado da Fase 6 (spec. A)
    z = M.padronizar(e, M.X_A + ["nep", var])
    t = pd.concat([M.teste_igualdade(z, "s_pt", a, b, extra=[var]) for a, b in [(2006, 2026), (2010, 2022), (2010, 2026)]])
    return t[t["variavel"] == var].reset_index(drop=True)


def tmi_simples(e: pd.DataFrame) -> pd.DataFrame:
    # s_pt ~ TMI + EF de UF, por eleição; última linha: diferença 2026 − 2010 no modelo empilhado
    z = M.padronizar(e, M.X_A + ["nep", TMI]).dropna(subset=["s_pt", TMI, "aptos", "id_microrregiao"])
    linhas = []
    for t, d in z.groupby("eleicao"):
        m = M._wls(f"s_pt ~ {TMI} + C(sg_uf)", d)
        linhas.append({"modelo": str(t), "beta": m.params[TMI], "ep": m.bse[TMI], "p": m.pvalues[TMI], "n": int(m.nobs)})
    d = z[z["eleicao"].isin([2010, 2026])].assign(T=lambda x: (x["eleicao"] == 2026).astype(int))
    m = M._wls(f"s_pt ~ {TMI} * T + C(sg_uf):C(eleicao)", d)
    v = f"{TMI}:T"
    linhas.append({"modelo": "2026 − 2010", "beta": m.params[v], "ep": m.bse[v], "p": m.pvalues[v], "n": int(m.nobs)})
    return pd.DataFrame(linhas)


def excesso() -> pd.DataFrame:
    """Uma linha por AMC: razão O/E em cada janela (suavizada e bruta) e óbitos notificados por Covid."""
    i = caminho("interim")
    a0, a1 = config()["sim"]["base_excesso"]
    amc = _amc_map()
    m = pd.read_parquet(i / "sim_mensal.parquet").assign(id_amc=lambda d: d["id_municipio"].map(amc))
    m = m.groupby(["id_amc", "ano", "mes"], as_index=False)[["obitos_total", "obitos_covid"]].sum()
    m["am"] = m["ano"] * 100 + m["mes"]
    pop = pd.read_parquet(i / "ibge_pop.parquet").assign(id_amc=lambda d: d["id_municipio"].map(amc))
    pop = pop.groupby(["id_amc", "ano"])["pop"].sum().rename("pop").reset_index()
    pop_base = pop[pop["ano"].between(a0, a1)].groupby("id_amc")["pop"].sum().rename("pop_base")
    base = m[m["ano"].between(a0, a1)].groupby(["id_amc", "mes"], as_index=False)["obitos_total"].sum()
    # taxa de cada mês do calendário: óbitos do mês em 2015–2019 por pessoa-ano
    base = base.join(pop_base, on="id_amc")
    base["taxa"] = base["obitos_total"] / base["pop_base"]
    out = pd.DataFrame(index=pop_base.index)
    for rot, (ini, fim) in JANELAS.items():
        a, b = ini[0] * 100 + ini[1], fim[0] * 100 + fim[1]
        meses = pd.DataFrame([(y, k) for y in range(ini[0], fim[0] + 1) for k in range(1, 13)
                              if a <= y * 100 + k <= b], columns=["ano", "mes"])
        esp = base[["id_amc", "mes", "taxa"]].merge(meses, on="mes").merge(pop, on=["id_amc", "ano"])
        esp = (esp["taxa"] * esp["pop"]).groupby(esp["id_amc"]).sum().reindex(out.index)
        obs = m[m["am"].between(a, b)].groupby("id_amc")["obitos_total"].sum().reindex(out.index).fillna(0)
        out[f"excesso {rot}"] = 100 * (bayes_empirico(obs, esp) - 1)
        out[f"bruto {rot}"] = 100 * (obs / esp - 1)
    c = m[m["ano"].isin([2020, 2021])].groupby("id_amc")["obitos_covid"].sum().reindex(out.index).fillna(0)
    p = pop[pop["ano"].isin([2020, 2021])].groupby("id_amc")["pop"].sum().reindex(out.index)
    out["notificados Covid 2020–2021"] = 1e5 * bayes_empirico(c, p)
    return out


def regressoes(e: pd.DataFrame, x: pd.DataFrame) -> pd.DataFrame:
    nac = e.groupby("eleicao").apply(lambda g: 100 * g["votos_pt"].sum() / g["validos"].sum(), include_groups=False)
    z = M.padronizar(e, M.X_B)
    w = e.pivot(index="id_amc", columns="eleicao", values="s_pt")
    fixo = e[e["eleicao"] == 2010].set_index("id_amc")[CENSO_FIXO].add_suffix("_10")
    medidas = [c for c in x.columns if not c.startswith("bruto")] + ["bruto 2020–2021"]
    linhas = []
    for rot, (a, b, ant) in DESFECHOS.items():
        d = z[z["eleicao"] == a].set_index("id_amc").join(fixo)
        d["swing_y"] = (w[b] - w[a]) - (nac[b] - nac[a])
        d["swing_ant"] = (w[a] - w[ant]) - (nac[a] - nac[ant])
        d["s_pt_0"] = w[a]
        ctrl1 = ["s_pt_0", "swing_ant"]
        ctrl2 = ctrl1 + M.X_B + ["ideb_ausente"] + list(fixo.columns)
        for med in medidas:
            d["x"] = (x[med] - x[med].mean()) / x[med].std()
            for nome, cs in [("M0: EF de UF", []), ("M1: + voto anterior", ctrl1), ("M2: + covariáveis", ctrl2)]:
                bd = d.dropna(subset=["swing_y", "x", "aptos", "id_microrregiao"] + cs)
                m = M._wls("swing_y ~ x + " + " + ".join(cs + ["C(sg_uf)"]), bd)
                ci = m.conf_int().loc["x"]
                linhas.append({"desfecho": rot, "medida": med, "modelo": nome, "beta_pp_por_dp": m.params["x"],
                               "ep": m.bse["x"], "ic_inf": ci[0], "ic_sup": ci[1], "p": m.pvalues["x"],
                               "n": int(m.nobs), "r2": m.rsquared})
    return pd.DataFrame(linhas)


def main() -> None:
    e = M.carregar()
    _salvar(serie(), "extra_sim_serie",
            "Óbitos por residência, sem município ignorado. Taxa de homicídios só em anos completos.")
    _salvar(betas_com(e, HOM), "extra_sim_homicidio_betas",
            "Betas padronizados de s_pt (p.p. por DP) com a taxa de homicídios no modelo; `beta_sem_variavel` = "
            "mesmo modelo e mesma amostra sem ela. Janela trienal terminando em eleição − 1 (2022–2024 na de 2026).")
    _salvar(teste_com(e, HOM), "extra_sim_homicidio_teste",
            "Diferença entre os coeficientes de homicídios (modelo empilhado com interações X × ano, EF UF × ano).")
    _salvar(betas_com(e, TMI), "extra_sim_tmi_betas",
            "Betas padronizados de s_pt (p.p. por DP) com a mortalidade infantil no modelo; `beta_sem_variavel` = "
            "mesmo modelo e mesma amostra sem ela. Janela trienal terminando em eleição − 1 (2022–2024 na de 2026).")
    _salvar(teste_com(e, TMI), "extra_sim_tmi_teste",
            "Diferença entre os coeficientes de mortalidade infantil (modelo empilhado, EF UF × ano).")
    _salvar(tmi_simples(e), "extra_sim_tmi_simples",
            "s_pt ~ mortalidade infantil (z) + EF de UF, sem outras covariáveis.")
    x = excesso()
    r = x.describe().T[["mean", "std", "min", "50%", "max"]].rename_axis("medida").reset_index()
    _salvar(r, "extra_sim_excesso_resumo", "Excesso de mortalidade por AMC, em % sobre o esperado. Médias não ponderadas.")
    _salvar(regressoes(e, x), "extra_sim_covid_voto",
            "β = variação do swing relativo do PT (p.p.) por 1 DP da medida. Associação ecológica. "
            "No placebo, o desfecho é anterior à pandemia: β ≠ 0 indica tendência prévia.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    main()
