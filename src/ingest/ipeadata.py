"""Séries municipais republicadas pelo Ipeadata (API OData v4, http://www.ipeadata.gov.br/api/odata4/).

Usado porque as fontes primárias estavam indisponíveis em 27/10/2026 (ver outputs/pendencias.md):
- Atlas do Desenvolvimento Humano (PNUD/Ipea/FJP) — sem link direto de download:
    ADH_IDHM, ADH_IDHM_E, ADH_IDHM_L, ADH_IDHM_R (1991, 2000, 2010). Por decisão do usuário,
    só 2010 entra na análise (nível inicial); não há IDHM municipal com o Censo 2022.
- MDS (Bolsa Família / Auxílio Brasil 2021–2023) — VIS Data e SAGI fora do ar:
    FAM_PBF (número de benefícios em dezembro), VAL_PBF (valor total dos benefícios em dezembro, R$ mil).
    Só beneficiários; % de cadastrados no CadÚnico fica pendente (decisão do usuário).
- MDIC/SECEX — totais municipais de comércio exterior (US$ FOB), usados como checagem independente
    dos arquivos detalhados do Comex Stat: EXPORTACAO, IMPORTACAO.
Endpoint: /ValoresSerie(SERCODIGO='<código>'); só linhas com NIVNOME = 'Municípios'; TERCODIGO = código
IBGE de 7 dígitos. JSON bruto em data/raw/ipeadata/<código>.json.

Saídas (data/interim/):
- atlas_idhm.parquet (id_municipio, ano, idhm, idhm_e, idhm_l, idhm_r)
- mds_pbf.parquet (id_municipio, ano, beneficios_pbf, valor_pbf_dez)
- ipea_comex_total.parquet (id_municipio, ano, exportacao_usd, importacao_usd)
"""

from __future__ import annotations

import json
import logging

import pandas as pd

from src.ingest.sidra import log_cobertura
from src.utils import baixar, caminho

log = logging.getLogger("ipeadata")
API = "http://www.ipeadata.gov.br/api/odata4/ValoresSerie(SERCODIGO='{cod}')"


def serie(cod: str) -> pd.DataFrame:
    arq = baixar(API.format(cod=cod), caminho("raw") / "ipeadata" / f"{cod}.json")
    d = pd.DataFrame(json.loads(arq.read_text(encoding="utf-8"))["value"])
    d = d[d["NIVNOME"].str.startswith("Munic")]
    out = pd.DataFrame({"id_municipio": d["TERCODIGO"].astype(int), "ano": d["VALDATA"].str[:4].astype(int),
                        "valor": pd.to_numeric(d["VALVALOR"], errors="coerce")})
    assert not out.duplicated(["id_municipio", "ano"]).any(), cod
    log.info("%s: %d linhas municipais, anos %d–%d", cod, len(out), out["ano"].min(), out["ano"].max())
    return out


def _juntar(mapa: dict[str, str]) -> pd.DataFrame:
    partes = [serie(c).rename(columns={"valor": nome}) for c, nome in mapa.items()]
    df = partes[0]
    for p in partes[1:]:
        df = df.merge(p, on=["id_municipio", "ano"], how="outer")
    return df


def main() -> None:
    i = caminho("interim")
    idhm = _juntar({"ADH_IDHM": "idhm", "ADH_IDHM_E": "idhm_e", "ADH_IDHM_L": "idhm_l", "ADH_IDHM_R": "idhm_r"})
    log_cobertura(idhm, "atlas_idhm", ["idhm"])
    idhm.to_parquet(i / "atlas_idhm.parquet", index=False)
    pbf = _juntar({"FAM_PBF": "beneficios_pbf", "VAL_PBF": "valor_pbf_dez"})
    pbf["valor_pbf_dez"] = pbf["valor_pbf_dez"] * 1000  # R$ mil → R$
    log_cobertura(pbf, "mds_pbf", ["beneficios_pbf"])
    pbf.to_parquet(i / "mds_pbf.parquet", index=False)
    cx = _juntar({"EXPORTACAO": "exportacao_usd", "IMPORTACAO": "importacao_usd"})
    cx.to_parquet(i / "ipea_comex_total.parquet", index=False)


if __name__ == "__main__":
    main()
