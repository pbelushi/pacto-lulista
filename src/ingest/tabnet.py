"""Cliente do TabNet/DATASUS (tabnet.datasus.gov.br) para contagens por município e ano.

Cada consulta = um arquivo anual (ex.: obtbr22.dbf), Linha = 'Município', Coluna desativada,
formato 'prn' (texto separado por ';' dentro de <PRE>), com filtros opcionais (campos S<variável>).
O formulário usa nomes de campo com acento: o corpo do POST vai codificado em latin-1.
Os municípios vêm com o código IBGE de 6 dígitos (sem dígito verificador); a conversão para 7
dígitos é feita pela lista de municípios do IBGE (6 primeiros dígitos são únicos).
Respostas brutas em data/raw/tabnet/<rotulo>_<arquivo>.txt.
"""

from __future__ import annotations

import io
import logging
import re
import time
from urllib.parse import urlencode

import pandas as pd
import requests

from src.utils import caminho

log = logging.getLogger("tabnet")
URL = "http://tabnet.datasus.gov.br/cgi/tabcgi.exe?{defn}"


def consultar(defn: str, incremento: str, arquivo: str, filtros: dict[str, list[str]], rotulo: str) -> pd.DataFrame:
    """Retorna DataFrame (cod6, valor) para um arquivo anual do TabNet."""
    pasta = caminho("raw") / "tabnet"
    pasta.mkdir(parents=True, exist_ok=True)
    arq = pasta / f"{rotulo}_{arquivo.replace('.dbf', '')}.txt"
    if not arq.exists():
        campos = [("Linha", "Município"), ("Coluna", "--Não-Ativa--"), ("Incremento", incremento),
                  ("Arquivos", arquivo)]
        for nome, valores in filtros.items():
            campos += [(nome, v) for v in valores]
        campos += [("formato", "prn"), ("mostre", "Mostra")]
        corpo = urlencode(campos, encoding="latin-1")
        for tentativa in range(5):
            try:
                r = requests.post(URL.format(defn=defn), data=corpo, timeout=600,
                                  headers={"Content-Type": "application/x-www-form-urlencoded"})
                r.raise_for_status()
                break
            except requests.RequestException as e:
                log.warning("TabNet %s %s: %s (tentativa %d)", rotulo, arquivo, e, tentativa + 1)
                time.sleep(10 * (tentativa + 1))
        else:
            raise RuntimeError(f"TabNet falhou: {rotulo} {arquivo}")
        time.sleep(1)  # cortesia com o servidor entre consultas
        texto = r.content.decode("latin-1")
        pre = re.search(r"<PRE>(.*?)</PRE>", texto, flags=re.S | re.I)
        if pre is None:
            if "Nenhum registro selecionado" in texto:
                arq.write_text("", encoding="utf-8")
            else:
                raise RuntimeError(f"TabNet sem tabela: {rotulo} {arquivo}: {texto[:300]}")
        else:
            arq.write_text(pre.group(1), encoding="utf-8")
    txt = arq.read_text(encoding="utf-8").strip()
    if not txt:
        return pd.DataFrame(columns=["cod6", "valor"])
    df = pd.read_csv(io.StringIO(txt), sep=";", dtype=str)
    col_mun, col_val = df.columns[0], df.columns[-1]
    df["cod6"] = df[col_mun].str.extract(r"^\"?(\d{6})")[0]
    df["valor"] = pd.to_numeric(df[col_val].str.replace(".", "", regex=False).replace("-", "0"), errors="coerce")
    return df.dropna(subset=["cod6"])[["cod6", "valor"]]


def _formulario(defn: str) -> str:
    """HTML do formulário (com retentativas: o servidor derruba conexões de forma intermitente)."""
    for tentativa in range(5):
        try:
            r = requests.get(f"http://tabnet.datasus.gov.br/cgi/deftohtm.exe?{defn}", timeout=120)
            r.raise_for_status()
            return r.content.decode("latin-1")
        except requests.RequestException as e:
            log.warning("TabNet formulário %s: %s (tentativa %d)", defn, e, tentativa + 1)
            time.sleep(10 * (tentativa + 1))
    raise RuntimeError(f"TabNet: formulário indisponível {defn}")


def opcoes(defn: str, campo: str) -> dict[str, str]:
    """Mapa rótulo → valor das opções de um campo de filtro do formulário."""
    import html

    t = _formulario(defn)
    m = re.search(rf'<select[^>]*name="{re.escape(campo)}"[^>]*>(.*?)</select>', t, flags=re.S | re.I)
    return {html.unescape(l).strip(): v for v, l in re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)', m.group(1), flags=re.I)}


def arquivos(defn: str) -> dict[int, str]:
    """Ano → nome do arquivo anual disponível no formulário."""
    import html

    t = _formulario(defn)
    m = re.search(r'<select[^>]*name="Arquivos"[^>]*>(.*?)</select>', t, flags=re.S | re.I)
    return {int(html.unescape(l).strip()): v for v, l in re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)', m.group(1), flags=re.I)
            if html.unescape(l).strip().isdigit()}
