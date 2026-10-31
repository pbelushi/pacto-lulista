"""Checks do extra raça (docs/planos/prompt_raca_margem.md)."""

import pandas as pd
import pytest

from src.pacto20_base import CHAVE
from src.utils import caminho


@pytest.fixture(scope="module", params=[2010, 2014, 2018, 2022, 2026])
def entorno(request):
    f = caminho("interim") / f"extra_raca_entorno_{request.param}.parquet"
    if not f.exists():
        pytest.skip("entorno do extra raça não rodado")
    return request.param, pd.read_parquet(f)


def test_preta_mais_parda_e_negra(entorno):
    _, e = entorno
    for s in ["vor", "buf"]:
        assert (e[f"pct_preta_{s}"] + e[f"pct_parda_{s}"] - e[f"pct_negra_{s}"]).abs().max() < 1e-6


def test_entorno_publicado_nao_mudou(entorno):
    ano, e = entorno
    o = pd.read_parquet(caminho("interim") / f"pacto20_entorno_{ano}.parquet")
    assert "pct_preta_vor" not in o and "pct_parda_vor" not in o
    m = o.merge(e, on=CHAVE, suffixes=("", "_novo"))
    assert len(m) == len(o)
    for s in ["vor", "buf"]:
        assert (m[f"pct_negra_{s}"] - m[f"pct_negra_{s}_novo"]).abs().max() < 1e-6


def test_painel_soma_negra():
    e = pd.read_parquet(caminho("processed") / "painel_eleicoes.parquet").dropna(subset=["pct_negra"])
    assert (e["pct_preta"] + e["pct_parda"] - e["pct_negra"]).abs().max() < 1e-9


def test_reproduz_modelo_entre_turnos():
    from src import models as M
    from src.extra_entre_turnos import amc, modelo

    f = caminho("tables") / "extra_turnos_amc_modelo.csv"
    if not f.exists():
        pytest.skip("extra entre turnos não rodado")
    pub = pd.read_csv(f)
    e = M.carregar()
    novo = pd.concat([modelo(amc(a, e), a) for a in [2022, 2026]], ignore_index=True)
    m = pub.merge(novo, on=["ano", "modelo", "variavel"], suffixes=("", "_novo"))
    assert len(m) == len(pub) and (m["beta"] - m["beta_novo"]).abs().max() < 1e-9


def test_tabelas():
    f = caminho("tables") / "extra_raca_r1.csv"
    if not f.exists():
        pytest.skip("extra raça não rodado")
    r = pd.read_csv(f)
    assert len(r) == 16 and set(r["ano"]) == {2022, 2026} and r[["beta_preta_dp", "beta_parda_dp"]].notna().all().all()
    # R1: em p.p., % preta supera % parda no Δ Lula de 2026, nos dois níveis
    d = r[(r["ano"] == 2026) & (r["desfecho"] == "Δ Lula")]
    assert (d["beta_preta_pp"] > d["beta_parda_pp"]).all()
    assert (pd.read_csv(caminho("tables") / "extra_raca_sigilo_quintil.csv")["vies_preta_pp"].abs() < 0.2).all()
    for g in ["coeficientes", "interacoes"]:
        assert (caminho("figures") / f"extra_raca_{g}.png").exists() and (caminho("figures") / f"extra_raca_{g}.svg").exists()
