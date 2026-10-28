"""Divisão territorial do IBGE: município → microrregião, mesorregião, região imediata, UF.

Fonte: API de localidades do IBGE, https://servicodados.ibge.gov.br/api/v1/localidades/municipios
(JSON bruto em data/raw/ibge_localidades_municipios.json). Usada para agrupar erros-padrão por
microrregião (Fase 6) e para vizinhança/efeitos regionais (Fase 7).
Municípios novos sem microrregião na API (ex.: instalados em 2025) recebem a do município-mãe via AMC.

Saída: data/interim/ibge_localidades.parquet (id_municipio, id_amc, id_microrregiao, id_mesorregiao,
id_regiao_imediata, id_uf)
"""

from __future__ import annotations

import json
import logging

import pandas as pd

from src.utils import baixar, caminho, config

log = logging.getLogger("ibge_localidades")
URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"


def main() -> None:
    arq = baixar(URL, caminho("raw") / "ibge_localidades_municipios.json")
    d = json.loads(arq.read_text(encoding="utf-8"))
    linhas = []
    for m in d:
        micro = m.get("microrregiao") or {}
        meso = micro.get("mesorregiao") or {}
        imed = m.get("regiao-imediata") or {}
        uf = (imed.get("regiao-intermediaria") or {}).get("UF") or meso.get("UF") or {}
        linhas.append({"id_municipio": int(m["id"]), "id_microrregiao": micro.get("id"),
                       "id_mesorregiao": meso.get("id"), "id_regiao_imediata": imed.get("id"), "id_uf": uf.get("id")})
    df = pd.DataFrame(linhas)
    amc = {int(k): int(v) for k, v in config()["amc"].items()}
    df["id_amc"] = df["id_municipio"].map(lambda c: amc.get(c, c))
    # município sem microrregião (instalado depois da extinção da divisão micro/meso): herda a da mãe
    mae = df.set_index("id_municipio")
    for col in ["id_microrregiao", "id_mesorregiao"]:
        falta = df[col].isna()
        df.loc[falta, col] = df.loc[falta, "id_amc"].map(mae[col])
    log.info("%d municípios; sem microrregião: %d", len(df), df["id_microrregiao"].isna().sum())
    df.to_parquet(caminho("interim") / "ibge_localidades.parquet", index=False)


if __name__ == "__main__":
    main()
