"""Comércio exterior por município, 2003–2025 (Comex Stat, MDIC/SECEX).

Arquivos (src/ingest/comex_download.py): EXP/IMP_COMPLETA_MUN.zip (1997–abr/2025) e EXP/IMP_2025_MUN.csv
(o arquivo anual substitui o ano correspondente do completo, que estava incompleto). Colunas: CO_ANO, SH4, SG_UF_MUN, CO_MUN, VL_FOB (US$).

Cuidados (PLANO.md, seção 3):
- Município = **domicílio fiscal da empresa**, não local de produção (viés de sede).
- Códigos de município: o Comex usa o código IBGE, exceto em SP, GO, MS e DF, onde o prefixo difere.
  Deslocamentos verificados empiricamente (100% dos códigos caem em municípios IBGE): SP +100000,
  GO −100000, MS −200000, DF −100000. Linhas com UF 'EX'/'ND' (exterior/não declarada) são descartadas.
- Integridade (o download foi feito sem verificação TLS, com autorização do usuário): os totais por
  município e ano têm de bater com a série independente do Ipeadata (EXPORTACAO/IMPORTACAO);
  o resultado fica em outputs/tables/comex_integridade.csv e é testado.

Indicadores:
- exportacao_usd, importacao_usd, saldo_usd; exp_commod_usd = SH2 01–27 (agro, alimentos, minerais,
  minérios e combustíveis — "SH 01–27 + minérios" do PLANO; o capítulo 26, minérios, já está no intervalo);
- pct_commodities = exp_commod / exportação (NaN se o município não exporta);
- hhi_exp = Σ (participação de cada SH4 na exportação)², 0–1 (NaN se não exporta);
- versões em R$ de dez/2025: câmbio médio anual (BCB SGS 3698, dólar venda, média mensal) × IPCA.

Saídas: data/interim/comex.parquet (município × ano) e data/interim/comex_amc.parquet (AMC × ano,
com HHI recalculado sobre os produtos somados da AMC).
"""

from __future__ import annotations

import io
import json
import logging
import zipfile

import numpy as np
import pandas as pd

from src.ingest.sidra import log_cobertura
from src.utils import baixar, caminho, config

log = logging.getLogger("comex")
DESLOCAMENTO = {"SP": 100000, "GO": -100000, "MS": -200000, "DF": -100000}
ANO_INI = 2003
BCB = ("https://api.bcb.gov.br/dados/serie/bcdata.sgs.3698/dados?formato=json"
       "&dataInicial=01/01/2000&dataFinal=31/12/2026")


def _ler(tipo: str) -> pd.DataFrame:
    pasta = caminho("raw") / "comex"
    z = zipfile.ZipFile(pasta / f"{tipo}_COMPLETA_MUN.zip")
    usar = ["CO_ANO", "SH4", "SG_UF_MUN", "CO_MUN", "VL_FOB"]
    partes = []
    with z.open(z.namelist()[0]) as fh:
        for ch in pd.read_csv(fh, sep=";", usecols=usar, chunksize=3_000_000, dtype={"SG_UF_MUN": str}):
            ch = ch[ch["CO_ANO"] >= ANO_INI]
            partes.append(ch.groupby(["CO_ANO", "SG_UF_MUN", "CO_MUN", "SH4"], as_index=False)["VL_FOB"].sum())
    df = pd.concat(partes, ignore_index=True)
    # arquivos anuais mais recentes substituem o ano no arquivo completo (o completo foi gerado em
    # maio/2025 e traz 2025 só até abril)
    for anual in sorted(pasta.glob(f"{tipo}_20??_MUN.csv")):
        ano = int(anual.name[4:8])
        extra = pd.read_csv(anual, sep=";", usecols=usar, dtype={"SG_UF_MUN": str})
        df = pd.concat([df[df["CO_ANO"] != ano], extra], ignore_index=True)
        log.info("%s: ano %d substituído pelo arquivo anual %s", tipo, ano, anual.name)
    df = df.groupby(["CO_ANO", "SG_UF_MUN", "CO_MUN", "SH4"], as_index=False)["VL_FOB"].sum()
    fora = df["SG_UF_MUN"].isin(["EX", "ND"])
    log.info("%s: descartado %.3f%% do valor (UF EX/ND)", tipo, 100 * df.loc[fora, "VL_FOB"].sum() / df["VL_FOB"].sum())
    df = df[~fora].copy()
    df["id_municipio"] = df["CO_MUN"] + df["SG_UF_MUN"].map(DESLOCAMENTO).fillna(0).astype(int)
    return df.rename(columns={"CO_ANO": "ano"})


def cambio_real() -> pd.Series:
    """R$ de dez/2025 por US$ do ano t = câmbio médio anual × fator IPCA anual."""
    arq = baixar(BCB, caminho("raw") / "bcb" / "sgs_3698.json")
    c = pd.DataFrame(json.loads(arq.read_text(encoding="utf-8")))
    c["ano"] = c["data"].str[-4:].astype(int)
    media = c.assign(valor=pd.to_numeric(c["valor"])).groupby("ano")["valor"].mean()
    ipca = pd.read_parquet(caminho("interim") / "ipca.parquet").set_index("ano")["fator_anual"]
    return (media * ipca).dropna()


def _indicadores(exp: pd.DataFrame, imp: pd.DataFrame, chave: str) -> pd.DataFrame:
    exp = exp.assign(commod=(exp["SH4"] // 100) <= 27)
    g = exp.groupby([chave, "ano"])
    out = g["VL_FOB"].sum().rename("exportacao_usd").to_frame()
    out["exp_commod_usd"] = exp[exp["commod"]].groupby([chave, "ano"])["VL_FOB"].sum()
    por_sh4 = exp.groupby([chave, "ano", "SH4"])["VL_FOB"].sum()
    part = por_sh4 / por_sh4.groupby(level=[0, 1]).transform("sum")
    out["hhi_exp"] = (part ** 2).groupby(level=[0, 1]).sum()
    out = out.join(imp.groupby([chave, "ano"])["VL_FOB"].sum().rename("importacao_usd"), how="outer")
    out[["exportacao_usd", "exp_commod_usd", "importacao_usd"]] = out[
        ["exportacao_usd", "exp_commod_usd", "importacao_usd"]].fillna(0)
    out["saldo_usd"] = out["exportacao_usd"] - out["importacao_usd"]
    out["pct_commodities"] = (100 * out["exp_commod_usd"] / out["exportacao_usd"]).where(out["exportacao_usd"] > 0)
    out.loc[out["exportacao_usd"] == 0, "hhi_exp"] = np.nan
    cr = cambio_real()
    fator = out.index.get_level_values("ano").map(cr)
    for c in ["exportacao", "exp_commod", "importacao", "saldo"]:
        out[f"{c}_real_brl"] = out[f"{c}_usd"] * fator
    return out.reset_index()


def integridade(mun: pd.DataFrame) -> pd.DataFrame:
    """Compara totais município × ano com o Ipeadata (fonte independente), por ano.

    Diferenças esperadas e não indicativas de corrupção: (i) o Ipeadata guarda uma safra antiga, anterior
    a revisões do Comex Stat (ex.: retirada de exportações fictas de plataformas de petróleo em 2013–2021,
    como Rio Grande/RS em 2013); (ii) erros de homônimo no Ipeadata (ex.: 2022, US$ 2,2 bi de São
    Sebastião/SP atribuídos a São Sebastião/AL).
    """
    ip = pd.read_parquet(caminho("interim") / "ipea_comex_total.parquet")
    m = mun.merge(ip, on=["id_municipio", "ano"], how="outer", suffixes=("", "_ipea"))
    m = m[m["ano"].between(ANO_INI, 2025)]
    linhas = []
    for c in ["exportacao_usd", "importacao_usd"]:
        a, b = m[c].fillna(0), m[f"{c}_ipea"].fillna(0)
        ativo = (a > 0) | (b > 0)
        bate = ((a - b).abs() <= 0.01 * np.maximum(a, b)) & ativo
        for ano, idx in m[ativo].groupby("ano").groups.items():
            linhas.append({"serie": c, "ano": ano, "razao_total_comex_ipea": a[idx].sum() / b[idx].sum(),
                           "pares_mun_ano": len(idx), "pct_pares_dif_ate_1pct": 100 * bate[idx].mean(),
                           "pct_valor_em_pares_dif_ate_1pct": 100 * b[idx][bate[idx]].sum() / b[idx].sum()})
    return pd.DataFrame(linhas)


def main() -> None:
    exp, imp = _ler("EXP"), _ler("IMP")
    mun = _indicadores(exp, imp, "id_municipio")
    integ = integridade(mun)
    integ.to_csv(caminho("tables") / "comex_integridade.csv", index=False, encoding="utf-8")
    log.info("integridade vs Ipeadata:\n%s", integ.to_string(index=False))
    log_cobertura(mun, "comex", ["pct_commodities", "hhi_exp"])
    mun.to_parquet(caminho("interim") / "comex.parquet", index=False)
    amc = {int(k): int(v) for k, v in config()["amc"].items()}
    for d in (exp, imp):
        d["id_amc"] = d["id_municipio"].map(lambda c: amc.get(c, c))
    _indicadores(exp, imp, "id_amc").to_parquet(caminho("interim") / "comex_amc.parquet", index=False)


if __name__ == "__main__":
    main()
