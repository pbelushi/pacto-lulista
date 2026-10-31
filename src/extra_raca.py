"""Extra raça: decompõe o efeito racial entre os turnos de 2026 em pretos e pardos (docs/planos/prompt_raca_margem.md).

Hipóteses: R1 (no Δ Lula de 2026, % preta > % parda; em 2022, nenhuma se destaca), R2 (o efeito de % preta cresce com
% superior), R3 (cresce com % jovens), R4 (a queda do gradiente racial no nível entre 2010 e 2026 vem de % parda).

Fase A: sigilo, cobertura, descritivas. Entorno: src/extra_raca_entorno.py. AMC: pct_preta e pct_parda do painel
(Censos 2010 e 2022, regras de config.yaml); % superior de adultos do Censo 2022 (SIDRA 10061); % eleitores de 16 a 34
do perfil do TSE. Locais: pct_superior e pct_jovens_16_34 do perfil do eleitorado TSE.
Fase B: Δ Lula em p.p. dos aptos por 1 DP, como extra_entre_turnos.modelo: peso = aptos; EF de UF e EP por microrregião
(AMC), EF e EP de município (locais); controles de voto disponível. Como os DP de % preta e % parda são muito
diferentes, os coeficientes e o teste de igualdade saem nas duas unidades: por 1 DP e por 1 p.p.
Interações: variáveis centradas (z); efeito marginal de % preta na média do 1º e do 4º quartil do moderador.
Fase C: s_pt no 2º turno, spec. A da Fase 6 (2010, 2014, 2022, 2026), por AMC; e por local, 2010–2026, EF município × ano,
com o Censo 2022 em todos os anos.

Saídas: outputs/tables/extra_raca_*; figuras extra_raca_coeficientes e extra_raca_interacoes.

Uso: python -m src.extra_raca [a] [b] [c]   (sem argumentos: as três fases)
"""

from __future__ import annotations

import logging
import sys

import matplotlib

matplotlib.use("Agg")
import geopandas as gpd  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src import models as M  # noqa: E402
from src.build_panel import _amc_map  # noqa: E402
from src.extra_entre_turnos import DISPONIVEL, X_MOD, amc  # noqa: E402
from src.extra_raca_entorno import setores_raca  # noqa: E402
from src.mapas import COR  # noqa: E402
from src.pacto20_base import CHAVE  # noqa: E402
from src.pacto20_modelos import _comb, _fit, dados  # noqa: E402
from src.utils import caminho, config  # noqa: E402

log = logging.getLogger("extra_raca")
FONTE = "Fonte: TSE; IBGE, Censos 2010 e 2022; Comex Stat; INEP. Elaboração própria."
X_AMC = [x for x in X_MOD if x != "pct_negra"]
X_LOC = ["jovens", "log_renda", "log_dens"]
DISP_LOC = ["terceiros", "abst"]
REGIAO = {1: "Norte", 2: "Nordeste", 3: "Sudeste", 4: "Sul", 5: "Centro-Oeste"}
ELEICOES_C = [2010, 2014, 2022, 2026]
ANOS_LOC = [2010, 2014, 2018, 2022, 2026]
DESFECHOS = {"d_lula": "Δ Lula", "d_comp": "Δ comparecimento", "captura": "Taxa de captura", "d_op": "Δ Flávio Bolsonaro / opositor"}


def _salvar(df: pd.DataFrame, nome: str, nota: str = "") -> None:
    df.to_csv(caminho("tables") / f"{nome}.csv", index=False, encoding="utf-8")
    md = df.to_markdown(index=False, floatfmt=".3g") + (f"\n\n{nota}" if nota else "") + f"\n\n{FONTE}\n"
    (caminho("tables") / f"{nome}.md").write_text(md, encoding="utf-8")
    log.info("tabela %s (%d linhas)", nome, len(df))


def _zs(d: pd.DataFrame, cols: list[str]) -> tuple[pd.DataFrame, dict]:
    z, dp = d.copy(), {}
    for c in cols:
        dp[c] = d[c].std()
        z[c] = (d[c] - d[c].mean()) / dp[c]
    return z, dp


def _comb_sm(m, pesos: dict) -> tuple[float, float, float]:
    a = np.zeros(len(m.params))
    for k, v in pesos.items():
        a[list(m.params.index).index(k)] = v
    t = m.t_test(a)
    return float(np.squeeze(t.effect)), float(np.squeeze(t.sd)), float(np.squeeze(t.pvalue))


def comb(m, pesos: dict) -> tuple[float, float, float]:
    return _comb_sm(m, pesos) if hasattr(m, "t_test") and hasattr(m, "params") and not hasattr(m, "_coefnames") else _comb(m, pesos)


# ---------------------------------------------------------------- bases
def variaveis_amc() -> pd.DataFrame:
    """Por AMC: % superior de adultos e de pretos, pardos e brancos (Censo 2022)."""
    mapa = _amc_map()
    i = pd.read_parquet(caminho("interim") / "ibge_instrucao.parquet")
    g = i.assign(id_amc=i["id_municipio"].map(mapa)).drop(columns="id_municipio").groupby("id_amc").sum(min_count=1)
    out = pd.DataFrame({"pct_superior": 100 * g["superior_total"] / g["adultos_total"],
                        "pct_superior_preta": 100 * g["superior_preta"] / g["adultos_preta"],
                        "pct_superior_parda": 100 * g["superior_parda"] / g["adultos_parda"]})
    return out


def jovens_amc(ano: int) -> pd.Series:
    mapa = _amc_map()
    t = pd.read_parquet(caminho("interim") / "tse_perfil_idade.parquet")
    t = t[t["ano"] == ano].dropna(subset=["id_municipio"])
    t = t.assign(id_amc=t["id_municipio"].astype(int).map(mapa), j=(t["pct_16_24"] + t["pct_25_34"]) * t["eleitores"])
    g = t.groupby("id_amc")[["j", "eleitores"]].sum()
    return (g["j"] / g["eleitores"]).rename("pct_jovens")


def base_amc(ano: int, e: pd.DataFrame) -> pd.DataFrame:
    d = amc(ano, e).join(variaveis_amc()).join(jovens_amc(ano))
    rm = set(gpd.read_parquet(caminho("raw") / "geobr_regioes_metropolitanas_2018.parquet")["code_muni"].astype(int))
    d["metro"] = d["capital"].fillna(False).astype(bool) | d.index.isin(rm)
    return d.assign(aptos=d["peso"]).dropna(subset=X_MOD + DISPONIVEL + ["pct_preta", "pct_parda", "d_lula", "id_microrregiao"])


def base_locais(ano: int, raio: str = "vor", min_aptos: int = 100) -> pd.DataFrame:
    d = dados(ano)
    e = pd.read_parquet(caminho("interim") / f"extra_raca_entorno_{ano}.parquet").drop(columns=["ano", "id_municipio"])
    d = d.merge(e, on=CHAVE, how="inner")
    d = d[(d["aptos_t1"] >= min_aptos) & (d["aptos_t2"] >= min_aptos)].copy()
    op = config()["presidencial"][ano]["op"]
    cand = [c for c in d.columns if c.startswith("c_") and c.endswith("_t1") and c not in ("c_13_t1", f"c_{op}_t1")]
    d["terceiros"] = 100 * d[cand].sum(axis=1) / d["aptos_t1"]
    d["abst"] = 100 - d["comp_t1"]
    d["d_lula"], d["d_op"] = d["d_pt_apt"], d["d_op_apt"]
    d["captura"] = d["d_lula"] / (100 - d["pt_apt_t1"] - d["op_apt_t1"])
    if raio == "buf":
        d["pct_preta"], d["pct_parda"] = d["pct_preta_buf"], d["pct_parda_buf"]
    else:
        d["pct_preta"], d["pct_parda"] = d["pct_preta_vor"], d["pct_parda_vor"]
    d["metro"] = d["capital"].fillna(False).astype(bool) | d["rm"].fillna(False).astype(bool)
    return d.dropna(subset=["pct_preta", "pct_parda", "pct_superior", "terceiros", "abst"])


# ---------------------------------------------------------------- Fase A
def fase_a() -> None:
    st = setores_raca().drop(columns="geometry")
    # 14.008 setores da malha não têm linha na tabela de cor
    st[["preta_sigilo", "parda_sigilo"]] = st[["preta_sigilo", "parda_sigilo"]].fillna(False).astype(bool)
    amc_map = _amc_map()
    st["id_amc"] = st["id_municipio"].map(amc_map)
    pop = st["pop"].sum()
    sig = pd.DataFrame([{"cor": c, "setores_com_sigilo_pct": 100 * st[f"{c}_sigilo"].mean(),
                         "pop_em_setor_com_sigilo_pct": 100 * st.loc[st[f"{c}_sigilo"], "pop"].sum() / pop,
                         "pop_mediana_do_setor_com_sigilo": st.loc[st[f"{c}_sigilo"], "pop"].median(),
                         "pessoas_nos_setores": st[f"cor_{c}"].sum()} for c in ["preta", "parda"]])
    e = M.carregar()
    p22 = e[e["eleicao"] == 2022].set_index("id_amc")
    g = st.groupby("id_amc")[["cor_preta", "cor_parda", "cor_total", "pop"]].sum()
    g["pop_sigilo"] = st[st["preta_sigilo"]].groupby("id_amc")["pop"].sum()
    g = g.join(p22[["pct_preta", "pct_parda", "pop"]], rsuffix="_censo").fillna({"pop_sigilo": 0})
    g["set_preta"], g["set_parda"] = 100 * g["cor_preta"] / g["cor_total"], 100 * g["cor_parda"] / g["cor_total"]
    g["viés_preta"], g["viés_parda"] = g["set_preta"] - g["pct_preta"], g["set_parda"] - g["pct_parda"]
    g["quintil_pct_preta"] = pd.qcut(g["pct_preta"], 5, labels=[f"Q{i}" for i in range(1, 6)])
    q = g.groupby("quintil_pct_preta", observed=True).agg(
        pct_preta_censo=("pct_preta", "mean"), vies_preta_pp=("viés_preta", "mean"), vies_parda_pp=("viés_parda", "mean"),
        vies_preta_relativo_pct=("viés_preta", lambda s: 100 * s.mean() / g.loc[s.index, "pct_preta"].mean()),
        pop_setor_com_sigilo_pct=("pop_sigilo", lambda s: 100 * s.sum() / g.loc[s.index, "pop"].sum())).reset_index()
    t = pd.DataFrame([{"quintil_pct_preta": "todas as AMCs", "pct_preta_censo": g["pct_preta"].mean(), "vies_preta_pp": g["viés_preta"].mean(),
                       "vies_parda_pp": g["viés_parda"].mean(), "vies_preta_relativo_pct": 100 * g["viés_preta"].mean() / g["pct_preta"].mean(),
                       "pop_setor_com_sigilo_pct": 100 * g["pop_sigilo"].sum() / g["pop"].sum()}])
    corr = g[["set_preta", "pct_preta"]].corr().iloc[0, 1]
    sig["corr_amc_setores_x_censo"] = [corr, g[["set_parda", "pct_parda"]].corr().iloc[0, 1]]
    _salvar(sig, "extra_raca_sigilo", "Sigilo (X) por setor censitário; X conta como 0, como em pct_negra.")
    _salvar(pd.concat([q, t], ignore_index=True), "extra_raca_sigilo_quintil",
            "Viés = % nos setores somados por AMC − % do Censo por município, em p.p., por quintil de % preta da AMC.")
    cob = []
    for a in ANOS_LOC:
        if not (caminho("interim") / f"extra_raca_entorno_{a}.parquet").exists():
            continue
        d = base_locais(a)
        cob.append({"nivel": "locais", "ano": a, "n": len(d), "aptos": d["aptos_t2"].sum(),
                    **{c: 100 * d[c].notna().mean() for c in ["pct_preta", "pct_parda", "pct_superior", "pct_jovens_16_34"]}})
        v = d.assign(uf=d["id_municipio"] // 1_000_000)
        if a == 2026:
            loc26 = v
    for a in [2022, 2026]:
        d = base_amc(a, e)
        cob.append({"nivel": "AMC", "ano": a, "n": len(d), "aptos": d["aptos"].sum(), "pct_preta": 100 * d["pct_preta"].notna().mean(),
                    "pct_parda": 100 * d["pct_parda"].notna().mean(), "pct_superior": 100 * d["pct_superior"].notna().mean(),
                    "pct_jovens_16_34": 100 * d["pct_jovens"].notna().mean()})
    _salvar(pd.DataFrame(cob), "extra_raca_cobertura", "% de unidades com a variável, na base de cada nível.")
    p = base_amc(2026, e)
    a = loc26.groupby("id_municipio").apply(
        lambda x: pd.Series({"p": np.average(x["pct_preta"], weights=x["aptos_t2"]), "w": x["aptos_t2"].sum()}), include_groups=False)
    a = a.join(p[["pct_preta"]], how="inner")
    c_ = a[["p", "pct_preta"]].corr().iloc[0, 1]
    log.info("correlação %% preta entorno (média do município) × %% preta Censo: %.3f (%d municípios)", c_, len(a))
    reg = []
    for nome, d, w, pre, par in [("AMC", p, "aptos", "pct_preta", "pct_parda"), ("locais", loc26, "aptos_t2", "pct_preta", "pct_parda")]:
        r = d.assign(reg=(d.index if nome == "AMC" else d["id_municipio"]))
        r["reg"] = (pd.Series(r["reg"]).astype(int) // 1_000_000).map(REGIAO).values
        for k, x in r.groupby("reg"):
            reg.append({"nivel": nome, "regiao": k, "unidades": len(x), "pct_preta": np.average(x[pre], weights=x[w]),
                        "pct_parda": np.average(x[par], weights=x[w]), "dp_pct_preta": x[pre].std(), "dp_pct_parda": x[par].std(),
                        "corr_preta_parda": x[[pre, par]].corr().iloc[0, 1]})
    reg = pd.DataFrame(reg)
    reg["corr_entorno_amc_nacional"] = c_
    _salvar(reg, "extra_raca_regiao", "Médias ponderadas por aptos, 2026. corr_entorno_amc_nacional: % preta do entorno, média por município, × Censo.")


# ---------------------------------------------------------------- Fase B
def ajuste_amc(d: pd.DataFrame, y: str, extra: list[str] = ()):
    cols = X_AMC + ["pct_preta", "pct_parda"] + DISPONIVEL + list(extra)
    return M._wls(f"{y} ~ " + " + ".join(cols) + " + C(sg_uf)", d)


def ajuste_loc(d: pd.DataFrame, y: str, extra: list[str] = (), w: str | None = "aptos_t2"):
    cols = X_LOC + ["pct_preta", "pct_parda"] + DISP_LOC + list(extra)
    return _fit(f"{y} ~ " + " + ".join(cols), d, w=w)


def linha(m, dp: dict, **rot) -> dict:
    p, q = dp["pct_preta"], dp["pct_parda"]
    bp, ep, pp = comb(m, {"pct_preta": 1})
    bq, eq, pq = comb(m, {"pct_parda": 1})
    _, _, wdp = comb(m, {"pct_preta": 1, "pct_parda": -1})
    dif, epd, wpp = comb(m, {"pct_preta": 1 / p, "pct_parda": -1 / q})
    return {**rot, "beta_preta_dp": bp, "ep_preta": ep, "p_preta": pp, "beta_parda_dp": bq, "ep_parda": eq, "p_parda": pq,
            "wald_p_dp": wdp, "dp_preta": p, "dp_parda": q, "beta_preta_pp": bp / p, "beta_parda_pp": bq / q,
            "dif_pp": dif, "ep_dif_pp": epd, "wald_p_pp": wpp, "n": int(m.nobs) if hasattr(m, "nobs") else int(m._N)}


def _prep_amc(d: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    return _zs(d, X_AMC + ["pct_preta", "pct_parda"] + DISPONIVEL)


def _prep_loc(d: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    z, dp = _zs(d, ["pct_preta", "pct_parda", "terceiros", "abst"])
    return z, dp


def interacoes(z: pd.DataFrame, modo: str, moderador: str, rotulo: str, ano: int, base: str) -> tuple[dict, list[dict]]:
    z = z.dropna(subset=[moderador]).copy()
    bruto = z[moderador]
    z["mod"] = (bruto - bruto.mean()) / bruto.std()
    z["preta_x_mod"], z["parda_x_mod"] = z["pct_preta"] * z["mod"], z["pct_parda"] * z["mod"]
    extra = ["mod", "preta_x_mod", "parda_x_mod"]
    m = ajuste_amc(z, "d_lula", extra) if modo == "AMC" else ajuste_loc(z, "d_lula", extra)
    r = {"nivel": modo, "ano": ano, "moderador": rotulo, "base": base, "n": int(m.nobs) if modo == "AMC" else int(m._N)}
    for t, k in [("preta_x_mod", "preta"), ("parda_x_mod", "parda")]:
        r[f"inter_{k}"], r[f"ep_inter_{k}"], r[f"p_inter_{k}"] = comb(m, {t: 1})
    q = pd.qcut(z["mod"], 4, labels=False, duplicates="drop")
    mar = []
    for nome, grp in [("Q1", 0), ("Q4", q.max())]:
        v = z.loc[q == grp, "mod"].mean()
        for k, tt in [("preta", "pct_preta"), ("parda", "pct_parda")]:
            est, ep, p = comb(m, {tt: 1, f"{k}_x_mod": v})
            mar.append({"nivel": modo, "ano": ano, "moderador": rotulo, "quartil": nome, "cor": k, "valor_moderador": bruto[q == grp].mean(),
                        "efeito_dp": est, "ep": ep, "ic_inf": est - 1.96 * ep, "ic_sup": est + 1.96 * ep, "p": p})
    return r, mar


def fase_b() -> None:
    e = M.carregar()
    amcs = {a: base_amc(a, e) for a in [2022, 2026]}
    locs = {a: base_locais(a) for a in [2022, 2026]}
    r1, rob, inter, marg = [], [], [], []
    for a in [2022, 2026]:
        z, dp = _prep_amc(amcs[a])
        zl, dl = _prep_loc(locs[a])
        for y, rot in DESFECHOS.items():
            r1.append(linha(ajuste_amc(z, y), dp, nivel="AMC", ano=a, desfecho=rot))
            r1.append(linha(ajuste_loc(zl, y), dl, nivel="locais", ano=a, desfecho=rot))
        for mod, nome, n2 in [("pct_superior", "% superior", "pct_superior"), ("pct_jovens", "% jovens 16–34", "pct_jovens_16_34")]:
            for nivel, zz, mm in [("AMC", z, mod), ("locais", zl, n2)]:
                r, mg = interacoes(zz, nivel, mm, nome, a, "Censo 2022" if nivel == "AMC" and mod == "pct_superior" else "TSE")
                inter.append(r); marg += mg
        r, mg = interacoes(z, "AMC", "pct_superior_preta", "% superior entre pretos", a, "Censo 2022")
        inter.append(r); marg += mg
    # robustez de R1, 2026
    d, dl = amcs[2026], locs[2026]
    def amc_r(x, rot):
        z, dp = _prep_amc(x)
        rob.append(linha(ajuste_amc(z, "d_lula"), dp, nivel="AMC", recorte=rot))
    def loc_r(x, rot, w="aptos_t2"):
        z, dp = _prep_loc(x)
        rob.append(linha(ajuste_loc(z, "d_lula", w=w), dp, nivel="locais", recorte=rot))
    amc_r(d, "principal"); loc_r(dl, "principal")
    amc_r(d[d["sg_uf"] != "GO"], "sem Goiás"); loc_r(dl[dl["sg_uf"] != "GO"], "sem Goiás")
    loc_r(dl[(dl["aptos_t1"] >= 300) & (dl["aptos_t2"] >= 300)], "≥ 300 aptos")
    loc_r(base_locais(2026, "buf"), "buffer 800 m")
    amc_r(d[d["metro"]], "capitais e RMs"); amc_r(d[~d["metro"]], "fora de capitais e RMs")
    loc_r(dl[dl["metro"]], "capitais e RMs"); loc_r(dl[~dl["metro"]], "fora de capitais e RMs")
    amc_r(d.assign(aptos=1.0), "sem ponderação"); loc_r(dl, "sem ponderação", None)
    r1, inter, marg, rob = map(pd.DataFrame, (r1, inter, marg, rob))
    _salvar(r1, "extra_raca_r1", "Coeficientes por 1 DP e por 1 p.p. wald_p_dp e wald_p_pp testam a igualdade preta = parda em cada unidade.")
    _salvar(rob, "extra_raca_r1_robustez", "Δ Lula, 2026.")
    _salvar(inter, "extra_raca_interacoes", "Moderador centrado (z). inter_*: variação do efeito (por DP de cor) por 1 DP do moderador.")
    _salvar(marg, "extra_raca_efeito_marginal", "Efeito de 1 DP de % preta ou % parda sobre Δ Lula, na média do 1º e do 4º quartil do moderador.")
    fig_interacoes(marg)


# ---------------------------------------------------------------- Fase C
def _xa() -> list[str]:
    return [x for x in M.X_A if x != "pct_negra"] + ["pct_preta", "pct_parda"]


def nivel_amc(e: pd.DataFrame, cols: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    z = M.padronizar(e[e["eleicao"].isin(ELEICOES_C)], cols + ["nep"])
    dps = e[e["eleicao"].isin(ELEICOES_C)].groupby("eleicao")[["pct_preta", "pct_parda", "pct_negra"]].std()
    bet = []
    for t, d in z.groupby("eleicao"):
        d = d.dropna(subset=["s_pt"] + cols + ["aptos", "id_microrregiao"])
        m = M._wls(f"s_pt ~ {' + '.join(cols)} + ideb_ausente + C(sg_uf)", d)
        ci = m.conf_int()
        bet += [{"nivel": "AMC", "eleicao": t, "variavel": v, "beta": m.params[v], "ep": m.bse[v], "ic_inf": ci.loc[v, 0], "ic_sup": ci.loc[v, 1],
                 "p": m.pvalues[v], "n": int(m.nobs)} for v in cols]
    d = z[z["eleicao"].isin([2010, 2026])].dropna(subset=["s_pt"] + cols + ["aptos", "id_microrregiao"]).copy()
    d["T"] = (d["eleicao"] == 2026).astype(int)
    m = M._wls(f"s_pt ~ ({' + '.join(cols)} + ideb_ausente) * T + C(sg_uf):C(eleicao)", d)
    delta = [{"nivel": "AMC", "unidade": "por DP", "variavel": v, "dif_2026_2010": m.params[f"{v}:T"], "ep": m.bse[f"{v}:T"], "p": m.pvalues[f"{v}:T"]} for v in cols]
    return pd.DataFrame(bet), pd.DataFrame(delta), dps


def nivel_amc_pp(e: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    # mesmas regressões com % preta e % parda em p.p., para comparar magnitudes entre as duas categorias
    z = M.padronizar(e[e["eleicao"].isin([2010, 2026])], [c for c in cols if c not in ("pct_preta", "pct_parda")] + ["nep"])
    d = z.dropna(subset=["s_pt"] + cols + ["aptos", "id_microrregiao"]).copy()
    d["T"] = (d["eleicao"] == 2026).astype(int)
    m = M._wls(f"s_pt ~ ({' + '.join(cols)} + ideb_ausente) * T + C(sg_uf):C(eleicao)", d)
    return pd.DataFrame([{"nivel": "AMC", "unidade": "por p.p.", "variavel": v, "b_2010": m.params[v], "b_2026": m.params[v] + m.params[f"{v}:T"],
                          "dif_2026_2010": m.params[f"{v}:T"], "ep": m.bse[f"{v}:T"], "p": m.pvalues[f"{v}:T"]} for v in ["pct_preta", "pct_parda"]])


def nivel_local() -> tuple[pd.DataFrame, pd.DataFrame]:
    partes = []
    for a in ANOS_LOC:
        d = base_locais(a, min_aptos=0)
        d = d[["id_municipio", "ano", "s_pt", "aptos_t2", "jovens", "log_renda", "log_dens", "pct_preta", "pct_parda"]].copy()
        d[["pct_preta", "pct_parda"]] = _zs(d, ["pct_preta", "pct_parda"])[0][["pct_preta", "pct_parda"]]
        partes.append(d)
    d = pd.concat(partes, ignore_index=True)
    d["mun_ano"] = d["id_municipio"].astype(str) + "_" + d["ano"].astype(str)
    vs = ["jovens", "log_renda", "log_dens", "pct_preta", "pct_parda"]
    termos = []
    for v in vs:
        for a in ANOS_LOC:
            d[f"{v}_{a}"] = d[v] * (d["ano"] == a)
            termos.append(f"{v}_{a}")
    f = _fit("s_pt ~ " + " + ".join(termos), d, fe="mun_ano")
    bet, dif = [], []
    for v in ["pct_preta", "pct_parda"]:
        for a in ANOS_LOC:
            est, ep, p = _comb(f, {f"{v}_{a}": 1})
            bet.append({"nivel": "locais", "eleicao": a, "variavel": v, "beta": est, "ep": ep, "ic_inf": est - 1.96 * ep, "ic_sup": est + 1.96 * ep, "p": p, "n": int(f._N)})
        est, ep, p = _comb(f, {f"{v}_2026": 1, f"{v}_2010": -1})
        dif.append({"nivel": "locais", "unidade": "por DP", "variavel": v, "dif_2026_2010": est, "ep": ep, "p": p})
    return pd.DataFrame(bet), pd.DataFrame(dif)


def fase_c() -> None:
    e = M.carregar()
    b0, d0, _ = nivel_amc(e, M.X_A)
    b1, d1, dps = nivel_amc(e, _xa())
    bl, dl = nivel_local()
    bet = pd.concat([b1[b1["variavel"].isin(["pct_preta", "pct_parda"])], b0[b0["variavel"] == "pct_negra"], bl], ignore_index=True)
    dif = pd.concat([d1[d1["variavel"].isin(["pct_preta", "pct_parda"])], d0[d0["variavel"] == "pct_negra"], nivel_amc_pp(e, _xa()), dl], ignore_index=True)
    outras = b0.merge(b1, on=["eleicao", "variavel"], suffixes=("_com_negra", "_decomposto"))
    outras = outras[["eleicao", "variavel", "beta_com_negra", "beta_decomposto"]]
    _salvar(bet, "extra_raca_nivel", "s_pt no 2º turno, p.p. por 1 DP. AMC: spec. A da Fase 6. Locais: empilhado, EF município × ano, Censo 2022 em todos os anos.")
    _salvar(dif, "extra_raca_nivel_delta", "Diferença 2026 − 2010, modelo empilhado com interações X × ano.")
    _salvar(outras, "extra_raca_nivel_outras", "Coeficientes das demais covariáveis com pct_negra e com pct_preta + pct_parda.")
    _salvar(dps.reset_index(), "extra_raca_nivel_dp", "Desvio-padrão entre AMCs usado na padronização, por eleição.")
    r1 = pd.read_csv(caminho("tables") / "extra_raca_r1.csv")
    fig_coeficientes(bet, r1)


# ---------------------------------------------------------------- figuras
def _estilo(ax) -> None:
    ax.axhline(0, color=COR["tinta2"], linewidth=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=8)


def fig_coeficientes(bet: pd.DataFrame, r1: pd.DataFrame) -> None:
    fig, axs = plt.subplots(1, 3, figsize=(12.5, 4.2), sharey=False)
    cores = {"pct_preta": COR["destaque"], "pct_parda": "#c8862a"}
    rot = {"pct_preta": "% preta", "pct_parda": "% parda"}
    for ax, nv, tit in zip(axs[:2], ["AMC", "locais"], ["Nível, por AMC", "Nível, por local de votação"]):
        for j, v in enumerate(["pct_preta", "pct_parda"]):
            d = bet[(bet["nivel"] == nv) & (bet["variavel"] == v)].sort_values("eleicao")
            x = np.arange(len(d)) + (j - 0.5) * 0.18
            ax.errorbar(x, d["beta"], yerr=1.96 * d["ep"], fmt="o-", ms=5, lw=1.6, capsize=2, color=cores[v], label=rot[v])
        ax.set_xticks(range(len(d)), d["eleicao"].astype(int)); ax.set_title(tit, fontsize=10, loc="left"); _estilo(ax)
    axs[0].set_ylabel("p.p. do voto no PT por 1 DP", fontsize=8); axs[0].legend(frameon=False, fontsize=8)
    ax = axs[2]
    d = r1[r1["desfecho"] == "Δ Lula"].sort_values(["nivel", "ano"]).reset_index(drop=True)
    for j, (b, ep, c) in enumerate([("beta_preta_dp", "ep_preta", "pct_preta"), ("beta_parda_dp", "ep_parda", "pct_parda")]):
        ax.errorbar(np.arange(len(d)) + (j - 0.5) * 0.18, d[b], yerr=1.96 * d[ep], fmt="o", ms=5, capsize=2, color=cores[c])
    ax.set_xticks(range(len(d)), [f"{n}\n{a}" for n, a in zip(d["nivel"], d["ano"])]); ax.set_title("Δ Lula entre turnos", fontsize=10, loc="left"); _estilo(ax)
    ax.set_ylabel("p.p. dos aptos por 1 DP", fontsize=8)
    fig.suptitle("% preta e % parda: voto no PT no 2º turno e crescimento entre turnos (IC 95%)", x=0.01, ha="left", fontsize=11)
    fig.text(0.01, -0.02, FONTE, fontsize=7, color=COR["tinta2"])
    fig.tight_layout()
    for ext in ["png", "svg"]:
        fig.savefig(caminho("figures") / f"extra_raca_coeficientes.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)


def fig_interacoes(m: pd.DataFrame) -> None:
    d = m[(m["ano"] == 2026) & (m["cor"] == "preta") & m["moderador"].isin(["% superior", "% jovens 16–34"])]
    fig, axs = plt.subplots(1, 2, figsize=(9, 3.8), sharey=True)
    cores = {"Q1": "#9a9990", "Q4": COR["destaque"]}
    for ax, mod in zip(axs, ["% superior", "% jovens 16–34"]):
        g = d[d["moderador"] == mod].sort_values(["nivel", "quartil"])
        niveis = list(g["nivel"].unique())
        for j, q in enumerate(["Q1", "Q4"]):
            s = g[g["quartil"] == q]
            ax.errorbar(np.arange(len(s)) + (j - 0.5) * 0.25, s["efeito_dp"], yerr=1.96 * s["ep"], fmt="o", ms=6, capsize=3, color=cores[q], label=f"{q} do moderador")
        ax.set_xticks(range(len(niveis)), niveis); ax.set_title(mod, fontsize=10, loc="left"); _estilo(ax)
    axs[0].set_ylabel("Efeito de 1 DP de % preta sobre Δ Lula (p.p.)", fontsize=8); axs[0].legend(frameon=False, fontsize=8)
    fig.suptitle("Efeito marginal de % preta no Δ Lula de 2026, por quartil (IC 95%)", x=0.01, ha="left", fontsize=11)
    fig.text(0.01, -0.03, FONTE, fontsize=7, color=COR["tinta2"])
    fig.tight_layout()
    for ext in ["png", "svg"]:
        fig.savefig(caminho("figures") / f"extra_raca_interacoes.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    fases = sys.argv[1:] or ["a", "b", "c"]
    for f, fn in [("a", fase_a), ("b", fase_b), ("c", fase_c)]:
        if f in fases:
            fn()
