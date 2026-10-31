"""Fase 2 — mapas e gráficos dos esquemas de grupos (PNG 300 dpi + SVG em outputs/figures/).

Convenção de cor (todas as figuras): vermelho = PT, azul = opositor/antipetista, cinza = neutro.
Os polígonos municipais são rasterizados dentro do SVG (texto, legenda e limites de UF ficam
vetoriais); sem isso cada SVG passa de 100 MB.
Esquemas com mais de 3 categorias viram small multiples (um painel por categoria em destaque),
porque mapas coropléticos com 4+ cores não são distinguíveis com segurança para daltônicos.

Uso: python -m src.mapas
"""

from __future__ import annotations

import logging

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from src.ingest.malhas import malha_uf  # noqa: E402
from src.utils import caminho, config  # noqa: E402

log = logging.getLogger("mapas")

COR = {"PT": "#e34948", "OP": "#2a78d6", "neutro": "#c3c2b7", "fundo": "#efeee9", "na": "#ffffff",
       "destaque": "#0d366b", "tinta": "#0b0b0b", "tinta2": "#52514e", "uf": "#52514e"}
COR_G = {"G_PT": COR["PT"], "G_EST": COR["neutro"], "G_OP": COR["OP"]}
COR_P = {"P_PT": COR["PT"], "P_OUTRO": COR["neutro"], "P_ANTI": COR["OP"]}
DIVERGENTE = LinearSegmentedColormap.from_list("op_pt", ["#104281", COR["OP"], "#f0efec", COR["PT"], "#9e2a2a"])

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans"], "font.size": 9, "text.color": COR["tinta"],
    "axes.edgecolor": "none", "figure.facecolor": "#fcfcfb", "savefig.facecolor": "#fcfcfb",
})

FONTE_PRES = "Fonte: TSE, 2º turno presidencial. Malha: IBGE 2022 (geobr), em AMCs."
FONTE_PROP = "Fonte: TSE, votação para deputado federal por partido. Malha: IBGE 2022 (geobr), em AMCs."


def _dados() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, pd.DataFrame]:
    malha = gpd.read_parquet(caminho("interim") / "malha_amc.parquet")
    ufs = gpd.GeoDataFrame(geometry=malha_uf().boundary)
    # simplificação só para desenho (≈ 500 m); não afeta nenhum cálculo
    malha["geometry"] = malha.simplify(0.005, preserve_topology=True)
    gpres = pd.read_parquet(caminho("processed") / "grupos_presidenciais.parquet")
    gprop = pd.read_parquet(caminho("processed") / "grupos_proporcionais.parquet")
    g = malha.merge(gpres.drop(columns=["sg_uf", "regiao"]), on="id_amc", how="left")
    return g, ufs, gprop


def _base(ax, ufs) -> None:
    ufs.plot(ax=ax, color=COR["uf"], linewidth=0.25)
    ax.set_axis_off()
    ax.set_aspect("equal")


def _salvar(fig, nome: str, fonte: str) -> None:
    fig.text(0.01, 0.01, fonte, fontsize=7, color=COR["tinta2"], ha="left", va="bottom")
    # PNG a 300 dpi; no SVG, só a camada rasterizada dos polígonos usa 100 dpi (texto segue vetorial)
    for ext, dpi in [("png", 300), ("svg", 100)]:
        fig.savefig(caminho("figures") / f"{nome}.{ext}", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    log.info("figura: %s", nome)


def _categorico(ax, g, col, cores, ufs, titulo, rotulos=None) -> None:
    cor = g[col].map(cores).fillna(COR["na"])
    g.plot(ax=ax, color=cor, linewidth=0, rasterized=True)
    _base(ax, ufs)
    ax.set_title(titulo, fontsize=10, loc="left")
    n = g[col].value_counts()
    alca = [Patch(facecolor=c, label=f"{(rotulos or {}).get(k, k)} ({n.get(k, 0)})") for k, c in cores.items()]
    if g[col].isna().any():
        alca.append(Patch(facecolor=COR["na"], edgecolor=COR["neutro"], label=f"empate ({g[col].isna().sum()})"))
    ax.legend(handles=alca, loc="lower left", frameon=False, fontsize=8)


def _small_multiples(g, col, categorias, ufs, titulo, nome, fonte, ncol=None, rotulos=None) -> None:
    n = len(categorias)
    ncol = ncol or min(n, 3)
    nlin = -(-n // ncol)
    fig, axs = plt.subplots(nlin, ncol, figsize=(4 * ncol, 4.2 * nlin))
    for ax in axs.flat[n:]:
        ax.set_visible(False)
    for ax, cat in zip(axs.flat, categorias):
        sel = g[col] == cat
        g.plot(ax=ax, color=COR["fundo"], linewidth=0, rasterized=True)
        g[sel].plot(ax=ax, color=COR["destaque"], linewidth=0, rasterized=True)
        _base(ax, ufs)
        apt = g.loc[sel, "aptos_2026"].sum() / g["aptos_2026"].sum() * 100
        ax.set_title(f"{(rotulos or {}).get(cat, cat)}\n{sel.sum()} AMCs · {apt:.0f}% do eleitorado 2026",
                     fontsize=9, loc="left")
    fig.suptitle(titulo, fontsize=11, x=0.01, ha="left")
    _salvar(fig, nome, fonte)


def mapa_swing(g, ufs) -> None:
    cfg = config()
    b, f = cfg["ano_base"], cfg["ano_final"]
    fig, axs = plt.subplots(1, 2, figsize=(12, 6))
    lim = 30
    g.plot(ax=axs[0], column=g["swing"].clip(-lim, lim), cmap=DIVERGENTE,
           norm=TwoSlopeNorm(0, -lim, lim), linewidth=0, rasterized=True, legend=True,
           legend_kwds={"shrink": 0.6, "label": "swing relativo (p.p.; truncado em ±30)"})
    _base(axs[0], ufs)
    axs[0].set_title(f"Swing relativo do PT, {b}→{f}\n(variação do município − variação nacional)", fontsize=10, loc="left")
    _categorico(axs[1], g, "g_swing", COR_G, ufs, f"Grupos de swing (±{cfg['grupos']['limiar_dp']:g} DP)")
    _salvar(fig, "fase2_mapa_swing", FONTE_PRES)

    fig, axs = plt.subplots(1, 3, figsize=(15, 5.5))
    for ax, col, tit in zip(axs, ["g_swing_dp05", "g_swing_q5", "g_swing_t3"], ["±0,5 DP", "quintis", "tercis"]):
        _categorico(ax, g, col, COR_G, ufs, f"Grupos de swing: {tit}")
    _salvar(fig, "fase2_mapa_swing_variantes", FONTE_PRES)


def mapa_tipologia(g, ufs) -> None:
    cats = ["PT↑OP↓", "PT↓OP↑", "ambos↑", "ambos↓"]
    b, f = config()["ano_base"], config()["ano_final"]
    _small_multiples(g, "tipo_2x2", cats, ufs, f"Tipologia 2×2 sobre o eleitorado apto, {b}→{f} (variação bruta)",
                     "fase2_mapa_tipologia_2x2", FONTE_PRES, ncol=4)
    _small_multiples(g, "tipo_2x2_rel", cats, ufs,
                     f"Tipologia 2×2 sobre o eleitorado apto, {b}→{f} (variação menos a variação nacional)",
                     "fase2_mapa_tipologia_2x2_rel", FONTE_PRES, ncol=4)


def mapa_clusters(g, ufs) -> None:
    rot = config()["grupos"]["rotulos_cluster"]
    cores_nivel = {1: COR["PT"], 2: COR["neutro"], 3: COR["OP"]}
    fig, ax = plt.subplots(figsize=(6.5, 6.5))
    _categorico(ax, g, "cluster_nivel", cores_nivel, ufs, "Clusters de trajetória: nível (k = 3)", rotulos=rot["nivel"])
    _salvar(fig, "fase2_mapa_cluster_nivel", FONTE_PRES)
    cats = sorted(g["cluster_forma"].dropna().unique())
    _small_multiples(g, "cluster_forma", cats, ufs, f"Clusters de trajetória: forma (k = {len(cats)})",
                     "fase2_mapa_cluster_forma", FONTE_PRES, ncol=len(cats), rotulos=rot["forma"])


def grafico_centroides() -> None:
    """Trajetória média de cada cluster de forma (desvio em relação ao share nacional do PT)."""
    c = pd.read_csv(caminho("tables") / "fase2_centroides_clusters.csv")
    k = config()["grupos"]["k_escolhido"]["forma"]
    rot = config()["grupos"]["rotulos_cluster"]["forma"]
    c = c[(c["modo"] == "forma") & (c["k"] == k)]
    anos = [a for a in c.columns if a.isdigit()]
    # cores fixas por cluster, sem vermelho/azul (reservados a PT/opositor nas demais figuras)
    cores = ["#1baf7a", "#eb6834", "#6250d6", "#eda100"]
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    ax.axhline(0, color="#c3c2b7", linewidth=1)
    for (_, r), cor in zip(c.iterrows(), cores):
        y = r[anos].astype(float).values
        ax.plot([int(a) for a in anos], y, color=cor, linewidth=2, marker="o", markersize=4)
        ax.annotate(f"{int(r['cluster'])}: {rot.get(int(r['cluster']), '')} (n={int(r['n'])})",
                    (int(anos[-1]), y[-1]), xytext=(6, 0), textcoords="offset points",
                    va="center", fontsize=8, color=COR["tinta"])
    ax.set_xticks([int(a) for a in anos])
    ax.set_ylabel("s_PT do município − s_PT nacional (p.p.)", color=COR["tinta2"])
    ax.grid(axis="y", color="#e1e0d9", linewidth=0.5)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_title("Trajetória média por cluster de forma (k = 4)", loc="left", fontsize=10)
    _salvar(fig, "fase2_centroides_cluster_forma", FONTE_PRES)


def mapa_proporcional(g, ufs, gprop) -> None:
    pres_anti = config()["presidencial"]
    for versao in ["partido", "federacao"]:
        anos = config()["anos_eleicao"]
        fig, axs = plt.subplots(2, 3, figsize=(15, 10))
        for ax, ano in zip(axs.flat, anos):
            gg = g[["id_amc", "geometry", "aptos_2026"]].merge(
                gprop[(gprop["ano"] == ano) & (gprop["versao"] == versao)][["id_amc", "g_prop"]], on="id_amc")
            gg = gpd.GeoDataFrame(gg, geometry="geometry")
            rot = {"P_PT": "PT", "P_ANTI": pres_anti[ano]["partido_op"], "P_OUTRO": "outro partido"}
            _categorico(ax, gg, "g_prop", COR_P, ufs, f"{ano}: partido mais votado para a Câmara", rotulos=rot)
        sufixo = "" if versao == "partido" else " (federações como unidade)"
        fig.suptitle(f"Grupos proporcionais por eleição{sufixo}", fontsize=11, x=0.01, ha="left")
        _salvar(fig, f"fase2_mapa_grupos_proporcionais_{versao}", FONTE_PROP)


def mapa_trajetoria_prop(g, ufs) -> None:
    cats = ["enraizado_PT", "enraizado_ANTI", "migrante_PT_ANTI", "migrante_ANTI_PT", "nunca_polarizado", "intermitente"]
    rot = {"enraizado_PT": "enraizado PT (≥4 de 6)", "enraizado_ANTI": "enraizado antipetista (≥4 de 6)",
           "migrante_PT_ANTI": "migrante PT → antipetista", "migrante_ANTI_PT": "migrante antipetista → PT",
           "nunca_polarizado": "nunca polarizado", "intermitente": "intermitente"}
    _small_multiples(g, "traj_prop", cats, ufs, "Trajetórias proporcionais (deputado federal, 2006–2026)",
                     "fase2_mapa_trajetoria_proporcional", FONTE_PROP, ncol=3, rotulos=rot)


def mapa_fora_diagonal(g, ufs, gprop) -> None:
    """Células fora da diagonal da matriz presidencial × proporcional no ano final."""
    f = config()["ano_final"]
    p = gprop[(gprop["ano"] == f) & (gprop["versao"] == "partido")].set_index("id_amc")["g_prop"]
    gg = g.assign(g_prop=g["id_amc"].map(p))
    gg["celula"] = None
    gg.loc[(gg["g_swing"] == "G_PT") & gg["g_prop"].isin(["P_OUTRO", "P_ANTI"]), "celula"] = "lula_sem_pt"
    gg.loc[(gg["g_swing"] == "G_OP") & (gg["g_prop"] == "P_OUTRO"), "celula"] = "bolsonarismo_sem_pl"
    rot = {"lula_sem_pt": f"\"Lula sem PT\": G_PT e PT não lidera na Câmara em {f}",
           "bolsonarismo_sem_pl": f"\"Bolsonarismo sem PL\": G_OP e outro partido lidera em {f}"}
    _small_multiples(gg, "celula", list(rot), ufs, f"Células fora da diagonal, presidencial × proporcional ({f})",
                     "fase2_mapa_fora_diagonal", FONTE_PRES + " Câmara: TSE.", ncol=2, rotulos=rot)


def main() -> None:
    g, ufs, gprop = _dados()
    mapa_swing(g, ufs)
    mapa_tipologia(g, ufs)
    mapa_clusters(g, ufs)
    grafico_centroides()
    mapa_proporcional(g, ufs, gprop)
    mapa_trajetoria_prop(g, ufs)
    mapa_fora_diagonal(g, ufs, gprop)


if __name__ == "__main__":
    main()
