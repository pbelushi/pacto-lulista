"""Fase 1 — votação do 2º turno presidencial por município, 2006–2026.

Fontes (TSE, Dados Abertos, CDN — ver src/ingest/tse_download.py):
- votacao_candidato_munzona_<ano>.zip → arquivo <...>_BRASIL.csv, filtro CD_CARGO=1 (Presidente), NR_TURNO=2
- detalhe_votacao_munzona_<ano>.zip → arquivo <...>_BRASIL.csv, mesmo filtro
- 2026: o CDN só tem o 1º turno (arquivos gerados em 25/10/2026 antes do fim da votação).
  Fallback = Portal Resultados (src/ingest/tse_portal.py), eleição 6258, cargo c0001.

Regras:
- Excluídos: exterior (SG_UF = 'ZZ') e seções de voto em trânsito (ST_VOTO_EM_TRANSITO = 'S').
  Obs.: nos arquivos munzona 2006–2026 a flag é sempre 'N' — o voto em trânsito fica no
  município onde foi dado e não é separável; o portal de 2026 tem o mesmo tratamento.
- Crosswalk TSE→IBGE: config de municípios do Portal Resultados 2026 (campos `cd` e `cdi`).
- AMC: municípios instalados após 2010 são somados ao município-mãe (config.yaml, chave `amc`).

Saídas:
- data/interim/tse_presidencial_totais_br.parquet (totais nacionais com exterior e trânsito, para checks)
- data/interim/tse_presidencial_municipio.parquet (municípios como no TSE em cada ano)
- data/interim/tse_presidencial.parquet (AMC; unidade de análise)
"""

from __future__ import annotations

import json
import logging
import zipfile

import pandas as pd

from src.ingest.tse_portal import pasta as pasta_portal
from src.utils import caminho, config

log = logging.getLogger("tse")

COLS_DETALHE = {
    "QT_APTOS": "aptos",
    "QT_COMPARECIMENTO": "comparecimento",
    "QT_ABSTENCOES": "abstencoes",
    "QT_VOTOS_BRANCOS": "brancos",
    # nulos = QT_VOTOS_NULOS + QT_VOTOS_NULOS_TECNICOS + QT_VOTOS_ANULADOS_APU_SEP.
    # Não usar QT_TOTAL_VOTOS_NULOS: em 2006 ele fica 18.645 votos abaixo dos componentes
    # e não fecha comparecimento = válidos + brancos + nulos.
    "QT_VOTOS_NULOS": "nulos_",
    "QT_VOTOS_NULOS_TECNICOS": "nulos_tecnicos",
    "QT_VOTOS_ANULADOS_APU_SEP": "anulados_apu_sep",
    "QT_TOTAL_VOTOS_VALIDOS": "validos_tse",
}
SOMAS = ["votos_pt", "votos_op", "validos", "aptos", "comparecimento", "abstencoes", "brancos", "nulos"]


def crosswalk() -> pd.DataFrame:
    """Código TSE (int) → código IBGE (int), a partir do config do Portal Resultados."""
    cm = json.loads((pasta_portal() / "mun-cm.json").read_text(encoding="utf-8"))
    linhas = [
        {"cd_tse": int(m["cd"]), "id_municipio": int(m["cdi"]), "sg_uf": uf["cd"].upper(), "nome": m["nm"]}
        for uf in cm["abr"]
        if uf["cd"] != "zz"
        for m in uf["mu"]
    ]
    return pd.DataFrame(linhas)


def _ler_brasil(conjunto: str, ano: int, usecols: list[str], cargo: int = 1, turno: int = 2) -> pd.DataFrame:
    """Lê <conjunto>_<ano>_BRASIL.csv só com as linhas do cargo e turno pedidos (padrão: Presidente, 2º turno)."""
    z = zipfile.ZipFile(caminho("raw") / "tse" / f"{conjunto}_{ano}.zip")
    partes = []
    with z.open(f"{conjunto}_{ano}_BRASIL.csv") as fh:
        for ch in pd.read_csv(fh, sep=";", encoding="latin-1", usecols=usecols, chunksize=2_000_000,
                              dtype={"SG_UF": str, "ST_VOTO_EM_TRANSITO": str}):
            partes.append(ch[(ch["CD_CARGO"] == cargo) & (ch["NR_TURNO"] == turno)])
    df = pd.concat(partes, ignore_index=True)
    df["CD_MUNICIPIO"] = df["CD_MUNICIPIO"].astype(int)
    return df


def _excluir_exterior_transito(df: pd.DataFrame, rotulo: str) -> pd.DataFrame:
    n_ext = (df["SG_UF"] == "ZZ").sum()
    n_tra = (df["ST_VOTO_EM_TRANSITO"] == "S").sum()
    log.info("%s: excluídas %d linhas do exterior e %d de trânsito", rotulo, n_ext, n_tra)
    return df[(df["SG_UF"] != "ZZ") & (df["ST_VOTO_EM_TRANSITO"] != "S")]


def colunas(conjunto: str, ano: int) -> list[str]:
    """Cabeçalho do arquivo BRASIL de um conjunto (os nomes de coluna mudam entre anos)."""
    z = zipfile.ZipFile(caminho("raw") / "tse" / f"{conjunto}_{ano}.zip")
    with z.open(f"{conjunto}_{ano}_BRASIL.csv") as fh:
        return [c.strip().strip(chr(34)) for c in fh.readline().decode("latin-1").split(";")]


def tse_para_amc() -> pd.DataFrame:
    """Código TSE → código IBGE e código da AMC (unidade de análise)."""
    amc = {int(k): int(v) for k, v in config()["amc"].items()}
    xw = crosswalk()
    xw["id_amc"] = xw["id_municipio"].map(lambda c: amc.get(c, c))
    return xw


def _ano_cdn(ano: int) -> tuple[pd.DataFrame, dict]:
    pres = config()["presidencial"][ano]
    base = ["NR_TURNO", "CD_CARGO", "SG_UF", "CD_MUNICIPIO", "ST_VOTO_EM_TRANSITO"]
    cand = _ler_brasil("votacao_candidato_munzona", ano, base + ["NR_CANDIDATO", "QT_VOTOS_NOMINAIS"])
    assert set(cand["NR_CANDIDATO"].unique()) == {pres["pt"], pres["op"]}, cand["NR_CANDIDATO"].unique()
    tot = cand.groupby("NR_CANDIDATO")["QT_VOTOS_NOMINAIS"].sum()
    total = {"ano": ano, "votos_pt": int(tot[pres["pt"]]), "votos_op": int(tot[pres["op"]])}
    cand = _excluir_exterior_transito(cand, f"candidatos {ano}")
    votos = (cand.pivot_table(index="CD_MUNICIPIO", columns="NR_CANDIDATO", values="QT_VOTOS_NOMINAIS",
                              aggfunc="sum", fill_value=0)
             .rename(columns={pres["pt"]: "votos_pt", pres["op"]: "votos_op"}))
    det = _ler_brasil("detalhe_votacao_munzona", ano, base + list(COLS_DETALHE))
    det = _excluir_exterior_transito(det, f"detalhe {ano}")
    det = det.rename(columns=COLS_DETALHE).groupby("CD_MUNICIPIO")[list(COLS_DETALHE.values())].sum()
    det["nulos"] = det.pop("nulos_") + det.pop("nulos_tecnicos") + det.pop("anulados_apu_sep")
    df = votos.join(det, how="outer").reset_index().rename(columns={"CD_MUNICIPIO": "cd_tse"})
    df["fonte"] = "TSE CDN"
    return df, total


def _ano_portal_2026() -> tuple[pd.DataFrame, dict]:
    pres = config()["presidencial"][2026]
    linhas = []
    total = {"ano": 2026, "votos_pt": 0, "votos_op": 0}
    for f in pasta_portal().glob("*/*-u.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        assert d["t"] == "2" and d["s"]["st"] == d["s"]["ts"], f"{f.name}: não totalizado"
        cand = {int(c["n"]): int(c["vap"]) for a in d["carg"][0]["agr"] for p in a["par"] for c in p["cand"]}
        total["votos_pt"] += cand[pres["pt"]]
        total["votos_op"] += cand[pres["op"]]
        if f.parent.name == "zz":  # exterior
            continue
        linhas.append({
            "cd_tse": int(d["cdabr"]),
            "votos_pt": cand[pres["pt"]], "votos_op": cand[pres["op"]],
            "aptos": int(d["e"]["te"]), "comparecimento": int(d["e"]["c"]),
            "abstencoes": int(d["e"]["a"]), "brancos": int(d["v"]["vb"]),
            "nulos": int(d["v"]["tvn"]), "validos_tse": int(d["v"]["vv"]),
        })
    df = pd.DataFrame(linhas)
    df["fonte"] = "TSE Portal Resultados (inclui trânsito)"
    return df, total


def _tem_2turno_cdn(ano: int) -> bool:
    z = zipfile.ZipFile(caminho("raw") / "tse" / f"detalhe_votacao_munzona_{ano}.zip")
    with z.open(f"detalhe_votacao_munzona_{ano}_BRASIL.csv") as fh:
        t = pd.read_csv(fh, sep=";", encoding="latin-1", usecols=["NR_TURNO", "CD_CARGO"])
    return bool(((t["NR_TURNO"] == 2) & (t["CD_CARGO"] == 1)).any())


def presidencial_municipio() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Retorna (votação por município, totais nacionais com exterior e trânsito)."""
    xw = crosswalk()
    anos, totais = [], []
    for ano in config()["anos_eleicao"]:
        if ano == 2026 and not _tem_2turno_cdn(2026):
            log.warning("2026: CDN sem 2º turno; usando Portal Resultados")
            df, total = _ano_portal_2026()
        else:
            df, total = _ano_cdn(ano)
        totais.append(total)
        df["ano"] = ano
        sem_ibge = set(df["cd_tse"]) - set(xw["cd_tse"])
        assert not sem_ibge, f"{ano}: códigos TSE sem correspondência IBGE: {sem_ibge}"
        anos.append(df.merge(xw, on="cd_tse", how="left"))
    df = pd.concat(anos, ignore_index=True)
    df["validos"] = df["votos_pt"] + df["votos_op"]
    return df, pd.DataFrame(totais)


def para_amc(df: pd.DataFrame) -> pd.DataFrame:
    df = df.merge(tse_para_amc()[["cd_tse", "id_amc"]], on="cd_tse", how="left")
    g = df.groupby(["ano", "id_amc"], as_index=False).agg(
        {**{c: "sum" for c in SOMAS + ["validos_tse"]}, "sg_uf": "first", "fonte": "first",
         "id_municipio": "count"}
    ).rename(columns={"id_municipio": "n_municipios_agregados"})
    return calcular_indicadores(g)


def calcular_indicadores(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["s_pt"] = 100 * df["votos_pt"] / df["validos"]
    df["e_pt"] = 100 * df["votos_pt"] / df["aptos"]
    df["e_op"] = 100 * df["votos_op"] / df["aptos"]
    df["tx_abstencao"] = 100 * df["abstencoes"] / df["aptos"]
    df["tx_brancos_nulos"] = 100 * (df["brancos"] + df["nulos"]) / df["comparecimento"]
    return df


def main() -> None:
    mun, totais = presidencial_municipio()
    totais.to_parquet(caminho("interim") / "tse_presidencial_totais_br.parquet", index=False)
    mun = calcular_indicadores(mun)
    mun.to_parquet(caminho("interim") / "tse_presidencial_municipio.parquet", index=False)
    amc = para_amc(mun)
    amc.to_parquet(caminho("interim") / "tse_presidencial.parquet", index=False)
    for ano, g in amc.groupby("ano"):
        log.info("%d: %d AMCs; s_PT nacional (sem exterior/trânsito) = %.2f%%; missing s_pt = %d",
                 ano, len(g), 100 * g["votos_pt"].sum() / g["validos"].sum(), g["s_pt"].isna().sum())


if __name__ == "__main__":
    main()
