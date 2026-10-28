"""Fase 6 — modelos (docs/planos/PLANO.md, seção 5).

Covariáveis (DATASUS e % de cadastrados no CadÚnico pendentes):
  log_pop, log_pib_pc (PIB per capita real), part_vab_agro, part_vab_adm_publica, ideb,
  pbf_100hab (benefícios do Bolsa Família em dezembro por 100 hab.; proxy direta de pobreza, H1),
  log_export_commod_pc (log de 1 + exportações de commodities SH 01–27 per capita; H3),
  e do Censo: pct_negra, pct_evangelica, pct_sem_religiao, pct_informal (% de ocupados informais) e
  taxa_desocupacao (amostra do Censo; substituem a RAIS para o mercado de trabalho).
  IDHM: só 2010 (não há municipal depois), usado como especificação alternativa das diferenças longas.
Especificações:
  A = todas (eleições com Censo: 2006*, 2010, 2014, 2022, 2026; *2006 com Censo 2010)
  B = sem as do Censo (todas as 6 eleições). O PLANO proíbe interpolar o Censo em regressões, por isso
      2018 só aparece em B.
Padrões comuns: WLS ponderada pelo eleitorado apto da eleição; efeito fixo de UF; X padronizado
(z-score) dentro de cada eleição; erros-padrão agrupados por microrregião IBGE (558 clusters).
Ideb ausente (10% em 2006, ≤ 1% depois): z = 0 + dummy `ideb_ausente`, para manter a amostra.

1. Coeficientes ao longo do tempo: y_t = α_UF + β_t·X + ε, y ∈ {s_pt, p_PT, p_ANTI}; e o modelo do
   hiato: hiato_lulista = α_UF + θ_t·X + λ·NEP + ε. Teste de igualdade 2010 × 2026 (e 2006 × 2026)
   em modelo empilhado com interações X × ano e efeitos fixos UF × ano.
2. Diferenças longas: swing = α_UF + γ·X_2010 + δ·ΔX + ε (ΔX entre as covariáveis alinhadas às
   eleições de 2010 e 2026), peso = aptos de 2010.
3. Logit multinomial G_PT / G_EST(base) / G_OP sobre X_2010 e ΔX, com dummies de macrorregião
   (com UF a separação é quase perfeita em várias UFs); efeitos marginais médios.
4. Oaxaca-Blinder do s_pt médio (ponderado por aptos) 2010 × 2026, em unidades originais, com
   dummies de UF; duas referências (β_2010 e β_2026); IC por bootstrap de microrregiões.
5. Logit multinomial P_PT / P_ANTI / P_OUTRO(base) por eleição, com NEP e dependência de puxador.

Saídas: outputs/tables/fase6_*.csv/.md e outputs/figures/fase6_*.png/.svg
"""

from __future__ import annotations

import logging
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import statsmodels.api as sm  # noqa: E402
import statsmodels.formula.api as smf  # noqa: E402

from src.mapas import COR  # noqa: E402
from src.utils import caminho, config  # noqa: E402

log = logging.getLogger("models")
warnings.filterwarnings("ignore", category=FutureWarning)

X_B = ["log_pop", "log_pib_pc", "part_vab_agro", "part_vab_adm_publica", "ideb", "pbf_100hab",
       "log_export_commod_pc"]
X_CENSO = ["pct_negra", "pct_evangelica", "pct_sem_religiao", "pct_informal", "taxa_desocupacao"]
X_A = X_B + X_CENSO
ROTULO = {"log_pop": "log população", "log_pib_pc": "log PIB per capita", "part_vab_agro": "% VAB agro",
          "part_vab_adm_publica": "% VAB adm. pública", "ideb": "Ideb", "pct_negra": "% negra",
          "pct_evangelica": "% evangélica", "pct_sem_religiao": "% sem religião", "nep": "NEP",
          "pbf_100hab": "Bolsa Família (benef./100 hab.)", "log_export_commod_pc": "log export. commodities pc",
          "idhm_2010": "IDHM 2010",
          "pct_informal": "% ocupados informais", "taxa_desocupacao": "taxa de desocupação"}
FONTE = "Fonte: TSE; IBGE; INEP; MDS e Atlas DH (via Ipeadata); Comex Stat. WLS (peso: eleitorado apto), EF de UF, IC 95% com erros agrupados por microrregião."
RNG = np.random.default_rng(20261027)


# ---------------------------------------------------------------- dados
def carregar() -> pd.DataFrame:
    p = caminho("processed")
    e = pd.read_parquet(p / "painel_eleicoes.parquet")
    loc = pd.read_parquet(caminho("interim") / "ibge_localidades.parquet").drop_duplicates("id_amc")
    e = e.merge(loc[["id_amc", "id_microrregiao"]], on="id_amc", how="left")
    e["log_pop"] = np.log(e["pop"])
    e["log_pib_pc"] = np.log(e["pib_pc_real"])
    e["ideb"] = e["ideb_ai_publica"]
    return e


def padronizar(e: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """z-score dentro de cada eleição; Ideb ausente → 0 + dummy."""
    z = e.copy()
    for c in cols:
        g = z.groupby("eleicao")[c]
        z[c] = (z[c] - g.transform("mean")) / g.transform("std")
    z["ideb_ausente"] = z["ideb"].isna().astype(int)
    z["ideb"] = z["ideb"].fillna(0)
    return z


def _salvar_tab(df: pd.DataFrame, nome: str, index: bool = False) -> None:
    df.to_csv(caminho("tables") / f"{nome}.csv", index=index, encoding="utf-8")
    (caminho("tables") / f"{nome}.md").write_text(df.to_markdown(index=index, floatfmt=".4g"), encoding="utf-8")


def _salvar_fig(fig, nome: str, fonte: str = FONTE) -> None:
    fig.text(0.01, 0.005, fonte, fontsize=7, color=COR["tinta2"], ha="left", va="bottom")
    for ext in ["png", "svg"]:
        fig.savefig(caminho("figures") / f"{nome}.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)
    log.info("figura: %s", nome)


def _wls(formula: str, d: pd.DataFrame, peso: str = "aptos"):
    """WLS com erros agrupados por microrregião. Para a versão sem ponderação (Fase 7), passe dados
    com a coluna de peso = 1."""
    return smf.wls(formula, data=d, weights=d[peso]).fit(
        cov_type="cluster", cov_kwds={"groups": d["id_microrregiao"].astype(int)})


# ---------------------------------------------------------------- 1. β ao longo do tempo
def betas_por_eleicao(z: pd.DataFrame, y: str, extra: list[str] = ()) -> pd.DataFrame:
    linhas = []
    for spec, xs in [("A", X_A), ("B", X_B)]:
        for t, d in z.groupby("eleicao"):
            if spec == "A" and config()["alinhamento"]["censo"][t] is None:
                continue
            cols = xs + list(extra)
            d = d.dropna(subset=[y] + cols + ["aptos", "id_microrregiao"])
            f = f"{y} ~ {' + '.join(cols)} + ideb_ausente + C(sg_uf)"
            m = _wls(f, d)
            ci = m.conf_int()
            for v in cols:
                linhas.append({"y": y, "spec": spec, "eleicao": t, "variavel": v, "beta": m.params[v],
                               "ep": m.bse[v], "ic_inf": ci.loc[v, 0], "ic_sup": ci.loc[v, 1], "p": m.pvalues[v],
                               "n": int(m.nobs), "r2": m.rsquared})
    return pd.DataFrame(linhas)


def teste_igualdade(z: pd.DataFrame, y: str, a: int, b: int, extra: list[str] = ()) -> pd.DataFrame:
    """Modelo empilhado: interações X × 1[ano = b], EF UF × ano. Coef. da interação = β_b − β_a."""
    cols = X_A + list(extra)
    d = z[z["eleicao"].isin([a, b])].dropna(subset=[y] + cols + ["aptos", "id_microrregiao"]).copy()
    d["T"] = (d["eleicao"] == b).astype(int)
    f = f"{y} ~ ({' + '.join(cols)} + ideb_ausente) * T + C(sg_uf):C(eleicao)"
    m = _wls(f, d)
    inter = [f"{v}:T" for v in cols]
    w = m.wald_test(" , ".join(f"{t} = 0" for t in inter), scalar=True)
    linhas = [{"y": y, "comparacao": f"{b} − {a}", "variavel": v, "dif_beta": m.params[f"{v}:T"],
               "ep": m.bse[f"{v}:T"], "p": m.pvalues[f"{v}:T"]} for v in cols]
    linhas.append({"y": y, "comparacao": f"{b} − {a}", "variavel": "TESTE CONJUNTO (Wald)",
                   "dif_beta": np.nan, "ep": np.nan, "p": float(w.pvalue)})
    return pd.DataFrame(linhas)


def fig_betas(tb: pd.DataFrame, ys: dict, nome: str, titulo: str, variaveis: list[str]) -> None:
    anos = config()["anos_eleicao"]
    n = len(variaveis)
    ncol = 4
    fig, axs = plt.subplots(-(-n // ncol), ncol, figsize=(16, 3.4 * -(-n // ncol)), sharex=True)
    for ax, v in zip(axs.flat, variaveis):
        ax.axhline(0, color="#c3c2b7", linewidth=1)
        for k, (y, (cor, rot)) in enumerate(ys.items()):
            for spec, desloc, cheio in [("A", -0.5, True), ("B", 0.5, False)]:
                d = tb[(tb["y"] == y) & (tb["spec"] == spec) & (tb["variavel"] == v)].sort_values("eleicao")
                if d.empty:
                    continue
                x = d["eleicao"] + desloc + (k - (len(ys) - 1) / 2) * 0.6
                ax.vlines(x, d["ic_inf"], d["ic_sup"], color=cor, linewidth=1.3)
                ax.scatter(x, d["beta"], s=26, zorder=3, color=cor if cheio else "white", edgecolor=cor, linewidth=1.3)
                if spec == "A":
                    ax.plot(x, d["beta"], color=cor, linewidth=0.8, alpha=0.5)
        ax.set_title(ROTULO[v], fontsize=9, loc="left")
        ax.set_xticks(anos)
        ax.set_xticklabels([str(a)[2:] for a in anos])
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="#e1e0d9", linewidth=0.5)
        ax.tick_params(labelsize=8, colors=COR["tinta2"])
    for ax in list(axs.flat)[n:]:
        ax.set_visible(False)
    alcas = [plt.Line2D([], [], color=c, marker="o", linewidth=0, label=r) for c, r in ys.values()]
    alcas += [plt.Line2D([], [], color=COR["tinta2"], marker="o", linewidth=0, label="spec. A (com Censo)"),
              plt.Line2D([], [], color=COR["tinta2"], marker="o", markerfacecolor="white", linewidth=0,
                         label="spec. B (sem Censo; inclui 2018)")]
    fig.legend(handles=alcas, loc="upper right", frameon=False, ncol=3, fontsize=8)
    fig.suptitle(titulo, fontsize=11, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.02, 1, 0.92))
    _salvar_fig(fig, nome)


def _mnlogit(y, X):
    """MNLogit: Newton; se não convergir (ex.: separação quase perfeita da dummy ideb_ausente, que nunca
    ocorre em P_ANTI em 2014/2022), BFGS — mesma log-verossimilhança, coeficiente da dummy não identificado.
    O Newton pode ainda declarar convergência com log-verossimilhança NaN (overflow, visto na robustez
    sem AMCs < 5 mil hab.); isso também aciona o BFGS."""
    m = sm.MNLogit(y, X).fit(disp=False, maxiter=300)
    if not m.mle_retvals["converged"] or not np.isfinite(m.llf) or np.isnan(np.asarray(m.bse)).any():
        m = sm.MNLogit(y, X).fit(disp=False, maxiter=5000, method="bfgs")
    assert m.mle_retvals["converged"], "MNLogit não convergiu"
    return m


def _ames(m, rotulos: dict[str, str], termos: list[str]) -> pd.DataFrame:
    """Efeitos marginais médios; índice do statsmodels = (f'{y}={k}', termo)."""
    me = m.get_margeff(at="overall").summary_frame().reset_index()
    me.columns = ["resultado", "termo", "ame", "ep", "z", "p", "ic_inf", "ic_sup"]
    me["resultado"] = me["resultado"].astype(str).str.split("=").str[-1].map(rotulos)
    return me[me["termo"].isin(termos)].reset_index(drop=True)


# ---------------------------------------------------------------- 2–3. diferenças longas e logit
def base_longa(e: pd.DataFrame, b: int | None = None, f: int | None = None) -> pd.DataFrame:
    """Base para diferenças longas b → f (padrão: config). O swing é recalculado para (b, f) com o
    share nacional sem exterior/trânsito; os grupos g_swing* são sempre os da Fase 2 (2010→2026)."""
    b = b or config()["ano_base"]
    f = f or config()["ano_final"]
    e0 = e[e["eleicao"] == b].set_index("id_amc")
    e1 = e[e["eleicao"] == f].set_index("id_amc")
    nac = e.groupby("eleicao").apply(lambda g: 100 * g["votos_pt"].sum() / g["validos"].sum(), include_groups=False)
    grupos = ["g_swing", "g_swing_dp05", "g_swing_q5", "g_swing_t3"]
    d = e0[grupos + ["sg_uf", "regiao", "aptos", "id_microrregiao", "capital"]].copy()
    d["swing"] = (e1["s_pt"] - e0["s_pt"]) - (nac[f] - nac[b])
    d["pop_final"] = e1["pop"]
    for v in X_A:
        d[f"{v}_0"] = e0[v]
        d[f"d_{v}"] = e1[v] - e0[v]
    d["ideb_ausente"] = (d["ideb_0"].isna() | d["d_ideb"].isna()).astype(int)
    cols = [f"{v}_0" for v in X_A] + [f"d_{v}" for v in X_A]
    for c in cols:
        d[c] = (d[c] - d[c].mean()) / d[c].std()
    d[["ideb_0", "d_ideb"]] = d[["ideb_0", "d_ideb"]].fillna(0)
    return d.dropna(subset=cols).reset_index()


def diferencas_longas(d: pd.DataFrame) -> pd.DataFrame:
    cols = [f"{v}_0" for v in X_A] + [f"d_{v}" for v in X_A]
    m = _wls(f"swing ~ {' + '.join(cols)} + ideb_ausente + C(sg_uf)", d)
    ci = m.conf_int()
    out = pd.DataFrame({"termo": cols, "coef": m.params[cols].values, "ep": m.bse[cols].values,
                        "ic_inf": ci.loc[cols, 0].values, "ic_sup": ci.loc[cols, 1].values, "p": m.pvalues[cols].values})
    out["bloco"] = np.where(out["termo"].str.startswith("d_"), "ΔX (mudança 2010→2026)", "X_2010 (nível inicial)")
    out["variavel"] = out["termo"].str.removeprefix("d_").str.removesuffix("_0")
    out.attrs.update(n=int(m.nobs), r2=m.rsquared)
    # contribuição de cada bloco à variância explicada (R² parcial aproximado: modelos só com cada bloco)
    r2 = {}
    for nome, cc in [("so_EF_UF", []), ("EF_UF+niveis", cols[:len(X_A)]), ("EF_UF+mudancas", cols[len(X_A):]),
                     ("completo", cols)]:
        f = "swing ~ " + (" + ".join(cc) + " + " if cc else "") + "C(sg_uf)"
        r2[nome] = smf.wls(f, data=d, weights=d["aptos"]).fit().rsquared
    out.attrs["r2_blocos"] = r2
    return out


def diferencas_longas_idhm(d: pd.DataFrame, e: pd.DataFrame) -> pd.DataFrame:
    """Alternativa: níveis de 2010 de PIB per capita e Ideb trocados pelo IDHM 2010 (índice composto)."""
    idh = e.drop_duplicates("id_amc").set_index("id_amc")["idhm_2010"]
    d = d.assign(idhm_2010=d["id_amc"].map(idh))
    d["idhm_2010"] = (d["idhm_2010"] - d["idhm_2010"].mean()) / d["idhm_2010"].std()
    niveis = [f"{v}_0" for v in X_A if v not in ("log_pib_pc", "ideb")] + ["idhm_2010"]
    cols = niveis + [f"d_{v}" for v in X_A]
    d = d.dropna(subset=cols)
    m = _wls(f"swing ~ {' + '.join(cols)} + ideb_ausente + C(sg_uf)", d)
    ci = m.conf_int()
    return pd.DataFrame({"termo": cols, "coef": m.params[cols].values, "ep": m.bse[cols].values,
                         "ic_inf": ci.loc[cols, 0].values, "ic_sup": ci.loc[cols, 1].values,
                         "p": m.pvalues[cols].values, "n": int(m.nobs), "r2": m.rsquared})


def logit_grupos(d: pd.DataFrame, col: str = "g_swing") -> pd.DataFrame:
    cols = [f"{v}_0" for v in X_A] + [f"d_{v}" for v in X_A]
    y = d[col].map({"G_EST": 0, "G_PT": 1, "G_OP": 2})
    X = pd.concat([d[cols + ["ideb_ausente"]], pd.get_dummies(d["regiao"], drop_first=True, dtype=float)], axis=1)
    # em subamostras (ex.: sem AMCs < 5 mil hab.) ideb_ausente pode ser constante → matriz singular
    X = X.loc[:, X.nunique() > 1]
    m = _mnlogit(y, sm.add_constant(X))
    me = _ames(m, {"0": "G_EST", "1": "G_PT", "2": "G_OP"}, cols)
    me["pseudo_r2"] = m.prsquared
    return me


# ---------------------------------------------------------------- 4. Oaxaca-Blinder
def oaxaca(e: pd.DataFrame, n_boot: int = 300) -> tuple[pd.DataFrame, pd.DataFrame]:
    b, f = config()["ano_base"], config()["ano_final"]
    d = e[e["eleicao"].isin([b, f])].dropna(subset=X_A + ["s_pt", "aptos"]).copy()
    # mesma amostra nos dois anos
    comum = set(d.loc[d["eleicao"] == b, "id_amc"]) & set(d.loc[d["eleicao"] == f, "id_amc"])
    d = d[d["id_amc"].isin(comum)]
    uf = pd.get_dummies(d["sg_uf"], prefix="uf", drop_first=True, dtype=float)
    X = pd.concat([pd.Series(1.0, index=d.index, name="const"), d[X_A], uf], axis=1)
    grupos = d.groupby("eleicao").groups
    micro = d["id_microrregiao"].astype(int)

    def decompor(idx0, idx1):
        res = {}
        for t, idx in [(b, idx0), (f, idx1)]:
            w = d.loc[idx, "aptos"]
            m = sm.WLS(d.loc[idx, "s_pt"], X.loc[idx], weights=w).fit()
            res[t] = (m.params, (X.loc[idx].mul(w, axis=0).sum() / w.sum()), np.average(d.loc[idx, "s_pt"], weights=w))
        (b0, x0, y0), (b1, x1, y1) = res[b], res[f]
        dx = x1 - x0
        db = b1 - b0
        return {"y_base": y0, "y_final": y1, "delta": y1 - y0,
                "explicado_ref_base": float(dx @ b0), "nao_explicado_ref_base": float(x1 @ db),
                "explicado_ref_final": float(dx @ b1), "nao_explicado_ref_final": float(x0 @ db),
                "detalhe_ref_base": dx * b0, "detalhe_ref_final": dx * b1}

    pt = decompor(grupos[b], grupos[f])
    boots = []
    clusters = micro.unique()
    por_cluster = {c: idx for c, idx in d.groupby(micro).groups.items()}
    for _ in range(n_boot):
        amostra = RNG.choice(clusters, len(clusters), replace=True)
        idx = np.concatenate([por_cluster[c] for c in amostra])
        dd = d.loc[idx]
        try:
            r = decompor(dd.index[dd["eleicao"] == b], dd.index[dd["eleicao"] == f])
        except Exception:  # noqa: BLE001 — reamostra degenerada (UF ausente)
            continue
        boots.append({k: v for k, v in r.items() if not k.startswith("detalhe")})
    bt = pd.DataFrame(boots)
    resumo = pd.DataFrame([{"componente": k, "estimativa": pt[k], "ic_inf": bt[k].quantile(.025),
                            "ic_sup": bt[k].quantile(.975)} for k in bt.columns])
    resumo.attrs["n_boot"] = len(bt)
    det = pd.DataFrame({"ref_base_2010": pt["detalhe_ref_base"], "ref_final_2026": pt["detalhe_ref_final"]})
    det.index.name = "termo"
    det = det.reset_index()
    det["grupo"] = np.where(det["termo"].str.startswith("uf_"), "UF (composição regional do eleitorado)",
                            det["termo"].map(lambda t: ROTULO.get(t, t)))
    det = det[det["termo"] != "const"].groupby("grupo")[["ref_base_2010", "ref_final_2026"]].sum().reset_index()
    return resumo, det


def fig_oaxaca(resumo: pd.DataFrame, det: pd.DataFrame) -> None:
    r = resumo.set_index("componente")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.8), gridspec_kw={"width_ratios": [1, 1.6]})
    itens = [("delta", "Δ total"), ("explicado_ref_base", "composição (ΔX·β₂₀₁₀)"),
             ("nao_explicado_ref_base", "comportamento (X₂₀₂₆·Δβ)"),
             ("explicado_ref_final", "composição (ΔX·β₂₀₂₆)"), ("nao_explicado_ref_final", "comportamento (X₂₀₁₀·Δβ)")]
    y = np.arange(len(itens))
    cores = [COR["tinta"], COR["OP"], COR["PT"], COR["OP"], COR["PT"]]
    for k, ((c, rot), cor) in enumerate(zip(itens, cores)):
        ax1.barh(k, r.loc[c, "estimativa"], color=cor, height=0.55, alpha=1 if k < 3 else 0.55)
        ax1.hlines(k, r.loc[c, "ic_inf"], r.loc[c, "ic_sup"], color=COR["tinta2"], linewidth=1.3)
    ax1.set_yticks(y)
    ax1.set_yticklabels([i[1] for i in itens], fontsize=8)
    ax1.invert_yaxis()
    ax1.axvline(0, color="#c3c2b7", linewidth=1)
    ax1.set_xlabel("p.p. de s_PT (média ponderada por aptos)", color=COR["tinta2"])
    ax1.set_title(f"Oaxaca-Blinder: s_PT 2010 → 2026\n(IC bootstrap de microrregiões, {resumo.attrs.get('n_boot', '')} reps)",
                  fontsize=10, loc="left")
    dd = det.sort_values("ref_base_2010")
    yy = np.arange(len(dd))
    ax2.barh(yy - 0.18, dd["ref_base_2010"], height=0.34, color=COR["OP"], label="referência β₂₀₁₀")
    ax2.barh(yy + 0.18, dd["ref_final_2026"], height=0.34, color=COR["OP"], alpha=0.45, label="referência β₂₀₂₆")
    ax2.set_yticks(yy)
    ax2.set_yticklabels(dd["grupo"], fontsize=8)
    ax2.axvline(0, color="#c3c2b7", linewidth=1)
    ax2.set_xlabel("contribuição da mudança de composição (p.p.)", color=COR["tinta2"])
    ax2.set_title("Parte explicada, por variável", fontsize=10, loc="left")
    ax2.legend(frameon=False, fontsize=8)
    for ax in (ax1, ax2):
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="x", color="#e1e0d9", linewidth=0.5)
        ax.tick_params(colors=COR["tinta2"])
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    _salvar_fig(fig, "fase6_oaxaca", "Fonte: TSE; IBGE (PIB dos Municípios; Censos 2010 e 2022); INEP; MDS (via Ipeadata); Comex Stat. Eleições 2010 e 2026. WLS por ano em unidades originais, com dummies de UF.")


# ---------------------------------------------------------------- 5. logit proporcional
def logit_proporcional(z: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    for t, d in z.groupby("eleicao"):
        xs = X_A if config()["alinhamento"]["censo"][t] is not None else X_B
        cols = xs + ["nep"]
        d = d.dropna(subset=cols + ["g_prop"]).copy()
        y = d["g_prop"].map({"P_OUTRO": 0, "P_PT": 1, "P_ANTI": 2})
        X = pd.concat([d[cols + ["ideb_ausente"]],
                       d[["dependencia_puxador_PT", "dependencia_puxador_ANTI"]].astype(float),
                       pd.get_dummies(d["regiao"], drop_first=True, dtype=float)], axis=1)
        m = _mnlogit(y, sm.add_constant(X))
        me = _ames(m, {"0": "P_OUTRO", "1": "P_PT", "2": "P_ANTI"}, cols)
        me["eleicao"], me["spec"], me["n"] = t, "A" if xs is X_A else "B", int(m.nobs)
        linhas.append(me)
    return pd.concat(linhas, ignore_index=True)


def main() -> None:
    e = carregar()
    z = padronizar(e, X_A + ["nep"])

    # 1. β_t
    tb = pd.concat([betas_por_eleicao(z, "s_pt"), betas_por_eleicao(z, "p_PT"), betas_por_eleicao(z, "p_ANTI"),
                    betas_por_eleicao(z, "hiato_lulista", extra=["nep"])])
    _salvar_tab(tb, "fase6_betas_por_eleicao")
    fig_betas(tb, {"s_pt": (COR["PT"], "s_PT presidencial")}, "fase6_betas_s_pt",
              "β_t: associação de cada covariável (z) com o voto presidencial no PT, por eleição", X_A)
    fig_betas(tb, {"s_pt": (COR["PT"], "s_PT presidencial"), "p_PT": ("#9e2a2a", "p_PT Câmara"),
                   "p_ANTI": (COR["OP"], "p_ANTI Câmara (PSDB→PSL→PL)")}, "fase6_betas_presidencial_x_camara",
              "β_t presidencial × Câmara: perfis divergentes = lulismo descolado do petismo", X_A)
    fig_betas(tb, {"hiato_lulista": ("#6250d6", "hiato_lulista = s_PT − p_PT")}, "fase6_betas_hiato",
              "θ_t: o que explica o hiato entre o voto presidencial e o voto na Câmara do PT (controle: NEP)", X_A + ["nep"])

    ti = pd.concat([teste_igualdade(z, y, a, config()["ano_final"], extra=ex)
                    for y, ex in [("s_pt", []), ("p_PT", []), ("p_ANTI", []), ("hiato_lulista", ["nep"])]
                    for a in [config()["ano_base"], 2006]])
    _salvar_tab(ti, "fase6_teste_igualdade_betas")

    # 2–3. diferenças longas e logit dos grupos
    d = base_longa(e)
    dl = diferencas_longas(d)
    _salvar_tab(dl, "fase6_diferencas_longas")
    _salvar_tab(pd.DataFrame([dl.attrs["r2_blocos"] | {"n": dl.attrs["n"]}]), "fase6_diferencas_longas_r2")
    _salvar_tab(diferencas_longas_idhm(d, e), "fase6_diferencas_longas_idhm2010")
    lg = logit_grupos(d)
    _salvar_tab(lg, "fase6_logit_grupos_swing_ame")

    # 4. Oaxaca-Blinder
    resumo, det = oaxaca(e)
    _salvar_tab(resumo, "fase6_oaxaca_resumo")
    _salvar_tab(det, "fase6_oaxaca_detalhe")
    fig_oaxaca(resumo, det)

    # 5. logit proporcional
    lp = logit_proporcional(z)
    _salvar_tab(lp, "fase6_logit_proporcional_ame")
    log.info("Fase 6 concluída")


if __name__ == "__main__":
    main()
