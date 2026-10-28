"""Fase 7 (robustez) — docs/planos/PLANO.md, seção 5, itens (a)–(i).

Estimativas centrais acompanhadas em todas as especificações:
  E1  Δβ (ano final − ano base) do voto presidencial s_pt: % evangélica, % negra, % VAB adm. pública,
      Bolsa Família por 100 hab., log população (modelo empilhado com interações; teste de igualdade da Fase 6).
  E2  Δθ do hiato_lulista (com NEP): % VAB adm. pública, % evangélica, log população.
  E3  Diferenças longas (swing ~ X_base + ΔX + EF UF): % evangélica, % VAB adm. pública, Bolsa Família
      e Ideb no ano base.
  E4  Logit multinomial: efeito marginal médio sobre P(G_PT) de % evangélica e % VAB adm. pública no ano base.
  E5  Δβ do voto do PT na Câmara (p_PT): % negra, % evangélica.

Especificações:
  principal              — Fase 6 (base 2010, final 2026, WLS por aptos, todas as AMCs)
  (a) limiar ±0,5 DP / quintis / tercis — só E4 (grupos)
  (b) sem ponderação     — aptos = 1
  (c) sem capitais
  (d) sem AMCs < 5 mil habitantes (população de 2010)
  (e) base 2006          — Δ 2026 − 2006; diferenças longas e grupos recalculados a partir de 2006
  (f) final 2022         — Δ 2022 − 2010; diferenças longas e grupos recalculados até 2022
  (g) federação          — E2 com hiato_lulista_fed; E5 com p_PT_fed
  (h) sem dependência de puxador — exclui AMCs com dependencia_puxador_PT na base ou no final (E2, E5)
  (i) só legenda         — E5 com leg_PT no lugar de p_PT
Nas especificações que recalculam grupos ((e), (f)), G_PT/G_OP = swing ≥ +1 DP / ≤ −1 DP do novo swing.

Saídas: outputs/tables/fase7_robustez.csv/.md e outputs/figures/fase7_robustez.png/.svg
"""

from __future__ import annotations

import logging
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src import models as M  # noqa: E402
from src.mapas import COR  # noqa: E402
from src.utils import caminho, config  # noqa: E402

log = logging.getLogger("robustness")
warnings.filterwarnings("ignore")

E1_VARS = ["pct_evangelica", "pct_negra", "part_vab_adm_publica", "pbf_100hab", "pct_informal", "log_pop"]
E2_VARS = ["part_vab_adm_publica", "pct_evangelica", "log_pop"]
E3_VARS = ["pct_evangelica_0", "part_vab_adm_publica_0", "pbf_100hab_0", "pct_informal_0", "ideb_0"]
E4_VARS = ["pct_evangelica_0", "part_vab_adm_publica_0"]
E5_VARS = ["pct_negra", "pct_evangelica"]
FAMILIA = {"E1": "Δβ voto presidencial PT", "E2": "Δθ hiato lulista", "E3": "Diferenças longas (nível base)",
           "E4": "AME sobre P(G_PT)", "E5": "Δβ voto PT na Câmara"}


def _linhas(df: pd.DataFrame, spec: str, fam: str, col_v: str, col_est: str, col_ep: str, col_p: str, vars_):
    d = df[df[col_v].isin(vars_)]
    return [{"spec": spec, "familia": fam, "variavel": r[col_v], "estimativa": r[col_est], "ep": r[col_ep],
             "p": r[col_p]} for _, r in d.iterrows()]


def _grupos_do_swing(dl: pd.DataFrame) -> pd.DataFrame:
    dp = dl["swing"].std()
    dl = dl.copy()
    dl["g_novo"] = np.select([dl["swing"] >= dp, dl["swing"] <= -dp], ["G_PT", "G_OP"], "G_EST")
    return dl


def estimar(e: pd.DataFrame, z: pd.DataFrame, spec: str, b: int, f: int, *, ids=None, sem_peso=False,
            col_grupo="g_swing", recalcular_grupo=False, y_hiato="hiato_lulista", y_camara="p_PT",
            familias=("E1", "E2", "E3", "E4", "E5")) -> list[dict]:
    zz, ee = z, e
    if ids is not None:
        zz, ee = z[z["id_amc"].isin(ids)], e[e["id_amc"].isin(ids)]
    if sem_peso:
        zz, ee = zz.assign(aptos=1.0), ee.assign(aptos=1.0)
    out = []
    if "E1" in familias:
        t = M.teste_igualdade(zz, "s_pt", b, f)
        out += _linhas(t, spec, "E1", "variavel", "dif_beta", "ep", "p", E1_VARS)
    if "E2" in familias:
        t = M.teste_igualdade(zz, y_hiato, b, f, extra=["nep"])
        out += _linhas(t, spec, "E2", "variavel", "dif_beta", "ep", "p", E2_VARS)
    if "E5" in familias:
        t = M.teste_igualdade(zz, y_camara, b, f)
        out += _linhas(t, spec, "E5", "variavel", "dif_beta", "ep", "p", E5_VARS)
    if "E3" in familias or "E4" in familias:
        dl = M.base_longa(ee, b, f)
        if "E3" in familias:
            r = M.diferencas_longas(dl)
            out += _linhas(r, spec, "E3", "termo", "coef", "ep", "p", E3_VARS)
        if "E4" in familias:
            col = col_grupo
            if recalcular_grupo:
                dl, col = _grupos_do_swing(dl), "g_novo"
            a = M.logit_grupos(dl, col)
            a = a[a["resultado"] == "G_PT"]
            out += _linhas(a, spec, "E4", "termo", "ame", "ep", "p", E4_VARS)
    log.info("robustez: %s", spec)
    return out


def main() -> None:
    cfg = config()
    b, f = cfg["ano_base"], cfg["ano_final"]
    e = M.carregar()
    z = M.padronizar(e, M.X_A + ["nep"])
    todos = set(e["id_amc"])
    capitais = set(e.loc[e["capital"], "id_amc"])
    pequenos = set(e.loc[(e["eleicao"] == b) & (e["pop"] < 5000), "id_amc"])
    pux = e[e["eleicao"].isin([b, f]) & e["dependencia_puxador_PT"].fillna(False).astype(bool)]["id_amc"]

    linhas = []
    linhas += estimar(e, z, "principal", b, f)
    for col, rot in [("g_swing_dp05", "(a) ±0,5 DP"), ("g_swing_q5", "(a) quintis"), ("g_swing_t3", "(a) tercis")]:
        linhas += estimar(e, z, rot, b, f, col_grupo=col, familias=("E4",))
    linhas += estimar(e, z, "(b) sem ponderação", b, f, sem_peso=True)
    linhas += estimar(e, z, "(c) sem capitais", b, f, ids=todos - capitais)
    linhas += estimar(e, z, "(d) sem AMCs < 5 mil hab.", b, f, ids=todos - pequenos)
    linhas += estimar(e, z, "(e) base 2006", 2006, f, recalcular_grupo=True)
    linhas += estimar(e, z, "(f) final 2022", b, 2022, recalcular_grupo=True)
    linhas += estimar(e, z, "(g) federação", b, f, y_hiato="hiato_lulista_fed", y_camara="p_PT_fed",
                      familias=("E2", "E5"))
    linhas += estimar(e, z, "(h) sem dependência de puxador", b, f, ids=todos - set(pux), familias=("E2", "E5"))
    linhas += estimar(e, z, "(i) só legenda", b, f, y_camara="leg_PT", familias=("E5",))

    rb = pd.DataFrame(linhas)
    rb["ic_inf"] = rb["estimativa"] - 1.96 * rb["ep"]
    rb["ic_sup"] = rb["estimativa"] + 1.96 * rb["ep"]
    princ = rb[rb["spec"] == "principal"].set_index(["familia", "variavel"])["estimativa"]
    rb["mesmo_sinal_que_principal"] = [np.sign(r.estimativa) == np.sign(princ.get((r.familia, r.variavel), np.nan))
                                       for r in rb.itertuples()]
    rb["n_excluidas"] = rb["spec"].map({"(c) sem capitais": len(capitais), "(d) sem AMCs < 5 mil hab.": len(pequenos),
                                        "(h) sem dependência de puxador": pux.nunique()})
    rb.to_csv(caminho("tables") / "fase7_robustez.csv", index=False, encoding="utf-8")
    (caminho("tables") / "fase7_robustez.md").write_text(rb.to_markdown(index=False, floatfmt=".3g"), encoding="utf-8")
    fig_robustez(rb)


def fig_robustez(rb: pd.DataFrame) -> None:
    paineis = [(fam, v) for fam, vs in [("E1", E1_VARS), ("E2", E2_VARS), ("E3", E3_VARS), ("E4", E4_VARS), ("E5", E5_VARS)]
               for v in vs]
    specs = list(dict.fromkeys(rb["spec"]))
    nlin = -(-len(paineis) // 5)
    fig, axs = plt.subplots(nlin, 5, figsize=(19, 4 * nlin), sharey=True)
    y = np.arange(len(specs))
    for ax, (fam, v) in zip(axs.flat, paineis):
        d = rb[(rb["familia"] == fam) & (rb["variavel"] == v)].set_index("spec").reindex(specs)
        ax.axvline(0, color="#c3c2b7", linewidth=1)
        p0 = d.loc["principal", "estimativa"]
        ax.axvline(p0, color=COR["PT"], linewidth=0.8, linestyle="--")
        ax.hlines(y, d["ic_inf"], d["ic_sup"], color=COR["tinta2"], linewidth=1.3)
        cor = [COR["PT"] if s == "principal" else COR["tinta"] for s in specs]
        ax.scatter(d["estimativa"], y, color=cor, s=22, zorder=3)
        nome = M.ROTULO.get(v.removesuffix("_0"), v)
        ax.set_title(f"{FAMILIA[fam]}\n{nome}", fontsize=8.5, loc="left")
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.grid(axis="x", color="#e1e0d9", linewidth=0.5)
        ax.tick_params(labelsize=8, colors=COR["tinta2"])
    for ax in list(axs.flat)[len(paineis):]:
        ax.set_visible(False)
    for ax in axs[:, 0]:
        ax.set_yticks(y)
        ax.set_yticklabels(specs, fontsize=8)
        ax.invert_yaxis()
    fig.suptitle("Robustez das estimativas centrais (ponto e IC 95%; linha tracejada = especificação principal)\n"
                 "linhas vazias = especificação não se aplica àquela estimativa", fontsize=11, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.02, 1, 0.95))
    fig.text(0.01, 0.005, "Fonte: TSE; IBGE; INEP; MDS (via Ipeadata); Comex Stat. Eleições 2006–2026. Erros agrupados por microrregião (E1–E3, E5); delta method (E4).",
             fontsize=7, color=COR["tinta2"])
    for ext in ["png", "svg"]:
        fig.savefig(caminho("figures") / f"fase7_robustez.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
