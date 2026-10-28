"""Teste extra (fora do PLANO): o antipetismo se concentra nos municípios com mais adultos nascidos
entre 1970 e 1990?

Dados: coortes de nascimento entre os adultos (18+) dos Censos 2010 e 2022 (src/ingest/ibge_idade.py),
ligadas às eleições como o resto do Censo (config.yaml, alinhamento.censo: 2010 → 2006–2014,
2022 → 2022–2026; 2018 fica de fora).

1. Descritiva:
   - coortes por grupo de swing (G_PT / G_EST / G_OP) e por quintil de s_PT em 2026;
   - "perfil etário relativo" de cada AMC no Censo 2022 = a coorte cuja participação está mais acima da
     média das AMCs, em desvios-padrão (z máximo). Quase nenhuma AMC tem maioria absoluta de nascidos em
     1970–1990 (2 de 5.570), por isso a comparação é relativa;
   - s_PT 2026, swing 2010→2026 e p_ANTI 2026 por perfil, no Brasil e por região.
2. Regressões (WLS por aptos, EF de UF, erros agrupados por microrregião), por eleição:
   y ∈ {s_pt, p_ANTI, hiato_lulista} ~ % 1991+ + % 1970–1990 (em p.p.; base: % até 1969), com e sem
   as covariáveis da spec. A da Fase 6 (X_A, em z). As três participações somam 100, então cada
   contraste = efeito de transferir 1 p.p. dos adultos de uma coorte para outra:
   - "1970–90 vs. até 1969" = β(% 1970–1990);
   - "1970–90 vs. 1991+"    = β(% 1970–1990) − β(% 1991+);
   - "1991+ vs. até 1969"   = β(% 1991+).
   Em 2010, "1991+" são só os de 18–19 anos (≈ 5% dos adultos): o contraste com 1991+ é impreciso.
3. Diferenças longas: swing 2010→2026 ~ coortes do Censo 2010 (a coorte de 1970–1990 tinha 20–39 anos)
   + X_A de 2010 + EF de UF.
Leitura ecológica: municípios com mais adultos de uma coorte, não eleitores dessa coorte.

Saídas: outputs/tables/extra_coortes_*.csv/.md e outputs/figures/extra_coortes_*.png/.svg
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

log = logging.getLogger("coortes")
COORTES = ["pct_coorte_1991", "pct_coorte_1970_1990", "pct_coorte_ate1969"]
ROT = {"pct_coorte_1991": "nascidos 1991+", "pct_coorte_1970_1990": "nascidos 1970–1990",
       "pct_coorte_ate1969": "nascidos até 1969"}
PERFIS = ["perfil 1991+", "perfil 1970–1990", "perfil até 1969"]
FONTE = ("Fonte: TSE (2º turno presidencial e deputado federal 2006–2026); IBGE (Censos 2010 e 2022, "
         "idade simples, tabelas 1378 e 9514). Unidade: AMC.")


def coortes_amc() -> pd.DataFrame:
    """Coortes por AMC e ano do Censo: média ponderada pela população de 18+."""
    d = pd.read_parquet(caminho("interim") / "ibge_idade.parquet")
    amc = {int(k): int(v) for k, v in config()["amc"].items()}
    d["id_amc"] = d["id_municipio"].map(lambda c: amc.get(c, c))
    cols = COORTES + ["idade_mediana_18mais"]
    num = d[cols].mul(d["pop_18mais"], axis=0).groupby([d["id_amc"], d["ano"]]).sum()
    den = d.groupby(["id_amc", "ano"])["pop_18mais"].sum()
    out = num.div(den, axis=0)
    out["pop_18mais"] = den
    return out.reset_index().rename(columns={"ano": "ano_censo"})


def base() -> pd.DataFrame:
    e = M.carregar()
    ref = config()["alinhamento"]["censo"]
    e["ano_censo"] = e["eleicao"].map(ref)
    e = e.merge(coortes_amc(), on=["id_amc", "ano_censo"], how="left")
    return e


def perfil_relativo(c22: pd.DataFrame) -> pd.Series:
    z = (c22[COORTES] - c22[COORTES].mean()) / c22[COORTES].std()
    return z.idxmax(axis=1).map(dict(zip(COORTES, PERFIS)))


# ---------------------------------------------------------------- 1. descritiva
def _media_pond(g: pd.DataFrame, col: str, peso: str = "aptos") -> float:
    ok = g[col].notna()
    return np.average(g.loc[ok, col], weights=g.loc[ok, peso]) if ok.any() else np.nan


def descritiva(e: pd.DataFrame) -> dict[str, pd.DataFrame]:
    f = config()["ano_final"]
    d = e[e["eleicao"] == f].copy()
    d["perfil"] = perfil_relativo(d)
    # `swing` (2010→2026, Fase 2) já está no painel
    out = {}
    # coortes (Censo 2022) por grupo de swing: mediana e média ponderada por aptos
    linhas = []
    for g, gg in d.groupby("g_swing"):
        for c in COORTES + ["idade_mediana_18mais"]:
            linhas.append({"grupo": g, "indicador": ROT.get(c, "idade mediana (18+)"), "mediana": gg[c].median(),
                           "media_pond_aptos": _media_pond(gg, c), "n_amc": len(gg)})
    out["por_grupo"] = pd.DataFrame(linhas)
    # por quintil de s_PT 2026 (ponderado não; quintis de AMCs)
    d["quintil_s_pt"] = pd.qcut(d["s_pt"], 5, labels=["Q1 (mais opositor)", "Q2", "Q3", "Q4", "Q5 (mais lulista)"])
    q = d.groupby("quintil_s_pt", observed=True)
    out["por_quintil"] = pd.DataFrame({
        "s_pt_mediano": q["s_pt"].median(),
        **{ROT[c]: q[c].median() for c in COORTES},
        "idade_mediana_18mais": q["idade_mediana_18mais"].median(), "n_amc": q.size()}).reset_index()
    # por perfil relativo, Brasil e regiões
    linhas = []
    for reg, dr in [("Brasil", d)] + list(d.groupby("regiao")):
        for p in PERFIS:
            g = dr[dr["perfil"] == p]
            if g.empty:
                continue
            linhas.append({"regiao": reg, "perfil": p, "n_amc": len(g),
                           "pct_eleitorado": 100 * g["aptos"].sum() / dr["aptos"].sum(),
                           "s_pt_2026": _media_pond(g, "s_pt"), "swing_2010_2026": _media_pond(g, "swing"),
                           "p_ANTI_2026": _media_pond(g, "p_ANTI"),
                           "pct_G_PT": 100 * (g["g_swing"] == "G_PT").mean(),
                           "pct_G_OP": 100 * (g["g_swing"] == "G_OP").mean()})
    out["por_perfil"] = pd.DataFrame(linhas)
    out["_base"] = d
    return out


# ---------------------------------------------------------------- 2. regressões por eleição
def regressoes(e: pd.DataFrame) -> pd.DataFrame:
    z = M.padronizar(e, M.X_A + ["nep"])
    for c in COORTES:  # coortes em p.p. (não padronizadas)
        z[c] = e[c]
    linhas = []
    for y in ["s_pt", "p_ANTI", "hiato_lulista"]:
        for t, d in z.groupby("eleicao"):
            if config()["alinhamento"]["censo"][t] is None:
                continue
            for spec, xs in [("só EF de UF", []), ("+ covariáveis spec. A", M.X_A)]:
                extra = ["nep"] if y == "hiato_lulista" else []
                cols = ["pct_coorte_1991", "pct_coorte_1970_1990"] + xs + extra
                dd = d.dropna(subset=[y] + cols + ["aptos", "id_microrregiao"])
                ctrl = " + ideb_ausente" if xs else ""
                m = M._wls(f"{y} ~ {' + '.join(cols)}{ctrl} + C(sg_uf)", dd)
                # contrastes da coorte do meio (por 1 p.p. transferido)
                for nome, w in [("1970–90 vs. até 1969", {"pct_coorte_1970_1990": 1}),
                                ("1970–90 vs. 1991+", {"pct_coorte_1970_1990": 1, "pct_coorte_1991": -1}),
                                ("1991+ vs. até 1969", {"pct_coorte_1991": 1})]:
                    r = np.zeros(len(m.params))
                    for k, v in w.items():
                        r[list(m.params.index).index(k)] = v
                    tt = m.t_test(r)
                    est, ep = float(tt.effect[0]), float(tt.sd[0][0])
                    linhas.append({"y": y, "eleicao": t, "spec": spec, "contraste": nome, "beta_pp": est,
                                   "ep": ep, "p": float(tt.pvalue), "ic_inf": est - 1.96 * ep,
                                   "ic_sup": est + 1.96 * ep, "n": int(m.nobs), "r2": m.rsquared})
    return pd.DataFrame(linhas)


def diferencas_longas_coortes(e: pd.DataFrame) -> pd.DataFrame:
    dl = M.base_longa(e)
    b = config()["ano_base"]
    c10 = e[e["eleicao"] == b].set_index("id_amc")[COORTES]
    dl = dl.join(c10, on="id_amc")
    linhas = []
    for spec, xs in [("só EF de UF", []), ("+ níveis e mudanças (Fase 6)", None)]:
        if xs is None:
            xs = [f"{v}_0" for v in M.X_A] + [f"d_{v}" for v in M.X_A] + ["ideb_ausente"]
        cols = ["pct_coorte_1991", "pct_coorte_1970_1990"] + xs
        dd = dl.dropna(subset=["swing"] + cols)
        m = M._wls(f"swing ~ {' + '.join(cols)} + C(sg_uf)", dd)
        for nome, w in [("1970–90 vs. até 1969", {"pct_coorte_1970_1990": 1}),
                        ("1970–90 vs. 1991+", {"pct_coorte_1970_1990": 1, "pct_coorte_1991": -1})]:
            r = np.zeros(len(m.params))
            for k, v in w.items():
                r[list(m.params.index).index(k)] = v
            tt = m.t_test(r)
            est, ep = float(tt.effect[0]), float(tt.sd[0][0])
            linhas.append({"y": "swing 2010→2026 (coortes do Censo 2010)", "spec": spec, "contraste": nome,
                           "beta_pp": est, "ep": ep, "p": float(tt.pvalue), "n": int(m.nobs), "r2": m.rsquared})
    return pd.DataFrame(linhas)


# ---------------------------------------------------------------- figuras
def fig_perfis(pp: pd.DataFrame) -> None:
    """Small multiples: s_PT 2026 e swing por perfil etário relativo, Brasil e regiões."""
    regs = ["Brasil", "Norte", "Nordeste", "Sudeste", "Sul", "Centro-Oeste"]
    # categorias ordenadas (idade): uma rampa de cinza, do mais jovem (claro) ao mais velho (escuro)
    cores = {"perfil 1991+": COR["neutro"], "perfil 1970–1990": "#8a8880", "perfil até 1969": COR["tinta2"]}
    fig, axs = plt.subplots(1, 2, figsize=(12, 5.2), sharey=True)
    for ax, col, tit in [(axs[0], "s_pt_2026", "s_PT 2026 (% válidos, média ponderada)"),
                         (axs[1], "swing_2010_2026", "Swing relativo 2010→2026 (p.p.)")]:
        y = np.arange(len(regs))
        for k, p in enumerate(PERFIS):
            v = pp[pp["perfil"] == p].set_index("regiao").reindex(regs)[col]
            ax.barh(y + (k - 1) * 0.26, v, height=0.24, color=cores[p], label=p)
        ax.set_yticks(y, regs)
        ax.axvline(0 if col.startswith("swing") else 50, color="#999", lw=0.8)
        ax.set_title(tit, fontsize=10, loc="left")
        ax.grid(axis="x", color="#e5e5e5")
        ax.set_axisbelow(True)
        for s in ["top", "right"]:
            ax.spines[s].set_visible(False)
    axs[0].invert_yaxis()  # eixo y compartilhado: inverter uma vez só
    fig.legend(*axs[0].get_legend_handles_labels(), frameon=False, fontsize=9, ncol=3, loc="upper right")
    fig.suptitle("Perfil etário relativo da AMC (Censo 2022: coorte com participação mais acima da média)",
                 fontsize=11, x=0.01, ha="left")
    M._salvar_fig(fig, "extra_coortes_perfis", FONTE)


def fig_betas(r: pd.DataFrame, dl: pd.DataFrame) -> None:
    contr = ["1970–90 vs. até 1969", "1970–90 vs. 1991+"]
    ys = {"s_pt": "s_PT presidencial", "p_ANTI": "p_ANTI (Câmara)", "hiato_lulista": "hiato lulista"}
    fig, axs = plt.subplots(len(contr), len(ys), figsize=(13, 6.5), sharex=True)
    for i, c in enumerate(contr):
        for j, (y, ty) in enumerate(ys.items()):
            ax = axs[i, j]
            for k, (spec, mk) in enumerate([("só EF de UF", "o"), ("+ covariáveis spec. A", "s")]):
                g = r[(r["y"] == y) & (r["contraste"] == c) & (r["spec"] == spec)].sort_values("eleicao")
                x = g["eleicao"] + (k - 0.5) * 0.6
                cor = COR["PT"] if y != "p_ANTI" else COR["OP"]
                ax.errorbar(x, g["beta_pp"], yerr=1.96 * g["ep"], fmt=mk, ms=5, color=cor, lw=1.2,
                            mfc=cor if k else "white", label=spec)
            ax.axhline(0, color="#999", lw=0.8)
            ax.set_xticks([2006, 2010, 2014, 2022, 2026], ["06", "10", "14", "22", "26"])
            ax.grid(axis="y", color="#e5e5e5")
            for s in ["top", "right"]:
                ax.spines[s].set_visible(False)
            if i == 0:
                ax.set_title(ty, fontsize=10, loc="left")
            if j == 0:
                ax.set_ylabel(f"{c}\n(p.p. de y por 1 p.p. de adultos)", fontsize=9)
    axs[0, 0].legend(frameon=False, fontsize=8)
    fig.suptitle("Coorte de 1970–1990 e voto, por eleição (WLS, EF de UF; IC 95%, erros por microrregião)",
                 fontsize=11, x=0.01, ha="left")
    M._salvar_fig(fig, "extra_coortes_betas", FONTE + " Censo 2010 para 2006–2014; Censo 2022 para 2022–2026.")


def main() -> None:
    e = base()
    desc = descritiva(e)
    for k in ["por_grupo", "por_quintil", "por_perfil"]:
        M._salvar_tab(desc[k], f"extra_coortes_{k}")
    r = regressoes(e)
    M._salvar_tab(r, "extra_coortes_regressoes")
    dl = diferencas_longas_coortes(e)
    M._salvar_tab(dl, "extra_coortes_diferencas_longas")
    fig_perfis(desc["por_perfil"])
    fig_betas(r, dl)
    log.info("teste de coortes concluído")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    main()
