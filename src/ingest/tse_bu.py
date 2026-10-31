"""Download dos boletins de urna (BU) do 2º turno de 2026.

Fonte: https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/buweb/bweb_2t_<UF>_<carimbo>.zip, um arquivo
por UF + ZZ (exterior), com o .sha512 publicado ao lado; dataset resultados-2026-boletim-de-urna do portal de dados
abertos (consultado em 31/10/2026; arquivos gerados em 26/10/2026, 07h42). O catálogo aponta o BU de RR para o
.sha512 por engano; o .zip existe na URL de padrão igual ao das outras UFs (HTTP 200).
Destino: data/raw/tse_secao/boletim_urna/. Cada arquivo é conferido com o SHA-512 publicado.

Uso: python -m src.ingest.tse_bu
"""

from __future__ import annotations

import hashlib
import logging

import requests

from src.ingest.tse_secao_download import UFS
from src.utils import baixar, caminho

log = logging.getLogger("tse_bu")
BASE = "https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/buweb"
CARIMBO = "261020260742"


def pasta():
    return caminho("raw") / "tse_secao" / "boletim_urna"


def baixar_bu() -> None:
    logging.getLogger("download").setLevel(logging.WARNING)
    for uf in UFS + ["ZZ"]:
        nome = f"bweb_2t_{uf}_{CARIMBO}.zip"
        f = baixar(f"{BASE}/{nome}", pasta() / nome)
        publicado = requests.get(f"{BASE}/{nome}.sha512", timeout=60).text.split()[0]
        calculado = hashlib.sha512(f.read_bytes()).hexdigest()
        assert calculado == publicado, f"{nome}: SHA-512 não confere"
    log.info("%d boletins baixados e conferidos com o SHA-512 publicado", len(UFS) + 1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    baixar_bu()
