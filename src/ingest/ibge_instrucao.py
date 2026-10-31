"""Pessoas de 18 anos ou mais por nível de instrução e cor ou raça, Censo 2022 (SIDRA 10061, nível municipal).

Consulta: v/2667 (pessoas), c1568 (120704 total; 99713 superior completo), c58/95253 (todas as idades),
c2/6794 (ambos os sexos), c86 (95251 total; 2776 branca; 2777 preta; 2779 parda). Dados da amostra do Censo.

Saída: data/interim/ibge_instrucao.parquet (id_municipio, adultos_<cor>, superior_<cor>).

Uso: python -m src.ingest.ibge_instrucao
"""

from __future__ import annotations

import logging

import pandas as pd

from src.ingest.sidra import consultar
from src.utils import caminho

log = logging.getLogger("ibge_instrucao")
COR = {"95251": "total", "2776": "branca", "2777": "preta", "2779": "parda"}
NIVEL = {"120704": "adultos", "99713": "superior"}


def main() -> None:
    d = consultar(10061, "v/2667/p/2022/c1568/" + ",".join(NIVEL) + "/c58/95253/c2/6794/c86/" + ",".join(COR), "instrucao_cor")
    d["coluna"] = d["Nível de instrução (Código)"].map(NIVEL) + "_" + d["Cor ou raça (Código)"].map(COR)
    w = d.pivot_table(index="Município (Código)", columns="coluna", values="Valor", aggfunc="first")
    w = w.rename_axis("id_municipio").rename_axis(columns=None).reset_index()
    w["id_municipio"] = w["id_municipio"].astype(int)
    w.to_parquet(caminho("interim") / "ibge_instrucao.parquet", index=False)
    log.info("%d municípios; adultos %.0f; superior %.2f%%; ausentes por coluna: %s", len(w), w["adultos_total"].sum(),
             100 * w["superior_total"].sum() / w["adultos_total"].sum(), w.isna().sum().to_dict())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    main()
