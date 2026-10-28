"""Pacto 2.0 — Fase B: entorno censitário de cada local de votação (plano2.md).

Setores censitários do Censo 2022 (src/ingest/ibge_setores.py):
- malha BR_setores_CD2022.gpkg (CD_SETOR, CD_MUN, SITUACAO, AREA_KM2, v0001 = pessoas);
- cor ou raça (V01317 branca … V01321 indígena; "X" = sigilo → ausente);
- demografia (V01031 0–4 … V01041 70+; usa-se 15–29 = V01034 + V01035 + V01036);
- renda do responsável (V06001 responsáveis em DPPO; V06004 rendimento nominal médio dos responsáveis
  com rendimento; V06006 mediano), em R$ de jul/2022, convertido a R$ de dez/2025 pelo IPCA (fator do
  ano de 2022 em data/interim/ipca.parquet).
Escopo: municípios com ≥ 10 locais de votação no ano (plano2.md, Fase B, item 4) e locais com coordenada.

Entorno de cada local, em EPSG:5880 (metros):
  (a) Voronoi dos locais do município, recortado pelo limite municipal (união dos setores do município).
      Locais com a mesma coordenada compartilham a célula.
  (b) buffer de 800 m em volta do local (pode cruzar o limite municipal).
Agregação: cada setor entra com peso = população × (área do setor dentro do entorno / área do setor).
  pct_negra   = Σ peso·(preta+parda)/Σ peso·(total de cor ou raça), só setores sem sigilo;
  pct_15_29   = idem com a demografia;
  renda_media = Σ (responsáveis × fração)·renda / Σ (responsáveis × fração);
  densidade   = Σ população × fração / Σ área da interseção (hab./km²);
  pct_urbana  = parcela da população (ponderada) em setores urbanos.
Variáveis do local (não dependem do entorno): distância à sede do município (geobr, sedes municipais),
capital (painel) e região metropolitana (geobr, composição das RMs).

Saídas: data/interim/pacto20_entorno_<ano>.parquet; outputs/tables/pacto20_faseB_*.csv/.md
"""

from __future__ import annotations

import logging
import zipfile

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from src.utils import caminho

log = logging.getLogger("pacto20_entorno")
ANOS = [2018, 2022, 2026]
CHAVE = ["cd_mun_tse", "nr_zona", "nr_local"]
CRS_M = 5880
RAIO = 800.0
MIN_LOCAIS = 10


# ---------------------------------------------------------------- setores
def _csv(nome: str, cols: list[str] | None = None) -> pd.DataFrame:
    z = zipfile.ZipFile(caminho("raw") / "ibge_setores" / nome)
    arq = [x for x in z.namelist() if x.lower().endswith(".csv")][0]
    d = pd.read_csv(z.open(arq), sep=";", encoding="latin-1", dtype=str, usecols=cols)
    d.columns = [c.upper() for c in d.columns]
    return d


def _num(s: pd.Series) -> pd.Series:
    """'X' (sigilo) e '.' → NaN; vírgula decimal → ponto."""
    return pd.to_numeric(s.str.replace(",", ".", regex=False), errors="coerce")


def setores() -> gpd.GeoDataFrame:
    destino = caminho("interim") / "pacto20_setores.parquet"
    if destino.exists():
        return gpd.read_parquet(destino)
    g = gpd.read_file(caminho("raw") / "ibge_setores" / "BR_setores_CD2022.gpkg",
                      columns=["CD_SETOR", "CD_MUN", "SITUACAO", "AREA_KM2", "v0001"])
    g = g.to_crs(CRS_M)
    # a malha tem polígonos inválidos (auto-interseções) que quebram a união e o overlay
    inval = ~g.geometry.is_valid
    g.loc[inval, "geometry"] = g.loc[inval, "geometry"].buffer(0)
    log.info("setores com geometria inválida corrigida (buffer 0): %d", int(inval.sum()))
    g["pop"] = pd.to_numeric(g["v0001"], errors="coerce").fillna(0)
    cor = _csv("Agregados_por_setores_cor_ou_raca_BR.zip", ["CD_SETOR"] + [f"V0{i}" for i in range(1317, 1322)])
    # sigilo ("X") em alguma categoria (em geral amarela ou indígena, contagens pequenas) anularia o
    # setor inteiro: conta-se X como 0 e marca-se o setor (cor_sigilo)
    v = {c: _num(cor[c]) for c in cor.columns if c != "CD_SETOR"}
    sig = pd.concat(v, axis=1).isna().any(axis=1)
    v = {k: x.fillna(0) for k, x in v.items()}
    cor = pd.DataFrame({"CD_SETOR": cor["CD_SETOR"], "cor_total": sum(v.values()),
                        "cor_negra": v["V01318"] + v["V01320"], "cor_sigilo": sig})
    dem = _csv("Agregados_por_setores_demografia_BR.zip")
    dem = pd.DataFrame({"CD_SETOR": dem["CD_SETOR"], "dem_total": _num(dem["V01006"]),
                        "dem_15_29": _num(dem["V01034"]).fillna(0) + _num(dem["V01035"]).fillna(0)
                        + _num(dem["V01036"]).fillna(0)})
    ren = _csv("Agregados_por_setores_renda_responsavel_BR_20260508_csv.zip")
    ren = pd.DataFrame({"CD_SETOR": ren["CD_SETOR"], "responsaveis": _num(ren["V06001"]),
                        "renda_media": _num(ren["V06004"]), "renda_mediana": _num(ren["V06006"])})
    for d in (cor, dem, ren):
        g = g.merge(d, on="CD_SETOR", how="left")
    g["urbana"] = g["SITUACAO"].str.startswith("Urbana").astype(float)
    g["area_m2"] = g.geometry.area
    g["id_municipio"] = g["CD_MUN"].astype(int)
    g = g.drop(columns=["v0001"])
    g.to_parquet(destino)
    log.info("setores: %d; pop %s; cor com sigilo em alguma categoria %.1f%%; sem cor %.1f%%; sem renda %.1f%%",
             len(g), f"{g['pop'].sum():,.0f}", 100 * g["cor_sigilo"].mean(), 100 * (g["cor_total"].fillna(0) == 0).mean(),
             100 * g["renda_media"].isna().mean())
    return g


# ---------------------------------------------------------------- entornos
def _voronoi(pts: gpd.GeoDataFrame, limite) -> gpd.GeoSeries:
    """Uma célula por coordenada distinta, recortada pelo limite do município.

    `ordered=True` devolve as células na ordem dos pontos geradores, de modo que um local com
    coordenada ligeiramente fora do limite fica com a parte da sua célula que cai dentro do
    município (antes, o ponto não era achado em nenhuma célula recortada e herdava a célula de outro).
    """
    u = pts.geometry.drop_duplicates()
    if len(u) == 1:
        cel = [limite]
    else:
        vor = shapely.voronoi_polygons(shapely.MultiPoint(list(u.values)), extend_to=limite.buffer(5000),
                                       ordered=True)
        cel = shapely.intersection(np.asarray(vor.geoms), limite)
    mapa = dict(zip(u.apply(lambda p: (round(p.x, 3), round(p.y, 3))).values, cel))
    return pts.geometry.apply(lambda p: mapa.get((round(p.x, 3), round(p.y, 3))))


def _agregar(ent: gpd.GeoDataFrame, st: gpd.GeoDataFrame) -> pd.DataFrame:
    """ent: GeoDataFrame com coluna 'k' (chave do local) e geometria do entorno."""
    ov = gpd.overlay(ent[["k", "geometry"]], st, how="intersection", keep_geom_type=True)
    if ov.empty:
        return pd.DataFrame(columns=["k"])
    ov["frac"] = (ov.geometry.area / ov["area_m2"]).clip(0, 1)
    ov["w"] = ov["pop"] * ov["frac"]
    ov["area_km2"] = ov.geometry.area / 1e6
    ov["w_cor"] = ov["w"].where(ov["cor_total"] > 0)
    ov["w_dem"] = ov["w"].where(ov["dem_total"] > 0)
    ov["w_ren"] = (ov["responsaveis"] * ov["frac"]).where(ov["renda_media"].notna())
    ov["negra"] = ov["cor_negra"] / ov["cor_total"]
    ov["j1529"] = ov["dem_15_29"] / ov["dem_total"]
    g = ov.groupby("k")
    soma = lambda a, b: (ov[a] * ov[b]).groupby(ov["k"]).sum()  # noqa: E731
    out = pd.DataFrame({
        "pop_entorno": g["w"].sum(),
        "area_entorno_km2": g["area_km2"].sum(),
        "pct_negra": 100 * soma("w_cor", "negra") / g["w_cor"].sum(),
        "pct_15_29": 100 * soma("w_dem", "j1529") / g["w_dem"].sum(),
        "renda_media": soma("w_ren", "renda_media") / g["w_ren"].sum(),
        "renda_mediana": soma("w_ren", "renda_mediana") / g["w_ren"].sum(),
        "pct_urbana": 100 * soma("w", "urbana") / g["w"].sum(),
    })
    out["densidade"] = out["pop_entorno"] / out["area_entorno_km2"]
    return out.reset_index()


def entorno_ano(ano: int, st: gpd.GeoDataFrame) -> pd.DataFrame:
    b = pd.read_parquet(caminho("interim") / f"pacto20_locais_{ano}.parquet")
    n = b.groupby("id_municipio").size()
    escopo = set(n[n >= MIN_LOCAIS].index)
    b = b[b["id_municipio"].isin(escopo) & b["lat"].notna()].copy()
    b["k"] = b[CHAVE].astype(int).astype(str).agg("-".join, axis=1)
    pts = gpd.GeoDataFrame(b[["k", "id_municipio"]], geometry=gpd.points_from_xy(b["lon"], b["lat"]),
                           crs=4326).to_crs(CRS_M)
    sidx = st.sindex
    partes = []
    for i, (mun, p) in enumerate(pts.groupby("id_municipio")):
        sm = st[st["id_municipio"] == mun]
        if sm.empty:
            continue
        limite = shapely.make_valid(shapely.union_all(shapely.make_valid(sm.geometry.values)))
        vor = gpd.GeoDataFrame({"k": p["k"].values}, geometry=_voronoi(p, limite).values, crs=CRS_M)
        vor = vor[vor.geometry.notna() & ~vor.geometry.is_empty]
        a = _agregar(vor, sm).add_suffix("_vor").rename(columns={"k_vor": "k"})
        buf = gpd.GeoDataFrame({"k": p["k"].values}, geometry=p.geometry.buffer(RAIO).values, crs=CRS_M)
        cand = st.iloc[sorted(set(sidx.query(shapely.union_all(buf.geometry.values), predicate="intersects")))]
        bb = _agregar(buf, cand).add_suffix("_buf").rename(columns={"k_buf": "k"})
        partes.append(a.merge(bb, on="k", how="outer"))
        if i % 250 == 0:
            log.info("%d: %d/%d municípios", ano, i, len(escopo))
    e = pd.concat(partes, ignore_index=True)
    e = b[["k"] + CHAVE + ["id_municipio"]].merge(e, on="k", how="left").drop(columns="k")
    e["ano"] = ano
    return e


# ---------------------------------------------------------------- variáveis do local
def variaveis_local(ano: int) -> pd.DataFrame:
    import geobr

    raw = caminho("raw")
    f_sede, f_rm = raw / "geobr_sedes_municipais_2010.parquet", raw / "geobr_regioes_metropolitanas_2018.parquet"
    if not f_sede.exists():
        geobr.read_municipal_seat(year=2010).to_parquet(f_sede)
    if not f_rm.exists():
        geobr.read_metro_area(year=2018).to_parquet(f_rm)
    sede = gpd.read_parquet(f_sede).to_crs(CRS_M)
    sede["id_municipio"] = sede["code_muni"].astype(int)
    rm = set(gpd.read_parquet(f_rm)["code_muni"].astype(int))
    b = pd.read_parquet(caminho("interim") / f"pacto20_locais_{ano}.parquet")
    b = b[b["lat"].notna()].copy()
    pts = gpd.GeoSeries(gpd.points_from_xy(b["lon"], b["lat"]), crs=4326).to_crs(CRS_M)
    s = sede.set_index("id_municipio").geometry.reindex(b["id_municipio"].values)
    b["dist_sede_km"] = [p.distance(q) / 1000 if q is not None else np.nan for p, q in zip(pts.values, s.values)]
    cap = pd.read_parquet(caminho("processed") / "painel_eleicoes.parquet")
    cap = set(cap.loc[cap["capital"], "id_amc"])
    b["capital"] = b["id_municipio"].isin(cap)
    b["rm"] = b["id_municipio"].isin(rm)
    return b[CHAVE + ["id_municipio", "dist_sede_km", "capital", "rm"]]


def main(anos: list[int] | None = None) -> None:
    st = setores()
    ipca = pd.read_parquet(caminho("interim") / "ipca.parquet").set_index("ano")["fator_anual"][2022]
    for ano in anos or ANOS:
        e = entorno_ano(ano, st)
        for suf in ["_vor", "_buf"]:
            for c in ["renda_media", "renda_mediana"]:
                e[f"{c}{suf}"] = e[f"{c}{suf}"] * ipca  # R$ de dez/2025
        e = e.merge(variaveis_local(ano), on=CHAVE + ["id_municipio"], how="left")
        e.to_parquet(caminho("interim") / f"pacto20_entorno_{ano}.parquet", index=False)
        log.info("%d: entorno de %d locais", ano, len(e))
    resumo()


# ---------------------------------------------------------------- resumo e checks (Fase B)
VARS = ["pct_negra", "pct_15_29", "renda_media", "densidade", "pct_urbana"]


def resumo() -> None:
    st = setores()
    pop_mun = st.groupby("id_municipio")["pop"].sum()
    escopo, cobertura, popchk, corr = [], [], [], []
    for ano in ANOS:
        b = pd.read_parquet(caminho("interim") / f"pacto20_locais_{ano}.parquet")
        e = pd.read_parquet(caminho("interim") / f"pacto20_entorno_{ano}.parquet")
        n = b.groupby("id_municipio").size()
        mun = n[n >= MIN_LOCAIS].index
        el = b.groupby("id_municipio")["aptos_t2"].sum()
        escopo.append({"ano": ano, "municipios_total": len(n), "municipios_escopo": len(mun),
                       "locais_escopo": int(n[mun].sum()), "pct_eleitorado_escopo": 100 * el[mun].sum() / el.sum()})
        bb = b[b["id_municipio"].isin(mun)].merge(e[CHAVE + ["pop_entorno_vor", "pop_entorno_buf"]], on=CHAVE, how="left")
        com = bb["pop_entorno_vor"].notna()
        cobertura.append({"ano": ano, "pct_locais_com_entorno": 100 * com.mean(),
                          "pct_eleitorado_com_entorno": 100 * bb.loc[com, "aptos_t2"].sum() / bb["aptos_t2"].sum()})
        # Voronoi particiona o município: soma por coordenada distinta (locais na mesma coordenada dividem a célula)
        u = bb[com].drop_duplicates(["id_municipio", "lat", "lon"]).groupby("id_municipio")["pop_entorno_vor"].sum()
        r = (u / pop_mun.reindex(u.index) - 1).dropna()
        popchk.append({"ano": ano, "municipios": len(r), "pct_dentro_1pct": 100 * (r.abs() <= 0.01).mean(),
                       "pct_dentro_5pct": 100 * (r.abs() <= 0.05).mean(), "dif_mediana": r.median()})
        for v in VARS:
            corr.append({"ano": ano, "variavel": v, "corr_vor_buf": e[f"{v}_vor"].corr(e[f"{v}_buf"]),
                         "mediana_vor": e[f"{v}_vor"].median(), "mediana_buf": e[f"{v}_buf"].median(),
                         "pct_ausente_vor": 100 * e[f"{v}_vor"].isna().mean()})
    for nome, df in [("escopo", escopo), ("cobertura", cobertura), ("check_pop_voronoi", popchk), ("vor_x_buf", corr)]:
        df = pd.DataFrame(df)
        df.to_csv(caminho("tables") / f"pacto20_faseB_{nome}.csv", index=False, encoding="utf-8")
        (caminho("tables") / f"pacto20_faseB_{nome}.md").write_text(df.to_markdown(index=False, floatfmt=".4g"),
                                                                     encoding="utf-8")

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    main([int(x) for x in sys.argv[1:]] or None)
