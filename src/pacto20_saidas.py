"""Fase E do pacto 2.0 (plano2.md): figuras (PNG 300 dpi + SVG em outputs/figures/).

- pacto20_mapas_capitais: s_PT no 2º turno por local de votação (células de Voronoi) em São Paulo,
  Rio de Janeiro, Salvador e Belo Horizonte, 2018 × 2026
- pacto20_betas: β de jovens e negros por eleição, 2010–2026 (2010 e 2014 = placebo), IC 95%
- pacto20_tercis: efeito de jovens e negros por tercil de renda do município, 2018/2022/2026
- pacto20_mobilizacao: Δ voto PT entre turnos (p.p. dos aptos) por perfil do local, cinco eleições

Convenção de cor do projeto (src/mapas.py): vermelho = PT, azul = opositor, cinza = neutro.
O validador de paleta do skill de visualização exige Node, ausente nesta máquina; as séries por ano
usam, além da cor, marcador e rótulo próprios (cor nunca é a única pista).

Uso: python -m src.pacto20_saidas
"""

from __future__ import annotations

import logging

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import shapely  # noqa: E402
from matplotlib.colors import Normalize  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from src.mapas import COR, DIVERGENTE  # noqa: E402
from src.pacto20_base import CHAVE  # noqa: E402
from src.pacto20_entorno import CRS_M, _voronoi  # noqa: E402
from src.utils import caminho  # noqa: E402

log = logging.getLogger("pacto20_saidas")
CAPITAIS = {3550308: "São Paulo", 3304557: "Rio de Janeiro", 2927408: "Salvador", 3106200: "Belo Horizonte"}
ANO_COR = {2018: "#9cbfe8", 2022: "#2a78d6", 2026: "#0d366b"}
ANO_MARCA = {2018: "o", 2022: "s", 2026: "D"}
ROT = {"jovens": "% jovens 16–34 no eleitorado do local (TSE)", "negros": "% pretos e pardos no entorno (Censo 2022)",
       "log_renda": "renda média do entorno (log)"}
FONTE = ("Fonte: TSE (votação e perfil do eleitorado por seção; locais de votação); IBGE, Censo 2022 por setor. "
         "Elaboração própria.")
FONTE_MOD = (FONTE + " WLS com EF de município×ano, peso = aptos; IC 95% com EP agrupado por município; "
             "X padronizado dentro de cada eleição.")


def _salvar(fig, nome: str, fonte: str = FONTE_MOD) -> None:
    fig.text(0.01, 0.005, fonte, fontsize=6.5, color=COR["tinta2"], ha="left", va="bottom", wrap=True)
    for ext, dpi in [("png", 300), ("svg", 150)]:
        fig.savefig(caminho("figures") / f"{nome}.{ext}", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    log.info("figura: %s", nome)


def _br(v: float, casas: int | None = None) -> str:
    """Número com vírgula decimal."""
    return (f"{v:.{casas}f}" if casas is not None else f"{v:g}").replace(".", ",")


def _eixo(ax) -> None:
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: _br(round(v, 6))))
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(COR["tinta2"])
    ax.tick_params(colors=COR["tinta2"], labelsize=8)
    ax.grid(axis="y", color="#e4e3dd", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.axhline(0, color=COR["tinta2"], linewidth=0.8)


# ---------------------------------------------------------------- mapas
def mapas_capitais() -> None:
    st = gpd.read_parquet(caminho("interim") / "pacto20_setores.parquet", columns=["id_municipio", "geometry"])
    st = st[st["id_municipio"].isin(CAPITAIS)]
    norm = Normalize(20, 80)
    fig, axs = plt.subplots(len(CAPITAIS), 2, figsize=(8.5, 3.3 * len(CAPITAIS)))
    for j, ano in enumerate([2018, 2026]):
        b = pd.read_parquet(caminho("interim") / f"pacto20_locais_{ano}.parquet")
        for i, (mun, nome) in enumerate(CAPITAIS.items()):
            ax = axs[i, j]
            sm = st[st["id_municipio"] == mun]
            limite = shapely.make_valid(shapely.union_all(shapely.make_valid(sm.geometry.values)))
            p = b[(b["id_municipio"] == mun) & b["lat"].notna() & (b["nominais_t2"] > 0)].copy()
            pts = gpd.GeoDataFrame(p[CHAVE], geometry=gpd.points_from_xy(p["lon"], p["lat"]), crs=4326).to_crs(CRS_M)
            # locais na mesma coordenada dividem a célula: a cor é o s_PT conjunto da célula
            pts["cel"] = _voronoi(pts, limite).values
            pts["c13"], pts["nom"] = p["c_13_t2"].values, p["nominais_t2"].values
            pts["k"] = pts.geometry.apply(lambda q: (round(q.x), round(q.y)))
            g = pts.groupby("k").agg(c13=("c13", "sum"), nom=("nom", "sum"), cel=("cel", "first"))
            g = gpd.GeoDataFrame(g, geometry=g["cel"], crs=CRS_M).drop(columns="cel")
            g = g[g.geometry.notna() & ~g.geometry.is_empty]
            g["s_pt"] = 100 * g["c13"] / g["nom"]
            g.plot(ax=ax, column=g["s_pt"].clip(20, 80), cmap=DIVERGENTE, norm=norm, linewidth=0.05,
                   edgecolor="#fcfcfb", rasterized=True)
            gpd.GeoSeries([limite], crs=CRS_M).boundary.plot(ax=ax, color=COR["tinta2"], linewidth=0.4)
            ax.set_axis_off()
            tot = 100 * g["c13"].sum() / g["nom"].sum()
            ax.set_title(f"{nome}, {ano}: PT {_br(tot, 1)}% ({len(g)} células)", fontsize=9, loc="left")
    cax = fig.add_axes([0.25, 0.05, 0.5, 0.007])
    cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=DIVERGENTE), cax=cax, orientation="horizontal")
    cb.set_label("% dos votos válidos do PT no 2º turno (escala cortada em 20 e 80)", fontsize=8)
    cb.ax.tick_params(labelsize=7)
    fig.suptitle("Voto no PT no 2º turno por local de votação: 2018 (Haddad) e 2026 (Lula)", x=0.01, ha="left",
                 fontsize=11, y=0.995)
    fig.subplots_adjust(bottom=0.075, top=0.955, hspace=0.1, wspace=0.02)
    _salvar(fig, "pacto20_mapas_capitais",
            "Fonte: TSE (votação por seção, 2º turno; coordenadas dos locais); IBGE, malha de setores do Censo 2022. "
            "Cada célula é a área de Voronoi do local de votação, recortada pelo limite municipal.")


# ---------------------------------------------------------------- β por eleição
def betas() -> None:
    b = pd.read_csv(caminho("tables") / "pacto20_faseD_placebo_betas.csv")
    fig, axs = plt.subplots(1, 2, figsize=(9, 3.6))
    for ax, v in zip(axs, ["jovens", "negros"]):
        s = b[b["variavel"] == v].sort_values("ano")
        ax.axvspan(2008, 2016, color="#efeee9", zorder=0)
        ax.text(2012, 1.0, "placebo\n(Dilma)", transform=ax.get_xaxis_transform(), ha="center", va="top",
                fontsize=7.5, color=COR["tinta2"])
        ax.errorbar(s["ano"], s["beta"], yerr=[s["beta"] - s["ic_inf"], s["ic_sup"] - s["beta"]], color=COR["PT"],
                    marker="o", markersize=6, linewidth=2, capsize=0, elinewidth=1.5)
        for _, r in s.iterrows():
            ax.annotate(_br(r["beta"], 1 if v == "negros" else 2), (r["ano"], r["beta"]),
                        xytext=(8, 7), textcoords="offset points", fontsize=7.5, color=COR["tinta"], va="bottom",
                        bbox={"boxstyle": "square,pad=0.1", "fc": "#fcfcfb", "ec": "none", "alpha": 0.85})
        _eixo(ax)
        ax.set_xticks(s["ano"])
        ax.set_xlim(2008, 2028)
        ax.set_title(ROT[v], fontsize=9, loc="left")
        ax.set_ylabel("p.p. de voto no PT por 1 DP", fontsize=8)
    fig.suptitle("Efeito líquido sobre o voto no PT no 2º turno, dentro do município (β e IC 95%)", x=0.01,
                 ha="left", fontsize=10)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    _salvar(fig, "pacto20_betas")


# ---------------------------------------------------------------- tercis
def tercis() -> None:
    t = pd.read_csv(caminho("tables") / "pacto20_faseC_c1_tercis.csv")
    t = t[t["tercil_renda"].astype(str).isin(["1", "2", "3"])].copy()
    t["tercil"] = t["tercil_renda"].astype(int)
    fig, axs = plt.subplots(1, 2, figsize=(9, 3.6))
    for ax, v in zip(axs, ["jovens", "negros"]):
        for k, (ano, s) in enumerate(t[t["variavel"] == v].groupby("ano")):
            x = s["tercil"] + (k - 1) * 0.18
            ax.errorbar(x, s["efeito_pp_por_dp"], yerr=[s["efeito_pp_por_dp"] - s["ic_inf"],
                                                         s["ic_sup"] - s["efeito_pp_por_dp"]],
                        color=ANO_COR[ano], marker=ANO_MARCA[ano], markersize=6, linestyle="none", elinewidth=1.5,
                        label=str(ano), markeredgecolor="#fcfcfb", markeredgewidth=0.8)
        _eixo(ax)
        ax.set_xticks([1, 2, 3], ["tercil inferior", "tercil médio", "tercil superior"])
        ax.set_title(ROT[v], fontsize=9, loc="left")
        ax.set_ylabel("p.p. de voto no PT por 1 DP", fontsize=8)
    axs[0].legend(title="eleição", frameon=False, fontsize=8, title_fontsize=8, loc="upper right")
    fig.suptitle("Efeito por tercil de renda do entorno (tercis dentro de cada município), IC 95%", x=0.01, ha="left",
                 fontsize=10)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    _salvar(fig, "pacto20_tercis")


# ---------------------------------------------------------------- mobilização entre turnos
def mobilizacao() -> None:
    c = pd.read_csv(caminho("tables") / "pacto20_faseC_c4_comparado.csv")
    c = c[c["resultado"] == "Δ voto PT (% aptos)"]
    fig, axs = plt.subplots(1, 3, figsize=(10, 3.4), sharey=True)
    for ax, v in zip(axs, ["negros", "jovens", "log_renda"]):
        s = c[c["variavel"] == v].sort_values("ano")
        cor = [COR["PT"] if a == 2026 else COR["neutro"] for a in s["ano"]]
        ax.bar(s["ano"].astype(str), s["beta"], color=cor, width=0.6)
        ax.errorbar(s["ano"].astype(str), s["beta"], yerr=1.96 * s["ep"], color=COR["tinta2"], linestyle="none",
                    elinewidth=1)
        _eixo(ax)
        ax.set_title(ROT[v], fontsize=8.5, loc="left")
    axs[0].set_ylabel("Δ voto PT entre turnos (p.p. dos aptos) por 1 DP", fontsize=8)
    fig.suptitle("Onde o PT cresceu do 1º para o 2º turno: 2026 (em vermelho) contra as eleições anteriores",
                 x=0.01, ha="left", fontsize=10)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    _salvar(fig, "pacto20_mobilizacao")


def main() -> None:
    betas()
    tercis()
    mobilizacao()
    mapas_capitais()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    main()
