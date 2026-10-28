"""Estrutura etária da população adulta por município e coorte de nascimento, Censos 2010 e 2022.

Tabelas SIDRA (IDs conferidos em 27/10/2026 via servicodados.ibge.gov.br/api/v3/agregados/<id>/metadados):
- 2010: 1378 "População residente, por situação do domicílio, sexo e idade, segundo a condição no
  domicílio e compartilhamento da responsabilidade pelo domicílio" (v93; c1=0, c2=0, c455=0; c287 = idade
  simples). Universo.
- 2022: 9514 "População residente, por sexo, idade e forma de declaração da idade" (v93; c2=6794,
  c286=113635; c287 = idade simples). Universo.
Os códigos de idade simples (c287, "18 anos" … "100 anos ou mais") são os mesmos nas duas tabelas e não
são contíguos; são lidos dos metadados, que ficam salvos em data/raw/sidra/<tabela>/metadados_c287.json.

Coortes (data de referência dos Censos: 31/07). Idade a na data de referência ⇒ nascido entre
ago/(ano − a − 1) e jul/(ano − a); a coorte fica definida com precisão de meio ano:
- "1991+"     — nascidos de ago/1990 em diante (2022: 18–31 anos; 2010: 18–19 anos)
- "1970–1990" — nascidos de ago/1970 a jul/1990 (2022: 32–51 anos; 2010: 20–39 anos)
- "até 1969"  — nascidos até jul/1970 (2022: 52+; 2010: 40+)
Base: população de 18 anos ou mais na data do Censo (proxy da população em idade de votar obrigatório).

Saída: data/interim/ibge_idade.parquet (id_municipio, ano ∈ {2010, 2022}, pop_18mais,
pct_coorte_1991, pct_coorte_1970_1990, pct_coorte_ate1969, idade_mediana_18mais)
"""

from __future__ import annotations

import json
import logging
import re

import numpy as np
import pandas as pd
import requests

from src.ingest.sidra import consultar, log_cobertura
from src.utils import caminho

log = logging.getLogger("ibge_idade")
TABELAS = {2010: (1378, "v/93/p/2010/c1/0/c2/0/c455/0/c287/"), 2022: (9514, "v/93/p/2022/c2/6794/c286/113635/c287/")}
# coorte pelo ano de AGOSTO da janela de nascimento ago/(ano − a − 1)–jul/(ano − a), isto é, ano − a − 1
COORTES = {"pct_coorte_1991": (1990, 9999), "pct_coorte_1970_1990": (1970, 1989), "pct_coorte_ate1969": (0, 1969)}


def codigos_idade(tabela: int) -> dict[int, str]:
    """{idade: código c287} para 18..100 (100 = '100 anos ou mais')."""
    arq = caminho("raw") / "sidra" / str(tabela) / "metadados_c287.json"
    if not arq.exists():
        arq.parent.mkdir(parents=True, exist_ok=True)
        m = requests.get(f"https://servicodados.ibge.gov.br/api/v3/agregados/{tabela}/metadados", timeout=120).json()
        cats = next(c for c in m["classificacoes"] if c["id"] == 287)["categorias"]
        arq.write_text(json.dumps(cats, ensure_ascii=False), encoding="utf-8")
    out = {}
    for c in json.loads(arq.read_text(encoding="utf-8")):
        mm = re.fullmatch(r"(\d+) anos?( ou mais)?", c["nome"])
        if mm and 18 <= int(mm.group(1)) <= 100:
            out[int(mm.group(1))] = str(c["id"])
    assert len(out) == 83, len(out)
    return out


def idade_simples(ano: int) -> pd.DataFrame:
    tabela, resto = TABELAS[ano]
    cod = codigos_idade(tabela)
    partes = []
    # duas consultas por UF (18–59 e 60–100) para ficar abaixo do limite de 50 mil valores
    for rot, faixa in [("18a59", range(18, 60)), ("60mais", range(60, 101))]:
        d = consultar(tabela, resto + ",".join(cod[a] for a in faixa), f"idade{ano}_{rot}")
        partes.append(d)
    d = pd.concat(partes, ignore_index=True)
    inv = {v: k for k, v in cod.items()}
    return pd.DataFrame({"id_municipio": d["Município (Código)"].astype(int),
                         "idade": d["Idade (Código)"].map(inv).astype(int), "pop": d["Valor"], "ano": ano})


def coortes(d: pd.DataFrame) -> pd.DataFrame:
    w = d.pivot_table(index=["id_municipio", "ano"], columns="idade", values="pop", aggfunc="first")
    tot = w.sum(axis=1, min_count=1)
    out = pd.DataFrame({"pop_18mais": tot})
    for nome, (ini, fim) in COORTES.items():
        partes = []
        for ano, g in w.groupby(level="ano"):
            idades = [a for a in w.columns if ini <= ano - a - 1 <= fim]
            partes.append(100 * g[idades].sum(axis=1) / tot.loc[g.index])
        out[nome] = pd.concat(partes)
    # idade mediana dos adultos (100+ tratado como 100)
    cum = w.cumsum(axis=1).div(tot, axis=0)
    out["idade_mediana_18mais"] = (cum >= 0.5).idxmax(axis=1).astype(float)
    return out.reset_index()


def main() -> None:
    d = pd.concat([idade_simples(2010), idade_simples(2022)], ignore_index=True)
    out = coortes(d)
    log_cobertura(out, "ibge_idade", [c for c in out.columns if c.startswith("pct_")])
    out.to_parquet(caminho("interim") / "ibge_idade.parquet", index=False)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    main()
