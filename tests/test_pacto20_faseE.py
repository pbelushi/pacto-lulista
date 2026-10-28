"""Checks da Fase E do pacto 2.0 (plano2.md): figuras e relatório."""

import re

import pytest

from src.utils import caminho

FIGS = ["pacto20_mapas_capitais", "pacto20_betas", "pacto20_tercis", "pacto20_mobilizacao"]


@pytest.mark.parametrize("nome", FIGS)
def test_figuras_png_svg(nome):
    for ext in ["png", "svg"]:
        assert (caminho("figures") / f"{nome}.{ext}").stat().st_size > 10_000


def test_relatorio_vereditos():
    p = caminho("report") / "pacto20.md"
    if not p.exists():
        pytest.skip("relatório não gerado")
    t = p.read_text(encoding="utf-8")
    for c in ["1. Associação líquida de renda", "2. Tendência", "3. Voto proporcional", "4. Mobilização", "5. Heterogeneidade"]:
        assert c in t
    assert "Não testado" in t and "Veredito geral" in t and "## 7. Limitações" in t
    # toda figura citada existe e tem legenda com fonte
    for f in re.findall(r"\(\.\./figures/(pacto20_\w+)\.png\)", t):
        assert f in FIGS
    assert len(re.findall(r"\*Figura \d\..*Fonte:", t)) == 4
