"""Checks do relatório do plano3."""

import re

import pytest

from src.utils import caminho


def test_relatorio():
    p = caminho("report") / "p3_relatorio.md"
    if not p.exists():
        pytest.skip("relatório do plano3 não gerado")
    t = p.read_text(encoding="utf-8")
    for h in ["**H0**", "**H1**", "**H2**", "**H3**", "**H4**", "## 5. Brasil", "## 6. Limitações"]:
        assert h in t
    figs = re.findall(r"\(\.\./figures/(p3_\w+)\.png\)", t)
    assert len(figs) == 6
    for f in figs:
        assert (caminho("figures") / f"{f}.png").exists() and (caminho("figures") / f"{f}.svg").exists()
    assert len(re.findall(r"\*Figura \d\..*Fonte:", t)) == 6
    assert "não é previsão" in t
