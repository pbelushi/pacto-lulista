"""Malha municipal (IBGE 2022, simplificada) via geobr, agregada em AMC.

Fonte: geobr.read_municipality(code_muni="all", year=2022, simplified=True) — 5.570 municípios
(Boa Esperança do Norte/MT, instalado em 2025, não está na malha; é agregado a Sorriso de qualquer forma).

Limites de UF: geobr.read_state(year=2020, simplified=True). Não dá para obtê-los dissolvendo a
malha municipal simplificada: as frestas entre municípios viram ~71 mil anéis internos.

Saídas:
- data/raw/geobr_municipios_2022.parquet (download intocado)
- data/raw/geobr_estados_2020.parquet (download intocado; só para desenho dos limites de UF)
- data/interim/malha_amc.parquet (geometrias dissolvidas por id_amc, com UF e macrorregião)

Uso: python -m src.ingest.malhas
"""

from __future__ import annotations

import logging

import geopandas as gpd

from src.utils import caminho, config

log = logging.getLogger("malhas")


def baixar_malha() -> gpd.GeoDataFrame:
    destino = caminho("raw") / "geobr_municipios_2022.parquet"
    if not destino.exists():
        import geobr

        geobr.read_municipality(code_muni="all", year=2022, simplified=True).to_parquet(destino)
    return gpd.read_parquet(destino)


def malha_uf() -> gpd.GeoDataFrame:
    destino = caminho("raw") / "geobr_estados_2020.parquet"
    if not destino.exists():
        import geobr

        geobr.read_state(code_state="all", year=2020, simplified=True).to_parquet(destino)
    return gpd.read_parquet(destino)


def malha_amc() -> gpd.GeoDataFrame:
    m = baixar_malha()
    amc = {int(k): int(v) for k, v in config()["amc"].items()}
    m["id_municipio"] = m["code_muni"].astype(int)
    m["id_amc"] = m["id_municipio"].map(lambda c: amc.get(c, c))
    g = m.dissolve(by="id_amc", aggfunc={"abbrev_state": "first", "name_region": "first"}).reset_index()
    g = g.rename(columns={"abbrev_state": "sg_uf", "name_region": "regiao"})
    log.info("malha: %d municípios → %d AMCs", len(m), len(g))
    return g


def main() -> None:
    malha_amc().to_parquet(caminho("interim") / "malha_amc.parquet")
    malha_uf()


if __name__ == "__main__":
    main()
