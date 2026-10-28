"""Download dos arquivos de resultados do TSE (Dados Abertos, CDN).

Fonte: https://cdn.tse.jus.br/estatistica/sead/odsele/<conjunto>/<conjunto>_<ano>.zip
Conjuntos:
- votacao_candidato_munzona: votos por candidato × município × zona (todos os cargos e turnos)
- detalhe_votacao_munzona: aptos, comparecimento, abstenção, brancos e nulos por município × zona
- votacao_partido_munzona: votos nominais e de legenda por partido × município × zona

Uso: python -m src.ingest.tse_download [conjunto ...] [ano ...]
     (sem conjuntos: os três; sem anos: anos_eleicao do config.yaml. A Fase E do plano3 usa
     detalhe_votacao_munzona votacao_candidato_munzona 1994 1998 2002.)
"""

from __future__ import annotations

import sys

from src.utils import baixar, caminho, config

CONJUNTOS = ["detalhe_votacao_munzona", "votacao_partido_munzona", "votacao_candidato_munzona"]


def baixar_tse(conjuntos: list[str] | None = None, anos: list[int] | None = None) -> None:
    cfg = config()
    for conjunto in conjuntos or CONJUNTOS:
        for ano in anos or cfg["anos_eleicao"]:
            url = f"{cfg['tse']['cdn']}/{conjunto}/{conjunto}_{ano}.zip"
            baixar(url, caminho("raw") / "tse" / f"{conjunto}_{ano}.zip")


if __name__ == "__main__":
    args = sys.argv[1:]
    baixar_tse([a for a in args if not a.isdigit()] or None, [int(a) for a in args if a.isdigit()] or None)
