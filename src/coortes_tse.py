"""Teste extra (fora do PLANO): coortes etárias com o eleitorado do TSE (perfil do eleitorado).

Complementa src/coortes.py (Censo) com o eleitorado efetivo de cada eleição
(src/ingest/tse_perfil.py), o que inclui 2018 e não depende do alinhamento com o Censo.

1. Brasil, eleição a eleição: eleitores nascidos a partir de 1991, em 1970–1990 e até 1969 (n e %).
2. "Onde os nascidos a partir de 1991 são mais representativos": em cada eleição, AMCs em quintis
   da participação dessa coorte no eleitorado — quintis nacionais e quintis dentro da UF (tira o
   efeito de região: o Norte e o Nordeste são mais jovens). Por quintil: s_PT, p_PT, p_ANTI
   (médias ponderadas pelo eleitorado; s_PT também sem ponderação, porque as capitais e cidades grandes
   caem no Q1 dentro da UF e dominam a média ponderada) e diferença Q5 − Q1.
3. Regressões por eleição (WLS por aptos, EF de UF, erros por microrregião), coortes em p.p. (base:
   até 1969), sem e com controles (spec. A nos anos com Censo; spec. B em 2018, que não tem Censo):
   contrastes "1991+ vs. 1970–90", "1991+ vs. até 1969", "1970–90 vs. até 1969".
Leitura ecológica: municípios com mais eleitores de uma coorte, não eleitores dessa coorte.

Saídas: outputs/tables/extra_tse_coortes_*.csv/.md e outputs/figures/extra_tse_coortes_*.png/.svg
"""

from __future__ import annotations

import logging

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src import models as M  # noqa: E402
from src.mapas import COR  # noqa: E402
from src.utils import caminho, config  # noqa: E402

log = logging.getLogger("coortes_tse")
COORTES = ["pct_coorte_1991", "pct_coorte_1970_1990", "pct_coorte_ate1969"]
ROT = {"pct_coorte_1991": "nascidos 1991+", "pct_coorte_1970_1990": "nascidos 1970–1990",
       "pct_coorte_ate1969": "nascidos até 1969"}
CONTRASTES = {"1991+ vs. 1970–90": {"pct_coorte_1991": 1, "pct_coorte_1970_1990": -1},
              "1991+ vs. até 1969": {"pct_coorte_1991": 1},
              "1970–90 vs. até 1969": {"pct_coorte_1970_1990": 1}}
FONTE = ("Fonte: TSE (perfil do eleitorado por faixa etária e município; 2º turno presidencial e deputado "
         "federal 2006–2026). Coortes estimadas a partir de faixas de 5 anos. Unidade: AMC.")


def perfil_amc() -> pd.DataFrame:
    d = pd.read_parquet(caminho("interim") / "tse_perfil_idade.parquet")
    amc = {int(k): int(v) for k, v in config()["amc"].items()}
    d["id_amc"] = d["id_municipio"].map(lambda c: amc.get(c, c))
    cols = [c for c in d.columns if c.startswith("pct_") and c != "pct_idade_ni"]
    num = d[cols].mul(d["eleitores"], axis=0).groupby([d["id_amc"], d["ano"]]).sum()
    den = d.groupby(["id_amc", "ano"])["eleitores"].sum()
    out = num.div(den, axis=0)
    out["eleitores_idade"] = den
    return out.reset_index().rename(columns={"ano": "eleicao"})


def base() -> pd.DataFrame:
    return M.carregar().merge(perfil_amc(), on=["id_amc", "eleicao"], how="left")


def _mp(g: pd.DataFrame, col: str) -> float:
    ok = g[col].notna()
    return np.average(g.loc[ok, col], weights=g.loc[ok, "aptos"]) if ok.any() else np.nan


# ---------------------------------------------------------------- 1. Brasil
def nacional() -> pd.DataFrame:
    d = pd.read_parquet(caminho("interim") / "tse_perfil_idade.parquet")
    linhas = []
    for ano, g in d.groupby("ano"):
        tot = g["eleitores"].sum()
        lin = {"eleicao": ano, "eleitores_com_idade": tot,
               "pct_idade_nao_informada": 100 * (1 - tot / (g["eleitores"] / (1 - g["pct_idade_ni"] / 100)).sum())}
        for c in COORTES:
            n = (g[c] / 100 * g["eleitores"]).sum()
            lin[f"n_{ROT[c]}"] = n
            lin[f"% {ROT[c]}"] = 100 * n / tot
        linhas.append(lin)
    return pd.DataFrame(linhas)


# ---------------------------------------------------------------- 2. quintis da coorte 1991+
def quintis(e: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    for t, d in e.dropna(subset=["pct_coorte_1991"]).groupby("eleicao"):
        if d["pct_coorte_1991"].max() == 0:
            continue
        d = d.copy()
        d["q_nac"] = pd.qcut(d["pct_coorte_1991"].rank(method="first"), 5, labels=False) + 1
        d["q_uf"] = d.groupby("sg_uf")["pct_coorte_1991"].transform(
            lambda s: pd.qcut(s.rank(method="first"), 5, labels=False) + 1 if len(s) >= 5 else np.nan)
        for tipo, col in [("quintil nacional", "q_nac"), ("quintil dentro da UF", "q_uf")]:
            for q, g in d.dropna(subset=[col]).groupby(col):
                linhas.append({"eleicao": t, "tipo": tipo, "quintil": int(q), "n_amc": len(g),
                               "pct_eleitorado": 100 * g["aptos"].sum() / d["aptos"].sum(),
                               "pct_1991_mediana": g["pct_coorte_1991"].median(),
                               "s_pt": _mp(g, "s_pt"), "p_PT": _mp(g, "p_PT"), "p_ANTI": _mp(g, "p_ANTI"),
                               "s_pt_nao_pond": g["s_pt"].mean(), "n_capitais": int(g["capital"].sum())})
    return pd.DataFrame(linhas)


def q5_menos_q1(q: pd.DataFrame) -> pd.DataFrame:
    w = q[q["quintil"].isin([1, 5])].pivot_table(index=["tipo", "eleicao"], columns="quintil",
                                                 values=["s_pt", "s_pt_nao_pond", "p_PT", "p_ANTI", "pct_1991_mediana"])
    out = pd.DataFrame({f"{v} Q5−Q1": w[(v, 5)] - w[(v, 1)] for v in ["s_pt", "s_pt_nao_pond", "p_PT", "p_ANTI"]})
    out["pct_1991 Q1"], out["pct_1991 Q5"] = w[("pct_1991_mediana", 1)], w[("pct_1991_mediana", 5)]
    return out.reset_index()


# ---------------------------------------------------------------- 3. regressões
def regressoes(e: pd.DataFrame) -> pd.DataFrame:
    z = M.padronizar(e, M.X_A + ["nep"])
    for c in COORTES:
        z[c] = e[c]
    linhas = []
    for y in ["s_pt", "p_ANTI"]:
        for t, d in z.groupby("eleicao"):
            if d["pct_coorte_1991"].isna().all():
                continue
            xs_ctrl = M.X_A if config()["alinhamento"]["censo"][t] is not None else M.X_B
            nome_ctrl = "+ controles (spec. A)" if xs_ctrl is M.X_A else "+ controles (spec. B, sem Censo)"
            for spec, xs in [("só EF de UF", []), (nome_ctrl, xs_ctrl)]:
                cols = ["pct_coorte_1991", "pct_coorte_1970_1990"] + xs
                dd = d.dropna(subset=[y] + cols + ["aptos", "id_microrregiao"])
                ctrl = " + ideb_ausente" if xs else ""
                m = M._wls(f"{y} ~ {' + '.join(cols)}{ctrl} + C(sg_uf)", dd)
                for nome, w in CONTRASTES.items():
                    r = np.zeros(len(m.params))
                    for k, v in w.items():
                        r[list(m.params.index).index(k)] = v
                    tt = m.t_test(r)
                    est, ep = float(tt.effect[0]), float(tt.sd[0][0])
                    linhas.append({"y": y, "eleicao": t, "spec": spec, "contraste": nome, "beta_pp": est, "ep": ep,
                                   "p": float(tt.pvalue), "ic_inf": est - 1.96 * ep, "ic_sup": est + 1.96 * ep,
                                   "n": int(m.nobs), "dp_pct_1991": dd["pct_coorte_1991"].std(),
                                   "dp_pct_1970_1990": dd["pct_coorte_1970_1990"].std()})
    return pd.DataFrame(linhas)


def comparar_censo(e: pd.DataFrame) -> pd.DataFrame:
    """Correlação, por AMC, entre as coortes do TSE (2010, 2022) e as do Censo (adultos 18+)."""
    from src.coortes import coortes_amc
    c = coortes_amc().rename(columns={"ano_censo": "eleicao"})
    m = e[["id_amc", "eleicao"] + COORTES].merge(c[["id_amc", "eleicao"] + COORTES], on=["id_amc", "eleicao"],
                                                 suffixes=("_tse", "_censo"))
    return pd.DataFrame([{"eleicao": t, "coorte": ROT[k], "corr": g[f"{k}_tse"].corr(g[f"{k}_censo"]),
                          "media_tse": g[f"{k}_tse"].mean(), "media_censo": g[f"{k}_censo"].mean()}
                         for t, g in m.groupby("eleicao") for k in COORTES])


# ---------------------------------------------------------------- figuras
def fig_jovens(nac: pd.DataFrame, q: pd.DataFrame) -> None:
    fig, axs = plt.subplots(1, 3, figsize=(14, 4.6))
    ax = axs[0]
    ax.bar(nac["eleicao"], nac["n_nascidos 1991+"] / 1e6, width=2.6, color=COR["tinta2"])
    for x, n, p in zip(nac["eleicao"], nac["n_nascidos 1991+"] / 1e6, nac["% nascidos 1991+"]):
        ax.text(x, n + 0.8, f"{n:.1f} mi\n({p:.0f}%)", ha="center", va="bottom", fontsize=8)
    ax.set_title("Eleitores nascidos a partir de 1991 (milhões)", fontsize=10, loc="left")
    ax.set_xticks(nac["eleicao"])
    ax.set_ylim(0, nac["n_nascidos 1991+"].max() / 1e6 * 1.3)
    # dentro da UF sem ponderação: com peso, as capitais (menos jovens de cada UF, no Q1) dominam a média
    for k, (tipo, tit, col) in enumerate([
            ("quintil nacional", "s_PT por quintil de % nascidos 1991+\n(Brasil; média ponderada)", "s_pt"),
            ("quintil dentro da UF", "s_PT por quintil de % nascidos 1991+\n(dentro da UF; média simples das AMCs)",
             "s_pt_nao_pond")]):
        ax = axs[k + 1]
        g = q[q["tipo"] == tipo]
        for qq, cor, lw in [(1, COR["neutro"], 2), (3, "#8a8880", 1.2), (5, COR["tinta"], 2)]:
            s = g[g["quintil"] == qq].sort_values("eleicao")
            ax.plot(s["eleicao"], s[col], marker="o", color=cor, lw=lw, ms=5,
                    label={1: "Q1 (menos jovens)", 3: "Q3", 5: "Q5 (mais jovens)"}[qq])
        ax.set_title(tit, fontsize=10, loc="left")
        ax.set_xticks(sorted(g["eleicao"].unique()))
        ax.set_ylabel("s_PT (% válidos)" if k == 0 else "")
        ax.legend(frameon=False, fontsize=8)
    for ax in axs:
        ax.grid(axis="y", color="#e5e5e5")
        ax.set_axisbelow(True)
        for s in ["top", "right"]:
            ax.spines[s].set_visible(False)
    M._salvar_fig(fig, "extra_tse_coortes_jovens", FONTE)


def fig_betas(r: pd.DataFrame) -> None:
    ys = {"s_pt": "s_PT presidencial", "p_ANTI": "p_ANTI (Câmara)"}
    fig, axs = plt.subplots(len(CONTRASTES), len(ys), figsize=(11, 8), sharex=True)
    for i, c in enumerate(CONTRASTES):
        for j, (y, ty) in enumerate(ys.items()):
            ax = axs[i, j]
            cor = COR["PT"] if y == "s_pt" else COR["OP"]
            for k, (filtro, mk) in enumerate([("só EF de UF", "o"), ("+ controles", "s")]):
                g = r[(r["y"] == y) & (r["contraste"] == c) & r["spec"].str.startswith(filtro)].sort_values("eleicao")
                ax.errorbar(g["eleicao"] + (k - 0.5) * 0.6, g["beta_pp"], yerr=1.96 * g["ep"], fmt=mk, ms=5,
                            color=cor, lw=1.2, mfc=cor if k else "white", label=filtro)
            ax.axhline(0, color="#999", lw=0.8)
            ax.set_xticks(sorted(r["eleicao"].unique()), [str(a)[2:] for a in sorted(r["eleicao"].unique())])
            ax.grid(axis="y", color="#e5e5e5")
            for s in ["top", "right"]:
                ax.spines[s].set_visible(False)
            if i == 0:
                ax.set_title(ty, fontsize=10, loc="left")
            if j == 0:
                ax.set_ylabel(f"{c}\n(p.p. de y por 1 p.p. do eleitorado)", fontsize=9)
    axs[0, 0].legend(frameon=False, fontsize=8)
    fig.suptitle("Coortes do eleitorado e voto, por eleição (WLS, EF de UF; IC 95%, erros por microrregião)",
                 fontsize=11, x=0.01, ha="left")
    M._salvar_fig(fig, "extra_tse_coortes_betas", FONTE + " Controles: spec. A da Fase 6 (2018: spec. B).")


def main() -> None:
    e = base()
    nac = nacional()
    M._salvar_tab(nac, "extra_tse_coortes_nacional")
    q = quintis(e)
    M._salvar_tab(q, "extra_tse_coortes_quintis_1991")
    M._salvar_tab(q5_menos_q1(q), "extra_tse_coortes_q5_menos_q1")
    r = regressoes(e)
    M._salvar_tab(r, "extra_tse_coortes_regressoes")
    M._salvar_tab(comparar_censo(e), "extra_tse_coortes_vs_censo")
    fig_jovens(nac, q)
    fig_betas(r)
    log.info("coortes TSE concluído")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    main()
