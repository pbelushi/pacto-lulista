"""Mortalidade infantil e homicídios por município, via TabNet/DATASUS (SIM e SINASC), 2003–2025.

Consultas (src/ingest/tabnet.py), sempre por município de **residência**:
- SIM (sim/cnv/obt10br.def, 'Óbitos_p/Residênc', arquivos obtbrAA.dbf):
  - obitos_infantis: SFaixa_Etária = 'Menor 1 ano'
  - homicidios: SCausa_-_CID-BR-10 = '110 Agressões' (CID-10 X85–Y09)
  - mortes_intervencao_legal: SCausa_-_CID-BR-10 = '112 Intervenções legais e operações de guerra' (Y35–Y36),
    separada como pede o PLANO
- SINASC (sinasc/cnv/nvbr.def, 'Nascim_p/resid.mãe', arquivos nvbrAA.dbf): nascidos_vivos
Os valores das opções de filtro são lidos do próprio formulário pelo rótulo (não fixados no código).

O TabNet omite municípios com zero: preenchidos com 0 para todo município com população no ano.
Linhas "Município ignorado" são descartadas (contadas no log).
Dados de 2024–2025 são preliminares no SIM/SINASC; 2026 não é usado (ano incompleto).

Indicadores (janela trienal t−2…t, como pede o PLANO):
- tmi_trienal = Σ óbitos infantis / Σ nascidos vivos × 1000
- tx_homicidio_trienal = Σ homicídios / Σ população × 100.000 (população: src/ingest/ibge_pop.py)
- tx_intervencao_legal_trienal, idem
- versões *_eb: suavização Bayesiana empírica global (Marshall, 1991), por ano, sobre a taxa trienal

Saída: data/interim/datasus.parquet (id_municipio, ano, contagens anuais, taxas trienais)
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from src.ingest.sidra import log_cobertura
from src.ingest.tabnet import arquivos, consultar, opcoes
from src.utils import caminho

log = logging.getLogger("datasus")
ANOS = range(2003, 2026)
SIM, SINASC = "sim/cnv/obt10br.def", "sinasc/cnv/nvbr.def"


def _opcao(defn: str, campo: str, comeca: str) -> str:
    ops = opcoes(defn, campo)
    achados = [v for rot, v in ops.items() if rot.startswith(comeca)]
    assert len(achados) == 1, f"{campo}: opção '{comeca}' não única em {list(ops)[:10]}"
    return achados[0]


def contagens() -> pd.DataFrame:
    arq_sim, arq_nv = arquivos(SIM), arquivos(SINASC)
    consultas = {
        "obitos_infantis": (SIM, "Óbitos_p/Residênc", arq_sim, {"SFaixa_Etária": [_opcao(SIM, "SFaixa_Etária", "Menor 1 ano")]}),
        "homicidios": (SIM, "Óbitos_p/Residênc", arq_sim, {"SCausa_-_CID-BR-10": [_opcao(SIM, "SCausa_-_CID-BR-10", ". 110 Agress")]}),
        "mortes_intervencao_legal": (SIM, "Óbitos_p/Residênc", arq_sim,
                                     {"SCausa_-_CID-BR-10": [_opcao(SIM, "SCausa_-_CID-BR-10", ". 112 Interven")]}),
        "nascidos_vivos": (SINASC, "Nascim_p/resid.mãe", arq_nv, {}),
    }
    partes = []
    for nome, (defn, inc, arqs, filtros) in consultas.items():
        for ano in ANOS:
            d = consultar(defn, inc, arqs[ano], filtros, nome).assign(ano=ano, var=nome)
            partes.append(d)
        log.info("%s: %d anos consultados", nome, len(ANOS))
    return pd.concat(partes, ignore_index=True)


def bayes_empirico(y: pd.Series, n: pd.Series) -> pd.Series:
    """EB global de Marshall (1991): encolhe r_i = y_i/n_i para a média m conforme o tamanho n_i."""
    ok = n > 0
    m = y[ok].sum() / n[ok].sum()
    r = y / n
    s2 = (n[ok] * (r[ok] - m) ** 2).sum() / n[ok].sum()
    a = max(s2 - m / n[ok].mean(), 0.0)
    c = a / (a + m / n)
    return (m + c * (r - m)).where(ok)


def main() -> None:
    bruto = contagens()
    pop = pd.read_parquet(caminho("interim") / "ibge_pop.parquet")[["id_municipio", "ano", "pop"]]
    cod6 = {str(i)[:6]: i for i in pop["id_municipio"].unique()}
    bruto["id_municipio"] = bruto["cod6"].map(cod6)
    ign = bruto["id_municipio"].isna()
    log.info("linhas sem município IBGE (ignorado/exterior) descartadas: %d (%.0f eventos)",
             ign.sum(), bruto.loc[ign, "valor"].sum())
    cont = (bruto[~ign].pivot_table(index=["id_municipio", "ano"], columns="var", values="valor", aggfunc="sum")
            .reset_index())
    base = pop[pop["ano"].isin(ANOS) & pop["pop"].notna()]
    df = base.merge(cont, on=["id_municipio", "ano"], how="left")
    vars_ = ["obitos_infantis", "homicidios", "mortes_intervencao_legal", "nascidos_vivos"]
    df[vars_] = df[vars_].fillna(0)
    df = df.sort_values(["id_municipio", "ano"])

    tri = df.groupby("id_municipio")[vars_ + ["pop"]].transform(lambda s: s.rolling(3, min_periods=3).sum())
    df["tmi_trienal"] = 1000 * tri["obitos_infantis"] / tri["nascidos_vivos"]
    df["tx_homicidio_trienal"] = 1e5 * tri["homicidios"] / tri["pop"]
    df["tx_intervencao_legal_trienal"] = 1e5 * tri["mortes_intervencao_legal"] / tri["pop"]
    df["tmi_trienal_eb"], df["tx_homicidio_trienal_eb"] = np.nan, np.nan
    for ano, idx in df.groupby("ano").groups.items():
        t = tri.loc[idx]
        if t["nascidos_vivos"].notna().any():
            df.loc[idx, "tmi_trienal_eb"] = 1000 * bayes_empirico(t["obitos_infantis"], t["nascidos_vivos"])
            df.loc[idx, "tx_homicidio_trienal_eb"] = 1e5 * bayes_empirico(t["homicidios"], t["pop"])
    df = df.drop(columns="pop")
    log_cobertura(df, "datasus", ["tmi_trienal", "tmi_trienal_eb", "tx_homicidio_trienal_eb"])
    df.to_parquet(caminho("interim") / "datasus.parquet", index=False)


if __name__ == "__main__":
    main()
