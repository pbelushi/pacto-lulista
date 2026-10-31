"""Checks da conferência do 2º turno de 2026: boletins de urna × arquivos por seção e CDN × Portal Resultados."""

import pandas as pd
import pytest

from src.utils import caminho


@pytest.fixture(scope="module")
def bu():
    f = caminho("tables") / "pacto20_bu_conferencia.csv"
    if not f.exists():
        pytest.skip("conferência dos boletins de urna não rodada")
    return pd.read_csv(f).set_index("medida")


def test_secoes_identicas(bu):
    assert (bu["secoes_diferentes"] == 0).all() and (bu["soma_abs_diferenca"] == 0).all()
    assert (bu["secoes_so_bu"] == 0).all() and (bu["secoes_comuns"] == 499_205).all()


def test_totais_oficiais(bu):
    assert bu.loc["votos_13", "total_bu"] == 64_256_232 and bu.loc["votos_22", "total_bu"] == 59_826_041
    assert bu.loc["comparecimento", "total_bu"] == bu.loc["comparecimento", "total_secao"] == 128_236_074
    # as seções sem BU têm aptos, mas nenhum comparecimento
    assert bu.loc["aptos", "total_secao"] - bu.loc["aptos", "total_bu"] == 525


def test_fase1_usa_cdn_em_2026():
    m = pd.read_parquet(caminho("interim") / "tse_presidencial_municipio.parquet")
    assert m.loc[m["ano"] == 2026, "fonte"].eq("TSE CDN").all()
