"""Extra: perfil demográfico dos lugares em que Lula mais cresceu entre o 1º e o 2º turno de 2026.

Complementa o Critério 4 do pacto 2.0 (regressões por local, dentro do município). Aqui, perfil descritivo em dois
níveis, mais a separação entre demografia e voto disponível.

Medida principal: Δ Lula = votos no 2º turno / aptos − votos no 1º turno / aptos, em p.p., como no Critério 4.
Maior crescimento = decil superior ponderado por aptos (os lugares que somam 10% do eleitorado, do maior Δ para o
menor), contra os outros 90%.

1. Locais de votação (entorno Voronoi do Censo 2022 e perfil do eleitorado TSE; ≥ 100 aptos nos dois turnos):
   a) Brasil; b) dentro do município: Δ menos a média do município, em municípios com ≥ 5 locais, o que retira
   diferenças regionais; c) decil de captura. Sensibilidade: ≥ 300 aptos. A base de entorno cobre 2.523 municípios
   (87% dos aptos): os menores ficam só no nível 2.
2. AMCs: acrescenta as covariáveis do painel e os dados novos (homicídios, mortalidade infantil, excesso de
   mortalidade 2020–2021). Recortes: ponderado por aptos (dominado por grandes cidades), sem ponderar (cada AMC
   vale 1), sem Goiás (Ronaldo Caiado, com 12,3% no estado, infla o voto disponível ali) e decil de captura.
3. Voto disponível: Lula só cresce onde há voto a ganhar. O modelo por AMC estima
   Δ Lula = α_UF + β·X (z) + ε, com e sem o voto disponível no 1º turno (terceiros/aptos e abstenção/aptos),
   peso = aptos, EP por microrregião, em 2026 e em 2022 (comparação: X da eleição correspondente; sem homicídios e
   mortalidade infantil como controle comum em nenhum dos dois, cada um entra como variável própria).
   Taxa de captura = Δ Lula / voto disponível, em que voto disponível = 100 − Lula − Flávio Bolsonaro no 1º turno
   (terceiros, brancos, nulos e abstenção, em % dos aptos): quanto do que estava em jogo foi para Lula.

Associação ecológica: lugares, não eleitores. Entorno censitário é aproximação do eleitor do local.

Saídas: outputs/tables/extra_turnos_{resumo,perfil,amc_modelo,uf,maiores}.

Uso: python -m src.extra_entre_turnos
"""

from __future__ import annotations

import logging
import zipfile

import numpy as np
import pandas as pd

from src import models as M
from src.extra_mortalidade import HOM, TMI, excesso
from src.p3_brasil import eleicao, tse_para_amc
from src.utils import caminho, config

log = logging.getLogger("extra_entre_turnos")
FONTE = "Fonte: TSE; IBGE, Censo 2022 por setor; DATASUS (SIM, SINASC); Atlas DH; Comex Stat. Elaboração própria."
CHAVE = ["cd_mun_tse", "nr_zona", "nr_local"]
V_LOCAIS = {"pct_negra_vor": "% negra (entorno)", "renda_media_vor": "Renda média (entorno, R$)",
            "pct_15_29_vor": "% 15–29 anos (entorno)", "pct_urbana_vor": "% urbana (entorno)",
            "densidade_vor": "Densidade (hab./km²)", "pct_jovens_16_34": "% eleitores 16–34",
            "pct_60mais": "% eleitores 60+", "pct_superior": "% eleitores com superior",
            "pct_mulheres": "% eleitoras", "lula_t1": "Lula, 1º turno (% aptos)", "terceiros_t1": "Terceiros, 1º turno (% aptos)",
            "abst_t1": "Abstenção, 1º turno (% aptos)", "d_lula": "Δ Lula (p.p. dos aptos)",
            "d_op": "Δ Flávio Bolsonaro (p.p. dos aptos)", "d_comp": "Δ comparecimento (p.p.)",
            "captura": "Taxa de captura"}
EXC = "excesso 2020–2021"
V_AMC = {"pct_negra": "% negra", "pct_evangelica": "% evangélica", "pct_sem_religiao": "% sem religião",
         "pbf_100hab": "Bolsa Família (benef./100 hab.)", "pib_pc_real": "PIB per capita (R$)", "idhm_2010": "IDHM 2010",
         "pct_informal": "% informal", "part_vab_agro": "% VAB agro", "log_pop": "log população",
         HOM: "Homicídios (100 mil, 2022–2024)", TMI: "Mortalidade infantil (por mil, 2022–2024)",
         EXC: "Excesso de mortalidade 2020–21 (%)", "lula_t1": "Lula, 1º turno (% aptos)",
         "terceiros_t1": "Terceiros, 1º turno (% aptos)", "abst_t1": "Abstenção, 1º turno (% aptos)",
         "d_lula": "Δ Lula (p.p. dos aptos)", "d_op": "Δ Flávio Bolsonaro (p.p. dos aptos)",
         "d_comp": "Δ comparecimento (p.p.)", "captura": "Taxa de captura"}
X_MOD = ["pct_negra", "pct_evangelica", "pct_sem_religiao", "pbf_100hab", "log_pib_pc", "pct_informal", "part_vab_agro",
         "log_pop"]
DISPONIVEL = ["terceiros_t1", "abst_t1"]


def _salvar(df: pd.DataFrame, nome: str, nota: str = "") -> None:
    df.to_csv(caminho("tables") / f"{nome}.csv", index=False, encoding="utf-8")
    md = df.to_markdown(index=False, floatfmt=".3g") + (f"\n\n{nota}" if nota else "") + f"\n\n{FONTE}\n"
    (caminho("tables") / f"{nome}.md").write_text(md, encoding="utf-8")
    log.info("tabela %s (%d linhas)", nome, len(df))


def _decil(s: pd.Series, w: pd.Series) -> pd.Series:
    """Verdadeiro para os maiores valores de s até somar 10% do peso."""
    o = s.sort_values(ascending=False, kind="stable").index
    return (w.loc[o].cumsum() / w.sum() <= 0.10).reindex(s.index)


def _wm(x: pd.Series, w: pd.Series) -> float:
    ok = x.notna()
    return np.average(x[ok], weights=w[ok])


def perfil(d: pd.DataFrame, topo: pd.Series, w: str, nomes: dict, recorte: str) -> pd.DataFrame:
    linhas = []
    for v, rot in nomes.items():
        x, p = d[v], d[w]
        mt, mr = _wm(x[topo], p[topo]), _wm(x[~topo], p[~topo])
        dp = np.sqrt(_wm((x - _wm(x, p)) ** 2, p))
        linhas.append({"recorte": recorte, "variavel": rot, "maior_crescimento": mt, "demais": mr,
                       "diferenca_dp": (mt - mr) / dp})
    return pd.DataFrame(linhas)


def locais(min_aptos: int = 100) -> pd.DataFrame:
    i = caminho("interim")
    d = pd.read_parquet(i / "pacto20_locais_2026.parquet")
    ent = pd.read_parquet(i / "pacto20_entorno_2026.parquet").drop(columns=["id_municipio", "ano"])
    d = d.merge(ent, on=CHAVE, how="inner")
    d = d[(d["aptos_t1"] >= min_aptos) & (d["aptos_t2"] >= min_aptos) & d["pct_negra_vor"].notna()
          & d["renda_media_vor"].notna() & d["id_municipio"].notna()].copy()
    terc = ["c_14_t1", "c_16_t1", "c_21_t1", "c_27_t1", "c_28_t1", "c_29_t1", "c_30_t1", "c_35_t1", "c_55_t1", "c_70_t1",
            "c_80_t1"]
    d["lula_t1"] = 100 * d["c_13_t1"] / d["aptos_t1"]
    d["terceiros_t1"] = 100 * d[terc].sum(axis=1) / d["aptos_t1"]
    d["abst_t1"] = 100 * (1 - d["comparecimento_t1"] / d["aptos_t1"])
    d["d_lula"] = 100 * d["c_13_t2"] / d["aptos_t2"] - d["lula_t1"]
    d["d_op"] = 100 * (d["c_22_t2"] / d["aptos_t2"] - d["c_22_t1"] / d["aptos_t1"])
    d["d_comp"] = 100 * (d["comparecimento_t2"] / d["aptos_t2"] - d["comparecimento_t1"] / d["aptos_t1"])
    d["captura"] = d["d_lula"] / (100 - d["lula_t1"] - 100 * d["c_22_t1"] / d["aptos_t1"])
    return d


def amc(ano: int, e: pd.DataFrame) -> pd.DataFrame:
    op = config()["presidencial"][ano]["op"]
    m, cand = eleicao(ano)
    xw = tse_para_amc()[["cd_tse", "id_amc"]]
    v = cand[cand["NR_CANDIDATO"] == op].rename(columns={"QT_VOTOS_NOMINAIS": "votos_op"})
    m = m.merge(v[["NR_TURNO", "SG_UF", "CD_MUNICIPIO", "votos_op"]], on=["NR_TURNO", "SG_UF", "CD_MUNICIPIO"], how="left")
    m = m.merge(xw, left_on="CD_MUNICIPIO", right_on="cd_tse", how="inner")
    g = m.groupby(["id_amc", "NR_TURNO"])[["aptos", "comparecimento", "validos", "votos_pt", "votos_op"]].sum().unstack("NR_TURNO")
    g.columns = [f"{a}_t{t}" for a, t in g.columns]
    d = e[e["eleicao"] == ano].set_index("id_amc").join(g, rsuffix="_v")
    d["lula_t1"] = 100 * d["votos_pt_t1"] / d["aptos_t1"]
    d["terceiros_t1"] = 100 * (d["validos_t1"] - d["votos_pt_t1"] - d["votos_op_t1"]) / d["aptos_t1"]
    d["abst_t1"] = 100 * (1 - d["comparecimento_t1"] / d["aptos_t1"])
    d["d_lula"] = 100 * d["votos_pt_t2"] / d["aptos_t2"] - d["lula_t1"]
    d["d_op"] = 100 * (d["votos_op_t2"] / d["aptos_t2"] - d["votos_op_t1"] / d["aptos_t1"])
    d["d_comp"] = 100 * (d["comparecimento_t2"] / d["aptos_t2"] - d["comparecimento_t1"] / d["aptos_t1"])
    d["captura"] = d["d_lula"] / (100 - 100 * (d["votos_pt_t1"] + d["votos_op_t1"]) / d["aptos_t1"])
    d["peso"] = d["aptos_t2"]
    return d


def modelo(d: pd.DataFrame, ano: int) -> pd.DataFrame:
    z = d.dropna(subset=X_MOD + DISPONIVEL + ["d_lula", "peso", "id_microrregiao"]).copy()
    for c in X_MOD + DISPONIVEL:
        z[c] = (z[c] - z[c].mean()) / z[c].std()
    z = z.assign(aptos=z["peso"])
    linhas = []
    for nome, cs in [("sem voto disponível", X_MOD), ("com voto disponível", X_MOD + DISPONIVEL)]:
        m = M._wls("d_lula ~ " + " + ".join(cs) + " + C(sg_uf)", z)
        for v in cs:
            linhas.append({"ano": ano, "modelo": nome, "variavel": v, "beta": m.params[v], "ep": m.bse[v], "p": m.pvalues[v],
                           "n": int(m.nobs), "r2": m.rsquared})
    return pd.DataFrame(linhas)


def main() -> None:
    res, perfis = [], []
    d = locais()
    log.info("locais: %d; aptos %.0f", len(d), d["aptos_t2"].sum())
    topo = _decil(d["d_lula"], d["aptos_t2"])
    perfis.append(perfil(d, topo, "aptos_t2", V_LOCAIS, "locais, Brasil"))
    n_loc = d.groupby("id_municipio")["d_lula"].transform("size")
    c = d[n_loc >= 5].copy()
    pond = (c["d_lula"] * c["aptos_t2"]).groupby(c["id_municipio"]).transform("sum") / c.groupby("id_municipio")["aptos_t2"].transform("sum")
    c["d_rel"] = c["d_lula"] - pond
    topo_c = _decil(c["d_rel"], c["aptos_t2"])
    perfis.append(perfil(c, topo_c, "aptos_t2", V_LOCAIS, "locais, dentro do município"))
    perfis.append(perfil(d, _decil(d["captura"], d["aptos_t2"]), "aptos_t2", V_LOCAIS, "locais, decil de captura"))
    d3 = locais(300)
    perfis.append(perfil(d3, _decil(d3["d_lula"], d3["aptos_t2"]), "aptos_t2", V_LOCAIS, "locais ≥ 300 aptos, Brasil"))
    e = M.carregar()
    x = excesso()
    a26 = amc(2026, e).join(x[[EXC]])
    a22 = amc(2022, e)
    topo_a = _decil(a26["d_lula"], a26["peso"])
    perfis.append(perfil(a26, topo_a, "peso", V_AMC, "AMCs, Brasil"))
    um = a26.assign(um=1.0)
    topo_u = _decil(um["d_lula"], um["um"])
    perfis.append(perfil(um, topo_u, "um", V_AMC, "AMCs sem ponderar"))
    sem_go = a26[a26["sg_uf"] != "GO"]
    perfis.append(perfil(sem_go, _decil(sem_go["d_lula"], sem_go["peso"]), "peso", V_AMC, "AMCs, sem Goiás"))
    perfis.append(perfil(a26, _decil(a26["captura"], a26["peso"]), "peso", V_AMC, "AMCs, decil de captura"))
    for nome, s, p, t in [("locais", d["d_lula"], d["aptos_t2"], topo), ("locais, dentro do município", c["d_lula"], c["aptos_t2"], topo_c),
                          ("AMCs", a26["d_lula"], a26["peso"], topo_a), ("AMCs sem ponderar", um["d_lula"], um["um"], topo_u)]:
        res.append({"recorte": nome, "unidades": len(s), "unidades_topo": int(t.sum()), "aptos": float(p.sum()),
                    "d_lula_media": _wm(s, p), "d_lula_topo": _wm(s[t], p[t]), "d_lula_demais": _wm(s[~t], p[~t]),
                    "corte_topo": np.nan if "dentro" in nome else float(s[t].min())})
    _salvar(pd.DataFrame(res), "extra_turnos_resumo", "Δ Lula em p.p. dos aptos; médias ponderadas por aptos.")
    _salvar(pd.concat(perfis, ignore_index=True), "extra_turnos_perfil",
            "Médias ponderadas por aptos: decil superior de Δ Lula contra os demais. Diferença em desvios-padrão.")
    _salvar(pd.concat([modelo(a26, 2026), modelo(a22, 2022)], ignore_index=True), "extra_turnos_amc_modelo",
            "Δ Lula (p.p. dos aptos) por 1 DP, EF de UF, peso = aptos, EP por microrregião.")
    u = a26.assign(topo=topo_a).groupby("sg_uf").apply(lambda g: pd.Series({
        "aptos": g["peso"].sum(), "d_lula": _wm(g["d_lula"], g["peso"]), "captura": _wm(g["captura"], g["peso"]),
        "terceiros_t1": _wm(g["terceiros_t1"], g["peso"]),
        "pct_aptos_no_topo": 100 * g.loc[g["topo"], "peso"].sum() / g["peso"].sum()}), include_groups=False).reset_index()
    _salvar(u.sort_values("d_lula", ascending=False), "extra_turnos_uf", "AMCs agregadas por UF. captura = Δ Lula / voto disponível.")
    _salvar(maiores(a26), "extra_turnos_maiores",
            "AMCs com ≥ 100 mil aptos: as 20 de maior Δ Lula. Nome do município-sede da AMC, segundo o TSE.")


def maiores(a: pd.DataFrame) -> pd.DataFrame:
    z = zipfile.ZipFile(caminho("raw") / "tse" / "detalhe_votacao_munzona_2026.zip")
    n = pd.read_csv(z.open("detalhe_votacao_munzona_2026_BRASIL.csv"), sep=";", encoding="latin-1",
                    usecols=["CD_MUNICIPIO", "NM_MUNICIPIO"]).drop_duplicates("CD_MUNICIPIO")
    xw = tse_para_amc()[["cd_tse", "id_amc"]].merge(n, left_on="cd_tse", right_on="CD_MUNICIPIO")
    nome = xw[xw["cd_tse"].map(xw.groupby("cd_tse").size()) == 1].drop_duplicates("id_amc").set_index("id_amc")["NM_MUNICIPIO"]
    g = a[a["peso"] >= 100_000].nlargest(20, "d_lula").join(nome)
    return g.reset_index()[["NM_MUNICIPIO", "sg_uf", "peso", "d_lula", "d_op", "d_comp", "captura", "lula_t1", "terceiros_t1"]]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    main()
