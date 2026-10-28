"""Fase 7 (parte espacial) — docs/planos/PLANO.md, seção 5.

Matriz de vizinhança: k = 8 vizinhos mais próximos pelos centroides das AMCs (projeção policônica,
EPSG:5880), padronizada na linha. Não se usa contiguidade (rainha) porque a malha simplificada do
geobr tem frestas entre municípios (ver src/ingest/malhas.py), o que criaria ilhas espúrias.

1. Moran's I global dos resíduos dos modelos centrais (s_pt por eleição, spec. A; diferenças longas)
   e do swing; 999 permutações.
2. LISA do swing 2010→2026 (Moran local, p < 0,05) e mapa.
3. Modelos com erro espacial (GM_Error_Het) e lag espacial (GM_Lag) do spreg para s_pt 2010 e 2026
   (spec. A) e para as diferenças longas, comparados ao MQO. O spreg não aceita pesos: as três versões
   são sem ponderação (comparar com a robustez "sem ponderação").
4. Erros-padrão de Conley (kernel de Bartlett, cortes de 100 e 250 km) para os β por eleição de
   s_pt e do hiato (WLS, spec. A), comparados aos agrupados por microrregião.

Saídas: outputs/tables/fase7_espacial_*.csv/.md e outputs/figures/fase7_lisa_swing.png/.svg
"""

from __future__ import annotations

import logging
import warnings

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from esda.moran import Moran, Moran_Local  # noqa: E402
from libpysal.weights import KNN, w_subset  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from sklearn.neighbors import BallTree  # noqa: E402
from spreg import OLS, GM_Error_Het, GM_Lag  # noqa: E402

from src import models as M  # noqa: E402
from src.mapas import COR, _base  # noqa: E402
from src.ingest.malhas import malha_uf  # noqa: E402
from src.utils import caminho, config  # noqa: E402

log = logging.getLogger("spatial")
warnings.filterwarnings("ignore")
K_VIZ = 8
RAIO_TERRA_KM = 6371.0


def _salvar(df: pd.DataFrame, nome: str) -> None:
    df.to_csv(caminho("tables") / f"{nome}.csv", index=False, encoding="utf-8")
    (caminho("tables") / f"{nome}.md").write_text(df.to_markdown(index=False, floatfmt=".4g"), encoding="utf-8")


def geometria() -> gpd.GeoDataFrame:
    g = gpd.read_parquet(caminho("interim") / "malha_amc.parquet")[["id_amc", "geometry"]]
    proj = g.to_crs(5880)
    cent = proj.geometry.centroid
    g["x"], g["y"] = cent.x, cent.y
    ll = gpd.GeoSeries(cent, crs=5880).to_crs(4326)
    g["lon"], g["lat"] = ll.x, ll.y
    return g.sort_values("id_amc").reset_index(drop=True)


def pesos(geo: gpd.GeoDataFrame):
    w = KNN(geo[["x", "y"]].to_numpy(), k=K_VIZ, ids=geo["id_amc"].tolist())
    w.transform = "r"
    return w


# ---------------------------------------------------------------- 1–2. Moran e LISA
def _residuos_wls(z: pd.DataFrame, y: str, t: int, extra=()) -> pd.Series:
    d = z[z["eleicao"] == t].dropna(subset=[y] + M.X_A + list(extra) + ["aptos", "id_microrregiao"])
    cols = M.X_A + list(extra)
    m = M._wls(f"{y} ~ {' + '.join(cols)} + ideb_ausente + C(sg_uf)", d)
    return pd.Series(m.resid.values, index=d["id_amc"].values)


def moran_global(z: pd.DataFrame, dl: pd.DataFrame, geo, w) -> pd.DataFrame:
    linhas = []
    ids = geo["id_amc"].to_numpy()

    def moran(serie: pd.Series, rotulo: str):
        v = serie.reindex(ids)
        ok = v.notna().to_numpy()
        ww = w
        if not ok.all():  # AMC sem covariável (ex.: 1 em 2006): restringe a vizinhança às disponíveis
            ww = w_subset(w, list(ids[ok]))
            ww.transform = "r"
        mi = Moran(v.to_numpy()[ok], ww, permutations=999)
        linhas.append({"serie": rotulo, "n": int(ok.sum()), "moran_I": mi.I, "E_I": mi.EI, "z": mi.z_sim,
                       "p_sim": mi.p_sim})

    sw = dl.set_index("id_amc")["swing"]
    moran(sw, "swing 2010→2026 (variável)")
    for t in config()["anos_eleicao"]:
        if config()["alinhamento"]["censo"][t] is None:
            continue
        moran(z[z["eleicao"] == t].set_index("id_amc")["s_pt"], f"s_pt {t} (variável)")
        moran(_residuos_wls(z, "s_pt", t), f"resíduo s_pt {t} (WLS, spec. A, EF UF)")
        moran(_residuos_wls(z, "hiato_lulista", t, ["nep"]), f"resíduo hiato_lulista {t}")
    cols = [f"{v}_0" for v in M.X_A] + [f"d_{v}" for v in M.X_A]
    m = M._wls(f"swing ~ {' + '.join(cols)} + ideb_ausente + C(sg_uf)", dl)
    moran(pd.Series(m.resid.values, index=dl["id_amc"].values), "resíduo diferenças longas")
    return pd.DataFrame(linhas)


def lisa_swing(dl: pd.DataFrame, geo, w) -> gpd.GeoDataFrame:
    v = dl.set_index("id_amc")["swing"].reindex(geo["id_amc"]).to_numpy()
    lm = Moran_Local(v, w, permutations=999, seed=20261027)
    quad = {1: "HH", 2: "LH", 3: "LL", 4: "HL"}
    g = geo.copy()
    g["lisa"] = [quad[q] if p < 0.05 else "n.s." for q, p in zip(lm.q, lm.p_sim)]
    return g


def fig_lisa(g: gpd.GeoDataFrame) -> None:
    ufs = gpd.GeoDataFrame(geometry=malha_uf().boundary)
    g = g.copy()
    g["geometry"] = g.simplify(0.005, preserve_topology=True)
    cores = {"HH": COR["PT"], "LL": COR["OP"], "HL": "#52514e", "LH": "#52514e", "n.s.": COR["fundo"]}
    rot = {"HH": "HH: swing pró-PT cercado de swing pró-PT", "LL": "LL: swing pró-oposição cercado de igual",
           "HL": "outliers (HL / LH)", "n.s.": "não significativo (p ≥ 0,05)"}
    fig, ax = plt.subplots(figsize=(7.5, 7.5))
    g.plot(ax=ax, color=g["lisa"].map(cores), linewidth=0, rasterized=True)
    _base(ax, ufs)
    n = g["lisa"].value_counts()
    alca = [Patch(facecolor=cores[k], label=f"{rot[k]} ({n.get(k, 0) + (n.get('LH', 0) if k == 'HL' else 0)})")
            for k in ["HH", "LL", "HL", "n.s."]]
    ax.legend(handles=alca, loc="upper left", bbox_to_anchor=(0, 0), frameon=False, fontsize=8, ncol=2)
    ax.set_title("LISA do swing relativo do PT, 2010→2026\n(k = 8 vizinhos, 999 permutações)", fontsize=10, loc="left")
    fig.text(0.01, 0.01, "Fonte: TSE; malha IBGE 2022 (geobr), em AMCs.", fontsize=7, color=COR["tinta2"])
    for ext, dpi in [("png", 300), ("svg", 100)]:
        fig.savefig(caminho("figures") / f"fase7_lisa_swing.{ext}", dpi=dpi, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------- 3. spreg
def _matriz(d: pd.DataFrame, cols: list[str]) -> tuple[np.ndarray, list[str]]:
    uf = pd.get_dummies(d["sg_uf"], prefix="uf", drop_first=True, dtype=float)
    X = pd.concat([d[cols + ["ideb_ausente"]].astype(float), uf], axis=1)
    return X.to_numpy(), list(X.columns)


def modelos_spreg(z: pd.DataFrame, dl: pd.DataFrame, geo) -> pd.DataFrame:
    linhas = []
    casos = [(f"s_pt {t}", z[z["eleicao"] == t], "s_pt", M.X_A) for t in [config()["ano_base"], config()["ano_final"]]]
    casos.append(("swing (diferenças longas)", dl, "swing", [f"{v}_0" for v in M.X_A] + [f"d_{v}" for v in M.X_A]))
    for rot, d, y, cols in casos:
        d = d.set_index("id_amc").reindex(geo["id_amc"]).reset_index()
        assert d[[y] + cols].notna().all().all(), rot
        wd = pesos(geo)
        X, nomes = _matriz(d, cols)
        yy = d[[y]].to_numpy(float)
        res = {"MQO": OLS(yy, X, w=wd, spat_diag=True, moran=True, name_x=nomes),
               "erro espacial (GM_Error_Het)": GM_Error_Het(yy, X, w=wd, name_x=nomes),
               "lag espacial (GM_Lag)": GM_Lag(yy, X, w=wd, name_x=nomes)}
        for nome, r in res.items():
            # GM_Lag guarda os nomes (inclusive W_dep_var = ρ) em name_z; os demais em name_x
            nx = list(r.name_z) if nome.startswith("lag") else list(r.name_x)
            ep = np.sqrt(np.diag(r.vm))
            for v in cols:
                i = nx.index(v)
                linhas.append({"modelo_de": rot, "estimador": nome, "variavel": v, "coef": float(r.betas[i][0]),
                               "ep": float(ep[i])})
            extra = {}
            if nome.startswith("erro"):
                extra = {"variavel": "lambda (erro espacial)", "coef": float(r.betas[-1][0]), "ep": float(ep[-1])}
            elif nome.startswith("lag"):
                extra = {"variavel": "rho (lag espacial)", "coef": float(r.betas[nx.index("W_dep_var")][0]),
                         "ep": float(ep[nx.index("W_dep_var")])}
            if extra:
                linhas.append({"modelo_de": rot, "estimador": nome, **extra})
        log.info("spreg: %s", rot)
    out = pd.DataFrame(linhas)
    out["z"] = out["coef"] / out["ep"]
    return out


# ---------------------------------------------------------------- 4. Conley
def conley(d: pd.DataFrame, formula: str, latlon: np.ndarray, cortes_km=(100, 250)) -> pd.DataFrame:
    """EPs de Conley (Bartlett) para WLS: V = B·M·B, B = (X'WX)⁻¹, M = Σ_ij K(d_ij)·s_i·s_j', s_i = w_i·x_i·e_i."""
    m = M._wls(formula, d)
    X = m.model.exog
    w = d["aptos"].to_numpy(float)
    e = (m.model.endog - X @ m.params.to_numpy())
    s = X * (w * e)[:, None]
    bread = np.linalg.inv(X.T @ (X * w[:, None]))
    arv = BallTree(np.radians(latlon), metric="haversine")
    saida = {"cluster_microrregiao": m.bse}
    for corte in cortes_km:
        ind, dist = arv.query_radius(np.radians(latlon), r=corte / RAIO_TERRA_KM, return_distance=True)
        meat = np.zeros((X.shape[1], X.shape[1]))
        for i in range(len(ind)):
            k = 1 - dist[i] * RAIO_TERRA_KM / corte
            meat += np.outer(s[i], (s[ind[i]] * k[:, None]).sum(axis=0))
        v = bread @ meat @ bread
        saida[f"conley_{corte}km"] = pd.Series(np.sqrt(np.diag(v)), index=m.params.index)
    out = pd.DataFrame(saida)
    out.insert(0, "coef", m.params)
    return out


def tabela_conley(z: pd.DataFrame, geo) -> pd.DataFrame:
    ll = geo.set_index("id_amc")[["lat", "lon"]]
    linhas = []
    for y, extra in [("s_pt", []), ("hiato_lulista", ["nep"])]:
        for t in config()["anos_eleicao"]:
            if config()["alinhamento"]["censo"][t] is None:
                continue
            cols = M.X_A + extra
            d = z[z["eleicao"] == t].dropna(subset=[y] + cols + ["aptos", "id_microrregiao"]).reset_index(drop=True)
            r = conley(d, f"{y} ~ {' + '.join(cols)} + ideb_ausente + C(sg_uf)", ll.loc[d["id_amc"]].to_numpy())
            r = r.loc[cols].reset_index(names="variavel").assign(y=y, eleicao=t)
            linhas.append(r)
        log.info("Conley: %s", y)
    out = pd.concat(linhas, ignore_index=True)
    for c in ["cluster_microrregiao", "conley_100km", "conley_250km"]:
        out[f"z_{c}"] = out["coef"] / out[c]
    return out


def main() -> None:
    e = M.carregar()
    z = M.padronizar(e, M.X_A + ["nep"])
    dl = M.base_longa(e)
    geo = geo_completa = geometria()
    fora = set(geo["id_amc"]) - set(dl["id_amc"])
    if fora:  # AMC sem alguma covariável nas diferenças longas (ex.: Nazária/PI sem Bolsa Família em 2009)
        log.info("AMCs fora da análise espacial (covariável ausente): %s", sorted(fora))
        geo = geo[~geo["id_amc"].isin(fora)].reset_index(drop=True)
    assert set(geo["id_amc"]) == set(dl["id_amc"]), "malha e painel com AMCs diferentes"
    w = pesos(geo)
    _salvar(moran_global(z, dl, geo, w), "fase7_espacial_moran")
    g = lisa_swing(dl, geo, w)
    g[["id_amc", "lisa"]].to_parquet(caminho("processed") / "lisa_swing.parquet", index=False)
    _salvar(g["lisa"].value_counts().rename_axis("lisa").reset_index(name="n_amc"), "fase7_espacial_lisa_contagem")
    fig_lisa(g)
    _salvar(modelos_spreg(z, dl, geo), "fase7_espacial_spreg")
    _salvar(tabela_conley(z, geo_completa), "fase7_espacial_conley")
    log.info("parte espacial concluída")


if __name__ == "__main__":
    main()
