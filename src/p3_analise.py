"""Fase D do plano3: análise dos episódios de polarização e seus desfechos.

Entrada: outputs/tables/p3_episodios.csv (Fase B) e p3_codificacao.csv (Fase C, coluna `codigo` = código final
após a revisão do usuário); painel data/interim/p3_painel.parquet (Fase A).

1. Descritiva: episódios por década e região; desfechos; duração mediana por desfecho; % com 15+ anos.
2. Duração: Kaplan-Meier (censurados incluídos), geral e por regime no início (democracia = RoW 2 ou 3).
3. Riscos competitivos: Cox por causa (R1, R2, P, D; os demais desfechos censuram), covariáveis no início do
   episódio, EP agrupado por país (lifelines, cluster_col). Incidência acumulada não paramétrica por
   Aalen-Johansen em tempo discreto (implementado aqui, por causa dos empates em anos inteiros). A lifelines não tem Fine-Gray; as probabilidades por desfecho do Brasil vêm da combinação dos
   Cox por causa (incidência acumulada a partir dos riscos de base), condicionadas à duração já transcorrida,
   com IC por bootstrap de países.
4. Sequência (H3): conflito aberto prévio entre R2 × R1 (versões estrita e ampla); R2 precedido de R1 no mesmo
   país nos 15 anos anteriores.
5. Brasil: série de v2cacamps; comparação 1960–1964 × 2016–2025; probabilidades condicionais.
6. Robustez: definições alternativas da Fase B (desfechos pelo pré-código, com o código final do episódio
   principal quando o episódio alternativo termina no mesmo país até 1 ano de distância); só democracias no
   início; só pós-1945; excluindo episódios com guerra entre Estados (e_miinteco, até 2000).

Uso: python -m src.p3_analise
"""

from __future__ import annotations

import logging
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from lifelines import CoxPHFitter, KaplanMeierFitter  # noqa: E402
from lifelines.statistics import logrank_test  # noqa: E402
from scipy import stats  # noqa: E402

from src.mapas import COR  # noqa: E402
from src.p3_codificacao import precodificar  # noqa: E402
from src.utils import RAIZ, caminho  # noqa: E402

log = logging.getLogger("p3_analise")
warnings.filterwarnings("ignore", category=FutureWarning)
CAUSAS = ["R1", "R2", "P", "D"]
# episódios excluídos por decisão do usuário (data/manual/p3_exclusoes.csv): desfecho por invasão externa
_ARQ_EXC = RAIZ / "data" / "manual" / "p3_exclusoes.csv"
EXCLUIDOS = set(pd.read_csv(_ARQ_EXC, encoding="utf-8-sig")["id"]) if _ARQ_EXC.exists() else set()
# país → ano de fim do episódio excluído (para achar o episódio correspondente nas variantes da Fase B)
EXCLUIDOS_ISO_FIM = {"FRA": 1940, "UKR": 2022}
NOME = {"R1": "R1 ruptura vencida por um polo", "R2": "R2 cesarismo", "P": "P pacto",
        "D": "D despolarização sem ruptura", "C": "C em curso (censurado)"}
COR_D = {"R1": "#9e2a2a", "R2": "#d98c1f", "P": "#2a8c82", "D": "#5f7fa8", "C": "#b9b8ae"}
X_BASE = ["polyarchy", "jucon", "militar", "golpe_10a", "presidencialismo"]
X_AMPL = X_BASE + ["crescimento_3a", "partidos"]
ROT = {"polyarchy": "democracia eleitoral (v2x_polyarchy)", "jucon": "restrições judiciais ao Executivo",
       "militar": "dimensão militar do Executivo", "golpe_10a": "golpe no país nos 10 anos anteriores",
       "presidencialismo": "presidencialismo", "crescimento_3a": "crescimento do PIB per capita (3 anos)",
       "partidos": "institucionalização partidária"}
FONTE = ("Fonte: V-Dem v16 (v2cacamps e demais), ERT v16, UCDP/PRIO 25.1, Archigos 4.1; códigos de desfecho "
         "revisados pelo usuário. Elaboração própria.")


# ---------------------------------------------------------------- dados
def covariaveis(e: pd.DataFrame, p: pd.DataFrame) -> pd.DataFrame:
    p = p.sort_values(["country_id", "year"])
    out = []
    for ep in e.itertuples():
        s = p[p["country_id"] == ep.country_id].set_index("year")
        r = s.loc[ep.inicio]
        ant = s.loc[ep.inicio - 10:ep.inicio - 1]
        cr = s.loc[ep.inicio - 2:ep.inicio, "crescimento_pib"]
        seg = s.loc[ep.inicio:ep.fim]
        out.append({"polyarchy": r["v2x_polyarchy"], "jucon": r["v2x_jucon"], "legcon": r["v2xlg_legcon"],
                    "militar": r["v2x_ex_military"], "partidos": r["v2xps_party"],
                    "presidencialismo": r["presidencialismo"], "golpe_10a": float((ant["golpe"].fillna(0) > 0).any()),
                    "crescimento_3a": cr.mean() if cr.notna().any() else np.nan,
                    "democracia_inicio": float(r["v2x_regime"] >= 2) if pd.notna(r["v2x_regime"]) else np.nan,
                    "guerra_interestatal": float((seg["e_miinteco"].fillna(0) > 0).any())})
    return pd.concat([e.reset_index(drop=True), pd.DataFrame(out)], axis=1)


def base() -> pd.DataFrame:
    p = pd.read_parquet(caminho("interim") / "p3_painel.parquet")
    e = pd.read_csv(caminho("tables") / "p3_episodios.csv")
    c = pd.read_csv(caminho("tables") / "p3_codificacao.csv", keep_default_na=False)
    e["id"] = e["iso"] + "-" + e["inicio"].astype(str)
    e = e.merge(c[["id", "codigo", "conflito_previo", "conflito_previo_estrito", "ano_desfecho"]], on="id")
    e = e[~e["id"].isin(EXCLUIDOS)]
    return covariaveis(e, p)


def _sem_excluidos(ev: pd.DataFrame) -> pd.DataFrame:
    """Variantes da Fase B: remove o episódio que termina no país excluído até 1 ano do fim do excluído."""
    fora = ev.apply(lambda r: abs(r["fim"] - EXCLUIDOS_ISO_FIM.get(r["iso"], -99)) <= 1, axis=1)
    return ev[~fora]


def _salvar(df: pd.DataFrame, nome: str, nota: str = "") -> None:
    df.to_csv(caminho("tables") / f"{nome}.csv", index=False, encoding="utf-8")
    md = df.to_markdown(index=False, floatfmt=".3g") + (f"\n\n{nota}" if nota else "") + f"\n\n{FONTE}\n"
    (caminho("tables") / f"{nome}.md").write_text(md, encoding="utf-8")
    log.info("tabela %s (%d linhas)", nome, len(df))


def _fig(fig, nome: str) -> None:
    fig.text(0.01, 0.005, FONTE, fontsize=6.5, color=COR["tinta2"], ha="left", va="bottom")
    for ext in ["png", "svg"]:
        fig.savefig(caminho("figures") / f"{nome}.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)
    log.info("figura %s", nome)


def _eixo(ax) -> None:
    from matplotlib.ticker import FuncFormatter

    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{round(v, 6):g}".replace(".", ",")))
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(COR["tinta2"])
    ax.tick_params(colors=COR["tinta2"], labelsize=8)
    ax.grid(axis="y", color="#e4e3dd", linewidth=0.6)
    ax.set_axisbelow(True)


# ---------------------------------------------------------------- 1. descritiva
def descritiva(d: pd.DataFrame) -> dict:
    d = d.assign(decada=d["inicio"] // 10 * 10)
    _salvar(pd.crosstab(d["decada"], d["codigo"], margins=True, margins_name="total").reset_index(),
            "p3_desc_decada", "Episódios por década de início e desfecho final.")
    _salvar(pd.crosstab(d["regiao"], d["codigo"], margins=True, margins_name="total").reset_index(),
            "p3_desc_regiao", "Episódios por região (V-Dem, 6 regiões) e desfecho final.")
    g = d.groupby("codigo")["duracao"]
    t = pd.DataFrame({"episodios": g.size(), "pct": 100 * g.size() / len(d), "duracao_mediana": g.median(),
                      "duracao_media": g.mean(), "pct_15_anos_ou_mais": g.apply(lambda s: 100 * (s >= 15).mean())})
    t = t.reindex(CAUSAS + ["C"]).reset_index()
    t.loc[len(t)] = ["total", len(d), 100, d["duracao"].median(), d["duracao"].mean(), 100 * (d["duracao"] >= 15).mean()]
    t["desfecho"] = t["codigo"].map(NOME).fillna("total")
    fech = d[d["codigo"] != "C"]
    _salvar(t, "p3_desc_desfechos",
            f"Entre os {len(fech)} episódios encerrados: ruptura (R1+R2) {100 * fech['codigo'].isin(['R1', 'R2']).mean():.0f}%, "
            f"pacto {100 * (fech['codigo'] == 'P').mean():.0f}%, despolarização sem ruptura {100 * (fech['codigo'] == 'D').mean():.0f}%.")
    return {"n": len(d), "fechados": len(fech), "pct_ruptura": 100 * fech["codigo"].isin(["R1", "R2"]).mean()}


# ---------------------------------------------------------------- 2. Kaplan-Meier
def kaplan_meier(d: pd.DataFrame) -> pd.DataFrame:
    ev = (d["codigo"] != "C").astype(int)
    linhas = []
    fig, axs = plt.subplots(1, 2, figsize=(9.5, 3.8), sharey=True)
    km = KaplanMeierFitter().fit(d["duracao"], ev, label="todos")
    km.plot_survival_function(ax=axs[0], color=COR["tinta"], ci_alpha=0.15)
    for nome, sel in [("todos", d.index == d.index)] + [
            ("democracia no início", d["democracia_inicio"] == 1), ("autocracia no início", d["democracia_inicio"] == 0)]:
        k = KaplanMeierFitter().fit(d.loc[sel, "duracao"], ev[sel])
        linhas.append({"grupo": nome, "episodios": int(sel.sum()), "encerrados": int(ev[sel].sum()),
                       "mediana_anos": k.median_survival_time_,
                       **{f"sobrevive_{t}_anos": float(k.survival_function_at_times(t).iloc[0]) for t in [5, 10, 15, 20, 30]}})
    for nome, sel, cor in [("democracia no início", d["democracia_inicio"] == 1, "#2a78d6"),
                           ("autocracia no início", d["democracia_inicio"] == 0, "#9e2a2a")]:
        KaplanMeierFitter().fit(d.loc[sel, "duracao"], ev[sel], label=nome).plot_survival_function(ax=axs[1], color=cor, ci_alpha=0.15)
    lr = logrank_test(d.loc[d["democracia_inicio"] == 1, "duracao"], d.loc[d["democracia_inicio"] == 0, "duracao"],
                      ev[d["democracia_inicio"] == 1], ev[d["democracia_inicio"] == 0])
    for ax, tit in zip(axs, ["Todos os episódios", f"Por regime no início (log-rank p = {lr.p_value:.2f})".replace(".", ",")]):
        _eixo(ax)
        ax.axvline(15, color=COR["tinta2"], linewidth=0.8, linestyle=":")
        ax.set_xlabel("anos desde o início do episódio", fontsize=8)
        ax.set_title(tit, fontsize=9, loc="left")
        ax.set_xlim(0, 45)
        ax.legend(frameon=False, fontsize=8)
    axs[0].set_ylabel("proporção de episódios ainda em curso", fontsize=8)
    fig.suptitle("Quanto duram os episódios de polarização (Kaplan-Meier, IC 95%)", x=0.01, ha="left", fontsize=10)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    _fig(fig, "p3_kaplan_meier")
    t = pd.DataFrame(linhas)
    t["logrank_p_dem_x_aut"] = lr.p_value
    _salvar(t, "p3_kaplan_meier", "Sobrevivência = proporção de episódios ainda em curso após t anos; censurados incluídos.")
    return t


# ---------------------------------------------------------------- 3. riscos competitivos
def aalen_johansen(d: pd.DataFrame) -> pd.DataFrame:
    """Incidência acumulada por causa em tempo discreto (anos inteiros; trata empates de forma exata, ao contrário
    da AalenJohansenFitter da lifelines, que desempata com ruído): CIF_k(t) = Σ_{s<=t} S(s−1)·d_k(s)/n(s)."""
    tempos = np.arange(1, int(d["duracao"].max()) + 1)
    S, linhas = 1.0, []
    acum = {c: 0.0 for c in CAUSAS}
    for t in tempos:
        n = int((d["duracao"] >= t).sum())
        if n == 0:
            break
        dk = {c: int(((d["duracao"] == t) & (d["codigo"] == c)).sum()) for c in CAUSAS}
        for c in CAUSAS:
            acum[c] += S * dk[c] / n
        S *= 1 - sum(dk.values()) / n
        linhas.append({"anos": t, **acum, "sobrevivencia": S})
    return pd.DataFrame(linhas).set_index("anos")


def incidencia(d: pd.DataFrame) -> pd.DataFrame:
    aj = aalen_johansen(d)
    linhas = []
    fig, ax = plt.subplots(figsize=(7, 4))
    for c in CAUSAS:
        ax.step(np.r_[0, aj.index], np.r_[0, aj[c]], where="post", color=COR_D[c], linewidth=2, label=NOME[c])
        for t in [5, 10, 15, 20, 30]:
            linhas.append({"desfecho": c, "anos": t, "incidencia_acumulada": aj.loc[aj.index <= t, c].iloc[-1]})
    _eixo(ax)
    ax.set_xlim(0, 45)
    ax.set_xlabel("anos desde o início do episódio", fontsize=8)
    ax.set_ylabel("probabilidade acumulada do desfecho", fontsize=8)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    ax.set_title("Incidência acumulada por desfecho (Aalen-Johansen; em curso = censurado)", fontsize=10, loc="left")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    _fig(fig, "p3_incidencia")
    t = pd.DataFrame(linhas).pivot(index="anos", columns="desfecho", values="incidencia_acumulada").reset_index()
    t["ainda_em_curso"] = 1 - t[CAUSAS].sum(axis=1)
    _salvar(t, "p3_incidencia", "Probabilidade de cada desfecho ter ocorrido até t anos do início, com riscos competitivos.")
    return t


def _padronizar(d: pd.DataFrame, xs: list[str]) -> tuple[pd.DataFrame, dict]:
    z = d.copy()
    esc = {}
    for x in xs:
        if d[x].nunique() > 2:
            esc[x] = (d[x].mean(), d[x].std())
            z[x] = (d[x] - esc[x][0]) / esc[x][1]
    return z, esc


def cox_causa(d: pd.DataFrame, xs: list[str], causa: str, penal: float = 0.01) -> CoxPHFitter:
    z = d.dropna(subset=xs)[xs + ["duracao", "codigo", "iso"]].copy()
    z["evento"] = (z["codigo"] == causa).astype(int)
    z, _ = _padronizar(z, xs)
    return CoxPHFitter(penalizer=penal).fit(z[xs + ["duracao", "evento", "iso"]], "duracao", "evento", cluster_col="iso")


def riscos(d: pd.DataFrame) -> pd.DataFrame:
    out = []
    for nome, xs in [("base", X_BASE), ("ampliado", X_AMPL)]:
        for c in CAUSAS + ["R1+R2"]:
            dd = d.assign(codigo=d["codigo"].replace({"R1": "R1+R2", "R2": "R1+R2"})) if c == "R1+R2" else d
            m = cox_causa(dd, xs, c)
            s = m.summary
            for x in xs:
                out.append({"modelo": nome, "desfecho": c, "variavel": x, "rotulo": ROT[x], "hr": s.loc[x, "exp(coef)"],
                            "ic_inf": s.loc[x, "exp(coef) lower 95%"], "ic_sup": s.loc[x, "exp(coef) upper 95%"],
                            "p": s.loc[x, "p"], "eventos": int(m.event_observed.sum()), "episodios": m._n_examples})
    t = pd.DataFrame(out)
    _salvar(t, "p3_cox_causa",
            "Cox por causa: razão de riscos (HR) do desfecho indicado; os demais desfechos e os em curso censuram. "
            "Variáveis contínuas padronizadas (1 DP); dummies em 0/1. EP agrupado por país. Penalização L2 de 0,01. "
            "Reportar 'eventos' ao lado de cada HR: com menos de ~40 eventos, ler como indicativo.")
    return t


# ---------------------------------------------------------------- 4. H3
def sequencia(d: pd.DataFrame) -> pd.DataFrame:
    out = []
    for col, nome in [("conflito_previo_estrito", "estrito (guerra civil ou tentativa de golpe)"),
                      ("conflito_previo", "amplo (inclui violência política frequente)")]:
        tab = pd.crosstab(d["codigo"], d[col])
        a = tab.loc[["R2", "R1"], ["sim", "não"]].values
        _, pf = stats.fisher_exact(a)
        for c in CAUSAS:
            s = d[d["codigo"] == c]
            out.append({"medida": nome, "desfecho": c, "episodios": len(s), "com_conflito_previo": int((s[col] == "sim").sum()),
                        "pct": 100 * (s[col] == "sim").mean(), "fisher_p_R2_x_R1": pf})
    # R2 precedido de R1 no mesmo país nos 15 anos anteriores (sequência à Brinton)
    d = d.sort_values(["iso", "inicio"])
    prev = []
    for r in d.itertuples():
        ant = d[(d["iso"] == r.iso) & (d["fim"] < r.inicio) & (d["fim"] >= r.inicio - 15)]
        prev.append(bool((ant["codigo"] == "R1").any()))
    d["r1_nos_15_anos_antes"] = prev
    for c in CAUSAS:
        s = d[d["codigo"] == c]
        out.append({"medida": "episódio R1 no mesmo país nos 15 anos anteriores", "desfecho": c, "episodios": len(s),
                    "com_conflito_previo": int(s["r1_nos_15_anos_antes"].sum()), "pct": 100 * s["r1_nos_15_anos_antes"].mean(),
                    "fisher_p_R2_x_R1": stats.fisher_exact(pd.crosstab(d.loc[d["codigo"].isin(["R1", "R2"]), "codigo"],
                                                                       d.loc[d["codigo"].isin(["R1", "R2"]), "r1_nos_15_anos_antes"]).values)[1]})
    t = pd.DataFrame(out)
    _salvar(t, "p3_sequencia_h3", "H3 (Brinton): o cesarismo (R2) vem depois de uma fase de conflito? Teste exato de Fisher R2 × R1.")
    return t


# ---------------------------------------------------------------- 5. Brasil
def _cif_condicional(d: pd.DataFrame, xs: list[str], perfil: pd.Series, t0: float, horizontes: list[int]) -> dict:
    """P(desfecho k entre t0 e t0+h | episódio em curso em t0), combinando Cox por causa."""
    z = d.dropna(subset=xs).copy()
    z, esc = _padronizar(z, xs)
    pz = perfil.copy()
    for x, (m, s) in esc.items():
        pz[x] = (perfil[x] - m) / s
    hz = {}
    for c in CAUSAS:
        zz = z.assign(evento=(z["codigo"] == c).astype(int))
        m = CoxPHFitter(penalizer=0.01).fit(zz[xs + ["duracao", "evento"]], "duracao", "evento")
        h0 = m.baseline_cumulative_hazard_.iloc[:, 0]
        risco = float(np.exp(((pz[xs] - m._norm_mean[xs]) * m.params_[xs]).sum()))
        hz[c] = h0 * risco
    tempos = sorted(set().union(*[h.index for h in hz.values()]))
    H = pd.DataFrame({c: h.reindex(tempos).ffill().fillna(0) for c, h in hz.items()})
    dH = H.diff().fillna(H.iloc[0])
    S = np.exp(-H.sum(axis=1))
    Sm = S.shift(fill_value=1.0)
    cif = (dH.mul(Sm, axis=0)).cumsum()
    def em(t):
        return cif.loc[cif.index <= t].iloc[-1] if (cif.index <= t).any() else cif.iloc[0] * 0
    s0 = float(S.loc[S.index <= t0].iloc[-1]) if (S.index <= t0).any() else 1.0
    return {h: ((em(t0 + h) - em(t0)) / s0).to_dict() for h in horizontes}


def brasil(d: pd.DataFrame, p: pd.DataFrame, reps: int = 200) -> pd.DataFrame:
    b = d[d["iso"] == "BRA"]
    comp = b[b["inicio"].isin([1960, 2016])][["id", "inicio", "fim", "duracao", "codigo", "pico", "media"] + X_AMPL + ["democracia_inicio"]]
    _salvar(comp, "p3_brasil_comparacao", "Brasil: covariáveis no início dos episódios de 1960–1964 e 2016–2025 (em curso).")
    # perfil atual: covariáveis em 2016 (início do episódio); t0 = duração já transcorrida (2016–2025 = 10 anos)
    atual = b[b["inicio"] == 2016].iloc[0]
    t0 = float(atual["duracao"])
    hor = [5, 10, 20]
    pontual = _cif_condicional(d, X_BASE, atual, t0, hor)
    rng = np.random.default_rng(2026)
    paises = d["iso"].unique()
    boot = {h: {c: [] for c in CAUSAS} for h in hor}
    for _ in range(reps):
        amostra = rng.choice(paises, len(paises), replace=True)
        db = pd.concat([d[d["iso"] == i] for i in amostra], ignore_index=True)
        try:
            r = _cif_condicional(db, X_BASE, atual, t0, hor)
        except Exception:  # noqa: BLE001 (réplica sem eventos de alguma causa)
            continue
        for h in hor:
            for c in CAUSAS:
                boot[h][c].append(r[h].get(c, np.nan))
    linhas = []
    for h in hor:
        for c in CAUSAS:
            v = np.array(boot[h][c], dtype=float)
            linhas.append({"horizonte_anos": h, "desfecho": c, "nome": NOME[c], "probabilidade": pontual[h][c],
                           "ic_inf": np.nanpercentile(v, 2.5), "ic_sup": np.nanpercentile(v, 97.5), "replicas": int(np.isfinite(v).sum())})
        linhas.append({"horizonte_anos": h, "desfecho": "em curso", "nome": "episódio ainda em curso",
                       "probabilidade": 1 - sum(pontual[h].values()), "ic_inf": np.nan, "ic_sup": np.nan, "replicas": reps})
    t = pd.DataFrame(linhas)
    _salvar(t, "p3_brasil_probabilidades",
            f"Exercício condicional, não previsão: probabilidade de cada desfecho nos próximos h anos para um episódio com o "
            f"perfil do Brasil em 2016 (covariáveis do modelo base) que já dura {int(t0)} anos. Cox por causa combinados em "
            f"incidência acumulada; IC 95% por bootstrap de países ({reps} réplicas).")
    # figura: série do Brasil
    s = p[p["country_text_id"] == "BRA"].sort_values("year")
    lim = pd.read_csv(caminho("tables") / "p3_faseB_robustez.csv")["limiar"].iat[0]
    fig, ax = plt.subplots(figsize=(10, 3.6))
    for r in b.itertuples():
        ax.axvspan(r.inicio - 0.5, r.fim + 0.5, color=COR_D[r.codigo], alpha=0.25, linewidth=0)
        ax.text((r.inicio + r.fim) / 2, 3.75, r.codigo, ha="center", fontsize=7.5, color=COR_D[r.codigo], fontweight="bold")
    ax.plot(s["year"], s["v2cacamps"], color=COR["tinta"], linewidth=1.6)
    ax.axhline(lim, color=COR["tinta2"], linewidth=0.8, linestyle="--")
    ax.text(1901, lim + 0.08, f"limiar (p80 mundial) = {lim:.2f}".replace(".", ","), fontsize=7.5, color=COR["tinta2"])
    _eixo(ax)
    ax.set_xlim(1899, 2026)
    ax.set_ylim(-3, 4)
    ax.set_ylabel("v2cacamps (maior = mais polarizado)", fontsize=8)
    ax.set_title("Brasil: polarização política 1900–2025 e episódios (cor = desfecho)", fontsize=10, loc="left")
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=COR_D[c], alpha=0.5, label=NOME[c]) for c in ["R1", "P", "C"]],
              frameon=False, fontsize=7.5, loc="lower left", ncol=3)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    _fig(fig, "p3_brasil")
    return t


# ---------------------------------------------------------------- linha do tempo
def linha_do_tempo(d: pd.DataFrame) -> None:
    from matplotlib.patches import Patch

    ordem = d.groupby("pais").agg(regiao=("regiao", "first"), ini=("inicio", "min")).sort_values(["regiao", "ini"])
    # uma linha em branco antes de cada região, com o nome da região
    pos, y, rotulos_reg = {}, 0, []
    for reg, g in ordem.groupby("regiao", sort=False):
        rotulos_reg.append((y, reg))
        y += 1
        for p_ in g.index:
            pos[p_] = y
            y += 1
    alt = 0.12 * y + 1.0
    fig, ax = plt.subplots(figsize=(9, alt))
    for r in d.itertuples():
        ax.barh(pos[r.pais], r.fim - r.inicio + 1, left=r.inicio, height=0.75, color=COR_D[r.codigo], linewidth=0)
    for y0, reg in rotulos_reg:
        ax.text(1900.5, y0 + 0.1, reg, fontsize=7.5, fontweight="bold", color=COR["tinta"], va="center")
    ax.set_yticks(list(pos.values()), list(pos.keys()), fontsize=4.8)
    ax.set_ylim(y, -1)
    ax.set_xlim(1900, 2026)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="x", labelsize=8)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color="#e4e3dd", linewidth=0.6)
    ax.set_axisbelow(True)
    fig.suptitle(f"{len(d)} episódios de polarização em {len(pos)} países, 1900–2025 (cor = desfecho)", x=0.01, ha="left",
                 fontsize=10, y=1 - 0.15 / alt)
    fig.legend(handles=[Patch(color=COR_D[c], label=NOME[c]) for c in CAUSAS + ["C"]], frameon=False, fontsize=7,
               loc="upper left", bbox_to_anchor=(0.01, 1 - 0.4 / alt), ncol=3)
    fig.subplots_adjust(top=1 - 0.95 / alt, bottom=0.45 / alt, left=0.17, right=0.98)
    _fig(fig, "p3_linha_do_tempo")


# ---------------------------------------------------------------- 6. robustez
def _resumo(d: pd.DataFrame, nome: str) -> dict:
    ev = (d["codigo"] != "C").astype(int)
    k = KaplanMeierFitter().fit(d["duracao"], ev)
    f = d[d["codigo"] != "C"]
    out = {"variante": nome, "episodios": len(d), "encerrados": len(f),
           **{f"pct_{c}": 100 * (f["codigo"] == c).mean() for c in CAUSAS},
           "mediana_km": k.median_survival_time_, "sobrevive_15_anos": float(k.survival_function_at_times(15).iloc[0])}
    r = d[d["codigo"].isin(["R1", "R2"])]
    out["pct_R2_com_conflito_estrito"] = 100 * (r.loc[r["codigo"] == "R2", "conflito_previo_estrito"] == "sim").mean()
    out["pct_R1_com_conflito_estrito"] = 100 * (r.loc[r["codigo"] == "R1", "conflito_previo_estrito"] == "sim").mean()
    try:
        m = cox_causa(d.assign(codigo=d["codigo"].replace({"R1": "R1+R2", "R2": "R1+R2"})), ["polyarchy", "militar"], "R1+R2")
        out["hr_ruptura_polyarchy"] = m.summary.loc["polyarchy", "exp(coef)"]
        out["p_ruptura_polyarchy"] = m.summary.loc["polyarchy", "p"]
        out["hr_ruptura_militar"] = m.summary.loc["militar", "exp(coef)"]
        out["p_ruptura_militar"] = m.summary.loc["militar", "p"]
    except Exception:  # noqa: BLE001
        pass
    return out


def robustez(d: pd.DataFrame, p: pd.DataFrame) -> pd.DataFrame:
    linhas = [_resumo(d, "principal (p80, mín. 3)")]
    linhas += [_resumo(d[d["democracia_inicio"] == 1], "só democracias no início"),
               _resumo(d[d["inicio"] >= 1945], "só pós-1945"),
               _resumo(d[d["guerra_interestatal"] == 0], "sem guerra entre Estados no episódio")]
    final = d.set_index("id")["codigo"]
    for arq, nome in [("limiar_0.75", "limiar p75"), ("limiar_0.9", "limiar p90"), ("duracao_2", "duração mínima 2"),
                      ("duracao_5", "duração mínima 5"), ("v2smpolsoc_", "v2smpolsoc (2000–2025)")]:
        f = caminho("interim") / f"p3_episodios_{arq}.csv"
        if not f.exists():
            continue
        ev = _sem_excluidos(pd.read_csv(f))
        c = precodificar(ev, p)
        c["codigo"] = c["codigo_proposto"]
        # código final do episódio principal que termina no mesmo país até 1 ano de distância
        for i, r in c.iterrows():
            m = d[(d["iso"] == r["iso"]) & ((d["fim"] - r["fim"]).abs() <= 1)]
            if len(m):
                c.at[i, "codigo"] = final[m["id"].iat[0]]
        ev["id"] = ev["iso"] + "-" + ev["inicio"].astype(str)
        ev = ev.merge(c[["id", "codigo", "conflito_previo", "conflito_previo_estrito"]], on="id")
        linhas.append(_resumo(covariaveis(ev, p), nome))
    t = pd.DataFrame(linhas)
    _salvar(t, "p3_robustez",
            "Definições alternativas da Fase B: desfecho pelo pré-código automático, substituído pelo código final do "
            "episódio principal quando o episódio alternativo termina no mesmo país até 1 ano de distância. "
            "hr_ruptura_*: Cox para R1+R2 com polyarchy e dimensão militar (padronizadas).")
    return t


# ---------------------------------------------------------------- recorte: episódios iniciados em democracia
def _subtipo(ev: str, just: str) -> str:
    """Tipo da ruptura pelo evento, sem atribuir autoria: o chefe de Estado nem sempre é quem governa (em sistemas
    parlamentaristas o poder está no chefe de governo), então não se infere quem fechou o regime."""
    primeiro = ev.split(";")[0] if ev else ""
    if "golpe" in primeiro or "entrada irregular" in primeiro:
        return "golpe ou entrada irregular"
    if "democracia" in primeiro.split("→")[0] and "autocracia" in primeiro.split("→")[-1]:
        return "autocratização sem golpe"
    return "outra mudança de regime"


def democracias(d: pd.DataFrame, p: pd.DataFrame) -> pd.DataFrame:
    """Recorte pedido pelo usuário (28/10/2026): só episódios iniciados em democracia (RoW 2 ou 3 no 1º ano).
    v2x_polyarchy >= 0,5 seleciona os mesmos episódios; a ampliação de N usa as variantes da Fase B."""
    c = pd.read_csv(caminho("tables") / "p3_codificacao.csv", keep_default_na=False).set_index("id")
    m = d[d["democracia_inicio"] == 1].copy()
    # pico de polarização sem o último ano do episódio (controle do viés retrospectivo: o V-Dem pode inflar o ano da ruptura)
    m["pico_antes_ultimo"] = [p.loc[(p["country_id"] == r.country_id) & p["year"].between(r.inicio, r.fim - 1), "v2cacamps"].max()
                              for r in m.itertuples()]
    m["subtipo_ruptura"] = [_subtipo(c.at[i, "evidencia"], c.at[i, "justificativa"]) if k in ("R1", "R2") else ""
                            for i, k in zip(m["id"], m["codigo"])]
    # correções do usuário onde as bases não registram o evento (data/manual/p3_subtipos_usuario.csv)
    arq = RAIZ / "data" / "manual" / "p3_subtipos_usuario.csv"
    if arq.exists():
        corr = pd.read_csv(arq, encoding="utf-8-sig").set_index("id")["subtipo_ruptura"]
        m["subtipo_ruptura"] = m["id"].map(corr).fillna(m["subtipo_ruptura"])
    m["quem_assumiu"] = m["id"].map(c["quem_assumiu"])
    m["evidencia"] = m["id"].map(c["evidencia"])
    cols = ["id", "pais", "inicio", "fim", "duracao", "codigo", "subtipo_ruptura", "quem_assumiu", "regime_inicio",
            "polyarchy", "jucon", "militar", "partidos", "golpe_10a", "presidencialismo", "crescimento_3a",
            "pico", "pico_antes_ultimo", "conflito_previo_estrito", "evidencia"]
    _salvar(m.sort_values("inicio")[cols], "p3_dem_episodios",
            "Episódios de polarização iniciados em democracia (RoW = democracia eleitoral ou liberal no 1º ano). "
            "Excluídos por invasão externa (decisão do usuário): França 1934–1940 e Ucrânia 2020–2022.")
    f = m[m["codigo"] != "C"]
    k = KaplanMeierFitter().fit(m["duracao"], (m["codigo"] != "C").astype(int))
    aj = aalen_johansen(m)
    linhas = [{"medida": "episódios", "valor": len(m)}, {"medida": "encerrados", "valor": len(f)},
              {"medida": "em curso (2025)", "valor": int((m["codigo"] == "C").sum())},
              *[{"medida": f"% dos encerrados: {NOME[x]}", "valor": 100 * (f["codigo"] == x).mean()} for x in CAUSAS],
              *[{"medida": f"rupturas: {st}", "valor": int((f["subtipo_ruptura"] == st).sum())}
                for st in ["golpe ou entrada irregular", "autocratização sem golpe", "outra mudança de regime"]],
              {"medida": "rupturas com pico de polarização no último ano do episódio (viés retrospectivo?)",
               "valor": int(((f["ano_pico"] == f["fim"]) & f["codigo"].isin(["R1", "R2"])).sum())},
              {"medida": "não rupturas com pico no último ano do episódio",
               "valor": int(((f["ano_pico"] == f["fim"]) & ~f["codigo"].isin(["R1", "R2"])).sum())},
              {"medida": "duração mediana (Kaplan-Meier, anos)", "valor": k.median_survival_time_},
              *[{"medida": f"% ainda em curso após {t} anos (KM)", "valor": 100 * float(k.survival_function_at_times(t).iloc[0])}
                for t in [5, 10, 15, 20]],
              *[{"medida": f"incidência acumulada em 15 anos: {NOME[x]}", "valor": 100 * aj.loc[aj.index <= 15, x].iloc[-1]}
                for x in CAUSAS],
              {"medida": "encerrados que começaram antes de 1945", "valor": int((f["inicio"] < 1945).sum())},
              {"medida": "episódios iniciados desde 2005", "valor": int((m["inicio"] >= 2005).sum())}]
    _salvar(pd.DataFrame(linhas), "p3_dem_resumo", "Recorte: episódios iniciados em democracia.")
    # o que separa ruptura (R1+R2) de não ruptura (P+D) entre os encerrados; Brasil 2016 ao lado
    rup = f["codigo"].isin(["R1", "R2"])
    br = m[m["id"] == "BRA-2016"].iloc[0]
    comp = []
    for x in ["polyarchy", "jucon", "militar", "partidos", "golpe_10a", "presidencialismo", "crescimento_3a", "duracao", "pico", "pico_antes_ultimo"]:
        a, b = f.loc[rup, x].dropna(), f.loc[~rup, x].dropna()
        comp.append({"variavel": x, "rotulo": ROT.get(x, x), "media_ruptura": a.mean(), "n_ruptura": len(a),
                     "media_sem_ruptura": b.mean(), "n_sem_ruptura": len(b),
                     "p_mann_whitney": stats.mannwhitneyu(a, b).pvalue if len(a) > 1 and len(b) > 1 else np.nan,
                     "brasil_2016": br[x]})
    _salvar(pd.DataFrame(comp), "p3_dem_ruptura_x_nao",
            "Entre os episódios encerrados iniciados em democracia: média das covariáveis no início, ruptura (R1+R2) × "
            "pacto ou despolarização (P+D). N muito pequeno: só descritivo. 'duracao' e 'pico' não são do início; "
            "'pico_antes_ultimo' exclui o último ano do episódio (ano da ruptura), para controlar o viés retrospectivo.")
    # ampliação de N com as variantes da Fase B
    final = d.set_index("id")["codigo"]
    amp = [{"variante": "principal (p80, mín. 3)", "episodios": len(m), "encerrados": len(f),
            **{f"pct_{x}": 100 * (f["codigo"] == x).mean() for x in CAUSAS}}]
    for arq, nome in [("limiar_0.75", "limiar p75"), ("duracao_2", "duração mínima 2"), ("limiar_0.9", "limiar p90")]:
        ev_ = pd.read_csv(caminho("interim") / f"p3_episodios_{arq}.csv")
        ev_ = ev_[ev_["regime_inicio"].isin(["democracia eleitoral", "democracia liberal"])]
        ev_ = _sem_excluidos(ev_)
        cc = precodificar(ev_, p)
        cc["codigo"] = cc["codigo_proposto"]
        for i, r in cc.iterrows():
            mm = d[(d["iso"] == r["iso"]) & ((d["fim"] - r["fim"]).abs() <= 1)]
            if len(mm):
                cc.at[i, "codigo"] = final[mm["id"].iat[0]]
        ff = cc[cc["codigo"] != "C"]
        amp.append({"variante": nome, "episodios": len(cc), "encerrados": len(ff),
                    **{f"pct_{x}": 100 * (ff["codigo"] == x).mean() for x in CAUSAS}})
    _salvar(pd.DataFrame(amp), "p3_dem_variantes",
            "Recorte democrático nas definições alternativas de episódio (desfechos dos encerrados, %).")
    # figura
    from matplotlib.patches import Patch

    m = m.sort_values("inicio").reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(9, 0.26 * len(m) + 1.4))
    for i, r in m.iterrows():
        ax.barh(i, r["fim"] - r["inicio"] + 1, left=r["inicio"], height=0.7, color=COR_D[r["codigo"]], linewidth=0)
        rot = r["codigo"] + (f" · {r['subtipo_ruptura']}" if r["subtipo_ruptura"] else "")
        ax.text(r["fim"] + 1.5, i, rot, va="center", fontsize=6.5, color=COR["tinta2"])
    ax.set_yticks(range(len(m)), [f"{r.pais} {r.inicio}" for r in m.itertuples()], fontsize=7)
    ax.invert_yaxis()
    ax.set_xlim(1915, 2050)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", labelsize=8)
    ax.grid(axis="x", color="#e4e3dd", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.legend(handles=[Patch(color=COR_D[x], label=NOME[x]) for x in CAUSAS + ["C"]], frameon=False, fontsize=7,
              loc="lower left", ncol=2)
    ax.set_title(f"Os {len(m)} episódios de polarização iniciados em democracia, 1900–2025", fontsize=10, loc="left")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    _fig(fig, "p3_dem_episodios")
    return m


def main() -> None:
    d = base()
    p = pd.read_parquet(caminho("interim") / "p3_painel.parquet")
    descritiva(d)
    kaplan_meier(d)
    incidencia(d)
    riscos(d)
    sequencia(d)
    brasil(d, p)
    linha_do_tempo(d)
    robustez(d, p)
    democracias(d, p)
    d.to_csv(caminho("interim") / "p3_analise_base.csv", index=False, encoding="utf-8")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    main()
