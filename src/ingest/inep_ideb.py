"""Ideb municipal, anos iniciais do ensino fundamental, rede pública, 2005–2025 (bienal).

Fonte: INEP, https://download.inep.gov.br/ideb/resultados/divulgacao_anos_iniciais_municipios_2025.zip
(planilha com a série 2005–2025; MD5 conferido contra o arquivo md5_*.txt do próprio zip).
Colunas usadas: CO_MUNICIPIO, REDE == 'Pública', VL_OBSERVADO_<ano> (Ideb observado).
Valores '-' ou '*' (sem Ideb: poucos alunos, taxa de participação baixa etc.) → NaN.

Saída: data/interim/inep_ideb.parquet (id_municipio, ano, ideb_ai_publica)
"""

from __future__ import annotations

import hashlib
import io
import logging
import re
import zipfile

import pandas as pd

from src.ingest.sidra import log_cobertura
from src.utils import baixar, caminho

log = logging.getLogger("inep_ideb")
URL = "https://download.inep.gov.br/ideb/resultados/divulgacao_anos_iniciais_municipios_2025.zip"
BASE = "divulgacao_anos_iniciais_municipios_2025/"


def ler() -> pd.DataFrame:
    z = zipfile.ZipFile(baixar(URL, caminho("raw") / "inep" / URL.rsplit("/", 1)[1]))
    x = z.read(BASE + "divulgacao_anos_iniciais_municipios_2025.xlsx")
    md5 = z.read(BASE + "md5_divulgacao_anos_iniciais_municipios_2025.txt").decode("latin-1")
    esperado = re.search(r"([0-9A-Fa-f]{32}) \*divulgacao_anos_iniciais_municipios_2025\.xlsx", md5).group(1)
    assert hashlib.md5(x).hexdigest() == esperado.lower(), "MD5 do xlsx do Ideb não confere"
    df = pd.read_excel(io.BytesIO(x), header=9)
    df = df[df["REDE"] == "Pública"]
    obs = [c for c in df.columns if str(c).startswith("VL_OBSERVADO_")]
    long = df.melt(id_vars=["CO_MUNICIPIO"], value_vars=obs, var_name="col", value_name="ideb_ai_publica")
    long["ano"] = long["col"].str[-4:].astype(int)
    long["ideb_ai_publica"] = pd.to_numeric(long["ideb_ai_publica"], errors="coerce")
    return long.rename(columns={"CO_MUNICIPIO": "id_municipio"})[["id_municipio", "ano", "ideb_ai_publica"]].dropna(
        subset=["id_municipio"]).astype({"id_municipio": int})


def main() -> None:
    df = ler()
    log_cobertura(df, "inep_ideb", ["ideb_ai_publica"])
    df.to_parquet(caminho("interim") / "inep_ideb.parquet", index=False)


if __name__ == "__main__":
    main()
