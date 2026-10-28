"""Setores censitários do Censo 2022: malha e agregados (pacto 2.0, Fase B).

Fontes (IBGE; listagens conferidas em 27/10/2026):
- Malha com atributos (geometria + situação urbana/rural + variáveis básicas), Brasil:
  ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios/malha_com_atributos/
  setores/gpkg/BR/BR_setores_CD2022.gpkg (1,50 GB)
- Agregados por setor (CSV), mesmo diretório-base, Agregados_por_Setor_csv/:
  - Agregados_por_setores_basico_BR_20260520.zip — V0001 pessoas, V0007 domicílios ocupados etc.
  - Agregados_por_setores_cor_ou_raca_BR.zip
  - Agregados_por_setores_demografia_BR.zip — pessoas por sexo e grupos de idade
  Dicionário: dicionario_de_dados_agregados_por_setores_censitarios_20260520.xlsx
- Rendimento do responsável (publicado em 08/05/2026):
  ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios_Rendimento_do_Responsavel/
  Agregados_por_setores_renda_responsavel_BR_20260508_csv.zip
  + dicionario_de_dados_renda_responsavel_20260508.xlsx
Destino: data/raw/ibge_setores/ (nunca editado à mão).

Uso: python -m src.ingest.ibge_setores
"""

from __future__ import annotations

import logging

from src.utils import baixar, caminho

log = logging.getLogger("ibge_setores")
BASE = "https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022"
AGR = f"{BASE}/Agregados_por_Setores_Censitarios"
REN = f"{BASE}/Agregados_por_Setores_Censitarios_Rendimento_do_Responsavel"
ARQUIVOS = [
    f"{AGR}/malha_com_atributos/setores/gpkg/BR/BR_setores_CD2022.gpkg",
    f"{AGR}/Agregados_por_Setor_csv/Agregados_por_setores_basico_BR_20260520.zip",
    f"{AGR}/Agregados_por_Setor_csv/Agregados_por_setores_cor_ou_raca_BR.zip",
    f"{AGR}/Agregados_por_Setor_csv/Agregados_por_setores_demografia_BR.zip",
    f"{AGR}/dicionario_de_dados_agregados_por_setores_censitarios_20260520.xlsx",
    f"{REN}/Agregados_por_setores_renda_responsavel_BR_20260508_csv.zip",
    f"{REN}/dicionario_de_dados_renda_responsavel_20260508.xlsx",
]


def pasta():
    return caminho("raw") / "ibge_setores"


def main() -> None:
    for u in ARQUIVOS:
        baixar(u, pasta() / u.rsplit("/", 1)[1])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    main()
