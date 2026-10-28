"""População municipal, série anual coerente 2000–2026.

Tabelas SIDRA (IDs conferidos em 27/10/2026 via servicodados.ibge.gov.br/api/v3/agregados/<id>/metadados):
- 202  "População residente, por sexo e situação do domicílio" — Censo 2000 (v93, c1=0, c2=0)
- 9605 "População residente, por cor ou raça, nos Censos Demográficos" — Censos 2010 e 2022 (v93, c86=95251 total)
- 6579 "População residente estimada" — estimativas anuais (v9324), 2001–2026 com lacunas

As estimativas não formam série única: há salto em 2013 (rebase pela projeção revisada) e as
estimativas pós-2022 (rebaseadas no Censo 2022) ficam abaixo das de 2021 em nível nacional.
Série coerente (`pop`):
- anos de Censo (2000, 2010, 2022): população recenseada;
- anos intercensitários: interpolação geométrica entre os dois Censos; municípios instalados após
  2000 (sem Censo 2000) são retroprojetados em 2001–2009 com a própria taxa 2010–2022, nos anos em
  que já constam das estimativas. Limitação: o Censo 2000 do município-mãe inclui o território
  desmembrado, então a interpolação da mãe em 2001–2009 fica levemente superestimada;
- 2023–2026: as estimativas pós-2022 incorporam a correção de cobertura do Censo 2022 (Brasil:
  Censo 2022 = 203,1 mi; estimativa 2024 = 212,6 mi, +4,7% em dois anos) e não estão na base de
  contagem dos Censos. Para manter a série toda na base censitária, a estimativa entra só como
  taxa de crescimento: 2023 e 2024 = Censo 2022 × (1 + r)^k, com r = crescimento 2024→2025 do
  próprio município; 2025 e 2026 = 2024 × variação da estimativa.
`pop_estimativa_ibge` guarda a estimativa original para comparação.

Municípios instalados depois de um Censo ficam sem pop até existirem nos dados; a agregação em
AMC (Fase 4) resolve isso.

Saída: data/interim/ibge_pop.parquet (id_municipio, ano, pop, pop_estimativa_ibge, fonte_pop)
"""

from __future__ import annotations

import logging

import pandas as pd

from src.ingest.sidra import consultar, log_cobertura
from src.utils import caminho

log = logging.getLogger("ibge_pop")


def _limpo(df: pd.DataFrame, col_ano: str) -> pd.DataFrame:
    return pd.DataFrame({"id_municipio": df["Município (Código)"].astype(int),
                         "ano": df[col_ano].astype(int), "valor": df["Valor"]})


def censos() -> pd.DataFrame:
    c00 = _limpo(consultar(202, "v/93/p/2000/c1/0/c2/0", "censo2000"), "Ano (Código)")
    c10_22 = _limpo(consultar(9605, "v/93/p/2010,2022/c86/95251", "censos_total"), "Ano (Código)")
    return pd.concat([c00, c10_22]).dropna().pivot(index="id_municipio", columns="ano", values="valor")


def estimativas() -> pd.DataFrame:
    e = _limpo(consultar(6579, "v/9324/p/all", "estimativas"), "Ano (Código)")
    return e.dropna().pivot(index="id_municipio", columns="ano", values="valor")


def serie_coerente(cen: pd.DataFrame, est: pd.DataFrame) -> pd.DataFrame:
    anos = range(2000, 2027)
    pop = pd.DataFrame(index=cen.index.union(est.index), columns=list(anos), dtype=float)
    fonte = pd.DataFrame(index=pop.index, columns=list(anos), dtype=object)
    for a in [2000, 2010, 2022]:
        pop[a] = cen[a].reindex(pop.index)
        fonte[a] = "censo"
    for a0, a1 in [(2000, 2010), (2010, 2022)]:
        for a in range(a0 + 1, a1):
            w = (a - a0) / (a1 - a0)
            pop[a] = pop[a0] ** (1 - w) * pop[a1] ** w
            fonte[a] = "interpolação geométrica entre Censos"
    # municípios instalados após o Censo 2000 (sem pop em 2000): retroprojeção 2001–2009 com a
    # taxa geométrica 2010–2022 do próprio município, só nos anos em que já existiam nas estimativas
    sem2000 = pop[2000].isna() & pop[2010].notna()
    taxa = (pop[2022] / pop[2010]) ** (1 / 12)
    anos_est = [a for a in range(2001, 2010) if a in est.columns]
    primeiro = est.reindex(pop.index)[anos_est].notna().idxmax(axis=1).where(
        est.reindex(pop.index)[anos_est].notna().any(axis=1))
    for a in range(2001, 2010):
        existe = sem2000 & (primeiro <= a)  # 2007 (sem estimativa IBGE) herda a existência dos anos vizinhos
        pop.loc[existe, a] = pop.loc[existe, 2010] * taxa[existe] ** (a - 2010)
        fonte.loc[existe, a] = "retroprojeção com crescimento 2010–2022 (instalado após 2000)"
    e = est.reindex(pop.index)
    r = e[2025] / e[2024] - 1
    for k, a in [(1, 2023), (2, 2024)]:
        pop[a] = pop[2022] * (1 + r) ** k
        fonte[a] = "Censo 2022 × crescimento 2024→2025 da estimativa"
    for a in [2025, 2026]:
        pop[a] = pop[a - 1] * e[a] / e[a - 1]
        fonte[a] = "base censitária × variação da estimativa IBGE"
    out = pop.stack(future_stack=True).rename("pop").reset_index().rename(columns={"level_1": "ano"})
    out["fonte_pop"] = fonte.stack(future_stack=True).values
    out["ano"] = out["ano"].astype(int)
    e = est.stack().rename("pop_estimativa_ibge").reset_index().rename(columns={"level_1": "ano"})
    e["ano"] = e["ano"].astype(int)
    return out.merge(e, on=["id_municipio", "ano"], how="left")


def main() -> None:
    df = serie_coerente(censos(), estimativas())
    df.loc[df["pop"].isna(), "fonte_pop"] = None
    log_cobertura(df, "ibge_pop", ["pop", "pop_estimativa_ibge"])
    df.to_parquet(caminho("interim") / "ibge_pop.parquet", index=False)


if __name__ == "__main__":
    main()
