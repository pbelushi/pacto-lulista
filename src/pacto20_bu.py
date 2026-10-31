"""Conferência do 2º turno de 2026: boletins de urna (BU) × arquivos por seção usados no pacto 2.0.

A base por local de votação (src/pacto20_base.py) lê votacao_secao_2026_BR.zip e detalhe_votacao_secao_2026.zip.
Esta etapa soma os BU (src/ingest/tse_bu.py) por seção e compara com esses arquivos: votos por candidato, brancos,
nulos, aptos e comparecimento, em cada seção (UF × município × zona × seção). Não altera a base.

Saída: outputs/tables/pacto20_bu_conferencia.{csv,md}.

Uso: python -m src.pacto20_bu
"""

from __future__ import annotations

import logging
import zipfile

import pandas as pd

from src.ingest.tse_bu import pasta
from src.pacto20_modelos import _salvar
from src.utils import caminho

log = logging.getLogger("pacto20_bu")
SECAO = ["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO"]
VOTAVEL = {13: "votos_13", 22: "votos_22", 95: "brancos", 96: "nulos"}
MEDIDAS = list(VOTAVEL.values()) + ["aptos", "comparecimento"]


def boletins() -> pd.DataFrame:
    partes = []
    for f in sorted(pasta().glob("bweb_2t_*.zip")):
        z = zipfile.ZipFile(f)
        nome = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        partes.append(pd.read_csv(z.open(nome), sep=";", encoding="latin-1",
                                  usecols=SECAO + ["CD_CARGO_PERGUNTA", "NR_VOTAVEL", "QT_VOTOS", "QT_APTOS",
                                                   "QT_COMPARECIMENTO"], dtype={"SG_UF": str}))
    d = pd.concat(partes, ignore_index=True)
    d = d[d["CD_CARGO_PERGUNTA"] == 1]
    w = d.pivot_table(index=SECAO, columns="NR_VOTAVEL", values="QT_VOTOS", aggfunc="sum", fill_value=0)
    w = w.reindex(columns=list(VOTAVEL), fill_value=0).rename(columns=VOTAVEL)
    # aptos e comparecimento vêm repetidos em cada linha do BU: um valor por seção
    return w.join(d.groupby(SECAO)[["QT_APTOS", "QT_COMPARECIMENTO"]].first()
                  .rename(columns={"QT_APTOS": "aptos", "QT_COMPARECIMENTO": "comparecimento"}))


def _ler_zip(arq, usecols) -> pd.DataFrame:
    z = zipfile.ZipFile(arq)
    nomes = [n for n in z.namelist() if n.lower().endswith(".csv")]
    # _BR.csv e _BRASIL.csv repetem os mesmos dados: usar só um (como em src/pacto20_base.py)
    br = [n for n in nomes if n.upper().endswith("_BR.CSV")][:1]
    return pd.concat([pd.read_csv(z.open(n), sep=";", encoding="latin-1", usecols=usecols, dtype={"SG_UF": str})
                      for n in (br or nomes)], ignore_index=True)


def secoes() -> pd.DataFrame:
    raw = caminho("raw") / "tse_secao"
    v = _ler_zip(raw / "votacao_secao" / "votacao_secao_2026_BR.zip",
                 SECAO + ["NR_TURNO", "CD_CARGO", "NR_VOTAVEL", "QT_VOTOS"])
    v = v[(v["NR_TURNO"] == 2) & (v["CD_CARGO"] == 1)]
    w = v.pivot_table(index=SECAO, columns="NR_VOTAVEL", values="QT_VOTOS", aggfunc="sum", fill_value=0)
    w = w.reindex(columns=list(VOTAVEL), fill_value=0).rename(columns=VOTAVEL)
    det = _ler_zip(raw / "detalhe_votacao_secao" / "detalhe_votacao_secao_2026.zip",
                   SECAO + ["NR_TURNO", "CD_CARGO", "QT_APTOS", "QT_COMPARECIMENTO"])
    det = det[(det["NR_TURNO"] == 2) & (det["CD_CARGO"] == 1)].set_index(SECAO)
    return w.join(det[["QT_APTOS", "QT_COMPARECIMENTO"]].rename(
        columns={"QT_APTOS": "aptos", "QT_COMPARECIMENTO": "comparecimento"}), how="outer")


def main() -> None:
    bu, sec = boletins(), secoes()
    so_bu, so_sec = bu.index.difference(sec.index), sec.index.difference(bu.index)
    comuns = bu.index.intersection(sec.index)
    log.info("seções: BU %d, arquivos por seção %d, comuns %d", len(bu), len(sec), len(comuns))
    d = bu.loc[comuns, MEDIDAS].astype(float) - sec.loc[comuns, MEDIDAS].astype(float)
    t = pd.DataFrame([{"medida": m, "total_bu": int(bu[m].sum()), "total_secao": int(sec[m].sum()),
                       "secoes_comuns": len(comuns), "secoes_diferentes": int((d[m] != 0).sum()),
                       "soma_abs_diferenca": int(d[m].abs().sum()), "secoes_so_bu": len(so_bu),
                       "secoes_so_arquivo_secao": len(so_sec)} for m in MEDIDAS])
    _salvar(t, "bu_conferencia", "2º turno de 2026: boletins de urna × arquivos por seção do TSE, com exterior",
            "Comparação seção a seção. BU: arquivos gerados em 26/10/2026, conferidos com o SHA-512 publicado.")
    print(t.to_string())
    falta = sec.loc[so_sec]
    log.info("seções só no arquivo por seção: %d; aptos %d; comparecimento %d", len(falta), falta["aptos"].sum(),
             falta["comparecimento"].sum())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    main()
