"""Raça e religião por município, Censos 2010 e 2022.

Tabelas SIDRA (IDs conferidos em 27/10/2026 via servicodados.ibge.gov.br/api/v3/agregados/<id>/metadados):
- 9605 "População residente, por cor ou raça, nos Censos Demográficos" (v93; c86: 95251 total,
  2776 branca, 2777 preta, 2778 amarela, 2779 parda, 2780 indígena), anos 2010 e 2022.
  (Usada no lugar da 3175 de 2010 indicada no PLANO, porque traz os dois Censos com as mesmas categorias.)
- Religião, **pessoas de 10 anos ou mais** nos dois anos, porque o Censo 2022 só divulgou
  religião para essa população:
  - 2010: 2103 "População residente, por situação do domicílio, sexo, grupos de idade e religião"
    (v93, c1=0, c2=0; c58: 0 total, 1140 0–4, 1141 5–9 → 10+ = total − 0–4 − 5–9;
     c133: 0 total, 95263 católica apostólica romana, 95277 evangélicas, 95265 evangélicas de
     origem pentecostal, 2836 sem religião)
  - 2022: 9537 "Pessoas de 10 anos ou mais de idade, por religião, segundo o sexo e os grupos de idade"
    (v140, c2=6794, c58=95253; c133: 95278 total, 95263, 95277, 2836)
  Pentecostais só existem em 2010; em 2022 há apenas o total de evangélicas.
- Trabalho (resultados da amostra; IDs conferidos em 27/10/2026 no mesmo endpoint de metadados):
  - 2010: 1572 "Pessoas de 10 anos ou mais de idade, por idade e condição de atividade e de ocupação na
    semana de referência - Resultados Gerais da Amostra" (v140; c287=12125 "14 anos ou mais";
    c12251: 104805 economicamente ativas, 104806 ocupadas, 104807 desocupadas)
  - 2010: 1577 "... ocupadas na semana de referência, por posição na ocupação e categoria do emprego no
    trabalho principal - Resultados Gerais da Amostra" (v916; c11913: 0 total, 96167 com carteira,
    96168 militar/estatutário, 12128 sem carteira, 9885 não remunerado, 96173 produção para o próprio
    consumo, 96170 empregador, 96171 conta própria). Só existe para 10 anos ou mais.
  - 2022: 6580 "Pessoas de 14 anos ou mais de idade, por condição em relação à força de trabalho e
    condição de ocupação..." (v1641; c2=6794, c58=95253; c629: 32386 força de trabalho, 32387 ocupada,
    32446 desocupada)
  - 2022: 10261 "Pessoas de 14 anos ou mais de idade ocupadas ... por posição na ocupação e categoria do
    emprego no trabalho principal, sexo e cor ou raça" (v4090; c2=6794, c86=95251; c11913: 96165 total,
    31723 privado sem carteira, 79368 doméstico sem carteira, 79373 setor público não estatutário sem
    carteira, 79376 estatais sem carteira, 79378 conta própria, 31731 familiar auxiliar)
  Definições harmonizadas (o CNPJ só existe em 2022 e a contribuição à previdência só em 2010, por
  isso nenhum dos dois entra):
  - taxa_desocupacao = desocupados / força de trabalho, 14 anos ou mais, nos dois anos;
  - pct_informal = (empregados sem carteira + conta própria + não remunerados/familiares auxiliares)
    / ocupados. Em 2010 exclui-se do denominador a produção para o próprio consumo, que em 2022 deixou
    de ser ocupação; 2010 cobre 10 anos ou mais (não há corte de 14+ municipal), 2022 cobre 14+;
  - pct_conta_propria = conta própria / ocupados (mesmos denominadores).
  O questionário e o conceito de ocupação mudaram entre os Censos (2022 segue a 19ª CIET); os níveis
  não são estritamente comparáveis — usar em z-score por eleição, como as demais covariáveis.

Saída: data/interim/ibge_censo.parquet (id_municipio, ano ∈ {2010, 2022}, pct_*)
"""

from __future__ import annotations

import logging

import pandas as pd

from src.ingest.sidra import consultar, log_cobertura
from src.utils import caminho

log = logging.getLogger("ibge_censo")

RACA = {"95251": "total", "2776": "branca", "2777": "preta", "2778": "amarela", "2779": "parda", "2780": "indigena"}
RELIG = {"0": "total", "95278": "total", "95263": "catolica", "95277": "evangelica", "95265": "pentecostal",
         "2836": "sem_religiao"}


def raca() -> pd.DataFrame:
    d = consultar(9605, "v/93/p/2010,2022/c86/" + ",".join(RACA), "raca")
    w = d.assign(id_municipio=d["Município (Código)"].astype(int), ano=d["Ano (Código)"].astype(int),
                 cat=d["Cor ou raça (Código)"].map(RACA)).pivot_table(
        index=["id_municipio", "ano"], columns="cat", values="Valor", aggfunc="first")
    out = pd.DataFrame(index=w.index)
    for c in ["branca", "preta", "parda", "amarela", "indigena"]:
        out[f"pct_{c}"] = 100 * w[c] / w["total"]
    out["pct_negra"] = out["pct_preta"] + out["pct_parda"]
    return out.reset_index()


def religiao() -> pd.DataFrame:
    cats10 = "0,95263,95277,95265,2836"
    d10 = consultar(2103, f"v/93/p/2010/c1/0/c2/0/c58/0,1140,1141/c133/{cats10}", "religiao2010")
    d10["idade"] = d10["Grupo de idade (Código)"]
    t = d10.pivot_table(index=["Município (Código)", "Religião (Código)"], columns="idade", values="Valor", aggfunc="first")
    # 10 anos ou mais = total − (0 a 4) − (5 a 9); NaN de sigilo em alguma faixa → NaN
    v10 = (t["0"] - t["1140"] - t["1141"]).rename("Valor").reset_index()
    v10["ano"] = 2010
    d22 = consultar(9537, "v/140/p/2022/c2/6794/c58/95253/c133/95278,95263,95277,2836", "religiao2022")
    d22 = d22[["Município (Código)", "Religião (Código)", "Valor"]].assign(ano=2022)
    d = pd.concat([v10, d22], ignore_index=True)
    w = d.assign(id_municipio=d["Município (Código)"].astype(int), cat=d["Religião (Código)"].map(RELIG)).pivot_table(
        index=["id_municipio", "ano"], columns="cat", values="Valor", aggfunc="first")
    out = pd.DataFrame(index=w.index)
    for c in ["catolica", "evangelica", "pentecostal", "sem_religiao"]:
        out[f"pct_{c}"] = 100 * w[c] / w["total"]
    # resíduo; em 2010 a faixa 10+ vem de subtração de estimativas amostrais e pode ficar
    # levemente negativa (até −0,07 p.p. em 28 municípios) → corte em 0
    out["pct_outras_religioes"] = (100 - out[["pct_catolica", "pct_evangelica", "pct_sem_religiao"]]
                                   .sum(axis=1, min_count=3)).clip(lower=0)
    return out.reset_index()


def _largo(d: pd.DataFrame, col_cat: str, ano: int) -> pd.DataFrame:
    return d.assign(id_municipio=d["Município (Código)"].astype(int)).pivot_table(
        index="id_municipio", columns=col_cat, values="Valor", aggfunc="first").assign(ano=ano)


def trabalho() -> pd.DataFrame:
    cat = "Condição de atividade e condição de ocupação (Código)"
    a10 = _largo(consultar(1572, "v/140/p/2010/c287/12125/c12251/104805,104806,104807", "atividade2010"), cat, 2010)
    a22 = _largo(consultar(6580, "v/1641/p/2022/c2/6794/c58/95253/c629/32386,32387,32446", "atividade2022"),
                 "Condição em relação à força de trabalho e condição de ocupação (Código)", 2022)
    pos = "Posição na ocupação e categoria do emprego no trabalho principal (Código)"
    p10 = _largo(consultar(1577, "v/916/p/2010/c11913/0,12128,9885,96173,96171", "posicao2010"), pos, 2010)
    p22 = _largo(consultar(10261, "v/4090/p/2022/c2/6794/c86/95251/c11913/96165,31723,79368,79373,79376,79378,31731",
                           "posicao2022"), pos, 2022)
    out10 = pd.DataFrame({
        "taxa_desocupacao": 100 * a10["104807"] / a10["104805"],
        "pct_informal": 100 * (p10["12128"] + p10["9885"] + p10["96171"]) / (p10["0"] - p10["96173"]),
        "pct_conta_propria": 100 * p10["96171"] / (p10["0"] - p10["96173"]), "ano": 2010})
    sem_cart = p22[["31723", "79368", "79373", "79376"]].sum(axis=1, min_count=1)
    out22 = pd.DataFrame({
        "taxa_desocupacao": 100 * a22["32446"] / a22["32386"],
        "pct_informal": 100 * (sem_cart + p22["79378"] + p22["31731"]) / p22["96165"],
        "pct_conta_propria": 100 * p22["79378"] / p22["96165"], "ano": 2022})
    return pd.concat([out10, out22]).reset_index()


def main() -> None:
    df = raca().merge(religiao(), on=["id_municipio", "ano"], how="outer")
    df = df.merge(trabalho(), on=["id_municipio", "ano"], how="outer")
    log_cobertura(df, "ibge_censo", [c for c in df.columns if c.startswith("pct_")])
    df.to_parquet(caminho("interim") / "ibge_censo.parquet", index=False)


if __name__ == "__main__":
    main()
