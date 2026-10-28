"""Checks da Fase 2 — grupos (docs/planos/PLANO.md, seções 1, 1A e 5)."""

import numpy as np
import pandas as pd
import pytest

from src.groups import share_nacional
from src.utils import caminho, config

N_AMC = 5571 - len(config()["amc"])


@pytest.fixture(scope="module")
def gpres():
    return pd.read_parquet(caminho("processed") / "grupos_presidenciais.parquet")


@pytest.fixture(scope="module")
def gprop():
    return pd.read_parquet(caminho("processed") / "grupos_proporcionais.parquet")


@pytest.fixture(scope="module")
def pres():
    return pd.read_parquet(caminho("interim") / "tse_presidencial.parquet")


def test_uma_linha_por_amc(gpres):
    assert len(gpres) == N_AMC and gpres["id_amc"].is_unique
    assert gpres["regiao"].notna().all()


def test_swing_recalculado(gpres, pres):
    b, f = config()["ano_base"], config()["ano_final"]
    s = pres.pivot(index="id_amc", columns="ano", values="s_pt")
    br = share_nacional(pres)
    esperado = (s[f] - s[b]) - (br[f] - br[b])
    assert np.allclose(gpres.set_index("id_amc")["swing"].loc[esperado.index], esperado)


def test_swing_media_ponderada_zero(gpres, pres):
    """Ponderado pelos válidos da base e do final, o swing relativo médio é ~0 (só não é exato
    porque os pesos mudam entre os anos)."""
    v = pres.pivot(index="id_amc", columns="ano", values="validos")[config()["ano_final"]]
    m = np.average(gpres.set_index("id_amc")["swing"].loc[v.index], weights=v)
    assert abs(m) < 1.5


def test_grupos_swing_respeitam_limiar(gpres):
    dp = gpres["swing"].std()
    k = config()["grupos"]["limiar_dp"]
    assert (gpres.loc[gpres["g_swing"] == "G_PT", "swing"] >= k * dp).all()
    assert (gpres.loc[gpres["g_swing"] == "G_OP", "swing"] <= -k * dp).all()
    assert gpres.loc[gpres["g_swing"] == "G_EST", "swing"].abs().lt(k * dp).all()


def test_quantis_balanceados(gpres):
    vc = gpres["g_swing_q5"].value_counts()
    assert abs(vc["G_PT"] - N_AMC / 5) <= 1 and abs(vc["G_OP"] - N_AMC / 5) <= 1


def test_tipologia_consistente(gpres):
    t = gpres
    assert ((t["tipo_2x2"] == "PT↑OP↓") == ((t["d_e_pt"] >= 0) & (t["d_e_op"] < 0))).all()
    assert ((t["tipo_2x2"] == "ambos↓") == ((t["d_e_pt"] < 0) & (t["d_e_op"] < 0))).all()


def test_clusters_completos(gpres):
    for modo in ["nivel", "forma"]:
        for k in config()["grupos"]["k_clusters"]:
            c = gpres[f"cluster_{modo}_k{k}"]
            assert c.notna().all() and set(c) == set(range(1, k + 1))
        assert gpres[f"cluster_{modo}"].equals(gpres[f"cluster_{modo}_k{config()['grupos']['k_escolhido'][modo]}"])


def test_clusters_coerentes_com_swing(gpres):
    """G_PT não cai no cluster de erosão contínua, e G_OP não cai no de ganho até 2018."""
    k = config()["grupos"]["k_escolhido"]["forma"]
    ct = pd.crosstab(gpres["g_swing"], gpres["cluster_forma"])
    assert ct.loc["G_PT", k] == 0 and ct.loc["G_OP", 1] == 0


def test_grupos_proporcionais(gprop):
    assert (gprop.groupby(["ano", "versao"]).size() == N_AMC).all()
    assert gprop["g_prop"].isna().sum() == gprop["empate_lider"].sum()
    pt = gprop["g_prop"] == "P_PT"
    assert (gprop.loc[pt, "margem_PT"] > 0).all()
    anti = gprop["g_prop"] == "P_ANTI"
    assert (gprop.loc[anti, "margem_ANTI"] > 0).all()
    pm = gprop["g_prop_margem"] == "P_PT"
    assert (gprop.loc[pm, "margem_PT"] >= config()["grupos"]["limiar_margem_pp"]).all()


def test_destaque_p80(gprop):
    frac = gprop.groupby(["ano", "versao"])["destaque_p80_PT"].mean()
    assert frac.between(0.19, 0.21).all()


def test_trajetoria_proporcional(gpres):
    t = gpres
    assert t["traj_prop"].notna().all()
    assert (t.loc[t["traj_prop"] == "enraizado_PT", "n_lid_PT"] >= 4).all()
    assert (t.loc[t["traj_prop"] == "nunca_polarizado", ["n_lid_PT", "n_lid_ANTI"]] == 0).all().all()
    assert (t["n_lid_PT"] + t["n_lid_ANTI"] <= 6).all()


def test_tabelas_e_figuras_existem():
    for t in ["fase2_tamanho_grupos", "fase2_silhueta", "fase2_concordancia_cramer_v",
              f"fase2_matriz_pres_x_prop_{config()['ano_base']}", f"fase2_matriz_pres_x_prop_{config()['ano_final']}"]:
        assert (caminho("tables") / f"{t}.csv").exists() and (caminho("tables") / f"{t}.md").exists()
    for fig in ["fase2_mapa_swing", "fase2_mapa_tipologia_2x2", "fase2_mapa_cluster_forma",
                "fase2_mapa_grupos_proporcionais_partido", "fase2_mapa_trajetoria_proporcional",
                "fase2_mapa_fora_diagonal", "fase2_centroides_cluster_forma"]:
        for ext in ["png", "svg"]:
            assert (caminho("figures") / f"{fig}.{ext}").exists(), f"{fig}.{ext}"
