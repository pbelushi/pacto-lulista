"""Fase E do plano3: indicadores brasileiros de esgotamento × conflito, eleições presidenciais 1994–2026.

Hipótese do plano: esgotamento → abstenção, brancos/nulos e votos fora dos dois primeiros em alta, e estrutura
social do voto (R²) em queda; conflito → o contrário (voto estruturado e concentrado em dois polos).

Fontes: TSE, CDN de Dados Abertos (detalhe_votacao_munzona e votacao_candidato_munzona, arquivos _BRASIL),
1994–2026. 1989 não está no CDN (HTTP 404 em 28/10/2026): a série começa em 1994 (registrado em pendencias.md).
1994 e 1998 não tiveram 2º turno, então os indicadores comparáveis são do 1º turno; o 2º turno entra de 2002 em
diante. Os arquivos de 2026 são os republicados pelo TSE em 30–31/10/2026, com o 2º turno (os de 25/10/2026 só
tinham o 1º; nesse intervalo o 2º turno vinha do painel do projeto, montado do Portal Resultados, com os mesmos
números município a município). Exterior (SG_UF = ZZ) e voto em trânsito (SG_UF = VT, em 2010) excluídos.

Indicadores (nacional e por UF; R² e Moran só nacional):
- abstenção (% dos aptos), brancos e nulos (% do comparecimento), 1º turno (e 2º quando houver);
- votos fora dos dois primeiros colocados nacionais (% dos válidos, 1º turno) e número efetivo de candidatos;
- R² da estrutura social: WLS (peso = aptos) da % do PT nos válidos por AMC sobre covariáveis fixas
  (IDHM 2010, % negra, % evangélica e % sem religião do Censo 2010, log do PIB per capita e peso da
  agropecuária no VAB do ano de referência do painel de 2010), sem efeito fixo de UF;
- Moran's I da % do PT por AMC (contiguidade queen, malha de AMCs do projeto; 999 permutações).
Limitação: AMCs criadas em 1997 e 2001 não existem em 1994 e 1998 (voto contado no município-mãe) e ficam sem
dado nesses anos.

Saídas: outputs/tables/p3_e_{nacional,uf}.{csv,md}; figuras p3_e_indicadores e p3_e_uf.

Uso: python -m src.p3_brasil
"""

from __future__ import annotations

import logging
import warnings
import zipfile

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import statsmodels.api as sm  # noqa: E402

from src.ingest.tse import colunas, tse_para_amc  # noqa: E402
from src.mapas import COR  # noqa: E402
from src.utils import caminho  # noqa: E402

log = logging.getLogger("p3_brasil")
warnings.filterwarnings("ignore", category=FutureWarning)
ANOS = [1994, 1998, 2002, 2006, 2010, 2014, 2018, 2022, 2026]
PT = 13
COVS = ["idhm_2010", "pct_negra", "pct_evangelica", "pct_sem_religiao", "log_pib_pc", "part_vab_agro"]
FONTE = "Fonte: TSE, Dados Abertos (1994–2026); IBGE; Atlas DH. Elaboração própria."


def _ler(conjunto: str, ano: int, cols: list[str]) -> pd.DataFrame:
    z = zipfile.ZipFile(caminho("raw") / "tse" / f"{conjunto}_{ano}.zip")
    partes = []
    with z.open(f"{conjunto}_{ano}_BRASIL.csv") as fh:
        for ch in pd.read_csv(fh, sep=";", encoding="latin-1", usecols=cols, chunksize=2_000_000, dtype={"SG_UF": str}):
            # ZZ = exterior; VT = voto em trânsito (código de UF próprio em 2010); ambos fora, como na Fase 1
            partes.append(ch[(ch["CD_CARGO"] == 1) & ~ch["SG_UF"].isin(["ZZ", "VT"])])
    return pd.concat(partes, ignore_index=True)


def eleicao(ano: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Por município TSE e turno: aptos, comparecimento, abstenção, brancos, nulos, válidos e votos do PT;
    e votos por candidato no 1º turno (para terceiros e número efetivo)."""
    base = ["NR_TURNO", "CD_CARGO", "SG_UF", "CD_MUNICIPIO"]
    det = _ler("detalhe_votacao_munzona", ano, base + ["QT_APTOS", "QT_COMPARECIMENTO", "QT_ABSTENCOES", "QT_VOTOS_BRANCOS",
                                                       "QT_VOTOS_NULOS", "QT_VOTOS_NULOS_TECNICOS", "QT_VOTOS_ANULADOS_APU_SEP"])
    det["nulos"] = det["QT_VOTOS_NULOS"] + det["QT_VOTOS_NULOS_TECNICOS"] + det["QT_VOTOS_ANULADOS_APU_SEP"]
    det = det.rename(columns={"QT_APTOS": "aptos", "QT_COMPARECIMENTO": "comparecimento", "QT_ABSTENCOES": "abstencoes",
                              "QT_VOTOS_BRANCOS": "brancos"})
    det = det.groupby(["NR_TURNO", "SG_UF", "CD_MUNICIPIO"])[["aptos", "comparecimento", "abstencoes", "brancos", "nulos"]].sum()
    # os arquivos do TSE preenchem só uma das duas colunas de votos e zeram a outra (1998: só _VALIDOS;
    # 2002–2006: só QT_VOTOS_NOMINAIS): usa-se o maior valor da linha
    vcols = [c for c in ["QT_VOTOS_NOMINAIS", "QT_VOTOS_NOMINAIS_VALIDOS"] if c in colunas("votacao_candidato_munzona", ano)]
    cand = _ler("votacao_candidato_munzona", ano, base + ["NR_CANDIDATO"] + vcols)
    cand["QT_VOTOS_NOMINAIS"] = cand[vcols].max(axis=1)
    cand = cand.groupby(["NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NR_CANDIDATO"])["QT_VOTOS_NOMINAIS"].sum().reset_index()
    v = cand.groupby(["NR_TURNO", "SG_UF", "CD_MUNICIPIO"])["QT_VOTOS_NOMINAIS"].sum().rename("validos")
    pt = cand[cand["NR_CANDIDATO"] == PT].groupby(["NR_TURNO", "SG_UF", "CD_MUNICIPIO"])["QT_VOTOS_NOMINAIS"].sum().rename("votos_pt")
    m = det.join(v).join(pt).fillna({"votos_pt": 0}).reset_index()
    m["ano"] = ano
    return m, cand.assign(ano=ano)


def nacional_uf(m: pd.DataFrame, cand: pd.DataFrame, nivel: list[str]) -> pd.DataFrame:
    g = m.groupby(nivel + ["NR_TURNO"])[["aptos", "comparecimento", "abstencoes", "brancos", "nulos", "validos", "votos_pt"]].sum()
    g["abstencao"] = 100 * g["abstencoes"] / g["aptos"]
    g["brancos_nulos"] = 100 * (g["brancos"] + g["nulos"]) / g["comparecimento"]
    g["s_pt"] = 100 * g["votos_pt"] / g["validos"]
    w = g[["abstencao", "brancos_nulos", "s_pt"]].unstack("NR_TURNO")
    w.columns = [f"{a}_t{t}" for a, t in w.columns]
    # 1º turno: votos fora dos dois primeiros nacionais e número efetivo de candidatos
    c1 = cand[cand["NR_TURNO"] == 1]
    top2 = c1.groupby("NR_CANDIDATO")["QT_VOTOS_NOMINAIS"].sum().nlargest(2).index
    tot = c1.groupby(nivel)["QT_VOTOS_NOMINAIS"].sum()
    fora = c1[~c1["NR_CANDIDATO"].isin(top2)].groupby(nivel)["QT_VOTOS_NOMINAIS"].sum()
    w["terceiros_t1"] = 100 * fora.reindex(w.index).fillna(0) / tot.reindex(w.index)
    pc = c1.groupby(nivel + ["NR_CANDIDATO"])["QT_VOTOS_NOMINAIS"].sum()
    pc = pc / pc.groupby(level=nivel).transform("sum")
    w["n_efetivo_candidatos_t1"] = 1 / (pc ** 2).groupby(level=nivel).sum()
    return w.reset_index()


# ---------------------------------------------------------------- estrutura (R²) e geografia (Moran)
def _amc(m: pd.DataFrame) -> pd.DataFrame:
    xw = tse_para_amc()[["cd_tse", "id_amc"]]
    a = m.merge(xw, left_on="CD_MUNICIPIO", right_on="cd_tse", how="left")
    perdidos = a.loc[a["id_amc"].isna(), "aptos"].sum() / a["aptos"].sum()
    if perdidos > 0.001:
        log.warning("%s: %.2f%% dos aptos sem AMC", m["ano"].iat[0], 100 * perdidos)
    return a.groupby(["NR_TURNO", "id_amc"])[["aptos", "validos", "votos_pt"]].sum().reset_index()


def covariaveis() -> pd.DataFrame:
    p = pd.read_parquet(caminho("processed") / "painel_eleicoes.parquet")
    c = p[p["eleicao"] == 2010].set_index("id_amc")
    out = pd.DataFrame({"idhm_2010": c["idhm_2010"], "pct_negra": c["pct_negra"], "pct_evangelica": c["pct_evangelica"],
                        "pct_sem_religiao": c["pct_sem_religiao"], "log_pib_pc": np.log(c["pib_pc_real"]),
                        "part_vab_agro": c["part_vab_agro"]})
    return out.dropna()


def r2_estrutura(s: pd.Series, w: pd.Series, x: pd.DataFrame) -> tuple[float, int]:
    d = x.join(s.rename("y")).join(w.rename("w")).dropna()
    d = d[d["w"] > 0]
    r = sm.WLS(d["y"], sm.add_constant(d[COVS]), weights=d["w"]).fit()
    return r.rsquared, len(d)


def moran(s: pd.Series, malha) -> tuple[float, float]:
    from esda.moran import Moran
    from libpysal.weights import Queen

    g = malha.merge(s.rename("y").reset_index(), on="id_amc", how="inner").dropna(subset=["y"]).reset_index(drop=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        w = Queen.from_dataframe(g, use_index=False)
        w.transform = "r"
        np.random.seed(20261028)  # esda.Moran sorteia as permutações no gerador global
        mi = Moran(g["y"].values, w, permutations=999)
    return mi.I, mi.p_sim


def main() -> None:
    import geopandas as gpd

    malha = gpd.read_parquet(caminho("interim") / "malha_amc.parquet")[["id_amc", "geometry"]]
    x = covariaveis()
    nac, uf, estr = [], [], []
    for ano in ANOS:
        m, cand = eleicao(ano)
        nac.append(nacional_uf(m.assign(br="Brasil"), cand.assign(br="Brasil"), ["br"]).assign(ano=ano))
        uf.append(nacional_uf(m, cand, ["SG_UF"]).assign(ano=ano))
        a = _amc(m)
        for t in [1, 2]:
            s = a[a["NR_TURNO"] == t].set_index("id_amc")
            if s.empty:
                continue
            spt = 100 * s["votos_pt"] / s["validos"]
            r2, n = r2_estrutura(spt, s["aptos"], x)
            mi, pm = moran(spt, malha)
            estr.append({"ano": ano, "turno": t, "r2_estrutura_social": r2, "amcs_r2": n, "moran_i": mi, "moran_p": pm,
                         "amcs_com_dado": int(spt.notna().sum())})
        log.info("%d: indicadores calculados", ano)
    n = pd.concat(nac).drop(columns="br")
    u = pd.concat(uf)
    e = pd.DataFrame(estr).pivot(index="ano", columns="turno", values=["r2_estrutura_social", "moran_i", "amcs_com_dado"])
    e.columns = [f"{a}_t{t}" for a, t in e.columns]
    n = n.merge(e.reset_index(), on="ano", how="left")
    cols = ["ano", "abstencao_t1", "brancos_nulos_t1", "terceiros_t1", "n_efetivo_candidatos_t1", "abstencao_t2",
            "brancos_nulos_t2", "s_pt_t1", "s_pt_t2", "r2_estrutura_social_t1", "r2_estrutura_social_t2", "moran_i_t1",
            "moran_i_t2", "amcs_com_dado_t1"]
    n = n[[c for c in cols if c in n]].astype({"ano": int, "amcs_com_dado_t1": int})
    _salvar(n, "p3_e_nacional",
            "Brasil sem exterior. t1/t2 = 1º/2º turno (1994 e 1998 sem 2º turno). terceiros_t1 = votos fora dos dois primeiros "
            "colocados nacionais, % dos válidos. R² = WLS da % do PT nos válidos por AMC sobre estrutura social fixa (IDHM 2010, "
            "% negra, % evangélica, % sem religião, log PIB per capita, % agro no VAB). Moran's I: contiguidade queen entre AMCs "
            "(todos com p < 0,01, 999 permutações). Em 1994 e 1998 as AMCs de municípios criados em 1997/2001 ficam sem dado.")
    _salvar(u[["ano", "SG_UF", "abstencao_t1", "brancos_nulos_t1", "terceiros_t1", "n_efetivo_candidatos_t1",
               "abstencao_t2", "brancos_nulos_t2", "s_pt_t1", "s_pt_t2"]], "p3_e_uf", "Por UF; mesmas definições da tabela nacional.")
    figuras(n, u)
    p_mor = pd.DataFrame(estr)["moran_p"].max()
    log.info("maior p de Moran: %.3f", p_mor)


def _salvar(df: pd.DataFrame, nome: str, nota: str = "") -> None:
    df.to_csv(caminho("tables") / f"{nome}.csv", index=False, encoding="utf-8")
    # inteiros (ano, contagens) como texto: o floatfmt do to_markdown também se aplica a eles
    md = df.astype({c: str for c in df.columns if pd.api.types.is_integer_dtype(df[c])})
    (caminho("tables") / f"{nome}.md").write_text(md.to_markdown(index=False, floatfmt=".3g") + f"\n\n{nota}\n\n{FONTE}\n",
                                                  encoding="utf-8")
    log.info("tabela %s", nome)


def _eixo(ax) -> None:
    from matplotlib.ticker import FuncFormatter

    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{round(v, 6):g}".replace(".", ",")))
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(COR["tinta2"])
    ax.tick_params(colors=COR["tinta2"], labelsize=7.5)
    ax.grid(axis="y", color="#e4e3dd", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.axvspan(2015, 2027, color="#efeee9", zorder=0)
    ax.set_xticks(ANOS, [str(a)[2:] if a < 2000 else str(a) for a in ANOS], fontsize=7)


def figuras(n: pd.DataFrame, u: pd.DataFrame) -> None:
    painel = [("abstencao_t1", "abstencao_t2", "Abstenção (% dos aptos)", "esgotamento ↑"),
              ("brancos_nulos_t1", "brancos_nulos_t2", "Brancos e nulos (% do comparecimento)", "esgotamento ↑"),
              ("terceiros_t1", None, "Votos fora dos 2 primeiros, 1º turno (% válidos)", "esgotamento ↑"),
              ("n_efetivo_candidatos_t1", None, "Número efetivo de candidatos, 1º turno", "esgotamento ↑"),
              ("r2_estrutura_social_t1", "r2_estrutura_social_t2", "R² da estrutura social no voto do PT", "conflito ↑"),
              ("moran_i_t1", "moran_i_t2", "Moran's I do voto do PT (AMCs)", "conflito ↑")]
    fig, axs = plt.subplots(2, 3, figsize=(11, 6))
    for ax, (c1, c2, tit, sinal) in zip(axs.ravel(), painel):
        ax.plot(n["ano"], n[c1], color=COR["tinta"], marker="o", markersize=4, linewidth=1.8, label="1º turno")
        if c2 and c2 in n:
            ax.plot(n["ano"], n[c2], color=COR["PT"], marker="s", markersize=4, linewidth=1.8, label="2º turno")
        _eixo(ax)
        ax.set_title(f"{tit}\n({sinal})", fontsize=8.5, loc="left")
    axs[0, 0].legend(frameon=False, fontsize=7.5)
    fig.suptitle("Brasil 1994–2026: indicadores de esgotamento × conflito (faixa cinza = episódio de polarização 2016–)",
                 x=0.01, ha="left", fontsize=10)
    fig.tight_layout(rect=(0, 0.04, 1, 0.97))
    fig.text(0.01, 0.005, FONTE, fontsize=6.5, color=COR["tinta2"])
    for ext in ["png", "svg"]:
        fig.savefig(caminho("figures") / f"p3_e_indicadores.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)
    # por UF: abstenção e terceiros no 1º turno, small multiples
    fig, axs = plt.subplots(1, 2, figsize=(11, 3.8), sharex=True)
    for ax, (c, tit) in zip(axs, [("abstencao_t1", "Abstenção no 1º turno (%), por UF"),
                                  ("terceiros_t1", "Votos fora dos 2 primeiros no 1º turno (%), por UF")]):
        for _, s in u.groupby("SG_UF"):
            ax.plot(s["ano"], s[c], color="#b9b8ae", linewidth=0.8)
        ax.plot(n["ano"], n[c], color=COR["tinta"], linewidth=2.2, marker="o", markersize=4, label="Brasil")
        _eixo(ax)
        ax.set_title(tit, fontsize=9, loc="left")
    axs[0].legend(frameon=False, fontsize=8)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.text(0.01, 0.005, FONTE + " Linhas cinza = UFs.", fontsize=6.5, color=COR["tinta2"])
    for ext in ["png", "svg"]:
        fig.savefig(caminho("figures") / f"p3_e_uf.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)
    log.info("figuras p3_e_indicadores e p3_e_uf")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    main()
