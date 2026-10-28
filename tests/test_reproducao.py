"""Checks da release replicável: pipeline, documentação, metadados e decisões manuais."""

import importlib.util
import json
import re

import yaml

from src.pipeline import ETAPAS
from src.utils import RAIZ


def test_etapas_existem_e_ids_unicos():
    ids = [e.id for e in ETAPAS]
    assert len(ids) == len(set(ids))
    assert ids == sorted(ids, key=float)
    for e in ETAPAS:
        assert importlib.util.find_spec(e.modulo) is not None, e.modulo


def test_links_do_readme():
    t = (RAIZ / "README.md").read_text(encoding="utf-8")
    for alvo in re.findall(r"\]\(([^)#]+)\)", t):
        if not alvo.startswith("http"):
            assert (RAIZ / alvo).exists(), alvo
    assert f"{len(ETAPAS)} etapas" in t


def test_metadados():
    z = json.loads((RAIZ / ".zenodo.json").read_text(encoding="utf-8"))
    c = yaml.safe_load((RAIZ / "CITATION.cff").read_text(encoding="utf-8"))
    p = (RAIZ / "pyproject.toml").read_text(encoding="utf-8")
    versao = re.search(r'^version = "([^"]+)"', p, re.M).group(1)
    assert z["version"] == c["version"] == versao
    assert z["license"] == c["license"] == "MIT"


def test_decisoes_manuais_versionadas():
    for f in ["p3_revisao_usuario.csv", "p3_exclusoes.csv", "p3_subtipos_usuario.csv"]:
        assert (RAIZ / "data" / "manual" / f).exists(), f


def test_planos():
    for f in ["PLANO.md", "plano2.md", "plano3.md"]:
        assert (RAIZ / "docs" / "planos" / f).exists()
