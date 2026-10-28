"""Cliente da API SIDRA (https://apisidra.ibge.gov.br) com consultas municipais divididas por UF.

A API limita cada consulta a 50.000 valores; consultar município por município de uma UF de cada vez
(`/n6/in n3 {uf}`) cabe no limite para as tabelas usadas aqui. As respostas brutas ficam em
data/raw/sidra/<tabela>/<rotulo>_<uf>.json e são reaproveitadas se já existirem.
"""

from __future__ import annotations

import json
import logging
import time

import pandas as pd
import requests

from src.utils import caminho

log = logging.getLogger("sidra")
API = "https://apisidra.ibge.gov.br/values"
UFS = [11, 12, 13, 14, 15, 16, 17, 21, 22, 23, 24, 25, 26, 27, 28, 29, 31, 32, 33, 35, 41, 42, 43, 50, 51, 52, 53]


def _get(url: str) -> list[dict]:
    for tentativa in range(5):
        r = requests.get(url, timeout=300)
        if r.status_code == 200:
            return r.json()
        if r.status_code == 400:
            raise RuntimeError(f"SIDRA 400: {r.text[:200]} — {url}")
        time.sleep(5 * (tentativa + 1))
    r.raise_for_status()
    return []


def consultar(tabela: int, resto: str, rotulo: str, nivel: str = "municipio") -> pd.DataFrame:
    """Consulta a tabela SIDRA. `resto` = parte da URL após o nível territorial (ex.: 'v/93/p/2010/c86/all').

    nivel='municipio' divide por UF; nivel='brasil' faz uma só consulta em /n1/all.
    Retorna DataFrame com colunas nomeadas pelo cabeçalho (ex.: 'Município (Código)', 'Valor').
    """
    pasta = caminho("raw") / "sidra" / str(tabela)
    pasta.mkdir(parents=True, exist_ok=True)
    alvos = [(f"n6/in%20n3%20{uf}", f"{rotulo}_{uf}") for uf in UFS] if nivel == "municipio" else [("n1/all", f"{rotulo}_br")]
    partes = []
    for terr, nome in alvos:
        arq = pasta / f"{nome}.json"
        if not arq.exists():
            dados = _get(f"{API}/t/{tabela}/{terr}/{resto}")
            arq.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
        dados = json.loads(arq.read_text(encoding="utf-8"))
        cab = dados[0]
        partes.append(pd.DataFrame(dados[1:]).rename(columns=cab))
    df = pd.concat(partes, ignore_index=True)
    # Valores especiais do SIDRA ('-' = zero absoluto, '...' / 'X' / '..' = indisponível ou sigilo)
    df["Valor"] = pd.to_numeric(df["Valor"].replace({"-": "0"}), errors="coerce")
    log.info("SIDRA %d (%s): %d linhas", tabela, rotulo, len(df))
    return df


def log_cobertura(df: pd.DataFrame, nome: str, cols: list[str]) -> None:
    """Loga N de municípios e % de missing por ano (exigência da Fase 3)."""
    for ano, g in df.groupby("ano"):
        miss = {c: round(100 * g[c].isna().mean(), 1) for c in cols}
        logging.getLogger(nome).info("%s: %d municípios; %% missing %s", ano, g["id_municipio"].nunique(), miss)
