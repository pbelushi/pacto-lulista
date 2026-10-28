"""Manifesto dos dados: caminho, tamanho e SHA-256 de cada arquivo em data/raw, data/manual e data/processed.

Os dados brutos não vão para o repositório (dezenas de GB; ver README). Quem reproduzir baixa tudo pelos scripts de
src/ingest/ e confere com este manifesto se recebeu os mesmos arquivos. Fontes que republicam arquivos (TSE, IBGE,
V-Dem) podem mudar o conteúdo; divergência de hash indica versão diferente da usada na publicação.

Uso: python -m src.manifesto            # gera data/manifesto_dados.csv
     python -m src.manifesto --conferir # compara os arquivos locais com o manifesto
"""

from __future__ import annotations

import csv
import hashlib
import sys

from src.utils import RAIZ

PASTAS = ["data/raw", "data/manual", "data/processed"]
SAIDA = RAIZ / "data" / "manifesto_dados.csv"
IGNORAR = (".part", ".tmp")


def sha256(caminho) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 22), b""):
            h.update(bloco)
    return h.hexdigest()


def arquivos():
    for pasta in PASTAS:
        for p in sorted((RAIZ / pasta).rglob("*")):
            if p.is_file() and not p.name.endswith(IGNORAR):
                yield p


def gerar() -> None:
    linhas = []
    for p in arquivos():
        linhas.append({"arquivo": p.relative_to(RAIZ).as_posix(), "bytes": p.stat().st_size, "sha256": sha256(p)})
        print(linhas[-1]["arquivo"], flush=True)
    with open(SAIDA, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["arquivo", "bytes", "sha256"])
        w.writeheader()
        w.writerows(linhas)
    print(f"{len(linhas)} arquivos, {sum(l['bytes'] for l in linhas) / 1e9:.1f} GB → {SAIDA.relative_to(RAIZ)}")


def conferir() -> int:
    with open(SAIDA, encoding="utf-8") as f:
        ref = {r["arquivo"]: r for r in csv.DictReader(f)}
    falta, difere = [], []
    for nome, r in ref.items():
        p = RAIZ / nome
        if not p.exists():
            falta.append(nome)
        elif p.stat().st_size != int(r["bytes"]) or sha256(p) != r["sha256"]:
            difere.append(nome)
    print(f"{len(ref)} no manifesto; faltando {len(falta)}; diferentes {len(difere)}")
    for n in falta[:20] + difere[:20]:
        print("  ", n)
    return 1 if falta or difere else 0


if __name__ == "__main__":
    sys.exit(conferir() if "--conferir" in sys.argv else gerar())
