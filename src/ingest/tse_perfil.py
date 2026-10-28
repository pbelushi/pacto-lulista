"""Eleitorado por faixa etária e município (TSE, perfil do eleitorado) e coortes de nascimento.

Fonte: cdn.tse.jus.br/estatistica/sead/odsele/perfil_eleitorado/perfil_eleitorado_<ano>.zip
(baixado por src.ingest.tse_download, conjunto "perfil_eleitorado"). Um CSV nacional (2006–2018) ou um
por UF mais um _BRASIL (2022, 2026; só o _BRASIL é lido); linhas com SG_UF = ZZ (exterior) são descartadas. Colunas usadas: CD_MUNICIPIO (código TSE),
CD_FAIXA_ETARIA, DS_FAIXA_ETARIA e QT_ELEITORES_PERFIL (até 2018) ou QT_ELEITORES (2022+).
O perfil é o do eleitorado apto da eleição (idade na data da eleição, outubro).

Faixas do TSE: idades simples de 16 a 20 e grupos de 5 anos depois (21–24, 25–29, …, 100+).
Coortes de nascimento a partir das faixas: a faixa [a, b] na eleição de outubro de T reúne nascidos
entre (T + 0,8 − b − 1) e (T + 0,8 − a) em anos decimais; cada faixa é repartida entre as coortes
proporcionalmente à sobreposição desse intervalo, supondo distribuição uniforme dentro da faixa.
Coortes (iguais às do Censo em src/ingest/ibge_idade.py, com o corte em 1º de janeiro):
  1991+ (nascidos a partir de 1991), 1970–1990, até 1969.
Base: todo o eleitorado apto (16+, inclusive facultativos). Faixa "inválida"/não informada é excluída
da base e o seu peso é registrado (pct_idade_ni).

Saída: data/interim/tse_perfil_idade.parquet (id_municipio, ano, eleitores, pct_coorte_*,
pct_idade_ni, e as faixas 16–24 / 25–34 / 35–44 / 45–59 / 60+ para descritiva).
"""

from __future__ import annotations

import logging
import re
import zipfile

import numpy as np
import pandas as pd

from src.ingest.tse import crosswalk
from src.utils import caminho, config

log = logging.getLogger("tse_perfil")
COORTES = {"pct_coorte_1991": (1991.0, 3000.0), "pct_coorte_1970_1990": (1970.0, 1991.0),
           "pct_coorte_ate1969": (1800.0, 1970.0)}
FAIXAS_DESC = {"pct_16_24": (16, 24), "pct_25_34": (25, 34), "pct_35_44": (35, 44), "pct_45_59": (45, 59),
               "pct_60mais": (60, 200)}


def _faixa(ds: str) -> tuple[float, float] | None:
    """'25 a 29 anos' → (25, 29); '16 anos' → (16, 16); '100 anos ou mais' → (100, 104)."""
    ds = str(ds).strip()
    if m := re.fullmatch(r"(\d+) a (\d+) anos", ds):
        return float(m.group(1)), float(m.group(2))
    if m := re.fullmatch(r"(\d+) anos ou mais", ds):
        return float(m.group(1)), float(m.group(1)) + 4
    if m := re.fullmatch(r"(\d+) anos", ds):
        return float(m.group(1)), float(m.group(1))
    return None


def ler_ano(ano: int) -> pd.DataFrame:
    z = zipfile.ZipFile(caminho("raw") / "tse" / f"perfil_eleitorado_{ano}.zip")
    csvs = [i.filename for i in z.infolist() if i.filename.lower().endswith(".csv")]
    # 2022+: há um _BRASIL.csv além dos arquivos por UF — usar só ele (senão o eleitorado dobra)
    arqs = [a for a in csvs if a.upper().endswith("_BRASIL.CSV")] or csvs
    partes = []
    for a in arqs:
        with z.open(a) as fh:
            cab = fh.readline().decode("latin-1")
        qt = "QT_ELEITORES" if '"QT_ELEITORES"' in cab else "QT_ELEITORES_PERFIL"
        with z.open(a) as fh:
            for ch in pd.read_csv(fh, sep=";", encoding="latin-1", usecols=["SG_UF", "CD_MUNICIPIO", "DS_FAIXA_ETARIA", qt],
                                  dtype={"SG_UF": str, "CD_MUNICIPIO": int, "DS_FAIXA_ETARIA": str},
                                  chunksize=3_000_000):
                ch = ch[ch["SG_UF"] != "ZZ"]  # exterior
                ch["DS_FAIXA_ETARIA"] = ch["DS_FAIXA_ETARIA"].str.strip()
                partes.append(ch.groupby(["CD_MUNICIPIO", "DS_FAIXA_ETARIA"])[qt].sum().rename("eleitores"))
    d = pd.concat(partes).groupby(level=[0, 1]).sum().reset_index()
    log.info("%d: %s eleitores, %d faixas distintas", ano, f"{d['eleitores'].sum():,}", d["DS_FAIXA_ETARIA"].nunique())
    return d.assign(ano=ano)


def coortes(d: pd.DataFrame) -> pd.DataFrame:
    ano = int(d["ano"].iloc[0])
    t = ano + 0.8  # eleição em outubro
    fx = d["DS_FAIXA_ETARIA"].map(_faixa)
    ok = fx.notna()
    tot_todos = d.groupby("CD_MUNICIPIO")["eleitores"].sum()
    v = d[ok].copy()
    v["a"] = [f[0] for f in fx[ok]]
    v["b"] = [f[1] for f in fx[ok]]
    nasc_ini, nasc_fim = t - v["b"] - 1, t - v["a"]  # intervalo de nascimento da faixa
    out = pd.DataFrame({"eleitores": v.groupby("CD_MUNICIPIO")["eleitores"].sum()})
    for nome, (c0, c1) in COORTES.items():
        frac = (np.minimum(nasc_fim, c1) - np.maximum(nasc_ini, c0)).clip(lower=0) / (nasc_fim - nasc_ini)
        out[nome] = 100 * (v["eleitores"] * frac).groupby(v["CD_MUNICIPIO"]).sum() / out["eleitores"]
    for nome, (a0, a1) in FAIXAS_DESC.items():
        m = (v["a"] >= a0) & (v["b"] <= a1)
        out[nome] = 100 * v["eleitores"].where(m, 0).groupby(v["CD_MUNICIPIO"]).sum() / out["eleitores"]
    out["pct_idade_ni"] = 100 * (1 - out["eleitores"] / tot_todos.reindex(out.index))
    out["ano"] = ano
    return out.reset_index().rename(columns={"CD_MUNICIPIO": "cd_tse"})


def main() -> None:
    xw = crosswalk()[["cd_tse", "id_municipio"]]
    partes = []
    for ano in config()["anos_eleicao"]:
        c = coortes(ler_ano(ano))
        if c["eleitores"].sum() == 0:
            log.warning("%d: sem faixa etária informada — ano descartado", ano)
            continue
        partes.append(c)
    df = pd.concat(partes, ignore_index=True).merge(xw, on="cd_tse", how="left")
    sem = df["id_municipio"].isna()
    if sem.any():
        log.warning("códigos TSE sem IBGE: %s", df.loc[sem, "cd_tse"].unique()[:20])
    df = df[~sem].astype({"id_municipio": int})
    for ano, g in df.groupby("ano"):
        log.info("%d: %d municípios; idade não informada %.2f%%; coortes %s", ano, len(g),
                 100 - 100 * g["eleitores"].sum() / (g["eleitores"] / (1 - g["pct_idade_ni"] / 100)).sum(),
                 {c: round(np.average(g[c], weights=g["eleitores"]), 1) for c in COORTES})
    df.to_parquet(caminho("interim") / "tse_perfil_idade.parquet", index=False)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    main()
