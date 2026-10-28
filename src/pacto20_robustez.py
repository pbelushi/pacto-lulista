"""Fase D do pacto 2.0 (docs/planos/plano2.md): robustez dos modelos por local de votação.

Modelo de referência: empilhado 2018/2022/2026 do Critério 2 (s_PT no 2º turno ~ X×ano, EF município×ano),
que dá β por eleição e Δβ. Variantes:
- entorno por buffer de 800 m em vez de Voronoi
- sem ponderação
- só capitais
- excluindo locais com menos de 300 aptos
Erros espaciais: Conley (2 e 5 km, núcleo de Bartlett) no modelo por eleição, contra o agrupado por município;
Moran's I dos resíduos com vizinhança restrita ao município (5 vizinhos mais próximos).
Placebo (2010 e 2014): ver placebo().

Uso: python -m src.pacto20_robustez [variantes conley moran placebo]
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from scipy import sparse, stats
from sklearn.neighbors import BallTree

from src.pacto20_modelos import ANOS, FOCO, X, _empilhado, _fit, _salvar, dados

log = logging.getLogger("pacto20_robustez")
R_TERRA_KM = 6371.0088


def _zscore(d: pd.DataFrame) -> pd.DataFrame:
    for v in X:
        d[v] = (d[f"{v}_raw"] - d[f"{v}_raw"].mean()) / d[f"{v}_raw"].std()
    return d


def com_buffer(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    d["negros_raw"] = d["pct_negra_buf"]
    d["log_renda_raw"] = np.log(d["renda_media_buf"].where(d["renda_media_buf"] > 0))
    d["log_dens_raw"] = np.log(d["densidade_buf"].where(d["densidade_buf"] > 0))
    d = d.dropna(subset=["negros_raw", "log_renda_raw", "log_dens_raw"])
    return _zscore(d)


def _sub(d: pd.DataFrame, mask) -> pd.DataFrame:
    return _zscore(d[mask].copy())


# ---------------------------------------------------------------- variantes
def variantes(bases: dict) -> None:
    casos = {
        "referência (Voronoi, ponderado)": (bases, "aptos_t2"),
        "buffer de 800 m": ({a: com_buffer(d) for a, d in bases.items()}, "aptos_t2"),
        "sem ponderação": (bases, None),
        "só capitais": ({a: _sub(d, d["capital"].fillna(False)) for a, d in bases.items()}, "aptos_t2"),
        "excluindo locais < 300 aptos": ({a: _sub(d, d["aptos_t2"] >= 300) for a, d in bases.items()}, "aptos_t2"),
    }
    betas, deltas = [], []
    for nome, (b, w) in casos.items():
        be, de = _empilhado(b, nome, w=w)
        betas.append(be)
        deltas.append(de)
    _salvar(pd.concat(betas), "faseD_variantes_betas",
            "Fase D — β de jovens, negros, renda e densidade por eleição, em cada variante",
            "Modelo empilhado com EF município×ano; p.p. de s_PT (2º turno) por 1 DP de X, padronizado na amostra da variante.")
    _salvar(pd.concat(deltas), "faseD_variantes_delta", "Fase D — Δβ de jovens e negros em cada variante",
            "EP agrupado por município.")


# ---------------------------------------------------------------- Conley
def _demean(d: pd.DataFrame, cols: list[str], w: np.ndarray) -> np.ndarray:
    """Remove a média ponderada por município (efeito fixo único, transformação exata)."""
    g = d["id_municipio"].values
    out = np.empty((len(d), len(cols)))
    for k, c in enumerate(cols):
        x = d[c].values.astype(float)
        sw = pd.Series(w).groupby(g).transform("sum").values
        swx = pd.Series(w * x).groupby(g).transform("sum").values
        out[:, k] = x - swx / sw
    return out


def _pares(lat: np.ndarray, lon: np.ndarray, corte_km: float) -> sparse.csr_matrix:
    """Matriz esparsa de pesos de Bartlett (1 − d/corte) para pares a até corte_km (inclui a diagonal)."""
    tree = BallTree(np.radians(np.c_[lat, lon]), metric="haversine")
    ind, dist = tree.query_radius(np.radians(np.c_[lat, lon]), r=corte_km / R_TERRA_KM, return_distance=True)
    lin = np.repeat(np.arange(len(lat)), [len(i) for i in ind])
    col = np.concatenate(ind)
    k = 1 - np.concatenate(dist) * R_TERRA_KM / corte_km
    return sparse.csr_matrix((k, (lin, col)), shape=(len(lat), len(lat)))


def conley(bases: dict) -> None:
    out = []
    for ano, d in bases.items():
        d = d.dropna(subset=["lat", "lon"])
        w = d["aptos_t2"].values.astype(float)
        f = _fit("s_pt ~ " + " + ".join(X), d)
        xd = _demean(d, X, w)
        yd = _demean(d, ["s_pt"], w)[:, 0]
        xtwx = xd.T @ (xd * w[:, None])
        bread = np.linalg.inv(xtwx)
        b = bread @ (xd.T @ (w * yd))
        e = yd - xd @ b
        u = xd * (w * e)[:, None]  # escores
        assert np.allclose(b, f.coef().reindex(X).values, atol=1e-6), "β difere do pyfixest"
        ep = {"agrupado por município": f.se().reindex(X).values}
        for km in [2, 5]:
            k = _pares(d["lat"].values, d["lon"].values, km)
            meat = u.T @ (k @ u)
            ep[f"Conley {km} km"] = np.sqrt(np.diag(bread @ meat @ bread))
        ep["robusto (HC0)"] = np.sqrt(np.diag(bread @ (u.T @ u) @ bread))
        for i, v in enumerate(X):
            for tipo, s in ep.items():
                out.append({"ano": ano, "variavel": v, "beta": b[i], "tipo_ep": tipo, "ep": s[i],
                            "p": 2 * stats.norm.sf(abs(b[i] / s[i]))})
        log.info("Conley %d: %d locais", ano, len(d))
    _salvar(pd.DataFrame(out), "faseD_conley",
            "Fase D — erros-padrão espaciais (Conley) contra agrupados por município, modelo por eleição",
            "s_PT (2º turno) ~ jovens + negros + log renda + log densidade, EF de município, peso = aptos. "
            "Conley com núcleo de Bartlett; p pela normal.")


# ---------------------------------------------------------------- Moran
def _knn_municipio(d: pd.DataFrame, k: int = 5) -> sparse.csr_matrix:
    lin, col = [], []
    pos = np.arange(len(d))
    for _, idx in d.groupby("id_municipio").indices.items():
        if len(idx) <= k:
            continue
        p = np.radians(d[["lat", "lon"]].values[idx])
        _, viz = BallTree(p, metric="haversine").query(p, k=k + 1)
        lin.append(np.repeat(pos[idx], k))
        col.append(pos[idx][viz[:, 1:]].ravel())
    lin, col = np.concatenate(lin), np.concatenate(col)
    return sparse.csr_matrix((np.full(len(lin), 1 / k), (lin, col)), shape=(len(d), len(d)))


def _moran(z: np.ndarray, wm: sparse.csr_matrix) -> tuple[float, float, float]:
    """I de Moran com z sob normalidade (só unidades com vizinhos)."""
    tem = np.asarray(wm.sum(axis=1)).ravel() > 0
    wm = wm[tem][:, tem]
    z = z[tem] - z[tem].mean()
    n, s0 = len(z), wm.sum()
    i = (n / s0) * (z @ (wm @ z)) / (z @ z)
    ws = wm + wm.T
    s1 = 0.5 * ws.multiply(ws).sum()
    s2 = np.sum((np.asarray(wm.sum(axis=1)).ravel() + np.asarray(wm.sum(axis=0)).ravel()) ** 2)
    ei = -1 / (n - 1)
    vi = (n * n * s1 - n * s2 + 3 * s0 * s0) / ((n * n - 1) * s0 * s0) - ei * ei
    zi = (i - ei) / np.sqrt(vi)
    return i, zi, 2 * stats.norm.sf(abs(zi))


def moran(bases: dict) -> None:
    out = []
    for ano, d in bases.items():
        d = d.dropna(subset=["lat", "lon"])
        d = d[d.groupby("id_municipio")["id_municipio"].transform("size") > 1].reset_index(drop=True)  # pyfixest descarta singletons
        w = d["aptos_t2"].values.astype(float)
        wm = _knn_municipio(d)
        y = _demean(d, ["s_pt"], w)[:, 0]
        f = _fit("s_pt ~ " + " + ".join(X), d)
        e = np.asarray(f.resid())
        for nome, z in [("s_PT (desviado da média do município)", y), ("resíduo do modelo", e)]:
            i, zi, p = _moran(z, wm)
            out.append({"ano": ano, "serie": nome, "moran_i": i, "z": zi, "p": p, "locais": int((wm.sum(axis=1) > 0).sum())})
        log.info("Moran %d", ano)
    _salvar(pd.DataFrame(out), "faseD_moran",
            "Fase D — autocorrelação espacial dentro dos municípios (I de Moran)",
            "Vizinhança: 5 locais mais próximos do mesmo município, linha padronizada; inferência sob normalidade.")


def main(partes: list[str] | None = None) -> None:
    partes = partes or ["variantes", "conley", "moran"]
    bases = {a: dados(a) for a in ANOS}
    if "variantes" in partes:
        variantes(bases)
    if "conley" in partes:
        conley(bases)
    if "moran" in partes:
        moran(bases)
    if "placebo" in partes:
        placebo(bases)


def placebo(bases: dict) -> None:
    """Mesmo modelo empilhado com 2010 e 2014 (Dilma × Serra/Aécio). Se jovens e negros já puxavam o PT
    com a mesma força antes de 2018, o padrão não é "2.0". O entorno é o do Censo 2022 em todos os anos."""
    todas = {**{a: dados(a) for a in (2010, 2014)}, **bases}
    be, de = _empilhado(todas, "2010–2026")
    _salvar(be, "faseD_placebo_betas", "Fase D — placebo: β por eleição, 2010–2026 (modelo empilhado, EF município×ano)",
            "p.p. de s_PT (2º turno) por 1 DP de X, padronizado dentro de cada eleição. Entorno censitário de 2022 em todos os anos.")
    _salvar(de, "faseD_placebo_delta", "Fase D — placebo: Δβ de jovens e negros contra 2026", "EP agrupado por município.")


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    main(sys.argv[1:] or None)
