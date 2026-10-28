"""Download do 2º turno presidencial de 2026 via Portal Resultados do TSE (fallback).

Os arquivos consolidados de Dados Abertos (votacao_candidato_munzona_2026.zip) foram
publicados antes do 2º turno (25/10/2026) e não o contêm. Fallback previsto no PLANO.md,
seção 3: JSON do Portal Resultados, um arquivo por município.

Endpoints (eleição federal 2º turno 2026 = código 6258, cargo Presidente = c0001):
- config de municípios: {base}/ele2026/6258/config/mun-e006258-cm.json
  (traz código TSE `cd` e código IBGE `cdi` de cada município — usado como crosswalk)
- resultado por município: {base}/ele2026/6258/dados/{uf}/{uf}{cd_tse}-c0001-e006258-u.json
- total Brasil (para check): {base}/ele2026/6258/dados/br/br-c0001-e006258-u.json

Os JSON são salvos intocados em data/raw/tse/portal_2026/.

Também baixa, como referência independente para os checks da Fase 1B, o total por UF de
deputado federal de 2026 (eleição estadual 1º turno = 6259, cargo c0006):
- {base}/ele2026/6259/dados/{uf}/{uf}-c0006-e006259-u.json → data/raw/tse/portal_2026/dep_federal/

Uso: python -m src.ingest.tse_portal
"""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor

from src.utils import baixar, caminho, config

ELEICAO = "6258"
CICLO = "ele2026"
log = logging.getLogger("tse_portal")


def _base() -> str:
    return f"{config()['tse']['portal_resultados']}/{CICLO}/{ELEICAO}"


def pasta():
    p = caminho("raw") / "tse" / "portal_2026"
    p.mkdir(parents=True, exist_ok=True)
    return p


def baixar_portal() -> None:
    cm = baixar(f"{_base()}/config/mun-e{ELEICAO.zfill(6)}-cm.json", pasta() / "mun-cm.json")
    baixar(f"{_base()}/dados/br/br-c0001-e{ELEICAO.zfill(6)}-u.json", pasta() / "br.json")
    muns = json.loads(cm.read_text(encoding="utf-8"))
    alvos = [(uf["cd"], m["cd"]) for uf in muns["abr"] for m in uf["mu"]]
    log.info("%d municípios (inclui exterior) no config", len(alvos))

    def um(alvo):
        uf, cd = alvo
        nome = f"{uf}{cd}-c0001-e{ELEICAO.zfill(6)}-u.json"
        destino = pasta() / uf / nome
        if destino.exists():
            return
        baixar(f"{_base()}/dados/{uf}/{nome}", destino)

    logging.getLogger("download").setLevel(logging.WARNING)
    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(um, alvos))
    n = sum(1 for _ in pasta().rglob("*-u.json"))
    log.info("%d arquivos municipais em %s", n, pasta())


def baixar_dep_federal_uf() -> None:
    base = f"{config()['tse']['portal_resultados']}/{CICLO}/6259/dados"
    cm = json.loads((pasta() / "mun-cm.json").read_text(encoding="utf-8"))
    for uf in (u["cd"] for u in cm["abr"] if u["cd"] != "zz"):
        baixar(f"{base}/{uf}/{uf}-c0006-e006259-u.json", pasta() / "dep_federal" / f"{uf}.json")


if __name__ == "__main__":
    baixar_portal()
    baixar_dep_federal_uf()
