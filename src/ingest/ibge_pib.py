"""PIB dos Municípios pela ótica da oferta, 2002–2023.

Fonte principal: bases de dados do IBGE no FTP (divulgação 2022–2023, referência 2010):
- https://ftp.ibge.gov.br/Pib_Municipios/2022_2023/base/base_de_dados_2002_2009_xlsx.zip
- https://ftp.ibge.gov.br/Pib_Municipios/2022_2023/base/base_de_dados_2010_2023_xlsx.zip
Motivo: na tabela SIDRA 5938 o VAB por atividade de 2022–2023 aparece como '...' (indisponível),
embora o PIB total esteja lá; a base do FTP traz o VAB completo até 2023. A tabela 5938
(v37, PIB) é usada como checagem cruzada em tests/test_fase3_indicadores.py.

Colunas (R$ 1.000, preços correntes, convertidas para R$): VAB agropecuária, indústria, serviços
exceto administração pública, administração pública (adm., defesa, educação, saúde públicas e
seguridade social), VAB total, PIB.

Derivadas:
- part_vab_{agro,industria,servicos,adm_publica}: % do VAB total (participações, como pede o PLANO);
- pib_pc_real, vab_agro_pc_real: R$ de dez/2025 por habitante, deflacionados pelo IPCA (média anual)
  e divididos pela série coerente de população (src/ingest/ibge_pop.py).
  O PLANO (seção 3) menciona o deflator implícito da UF; a Fase 3 pede IPCA. Usado o IPCA; ver
  outputs/pendencias.md.

Saída: data/interim/ibge_pib.parquet (id_municipio, ano, ...)
"""

from __future__ import annotations

import logging
import zipfile

import pandas as pd

from src.ingest.sidra import log_cobertura
from src.utils import baixar, caminho

log = logging.getLogger("ibge_pib")
FTP = "https://ftp.ibge.gov.br/Pib_Municipios/2022_2023/base"
ARQUIVOS = ["base_de_dados_2002_2009_xlsx.zip", "base_de_dados_2010_2023_xlsx.zip"]
# trecho do nome da coluna (sem quebras de linha) → variável
COLUNAS = {
    "Valor adicionado bruto da Agropecuária": "vab_agro",
    "Valor adicionado bruto da Indústria": "vab_industria",
    "Valor adicionado bruto dos Serviços": "vab_servicos",
    "Valor adicionado bruto da Administração": "vab_adm_publica",
    "Valor adicionado bruto total": "vab",
    "Produto Interno Bruto,": "pib",
}


def ler_base(nome: str) -> pd.DataFrame:
    z = zipfile.ZipFile(baixar(f"{FTP}/{nome}", caminho("raw") / "ibge_pib" / nome))
    d = pd.read_excel(z.open(z.namelist()[0]))
    d.columns = [" ".join(str(c).split()) for c in d.columns]
    mapa = {"Ano": "ano", "Código do Município": "id_municipio"}
    for trecho, var in COLUNAS.items():
        achadas = [c for c in d.columns if c.startswith(trecho)]
        assert len(achadas) == 1, (nome, trecho, achadas)
        mapa[achadas[0]] = var
    return d[list(mapa)].rename(columns=mapa)


def main() -> None:
    w = pd.concat([ler_base(a) for a in ARQUIVOS], ignore_index=True)
    w = w.astype({"ano": int, "id_municipio": int})
    for c in COLUNAS.values():
        w[c] = pd.to_numeric(w[c], errors="coerce") * 1000  # R$ 1.000 → R$
    for c in ["agro", "industria", "servicos", "adm_publica"]:
        w[f"part_vab_{c}"] = 100 * w[f"vab_{c}"] / w["vab"]
    ipca = pd.read_parquet(caminho("interim") / "ipca.parquet")[["ano", "fator_anual"]]
    pop = pd.read_parquet(caminho("interim") / "ibge_pop.parquet")[["id_municipio", "ano", "pop"]]
    w = w.merge(ipca, on="ano", how="left").merge(pop, on=["id_municipio", "ano"], how="left")
    w["pib_pc_real"] = w["pib"] * w["fator_anual"] / w["pop"]
    w["vab_agro_pc_real"] = w["vab_agro"] * w["fator_anual"] / w["pop"]
    w = w.drop(columns=["fator_anual", "pop"])
    log_cobertura(w, "ibge_pib", ["pib", "part_vab_agro", "pib_pc_real"])
    w.to_parquet(caminho("interim") / "ibge_pib.parquet", index=False)


if __name__ == "__main__":
    main()
