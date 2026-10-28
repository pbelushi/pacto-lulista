"""Fase 5 — análise descritiva das trajetórias (PLANO.md, seção 5).

Fontes: IBGE, INEP, MDS e Atlas DH (via Ipeadata), Comex Stat (ver outputs/pendencias.md). Indicadores:
- anuais (painel_amc_anual): população, PIB per capita real, participações do VAB (agro, indústria,
  adm. pública), Ideb, benefícios do Bolsa Família por 100 hab., exportações de commodities per capita;
- censitários (2010 e 2022): % negra, % evangélica, % católica, % sem religião.

Blocos:
1. Trajetórias por grupo (g_swing e cluster_forma): mediana e IQR por ano; também média ponderada pelo
   eleitorado apto de 2010 (PLANO, seção 2: descritivas com e sem peso).
2. Δ 2010 → último ano por grupo, diferenças de mediana entre grupos com IC bootstrap 95%
   (2.000 reamostragens), Brasil e por macrorregião. Δ em % (log) para população e PIB per capita,
   em p.p. para participações e percentuais, em pontos para o Ideb.
3. Perfil inicial (2010) × final por grupo.
4. Grupos por macrorregião.
5. Grupos proporcionais (P_PT / P_ANTI / P_OUTRO) em cada eleição: perfil em z-score **dentro da
   eleição** (posição relativa, não nível). Pergunta-guia: o P_PT de 2026 se parece mais com o P_PT de
   2006 ou com o G_PT? Distância euclidiana entre vetores de perfil.
6. Células fora da diagonal (presidencial × proporcional) em 2010 e 2026; P_ANTI-PSDB (2006–2014) ×
   P_ANTI-PSL/PL (2018–2026).
Censo de 2018 nos perfis por eleição: colunas *_interp (só descritivas, como permite o PLANO).

Saídas: outputs/tables/fase5_*.csv/.md e outputs/figures/fase5_*.png/.svg
"""

from __future__ import annotations

import logging

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.mapas import COR, COR_G, COR_P  # noqa: E402  (mesma convenção de cor e rcParams)
from src.utils import caminho, config  # noqa: E402

log = logging.getLogger("descriptives")
RNG = np.random.default_rng(20261027)
N_BOOT = 2000

ANUAIS = {
    "pop": ("População (mil, escala log)", "log"),
    "pib_pc_real": ("PIB per capita (R$ mil de dez/2025)", "log"),
    "part_vab_agro": ("% do VAB: agropecuária", "pp"),
    "part_vab_industria": ("% do VAB: indústria", "pp"),
    "part_vab_adm_publica": ("% do VAB: adm. pública", "pp"),
    "ideb_ai_publica": ("Ideb anos iniciais, rede pública", "pt"),
    "pbf_100hab": ("Bolsa Família: benefícios / 100 hab.", "dif"),
    "log_export_commod_pc": ("log(1 + export. commodities pc, R$)", "dif"),
}
CENSITARIOS = {
    "pct_negra": "% preta + parda",
    "pct_evangelica": "% evangélica (10+)",
    "pct_catolica": "% católica (10+)",
    "pct_sem_religiao": "% sem religião (10+)",
    "pct_informal": "% ocupados informais",
    "taxa_desocupacao": "Taxa de desocupação (14+)",
}
# covariáveis do perfil por eleição (painel_eleicoes); censitárias via *_interp para incluir 2018
PERFIL = {
    "log_pop": "log população",
    "pib_pc_real": "PIB per capita",
    "part_vab_agro": "% VAB agro",
    "part_vab_adm_publica": "% VAB adm. pública",
    "ideb_ai_publica": "Ideb",
    "pbf_100hab": "Bolsa Família / 100 hab.",
    "log_export_commod_pc": "export. commodities pc",
    "pct_negra_interp": "% negra",
    "pct_evangelica_interp": "% evangélica",
    "pct_sem_religiao_interp": "% sem religião",
    "pct_informal_interp": "% informais",
    "taxa_desocupacao_interp": "desocupação",
}
ORDEM_G = ["G_PT", "G_EST", "G_OP"]
ORDEM_P = ["P_PT", "P_OUTRO", "P_ANTI"]
COR_CLUSTER = {1: "#1baf7a", 2: "#eb6834", 3: "#6250d6", 4: "#eda100"}  # igual a fase2_centroides
FONTE = ("Fonte: TSE; IBGE (Censos, estimativas, PIB dos Municípios); INEP (Ideb); MDS (via Ipeadata); "
         "Comex Stat. Unidade: AMC.")


# ---------------------------------------------------------------- utilidades
def _salvar_tab(df: pd.DataFrame, nome: str, index: bool = False) -> None:
    df.to_csv(caminho("tables") / f"{nome}.csv", index=index, encoding="utf-8")
    (caminho("tables") / f"{nome}.md").write_text(df.to_markdown(index=index, floatfmt=".3g"), encoding="utf-8")


def _salvar_fig(fig, nome: str) -> None:
    fig.text(0.01, 0.005, FONTE, fontsize=7, color=COR["tinta2"], ha="left", va="bottom")
    for ext in ["png", "svg"]:
        fig.savefig(caminho("figures") / f"{nome}.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)
    log.info("figura: %s", nome)


def _eixo(ax) -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e1e0d9", linewidth=0.5)
    ax.tick_params(colors=COR["tinta2"], labelsize=8)


def _wmean(x: pd.Series, w: pd.Series) -> float:
    ok = x.notna() & w.notna()
    return float(np.average(x[ok], weights=w[ok])) if ok.any() else np.nan


def carregar() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    p = caminho("processed")
    amc = pd.read_parquet(p / "painel_amc_anual.parquet")
    ele = pd.read_parquet(p / "painel_eleicoes.parquet")
    gpres = pd.read_parquet(p / "grupos_presidenciais.parquet")[
        ["id_amc", "g_swing", "cluster_forma", "cluster_forma_rotulo", "regiao", "aptos_2010"]]
    amc = amc.merge(gpres, on="id_amc", how="left")
    amc["pop"] = amc["pop"] / 1000
    amc["pib_pc_real"] = amc["pib_pc_real"] / 1000
    return amc, ele, gpres


# ---------------------------------------------------------------- bloco 1
def trajetorias(amc: pd.DataFrame, esquema: str) -> pd.DataFrame:
    linhas = []
    for ind in list(ANUAIS) + list(CENSITARIOS):
        sub = amc[amc[ind].notna()]
        for (g, ano), d in sub.groupby([esquema, "ano"]):
            linhas.append({"esquema": esquema, "grupo": g, "indicador": ind, "ano": ano, "n": len(d),
                           "mediana": d[ind].median(), "q25": d[ind].quantile(.25), "q75": d[ind].quantile(.75),
                           "media_pond_aptos2010": _wmean(d[ind], d["aptos_2010"])})
    return pd.DataFrame(linhas)


def fig_trajetorias(tr: pd.DataFrame, esquema: str, cores: dict, rotulos: dict, nome: str, titulo: str) -> None:
    inds = list(ANUAIS) + list(CENSITARIOS)
    nlin = -(-len(inds) // 5)
    fig, axs = plt.subplots(nlin, 5, figsize=(17, 3.4 * nlin))
    for ax, ind in zip(axs.flat, inds):
        t = tr[(tr["indicador"] == ind)]
        for g, cor in cores.items():
            d = t[t["grupo"] == g].sort_values("ano")
            if d.empty:
                continue
            ax.fill_between(d["ano"], d["q25"], d["q75"], color=cor, alpha=0.15, linewidth=0)
            mk = "o" if ind in CENSITARIOS else None
            ax.plot(d["ano"], d["mediana"], color=cor, linewidth=2, marker=mk, markersize=5)
        rot = ANUAIS.get(ind, (CENSITARIOS.get(ind), None))[0]
        ax.set_title(rot, fontsize=9, loc="left")
        if ind in ANUAIS and ANUAIS[ind][1] == "log":
            ax.set_yscale("log")
        if ind in CENSITARIOS:
            ax.set_xticks([2010, 2022])
            ax.set_xlim(2007, 2025)
        _eixo(ax)
    for ax in axs.flat[len(inds):]:
        ax.set_visible(False)
    alcas = [plt.Line2D([], [], color=c, linewidth=2, label=rotulos.get(g, g)) for g, c in cores.items()]
    fig.legend(handles=alcas, loc="upper right", frameon=False, ncol=len(cores), fontsize=9)
    fig.suptitle(titulo + "\nlinha = mediana; faixa = intervalo interquartil", fontsize=11, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.02, 1, 0.95))
    _salvar_fig(fig, nome)


# ---------------------------------------------------------------- bloco 2 e 3
def _deltas(amc: pd.DataFrame, base: int) -> pd.DataFrame:
    """Δ base → último ano disponível por indicador, por AMC."""
    out = amc.drop_duplicates("id_amc").set_index("id_amc")[["g_swing", "cluster_forma", "regiao", "aptos_2010"]]
    for ind in list(ANUAIS) + list(CENSITARIOS):
        s = amc[amc[ind].notna()].pivot(index="id_amc", columns="ano", values=ind)
        fim = max(s.columns)
        # ano inicial: o próprio ano-base ou, se não houver (Ideb é bienal ímpar), o último anterior a ele
        ini = base if base in s.columns else max((c for c in s.columns if c < base), default=min(s.columns))
        tipo = ANUAIS.get(ind, (None, "pp"))[1]
        if tipo == "log":
            d = 100 * np.log(s[fim] / s[ini])
        else:
            d = s[fim] - s[ini]
        out[f"d_{ind}"] = d
        out[f"ini_{ind}"], out[f"fim_{ind}"] = s[ini], s[fim]
        out.attrs[ind] = (ini, fim)
    return out


def _boot_diff_mediana(a: np.ndarray, b: np.ndarray) -> tuple[float, float, float, float]:
    a, b = a[~np.isnan(a)], b[~np.isnan(b)]
    if len(a) < 10 or len(b) < 10:
        return (np.nan,) * 4
    obs = np.median(a) - np.median(b)
    ia = RNG.integers(0, len(a), (N_BOOT, len(a)))
    ib = RNG.integers(0, len(b), (N_BOOT, len(b)))
    bs = np.median(a[ia], axis=1) - np.median(b[ib], axis=1)
    lo, hi = np.percentile(bs, [2.5, 97.5])
    p = min(1.0, 2 * min((bs <= 0).mean(), (bs >= 0).mean()))
    return obs, lo, hi, p


def tabela_deltas(dl: pd.DataFrame, esquema: str, pares: list[tuple]) -> pd.DataFrame:
    linhas = []
    regioes = ["Brasil"] + sorted(dl["regiao"].dropna().unique())
    for ind in list(ANUAIS) + list(CENSITARIOS):
        ini, fim = dl.attrs[ind]
        for reg in regioes:
            sub = dl if reg == "Brasil" else dl[dl["regiao"] == reg]
            for a, b in pares:
                xa = sub.loc[sub[esquema] == a, f"d_{ind}"].to_numpy(float)
                xb = sub.loc[sub[esquema] == b, f"d_{ind}"].to_numpy(float)
                obs, lo, hi, p = _boot_diff_mediana(xa, xb)
                linhas.append({"esquema": esquema, "indicador": ind, "periodo": f"{ini}→{fim}", "regiao": reg,
                               "grupo_a": a, "grupo_b": b, "n_a": int(np.isfinite(xa).sum()),
                               "n_b": int(np.isfinite(xb).sum()),
                               "mediana_delta_a": np.nanmedian(xa) if len(xa) else np.nan,
                               "mediana_delta_b": np.nanmedian(xb) if len(xb) else np.nan,
                               "dif_medianas": obs, "ic95_inf": lo, "ic95_sup": hi, "p_bootstrap": p})
    return pd.DataFrame(linhas)


def perfil_inicial_final(dl: pd.DataFrame, esquema: str) -> pd.DataFrame:
    linhas = []
    for ind in list(ANUAIS) + list(CENSITARIOS):
        ini, fim = dl.attrs[ind]
        for g, d in dl.groupby(esquema):
            linhas.append({"esquema": esquema, "grupo": g, "indicador": ind, "ano_ini": ini, "ano_fim": fim,
                           "mediana_ini": d[f"ini_{ind}"].median(), "mediana_fim": d[f"fim_{ind}"].median(),
                           "mediana_delta": d[f"d_{ind}"].median(),
                           "media_pond_ini": _wmean(d[f"ini_{ind}"], d["aptos_2010"]),
                           "media_pond_fim": _wmean(d[f"fim_{ind}"], d["aptos_2010"])})
    return pd.DataFrame(linhas)


# ---------------------------------------------------------------- bloco 5 e 6
def perfis_eleicao(ele: pd.DataFrame) -> pd.DataFrame:
    """z-score de cada covariável dentro de cada eleição (posição relativa)."""
    e = ele.copy()
    e["log_pop"] = np.log(e["pop"])
    z = e.groupby("eleicao")[list(PERFIL)].transform(lambda s: (s - s.mean()) / s.std())
    return pd.concat([e[["eleicao", "id_amc", "g_prop", "g_swing", "aptos", "regiao"]], z], axis=1)


def perfil_grupos(z: pd.DataFrame, col: str) -> pd.DataFrame:
    g = z.dropna(subset=[col]).groupby(["eleicao", col])
    out = g[list(PERFIL)].mean()
    out["n"] = g.size()
    out["pct_eleitorado"] = 100 * g["aptos"].sum() / z.groupby("eleicao")["aptos"].sum()
    return out.reset_index()


def distancias(pp: pd.DataFrame, pg: pd.DataFrame) -> pd.DataFrame:
    """Distância euclidiana entre perfis (z médio) — pergunta-guia da Fase 5."""
    f = config()["ano_final"]
    v = lambda df, col, g, t: df[(df[col] == g) & (df["eleicao"] == t)][list(PERFIL)].iloc[0].to_numpy(float)  # noqa: E731
    alvo = v(pp, "g_prop", "P_PT", f)
    linhas = [{"perfil_a": f"P_PT {f}", "perfil_b": f"P_PT {t}", "distancia": float(np.linalg.norm(alvo - v(pp, "g_prop", "P_PT", t)))}
              for t in config()["anos_eleicao"] if t != f]
    linhas += [{"perfil_a": f"P_PT {f}", "perfil_b": f"G_PT (covariáveis de {t})",
                "distancia": float(np.linalg.norm(alvo - v(pg, "g_swing", "G_PT", t)))} for t in [config()["ano_base"], f]]
    anti = {t: v(pp, "g_prop", "P_ANTI", t) for t in config()["anos_eleicao"]}
    linhas += [{"perfil_a": f"P_ANTI {a}", "perfil_b": f"P_ANTI {b}", "distancia": float(np.linalg.norm(anti[a] - anti[b]))}
               for a in [2006, 2010, 2014] for b in [2018, 2022, 2026]]
    linhas += [{"perfil_a": "P_ANTI 2006", "perfil_b": f"P_ANTI {b}", "distancia": float(np.linalg.norm(anti[2006] - anti[b]))}
               for b in [2010, 2014]]
    linhas += [{"perfil_a": "P_ANTI 2018", "perfil_b": f"P_ANTI {b}", "distancia": float(np.linalg.norm(anti[2018] - anti[b]))}
               for b in [2022, 2026]]
    return pd.DataFrame(linhas)


def fig_perfil_proporcional(pp: pd.DataFrame, pg: pd.DataFrame) -> None:
    anos = config()["anos_eleicao"]
    nlin = -(-len(PERFIL) // 4)
    fig, axs = plt.subplots(nlin, 4, figsize=(16, 3.5 * nlin), sharey=True)
    partido_op = {t: config()["presidencial"][t]["partido_op"] for t in anos}
    for ax, var in zip(axs.flat, PERFIL):
        ax.axhline(0, color="#c3c2b7", linewidth=1)
        for g in ORDEM_P:
            d = pp[pp["g_prop"] == g].sort_values("eleicao")
            ax.plot(d["eleicao"], d[var], color=COR_P[g], linewidth=2, marker="o", markersize=4)
        d = pg[pg["g_swing"] == "G_PT"].sort_values("eleicao")
        ax.plot(d["eleicao"], d[var], color=COR["PT"], linewidth=1.2, linestyle="--")
        ax.set_title(PERFIL[var], fontsize=9, loc="left")
        ax.set_xticks(anos)
        ax.set_xticklabels([str(a)[2:] for a in anos])
        ax.axvspan(2016, 2028, color="#f0efec", zorder=0)
        _eixo(ax)
    for ax in list(axs.flat)[len(PERFIL):]:
        ax.set_visible(False)
    axs[0, 0].set_ylabel("média do z-score na eleição", color=COR["tinta2"])
    alcas = [plt.Line2D([], [], color=COR_P["P_PT"], linewidth=2, marker="o", label="P_PT (PT mais votado p/ Câmara)"),
             plt.Line2D([], [], color=COR_P["P_OUTRO"], linewidth=2, marker="o", label="P_OUTRO"),
             plt.Line2D([], [], color=COR_P["P_ANTI"], linewidth=2, marker="o",
                        label="P_ANTI (PSDB até 2014; PSL 2018; PL 2022–26)"),
             plt.Line2D([], [], color=COR["PT"], linewidth=1.2, linestyle="--", label="G_PT (swing presidencial, fixo)")]
    fig.legend(handles=alcas, loc="upper right", frameon=False, ncol=2, fontsize=8)
    fig.suptitle("Perfil relativo dos grupos proporcionais por eleição (z-score dentro de cada eleição)\n"
                 "faixa cinza = antipetista bolsonarista (PSL/PL); Censo 2018 interpolado (só descritiva)",
                 fontsize=11, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.02, 1, 0.93))
    _salvar_fig(fig, "fase5_perfil_proporcional")


def _rotulos_celulas(ano: int) -> dict:
    op = config()["presidencial"][ano]["partido_op"]
    return {("G_PT", "P_PT"): "G_PT, PT lidera a Câmara", ("G_PT", "P_OUTRO"): "G_PT, outro partido lidera",
            ("G_PT", "P_ANTI"): f"G_PT, {op} lidera", ("G_OP", "P_ANTI"): f"G_OP, {op} lidera",
            ("G_OP", "P_OUTRO"): "G_OP, outro partido lidera", ("G_OP", "P_PT"): "G_OP, PT lidera",
            ("G_EST", "P_PT"): "G_EST, PT lidera", ("G_EST", "P_OUTRO"): "G_EST, outro lidera",
            ("G_EST", "P_ANTI"): f"G_EST, {op} lidera"}


def celulas(z: pd.DataFrame, ano: int) -> pd.DataFrame:
    """Perfil (z médio) das 9 células presidencial × proporcional. Em 2026, 'G_PT, outro partido lidera'
    é o "Lula sem PT" e 'G_OP, outro partido lidera' é o "bolsonarismo sem PL" do PLANO."""
    d = z[(z["eleicao"] == ano)].dropna(subset=["g_prop"])
    rot = _rotulos_celulas(ano)
    d = d.assign(celula=[rot[(a, b)] for a, b in zip(d["g_swing"], d["g_prop"])])
    g = d.groupby("celula")
    out = g[list(PERFIL)].mean()
    out["n"] = g.size()
    out["pct_eleitorado"] = 100 * g["aptos"].sum() / d["aptos"].sum()
    return out.reset_index().assign(eleicao=ano)


def fig_celulas(cel: pd.DataFrame, ano: int) -> None:
    r = _rotulos_celulas(ano)
    sel = {r[("G_PT", "P_PT")]: COR["PT"], r[("G_PT", "P_OUTRO")]: "#f2a3a3",
           r[("G_OP", "P_ANTI")]: COR["OP"], r[("G_OP", "P_OUTRO")]: "#86b6ef"}
    c = cel[(cel["eleicao"] == ano) & cel["celula"].isin(sel)].set_index("celula")
    fig, ax = plt.subplots(figsize=(8, 5))
    ys = np.arange(len(PERFIL))
    ax.axvline(0, color="#c3c2b7", linewidth=1)
    for k, (cel_nome, cor) in enumerate(sel.items()):
        if cel_nome not in c.index:
            continue
        ax.scatter(c.loc[cel_nome, list(PERFIL)], ys + (k - 1.5) * 0.12, color=cor, s=40, zorder=3,
                   edgecolor="white", linewidth=1,
                   label=f"{cel_nome} (n={int(c.loc[cel_nome, 'n'])}; {c.loc[cel_nome, 'pct_eleitorado']:.0f}% do eleitorado)")
    ax.set_yticks(ys)
    ax.set_yticklabels(PERFIL.values())
    ax.invert_yaxis()
    ax.set_xlabel("média do z-score (0 = média dos municípios na eleição)", color=COR["tinta2"])
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.grid(axis="x", color="#e1e0d9", linewidth=0.5)
    ax.legend(frameon=False, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=2)
    ax.set_title(f"Perfil das células grupo de swing × partido mais votado na Câmara, {ano}\n"
                 "(G_PT/G_OP: swing presidencial 2010→2026)", fontsize=10, loc="left")
    _salvar_fig(fig, f"fase5_perfil_celulas_{ano}")


def fig_deltas(td: pd.DataFrame) -> None:
    """Diferença de medianas de Δ (G_PT − G_OP) com IC bootstrap, Brasil e regiões."""
    t = td[(td["esquema"] == "g_swing") & (td["grupo_a"] == "G_PT") & (td["grupo_b"] == "G_OP")]
    inds = list(ANUAIS) + list(CENSITARIOS)
    regioes = ["Brasil", "Norte", "Nordeste", "Sudeste", "Sul", "Centro-Oeste"]
    nlin = -(-len(inds) // 5)
    fig, axs = plt.subplots(nlin, 5, figsize=(17, 3.3 * nlin))
    for ax, ind in zip(axs.flat, inds):
        d = t[t["indicador"] == ind].set_index("regiao").reindex(regioes)
        y = np.arange(len(regioes))
        ax.axvline(0, color="#c3c2b7", linewidth=1)
        ax.hlines(y, d["ic95_inf"], d["ic95_sup"], color=COR["tinta2"], linewidth=1.5)
        ax.scatter(d["dif_medianas"], y, color=COR["tinta"], s=22, zorder=3)
        ax.set_yticks(y)
        ax.set_yticklabels(regioes if inds.index(ind) % 5 == 0 else [""] * len(regioes))
        ax.invert_yaxis()
        unid = {"log": "% (log)", "pp": "p.p.", "pt": "pontos", "dif": "diferença"}[ANUAIS.get(ind, (None, "pp"))[1]]
        rot = ANUAIS.get(ind, (CENSITARIOS.get(ind), None))[0]
        ax.set_title(f"{rot}\nΔ {d['periodo'].dropna().iloc[0]}, {unid}", fontsize=8.5, loc="left")
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.grid(axis="x", color="#e1e0d9", linewidth=0.5)
        ax.tick_params(labelsize=8, colors=COR["tinta2"])
    for ax in list(axs.flat)[len(inds):]:
        ax.set_visible(False)
    fig.suptitle("Δ dos indicadores: mediana em G_PT − mediana em G_OP (IC bootstrap 95%)\n"
                 "> 0 = o indicador cresceu mais nos municípios que migraram para o PT", fontsize=11, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.02, 1, 0.92))
    _salvar_fig(fig, "fase5_deltas_gpt_menos_gop")


def main() -> None:
    cfg = config()
    base, final = cfg["ano_base"], cfg["ano_final"]
    amc, ele, gpres = carregar()

    # 1. trajetórias
    tr_g = trajetorias(amc, "g_swing")
    tr_c = trajetorias(amc, "cluster_forma")
    _salvar_tab(pd.concat([tr_g, tr_c]), "fase5_trajetorias_mediana_iqr")
    fig_trajetorias(tr_g, "g_swing", {g: COR_G[g] for g in ORDEM_G}, {}, "fase5_trajetorias_g_swing",
                    f"Trajetórias dos indicadores por grupo de swing ({base}→{final}, ±1 DP)")
    rot_c = {k: f"{k}: {v}" for k, v in cfg["grupos"]["rotulos_cluster"]["forma"].items()}
    fig_trajetorias(tr_c, "cluster_forma", COR_CLUSTER, rot_c, "fase5_trajetorias_cluster_forma",
                    "Trajetórias dos indicadores por cluster de forma (k = 4)")

    # 2–3. deltas e perfil inicial/final
    dl = _deltas(amc, base)
    td = pd.concat([
        tabela_deltas(dl, "g_swing", [("G_PT", "G_OP"), ("G_PT", "G_EST"), ("G_OP", "G_EST")]),
        tabela_deltas(dl, "cluster_forma", [(1, 4), (1, 2), (3, 4)]),
    ])
    _salvar_tab(td, "fase5_deltas_bootstrap")
    fig_deltas(td)
    _salvar_tab(pd.concat([perfil_inicial_final(dl, "g_swing"), perfil_inicial_final(dl, "cluster_forma")]),
                "fase5_perfil_inicial_final")

    # 4. grupos por região
    reg = pd.crosstab(gpres["regiao"], gpres["g_swing"], normalize="index")[ORDEM_G] * 100
    reg["n_amc"] = gpres["regiao"].value_counts()
    _salvar_tab(reg.reset_index(), "fase5_grupos_por_regiao")
    regc = pd.crosstab(gpres["regiao"], gpres["cluster_forma_rotulo"], normalize="index") * 100
    _salvar_tab(regc.reset_index(), "fase5_clusters_por_regiao")

    # 5–6. proporcional
    z = perfis_eleicao(ele)
    pp = perfil_grupos(z, "g_prop")
    pg = perfil_grupos(z, "g_swing")
    _salvar_tab(pp, "fase5_perfil_proporcional_z")
    _salvar_tab(pg, "fase5_perfil_g_swing_z")
    _salvar_tab(distancias(pp, pg), "fase5_distancias_perfis")
    fig_perfil_proporcional(pp, pg)
    cel = pd.concat([celulas(z, base), celulas(z, final)])
    _salvar_tab(cel, "fase5_perfil_celulas")
    for a in [base, final]:
        fig_celulas(cel, a)
    # perfil por região dos grupos proporcionais (z médio), eleição final
    ppr = (z.dropna(subset=["g_prop"]).groupby(["eleicao", "regiao", "g_prop"])[list(PERFIL)].mean()
           .reset_index())
    _salvar_tab(ppr, "fase5_perfil_proporcional_z_por_regiao")


if __name__ == "__main__":
    main()
