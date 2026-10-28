"""Checks da Fase 8 — relatório (docs/planos/PLANO.md, Fase 8)."""

import re

from src.utils import caminho

SECOES = ["Resumo executivo", "Onde o PT ganhou", "Quem se moveu", "β_t", "decomposição", "Robustez", "Limitações"]


def _texto():
    return (caminho("report") / "relatorio.md").read_text(encoding="utf-8")


def test_relatorio_secoes():
    t = _texto()
    for s in SECOES:
        assert s in t, s


def test_figuras_existem_e_tem_fonte():
    t = _texto()
    figs = re.findall(r"!\[[^\]]*\]\(\.\./figures/([^)]+)\.png\)", t)
    # mapas dos grupos, trajetórias, β_t e decomposição (exigidos pelo PLANO)
    for f in ["fase2_mapa_swing", "fase5_trajetorias_g_swing", "fase6_betas_s_pt", "fase6_oaxaca"]:
        assert f in figs, f
    for f in figs:
        assert (caminho("figures") / f"{f}.png").exists() and (caminho("figures") / f"{f}.svg").exists(), f
    # cada figura seguida de legenda com fonte e ano
    for bloco in re.split(r"!\[", t)[1:]:
        legenda = bloco.split("\n\n")[1]
        assert "Fonte:" in legenda and re.search(r"20\d\d", legenda), legenda[:80]
