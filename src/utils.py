"""Utilidades comuns: configuração, caminhos e download reprodutível."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import requests
import truststore
import yaml

# Verificação TLS pelo repositório de certificados do sistema operacional. Alguns servidores públicos
# (ex.: download.inep.gov.br) não enviam a cadeia intermediária; o Windows a completa, o certifi não.
truststore.inject_into_ssl()

RAIZ = Path(__file__).resolve().parents[1]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@lru_cache
def config() -> dict:
    with open(RAIZ / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def caminho(chave: str) -> Path:
    """Caminho absoluto de uma pasta definida em config.yaml (raw, interim, ...)."""
    p = RAIZ / config()["caminhos"][chave]
    p.mkdir(parents=True, exist_ok=True)
    return p


def baixar(url: str, destino: Path, forcar: bool = False, verificar_tls: bool = True) -> Path:
    """Baixa `url` para `destino` se ainda não existir (ou se o tamanho divergir).

    Escreve em arquivo temporário e renomeia ao fim, para nunca deixar um
    arquivo truncado em data/raw/.
    """
    log = logging.getLogger("download")
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists() and not forcar:
        tam_remoto = requests.head(url, timeout=60, verify=verificar_tls).headers.get("Content-Length")
        if tam_remoto is None or int(tam_remoto) == destino.stat().st_size:
            log.info("já existe: %s", destino.name)
            return destino
        log.info("tamanho divergente, rebaixando: %s", destino.name)
    tmp = destino.with_suffix(destino.suffix + ".part")
    with requests.get(url, stream=True, timeout=120, verify=verificar_tls) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for bloco in r.iter_content(chunk_size=1 << 20):
                f.write(bloco)
    tmp.replace(destino)
    log.info("baixado: %s (%.1f MB)", destino.name, destino.stat().st_size / 1e6)
    return destino
