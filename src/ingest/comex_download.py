"""Download dos dados municipais do Comex Stat (MDIC/SECEX).

Fonte: https://balanca.economia.gov.br/balanca/bd/comexstat-bd/mun/
- EXP_COMPLETA_MUN.zip / IMP_COMPLETA_MUN.zip (série histórica completa até a data de geração)
- EXP_<ano>_MUN.csv / IMP_<ano>_MUN.csv (anos posteriores ao arquivo completo)
Tabelas auxiliares: https://balanca.economia.gov.br/balanca/bd/tabelas/{UF_MUN,NCM_SH}.csv

TLS: o certificado de balanca.economia.gov.br venceu em 03/10/2026 e a API oficial respondia 503.
O usuário autorizou em 27/10/2026 o download **sem verificação TLS, só neste domínio**. Como contrapartida,
a integridade é conferida em src/ingest/comex.py: os totais municipais de exportação e importação por ano
têm de bater com a série independente do Ipeadata (EXPORTACAO/IMPORTACAO, MDIC/SECEX).

Uso: python -m src.ingest.comex_download
"""

from __future__ import annotations

import urllib3

from src.utils import baixar, caminho

BASE = "https://balanca.economia.gov.br/balanca/bd"
urllib3.disable_warnings()


def main() -> None:
    pasta = caminho("raw") / "comex"
    for f in ["EXP_COMPLETA_MUN.zip", "IMP_COMPLETA_MUN.zip", "EXP_2025_MUN.csv", "IMP_2025_MUN.csv"]:
        baixar(f"{BASE}/comexstat-bd/mun/{f}", pasta / f, verificar_tls=False)
    for f in ["UF_MUN.csv", "NCM_SH.csv"]:
        baixar(f"{BASE}/tabelas/{f}", pasta / f, verificar_tls=False)


if __name__ == "__main__":
    main()
