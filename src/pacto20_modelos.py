"""Fase C do pacto 2.0 (docs/planos/plano2.md): modelos por local de votação com efeito fixo de município.

Base: data/interim/pacto20_locais_<ano>.parquet (Fase A) + pacto20_entorno_<ano>.parquet (Fase B).
Escopo: municípios com >= 10 locais (MIN_LOCAIS) e locais com entorno Voronoi.

Especificação comum: WLS com efeito fixo de município, peso = aptos do local no 2º turno, erros
agrupados por município; X padronizados (z) dentro de cada eleição, sobre a amostra de estimação.
- jovens: % do eleitorado do local com 16–34 anos (TSE, perfil por seção)
- negros: % pretos e pardos no entorno Voronoi (Censo 2022, setores)
- log_renda: log da renda média do responsável no entorno (R$ de dez/2025)
- log_dens: log da densidade (hab/km²) do entorno

Critérios (o Critério 3, voto para deputado, foi retirado por decisão do usuário; ver pendencias.md):
1. s_PT 2º turno ~ X + jovens×renda + negros×renda; efeitos por tercil de renda (tercis dentro do município)
2. empilhado 2018/2022/2026 com X×ano e EF município×ano; Δβ 2026−2018 e 2026−2022
4. mobilização entre turnos: Δcomparecimento, Δ voto PT e Δ voto do opositor (p.p. dos aptos) ~ X;
   comparecimento por faixa etária (zona eleitoral, TSE); inferência ecológica R×C (PyEI) nas capitais grandes
5. heterogeneidade do Critério 1: capital / RM (exceto capital) / interior; macrorregião

Uso: python -m src.pacto20_modelos [c1 c2 c4 c5 idade ei]
"""

from __future__ import annotations

import logging
import zipfile

import numpy as np
import pandas as pd
import pyfixest as pf
from scipy import stats

from src.pacto20_base import CHAVE
from src.pacto20_entorno import MIN_LOCAIS
from src.utils import caminho, config

log = logging.getLogger("pacto20_modelos")
ANOS = [2018, 2022, 2026]
X = ["jovens", "negros", "log_renda", "log_dens"]
FOCO = ["jovens", "negros"]
ROTULO = {"jovens": "% jovens 16–34 (TSE)", "negros": "% pretos e pardos (Censo)", "log_renda": "log renda média",
          "log_dens": "log densidade", "jovens:log_renda": "jovens × renda", "negros:log_renda": "negros × renda"}
MACRO = {1: "Norte", 2: "Nordeste", 3: "Sudeste", 4: "Sul", 5: "Centro-Oeste"}
FONTE = ("Fonte: TSE (votação, comparecimento e perfil do eleitorado por seção; locais de votação), "
         "IBGE Censo 2022 (agregados por setor). Elaboração própria.")


# ---------------------------------------------------------------- dados
def dados(ano: int) -> pd.DataFrame:
    op = config()["presidencial"][ano]["op"]
    b = pd.read_parquet(caminho("interim") / f"pacto20_locais_{ano}.parquet")
    e = pd.read_parquet(caminho("interim") / f"pacto20_entorno_{ano}.parquet")
    n = b.groupby("id_municipio").size()
    b = b[b["id_municipio"].isin(n[n >= MIN_LOCAIS].index)]
    d = b.merge(e.drop(columns=["ano", "id_municipio"]), on=CHAVE, how="inner")
    d = d[(d["nominais_t2"] > 0) & (d["aptos_t1"] > 0) & (d["aptos_t2"] > 0)].copy()
    d["s_pt"] = 100 * d["c_13_t2"] / d["nominais_t2"]
    d["s_pt_t1"] = 100 * d["c_13_t1"] / d["nominais_t1"].where(d["nominais_t1"] > 0)
    for t in [1, 2]:
        d[f"comp_t{t}"] = 100 * d[f"comparecimento_t{t}"] / d[f"aptos_t{t}"]
        d[f"pt_apt_t{t}"] = 100 * d[f"c_13_t{t}"] / d[f"aptos_t{t}"]
        d[f"op_apt_t{t}"] = 100 * d[f"c_{op}_t{t}"] / d[f"aptos_t{t}"]
        d[f"bn_apt_t{t}"] = 100 * (d[f"comparecimento_t{t}"] - d[f"nominais_t{t}"]) / d[f"aptos_t{t}"]
    for v in ["comp", "pt_apt", "op_apt", "bn_apt"]:
        d[f"d_{v}"] = d[f"{v}_t2"] - d[f"{v}_t1"]
    d["jovens_raw"] = d["pct_jovens_16_34"]
    d["negros_raw"] = d["pct_negra_vor"]
    d["renda_raw"] = d["renda_media_vor"]
    d["dens_raw"] = d["densidade_vor"]
    d["log_renda_raw"] = np.log(d["renda_raw"].where(d["renda_raw"] > 0))
    d["log_dens_raw"] = np.log(d["dens_raw"].where(d["dens_raw"] > 0))
    d = d.dropna(subset=["s_pt", "jovens_raw", "negros_raw", "log_renda_raw", "log_dens_raw"])
    for v, r in zip(X, ["jovens_raw", "negros_raw", "log_renda_raw", "log_dens_raw"]):
        d[v] = (d[r] - d[r].mean()) / d[r].std()
    # tercis de renda dentro do município (variação intraurbana)
    d["tercil"] = d.groupby("id_municipio")["log_renda_raw"].transform(
        lambda s: np.ceil(3 * s.rank(method="first") / len(s))).astype(int)
    for t in [1, 2, 3]:
        d[f"T{t}"] = (d["tercil"] == t).astype(float)
        for v in FOCO:
            d[f"{v}_T{t}"] = d[v] * d[f"T{t}"]
    d["grupo"] = np.where(d["capital"].fillna(False), "capital",
                          np.where(d["rm"].fillna(False), "RM (exceto capital)", "interior"))
    d["macro"] = (d["id_municipio"] // 1_000_000).map(MACRO)
    d["ano"] = ano
    return d


def _fit(fml: str, d: pd.DataFrame, fe: str = "id_municipio", w: str | None = "aptos_t2"):
    kw = {"weights": w} if w else {}
    return pf.feols(f"{fml} | {fe}", data=d, vcov={"CRV1": "id_municipio"}, **kw)


def _tab(fit, extra: dict) -> pd.DataFrame:
    t = fit.tidy().reset_index().rename(columns={"Coefficient": "termo", "Estimate": "coef", "Std. Error": "ep",
                                                  "Pr(>|t|)": "p", "2.5%": "ic_inf", "97.5%": "ic_sup"})
    t = t[["termo", "coef", "ep", "p", "ic_inf", "ic_sup"]]
    for k, v in reversed(list(extra.items())):
        t.insert(0, k, v)
    t["n_locais"] = fit._N
    t["r2_within"] = getattr(fit, "_r2_within", np.nan)
    return t


def _comb(fit, pesos: dict) -> tuple[float, float, float]:
    """Combinação linear dos coeficientes: estimativa, erro-padrão e p (t com G−1 g.l.)."""
    nomes = list(fit._coefnames)
    a = np.zeros(len(nomes))
    for k, v in pesos.items():
        a[nomes.index(k)] = v
    b = fit.coef().reindex(nomes).values
    est, ep = a @ b, float(np.sqrt(a @ fit._vcov @ a))
    g = fit._data["id_municipio"].nunique() if hasattr(fit, "_data") else 1000
    return est, ep, 2 * stats.t.sf(abs(est / ep), g - 1)


def _salvar(df: pd.DataFrame, nome: str, titulo: str, nota: str = "") -> None:
    df.to_csv(caminho("tables") / f"pacto20_{nome}.csv", index=False, encoding="utf-8")
    md = f"**{titulo}**\n\n" + df.to_markdown(index=False, floatfmt=".4g") + f"\n\n{nota}{' ' if nota else ''}{FONTE}\n"
    (caminho("tables") / f"pacto20_{nome}.md").write_text(md, encoding="utf-8")
    log.info("tabela pacto20_%s (%d linhas)", nome, len(df))


# ---------------------------------------------------------------- Critério 1
F_C1 = "s_pt ~ jovens + negros + log_renda + log_dens + jovens:log_renda + negros:log_renda"
F_TERC = "s_pt ~ jovens_T1 + jovens_T2 + jovens_T3 + negros_T1 + negros_T2 + negros_T3 + T2 + T3 + log_renda + log_dens"


def criterio1(bases: dict) -> None:
    coef, terc, desc = [], [], []
    for ano, d in bases.items():
        f = _fit(F_C1, d)
        coef.append(_tab(f, {"ano": ano, "modelo": "interação contínua"}))
        ft = _fit(F_TERC, d)
        for v in FOCO:
            for t in [1, 2, 3]:
                est, ep, p = _comb(ft, {f"{v}_T{t}": 1})
                terc.append({"ano": ano, "variavel": v, "tercil_renda": t, "efeito_pp_por_dp": est, "ep": ep, "p": p,
                             "ic_inf": est - 1.96 * ep, "ic_sup": est + 1.96 * ep})
            est, ep, p = _comb(ft, {f"{v}_T3": 1, f"{v}_T1": -1})
            terc.append({"ano": ano, "variavel": v, "tercil_renda": "T3−T1", "efeito_pp_por_dp": est, "ep": ep, "p": p,
                         "ic_inf": est - 1.96 * ep, "ic_sup": est + 1.96 * ep})
        desc.append({"ano": ano, "locais": len(d), "municipios": d["id_municipio"].nunique(),
                     "aptos_t2": int(d["aptos_t2"].sum()), "s_pt_media_pond": np.average(d["s_pt"], weights=d["aptos_t2"]),
                     **{f"dp_{v}": d[f"{v}_raw" if v in FOCO else f"{v}_raw"].std() for v in X}})
    _salvar(pd.concat(coef), "faseC_c1_coef",
            "Critério 1 — s_PT no 2º turno (% válidos) por local, EF de município",
            "X em desvios-padrão dentro da eleição; coeficientes em p.p. de s_PT por 1 DP. Peso: aptos; EP agrupado por município.")
    _salvar(pd.DataFrame(terc), "faseC_c1_tercis",
            "Critério 1 — efeito de jovens e negros por tercil de renda (tercis dentro do município)",
            "Efeito em p.p. de s_PT por 1 DP, com EF de município e controles de log renda e log densidade.")
    _salvar(pd.DataFrame(desc), "faseC_amostra", "Amostra da Fase C por eleição",
            "dp_*: desvio-padrão da variável original (p.p.; log para renda e densidade), para converter os efeitos padronizados.")


# ---------------------------------------------------------------- Critério 2
def _empilhado(bases: dict, nome: str, w: str | None = "aptos_t2") -> tuple[pd.DataFrame, pd.DataFrame]:
    d = pd.concat(bases.values(), ignore_index=True)
    d["mun_ano"] = d["id_municipio"].astype(str) + "_" + d["ano"].astype(str)
    anos = sorted(bases)
    termos = []
    for v in X:
        for a in anos:
            d[f"{v}_{a}"] = d[v] * (d["ano"] == a)
            termos.append(f"{v}_{a}")
    f = _fit("s_pt ~ " + " + ".join(termos), d, fe="mun_ano", w=w)
    beta = []
    for v in X:
        for a in anos:
            est, ep, p = _comb(f, {f"{v}_{a}": 1})
            beta.append({"amostra": nome, "variavel": v, "ano": a, "beta": est, "ep": ep, "p": p,
                         "ic_inf": est - 1.96 * ep, "ic_sup": est + 1.96 * ep})
    delta = []
    for v in FOCO:
        for a0 in [a for a in anos if a < 2026]:
            est, ep, p = _comb(f, {f"{v}_2026": 1, f"{v}_{a0}": -1})
            delta.append({"amostra": nome, "variavel": v, "contraste": f"2026−{a0}", "delta_beta": est, "ep": ep, "p": p,
                          "ic_inf": est - 1.96 * ep, "ic_sup": est + 1.96 * ep})
        if {2018, 2022} <= set(bases):
            est, ep, p = _comb(f, {f"{v}_2022": 1, f"{v}_2018": -1})
            delta.append({"amostra": nome, "variavel": v, "contraste": "2022−2018", "delta_beta": est, "ep": ep, "p": p,
                          "ic_inf": est - 1.96 * ep, "ic_sup": est + 1.96 * ep})
    log.info("empilhado %s: %d locais-ano", nome, f._N)
    return pd.DataFrame(beta).assign(n_locais_ano=f._N), pd.DataFrame(delta).assign(n_locais_ano=f._N)


def _painel_balanceado(bases: dict) -> dict:
    """Só locais de 2026 que têm correspondente em 2018 e em 2022 (pacto20_match)."""
    m = pd.read_parquet(caminho("interim") / "pacto20_match.parquet")
    m = m[m["ano_ref"] == 2026]
    k = lambda d: d[CHAVE].astype(int).astype(str).agg("-".join, axis=1)  # noqa: E731
    ref = {a: m[m["ano"] == a].set_index("chave")["ref"] for a in [2018, 2022]}
    out = {}
    for a, d in bases.items():
        d = d.copy()
        d["ref"] = k(d) if a == 2026 else k(d).map(ref[a])
        out[a] = d
    comum = set(out[2026]["ref"]) & set(out[2018]["ref"].dropna()) & set(out[2022]["ref"].dropna())
    return {a: d[d["ref"].isin(comum)] for a, d in out.items()}


def criterio2(bases: dict) -> None:
    b1, d1 = _empilhado(bases, "todos os locais")
    b2, d2 = _empilhado(_painel_balanceado(bases), "locais presentes nas 3 eleições")
    _salvar(pd.concat([b1, b2]), "faseC_c2_betas",
            "Critério 2 — β por eleição no modelo empilhado (EF município×ano)",
            "p.p. de s_PT (2º turno) por 1 DP de X, padronizado dentro de cada eleição. EP agrupado por município.")
    _salvar(pd.concat([d1, d2]), "faseC_c2_delta", "Critério 2 — Δβ entre eleições (jovens e negros)",
            "Teste t da diferença com a matriz de covariância agrupada por município.")


# ---------------------------------------------------------------- Critério 4
def criterio4(bases: dict) -> None:
    out = []
    for ano, d in bases.items():
        for y, rot in [("d_comp", "Δ comparecimento"), ("d_pt_apt", "Δ voto PT (% aptos)"),
                       ("d_op_apt", "Δ voto opositor (% aptos)"), ("d_bn_apt", "Δ brancos e nulos (% aptos)")]:
            f = _fit(f"{y} ~ " + " + ".join(X), d)
            t = _tab(f, {"ano": ano, "resultado": rot})
            t.insert(3, "media_pond", np.average(d[y], weights=d["aptos_t2"]))
            out.append(t)
    _salvar(pd.concat(out), "faseC_c4_turnos",
            "Critério 4 — mudança entre o 1º e o 2º turno por local (p.p. dos aptos), EF de município",
            "media_pond: média ponderada da variação. Coeficientes em p.p. por 1 DP de X.")


def criterio4_comparado(anos: tuple[int, ...] = (2010, 2014, 2018, 2022, 2026)) -> None:
    """Mobilização entre turnos em cinco eleições: mesmo modelo empilhado (EF município×ano), com
    teste de que o coeficiente de 2026 difere do de cada eleição anterior. 2010 e 2014 usam as bases
    do placebo (Fase D)."""
    bases = {a: dados(a) for a in anos}
    d = pd.concat(bases.values(), ignore_index=True)
    d["mun_ano"] = d["id_municipio"].astype(str) + "_" + d["ano"].astype(str)
    termos = []
    for v in X:
        for a in anos:
            d[f"{v}_{a}"] = d[v] * (d["ano"] == a)
            termos.append(f"{v}_{a}")
    out, med = [], []
    for y, rot in [("d_comp", "Δ comparecimento"), ("d_pt_apt", "Δ voto PT (% aptos)"),
                   ("d_op_apt", "Δ voto opositor (% aptos)"), ("d_bn_apt", "Δ brancos e nulos (% aptos)")]:
        f = _fit(f"{y} ~ " + " + ".join(termos), d, fe="mun_ano")
        for v in X:
            for a in anos:
                est, ep, p = _comb(f, {f"{v}_{a}": 1})
                linha = {"resultado": rot, "variavel": v, "ano": a, "beta": est, "ep": ep, "p": p}
                if a != 2026:
                    de, dep, dp = _comb(f, {f"{v}_2026": 1, f"{v}_{a}": -1})
                    linha.update({"dif_2026_menos_ano": de, "ep_dif": dep, "p_dif": dp})
                out.append(linha)
        for a, s in d.groupby("ano"):
            med.append({"resultado": rot, "ano": a, "media_pond": np.average(s[y], weights=s["aptos_t2"])})
    t = pd.DataFrame(out).merge(pd.DataFrame(med), on=["resultado", "ano"])
    _salvar(t, "faseC_c4_comparado",
            "Critério 4 — mudança entre o 1º e o 2º turno por local em cinco eleições (p.p. dos aptos), EF município×ano",
            "beta: p.p. por 1 DP de X (padronizado dentro da eleição). dif_2026_menos_ano: diferença do coeficiente de 2026 "
            "para o da eleição da linha, com EP agrupado por município. media_pond: variação média ponderada.")


def comparecimento_idade() -> None:
    """Comparecimento por faixa etária (TSE, município × zona): menor nível publicado com idade."""
    faixas = {"16 a 24": ["16 anos", "17 anos", "18 anos", "19 anos", "20 anos", "21 a 24 anos"],
              "25 a 34": ["25 a 29 anos", "30 a 34 anos"], "35 a 44": ["35 a 39 anos", "40 a 44 anos"],
              "45 a 59": ["45 a 49 anos", "50 a 54 anos", "55 a 59 anos"]}
    mapa = {f: g for g, fs in faixas.items() for f in fs}
    out = []
    for ano in ANOS:
        z = zipfile.ZipFile(caminho("raw") / "tse_secao" / "perfil_comparecimento_abstencao"
                            / f"perfil_comparecimento_abstencao_{ano}.zip")
        nomes = [n for n in z.namelist() if n.upper().endswith(".CSV")]
        br = [n for n in nomes if n.upper().endswith("_BRASIL.CSV")]
        nomes = br or [n for n in nomes if not n.upper().endswith("_ZZ.CSV")]
        partes = []
        for n in nomes:
            for ch in pd.read_csv(z.open(n), sep=";", encoding="latin1", chunksize=2_000_000,
                                  usecols=["NR_TURNO", "SG_UF", "DS_FAIXA_ETARIA", "QT_APTOS", "QT_COMPARECIMENTO"]):
                ch = ch[ch["SG_UF"] != "ZZ"]
                ch["faixa"] = ch["DS_FAIXA_ETARIA"].str.strip().map(mapa).fillna("60 ou mais")
                ch.loc[ch["DS_FAIXA_ETARIA"].str.contains("Inv", na=False), "faixa"] = "inválida"
                partes.append(ch.groupby(["NR_TURNO", "faixa"])[["QT_APTOS", "QT_COMPARECIMENTO"]].sum())
        g = pd.concat(partes).groupby(level=[0, 1]).sum().reset_index()
        g = g[g["faixa"] != "inválida"]
        g["comparecimento_pct"] = 100 * g["QT_COMPARECIMENTO"] / g["QT_APTOS"]
        w = g.pivot(index="faixa", columns="NR_TURNO", values="comparecimento_pct").add_prefix("comp_t").reset_index()
        if "comp_t2" not in w:
            w["comp_t2"] = np.nan
        w["delta_t2_t1"] = w["comp_t2"] - w["comp_t1"]
        w.insert(0, "ano", ano)
        w["turnos_publicados"] = ",".join(str(t) for t in sorted(g["NR_TURNO"].unique()))
        out.append(w)
        log.info("comparecimento por idade %d: turnos %s", ano, w["turnos_publicados"].iat[0])
    _salvar(pd.concat(out), "faseC_c4_idade",
            "Critério 4 — comparecimento por faixa etária, Brasil sem exterior (TSE, perfil de comparecimento e abstenção)",
            "Nível mínimo publicado com idade: município × zona eleitoral. Em 2026 o arquivo (gerado em 13/10/2026) só traz o 1º turno.")


EI_LINHAS = {"Lula": ["c_13_t1"], "Flávio": ["c_22_t1"], "Cury": ["c_70_t1"], "Renan Santos": ["c_14_t1"],
             "Caiado": ["c_55_t1"]}
EI_COLUNAS = ["Lula", "Flávio", "branco/nulo", "abstenção"]
# as quatro capitais dos mapas da Fase E (decisão do usuário: a amostragem é lenta)
EI_CIDADES = {3550308: "São Paulo", 3304557: "Rio de Janeiro", 2927408: "Salvador", 3106200: "Belo Horizonte"}


def inferencia_ecologica(bases: dict, draws: int = 1000, tune: int = 1000) -> None:
    """R×C (PyEI, multinomial-Dirichlet) do 1º para o 2º turno de 2026, por local, nas capitais grandes."""
    from pyei.r_by_c import RowByColumnEI

    d = bases[2026]
    cand = [c for c in d if c.startswith("c_") and c.endswith("_t1")]
    out = []
    for mun, nome in EI_CIDADES.items():
        m = d[d["id_municipio"] == mun].copy()
        if len(m) < 50:
            continue
        n = m["aptos_t2"].values.astype(int)
        r1 = pd.DataFrame({k: m[v].sum(axis=1) for k, v in EI_LINHAS.items()})
        usados = sum(EI_LINHAS.values(), [])
        r1["outros"] = m[[c for c in cand if c not in usados]].sum(axis=1)
        r1["branco/nulo"] = m["comparecimento_t1"] - m["nominais_t1"]
        r1["abstenção"] = m["abstencoes_t1"]
        c2 = pd.DataFrame({"Lula": m["c_13_t2"], "Flávio": m["c_22_t2"],
                           "branco/nulo": m["comparecimento_t2"] - m["nominais_t2"], "abstenção": m["abstencoes_t2"]})
        # proporções sobre aptos de cada turno (aptos do 1º e do 2º turno diferem marginalmente)
        p1 = r1.div(r1.sum(axis=1), axis=0).clip(lower=1e-6)
        p2 = c2.div(c2.sum(axis=1), axis=0).clip(lower=1e-6)
        p1, p2 = p1.div(p1.sum(axis=1), axis=0), p2.div(p2.sum(axis=1), axis=0)
        ei = RowByColumnEI(model_name="multinomial-dirichlet-modified", pareto_scale=8, pareto_shape=2)
        ei.fit(p1.values.T, p2.values.T, n, list(p1.columns), list(p2.columns),
               draws=draws, tune=tune, chains=2, target_accept=0.95, random_seed=2026, progressbar=False)
        s = ei.sampled_voter_prefs  # (amostras, linhas, colunas), proporção da linha que vai para a coluna
        for i, lin in enumerate(p1.columns):
            for j, col in enumerate(p2.columns):
                x = s[:, i, j]
                out.append({"municipio": nome, "origem_1t": lin, "destino_2t": col, "proporcao": float(np.mean(x)),
                            "ic_inf": float(np.percentile(x, 2.5)), "ic_sup": float(np.percentile(x, 97.5)),
                            "peso_origem_pct": 100 * (r1[lin].sum() / r1.values.sum()), "locais": len(m)})
        log.info("EI %s: %d locais", nome, len(m))
        _salvar_ei(out)


def _salvar_ei(out: list) -> None:
    """Salva a cada cidade concluída (a amostragem leva vários minutos por cidade)."""
    _salvar(pd.DataFrame(out), "faseC_c4_ei",
            "Critério 4 — destino no 2º turno de 2026 dos votos e abstenções do 1º turno (inferência ecológica R×C, PyEI)",
            "proporcao: fração dos eleitores da origem (1º turno) estimada no destino (2º turno); IC de 95% da posterior. "
            "Unidade: local de votação. Inferência ecológica; leitura agregada, não individual.")


def _tabelas_ei(m: pd.DataFrame, cand: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Proporções por local: origem no 1º turno (linhas) e destino no 2º turno (colunas)."""
    r1 = pd.DataFrame({k: m[v].sum(axis=1) for k, v in EI_LINHAS.items()})
    usados = sum(EI_LINHAS.values(), [])
    r1["outros"] = m[[c for c in cand if c not in usados]].sum(axis=1)
    r1["branco/nulo"] = m["comparecimento_t1"] - m["nominais_t1"]
    r1["abstenção"] = m["abstencoes_t1"]
    c2 = pd.DataFrame({"Lula": m["c_13_t2"], "Flávio": m["c_22_t2"],
                       "branco/nulo": m["comparecimento_t2"] - m["nominais_t2"], "abstenção": m["abstencoes_t2"]})
    return r1, c2


def _goodman(x: np.ndarray, y: np.ndarray, w: np.ndarray) -> np.ndarray:
    """min Σ w_i ||y_i − x_i P||², P >= 0, linhas de P somam 1 (regressão ecológica restrita)."""
    from scipy.optimize import minimize

    r, c = x.shape[1], y.shape[1]
    w = w / w.mean()  # escala da função objetivo (aptos estão na casa dos milhares)
    xw, yw = x * np.sqrt(w)[:, None], y * np.sqrt(w)[:, None]
    f = lambda v: np.sum((yw - xw @ v.reshape(r, c)) ** 2)  # noqa: E731
    g = lambda v: (-2 * xw.T @ (yw - xw @ v.reshape(r, c))).ravel()  # noqa: E731
    cons = {"type": "eq", "fun": lambda v: v.reshape(r, c).sum(axis=1) - 1,
            "jac": lambda v: np.kron(np.eye(r), np.ones(c))}
    v0 = np.tile(y.mean(axis=0), r)
    res = minimize(f, v0, jac=g, bounds=[(0, 1)] * (r * c), constraints=[cons], method="SLSQP",
                   options={"maxiter": 3000, "ftol": 1e-10})
    if not res.success:
        log.warning("Goodman não convergiu: %s", res.message)
    return res.x.reshape(r, c)


def regressao_ecologica(bases: dict, reps: int = 300) -> None:
    """Alternativa rápida ao PyEI: Goodman restrito por cidade, IC por bootstrap dos locais."""
    d = bases[2026]
    cand = [c for c in d if c.startswith("c_") and c.endswith("_t1")]
    rng = np.random.default_rng(2026)
    out = []
    for mun, nome in EI_CIDADES.items():
        m = d[d["id_municipio"] == mun]
        r1, c2 = _tabelas_ei(m, cand)
        x = r1.div(r1.sum(axis=1), axis=0).values
        y = c2.div(c2.sum(axis=1), axis=0).values
        w = m["aptos_t2"].values.astype(float)
        p = _goodman(x, y, w)
        boot = np.array([_goodman(x[i], y[i], w[i]) for i in (rng.integers(0, len(m), len(m)) for _ in range(reps))])
        for i, lin in enumerate(r1.columns):
            for j, col in enumerate(c2.columns):
                out.append({"municipio": nome, "origem_1t": lin, "destino_2t": col, "proporcao": p[i, j],
                            "ic_inf": np.percentile(boot[:, i, j], 2.5), "ic_sup": np.percentile(boot[:, i, j], 97.5),
                            "peso_origem_pct": 100 * r1[lin].sum() / r1.values.sum(), "locais": len(m)})
        log.info("regressão ecológica %s: %d locais", nome, len(m))
    _salvar(pd.DataFrame(out), "faseC_c4_goodman",
            "Critério 4 — destino no 2º turno de 2026 dos votos e abstenções do 1º turno (regressão ecológica restrita)",
            "proporcao: fração da origem (1º turno) que vai ao destino (2º turno), matriz única por cidade, "
            f"com P >= 0 e linhas somando 1; IC de 95% por bootstrap dos locais ({reps} réplicas). "
            "Supõe transferências constantes entre locais da cidade; leitura agregada, não individual.")


# ---------------------------------------------------------------- Critério 5
def criterio5(bases: dict) -> None:
    out = []
    for ano, d in bases.items():
        for col in ["grupo", "macro"]:
            for g, s in d.groupby(col):
                if s["id_municipio"].nunique() < 5:
                    continue
                f = _fit("s_pt ~ " + " + ".join(X), s)
                t = _tab(f, {"ano": ano, "recorte": col, "grupo": g})
                t["municipios"] = s["id_municipio"].nunique()
                out.append(t[t["termo"].isin(FOCO)])
    _salvar(pd.concat(out), "faseC_c5_heterogeneidade",
            "Critério 5 — efeito de jovens e negros sobre s_PT (2º turno) por tipo de município e macrorregião",
            "Modelo do Critério 1 sem interações, estimado separadamente em cada grupo (EF de município).")


def main(partes: list[str] | None = None) -> None:
    partes = partes or ["c1", "c2", "c4", "idade", "c5", "ei"]
    bases = {a: dados(a) for a in ANOS}
    for a, d in bases.items():
        log.info("%d: %d locais em %d municípios", a, len(d), d["id_municipio"].nunique())
    if "c1" in partes:
        criterio1(bases)
    if "c2" in partes:
        criterio2(bases)
    if "c4" in partes:
        criterio4(bases)
    if "c4comp" in partes:
        criterio4_comparado()
    if "idade" in partes:
        comparecimento_idade()
    if "c5" in partes:
        criterio5(bases)
    if "goodman" in partes:
        regressao_ecologica(bases)
    if "ei" in partes:
        inferencia_ecologica(bases)


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    main(sys.argv[1:] or None)
