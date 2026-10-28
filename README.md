# O pacto lulista mudou de perfil?

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23735410.svg)](https://doi.org/10.5281/zenodo.23735410)

Três estudos empíricos, com código e resultados replicáveis, sobre a base eleitoral do PT e a polarização no Brasil:

| Estudo | Pergunta | Unidade e período | Relatório |
|---|---|---|---|
| **1. Pacto lulista** | A base territorial do voto petista no 2º turno (municípios pobres, nordestinos, dependentes de transferências) se manteve, se deslocou ou se dissolveu? | 5.565 AMCs, eleições de 2006 a 2026 | [`outputs/report/relatorio.md`](outputs/report/relatorio.md) e [`extra_coortes.md`](outputs/report/extra_coortes.md) |
| **2. Pacto lulista 2.0** | Dentro das mesmas cidades, os locais de votação mais jovens e mais negros passaram a votar mais no PT, líquido de renda? | ~80 mil locais de votação, 2018–2026 (placebo 2010–2014) | [`outputs/report/pacto20.md`](outputs/report/pacto20.md) |
| **3. A polarização se resolve?** | Episódios de polarização intensa terminam por conflito, cesarismo, pacto ou despolarização? Onde está o Brasil? | 269 episódios em 95 países, 1900–2025; Brasil 1994–2026 | [`outputs/report/p3_relatorio.md`](outputs/report/p3_relatorio.md) |

Os planos de pesquisa que guiaram cada estudo estão em [`docs/planos/`](docs/planos/). As decisões de dados (fontes indisponíveis, alternativas adotadas, correções) estão registradas, em ordem cronológica, em [`outputs/pendencias.md`](outputs/pendencias.md).

**English summary.** Replication package for three studies on Brazil's "lulista pact" (the electoral base of Lula and the Workers' Party): (1) a municipal panel of presidential runoffs, 2006–2026, testing whether the party's territorial base shifted (poverty, religion, race, cash transfers); (2) a polling-station-level analysis, 2018–2026 with 2010–2014 placebos, linking each station to its 2022 Census surroundings to test a young, Black, urban "pact 2.0"; (3) a comparative study of 269 episodes of intense political polarization in 95 countries (V-Dem, 1900–2025), coding how they ended (victory of one pole, Caesarism, pact, depolarization) and placing Brazil's current episode in that distribution. All data are downloaded from official sources by the scripts in `src/ingest/`; a single command (`python -m src.pipeline`) rebuilds every table and figure. Texts are in Portuguese.

---

## Estrutura

```
pacto-lulista/
├── README.md, LICENSE, CITATION.cff, .zenodo.json, CHANGELOG.md
├── pyproject.toml, requirements.txt   # dependências (faixas e versões exatas)
├── config.yaml                        # anos, caminhos, candidatos, AMCs, limiares
├── docs/planos/                       # planos de pesquisa dos três estudos
├── src/
│   ├── pipeline.py                    # reprodução completa, na ordem de execução
│   ├── manifesto.py                   # SHA-256 dos dados (data/manifesto_dados.csv)
│   ├── ingest/                        # um script por fonte; todo download é feito aqui
│   ├── build_panel.py, groups.py, descriptives.py, models.py, spatial.py, robustness.py, mapas.py,
│   │   coortes.py, coortes_tse.py     # estudo 1
│   ├── pacto20_*.py                   # estudo 2
│   └── p3_*.py                        # estudo 3
├── tests/                             # checks de cada fase (pytest)
├── data/
│   ├── manual/                        # decisões manuais do autor (versionadas)
│   ├── manifesto_dados.csv            # tamanho e SHA-256 dos dados usados
│   └── raw/, interim/, processed/     # gerados pelos scripts (fora do git)
└── outputs/
    ├── tables/                        # CSV + Markdown de todas as tabelas
    ├── figures/                       # PNG 300 dpi + SVG
    ├── report/                        # relatórios (superadas/: notas parciais substituídas)
    └── pendencias.md                  # registro de decisões e fontes indisponíveis
```

## Como reproduzir

**Ambiente.** Python 3.11+ (a execução publicada usou Python 3.13.7 no Windows 11).

```bash
python -m venv .venv
.venv/Scripts/activate            # Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
```

**Execução.** Um comando refaz tudo, das descargas às figuras:

```bash
python -m src.pipeline --listar           # as 46 etapas, com o comando de cada uma
python -m src.pipeline --testes           # tudo + pytest ao fim
python -m src.pipeline --estudo 3         # só um estudo (o 2 e o 3 usam o painel e a malha do estudo 1)
python -m src.pipeline --sem-rede         # sem downloads, com data/raw/ já preenchido
python -m src.pipeline --a-partir-de 2.05 # retoma de uma etapa
python -m src.manifesto --conferir        # compara os dados baixados com os da publicação
```

**Custo.** Cerca de 22 GB em `data/raw/` (16 GB só dos arquivos do TSE por seção; 6.642 arquivos no manifesto) e algumas horas de execução. As etapas mais longas são o entorno censitário dos locais de votação (~80 min para 2018–2026 e ~55 min para 2010–2014) e os downloads.

**Determinismo.** Bootstraps e permutações usam sementes fixas. As fontes oficiais republicam arquivos com correções. Se `src.manifesto --conferir` acusar diferença, os resultados podem mudar marginalmente. Os arquivos usados na publicação foram baixados entre 25 e 28/10/2026.

**Testes.** `pytest tests/` verifica cada fase: totais que batem com as fontes, ausência de duplicatas, faixas plausíveis, coerência entre tabelas e existência das figuras. Testes de fases não rodadas são pulados.

## Fontes de dados

Todas são públicas e baixadas por script. Datas de acesso e versões estão nas docstrings de `src/ingest/` e em `outputs/pendencias.md`.

| Fonte | Uso | Estudos |
|---|---|---|
| TSE, Dados Abertos (CDN `cdn.tse.jus.br/estatistica/sead/odsele`) | Resultados por município e zona (1994–2026), por seção, locais de votação, perfil do eleitorado, comparecimento por idade e sexo | 1, 2, 3 |
| TSE, Portal Resultados | 2º turno presidencial de 2026 (não publicado no CDN quando o painel foi montado) | 1, 2, 3 |
| IBGE (SIDRA, API de localidades, FTP do Censo 2022, `geobr`) | População, PIB, Censo 2010/2022 (raça, religião, trabalho, idade), setores censitários 2022, malhas | 1, 2 |
| INEP | Ideb | 1 |
| Ipeadata | Bolsa Família, IDHM (Atlas do Desenvolvimento Humano) | 1 |
| Comex Stat (MDIC) | Exportações por município | 1 |
| V-Dem v16 e ERT v16 (repositórios oficiais `vdeminstitute/vdemdata` e `vdeminstitute/ERT`) | Polarização, regimes, golpes (Powell e Thyne), guerra civil | 3 |
| UCDP/PRIO Armed Conflict Dataset v25.1 | Conflitos internos, 1946–2024 | 3 |
| Archigos 4.1 | Entradas e saídas irregulares de líderes, 1875–2015 | 3 |

**Indisponíveis e alternativas adotadas.**

| Fonte | Problema | Alternativa adotada |
|---|---|---|
| DATASUS (TabNet) | Bloqueia acesso automatizado | Não contornado; indicadores de saúde fora do estudo 1 |
| RAIS | Indisponível | Variáveis de trabalho do Censo |
| Powell e Thyne, site original | HTTP 403 | Mesmos dados embutidos no V-Dem |
| Correlates of War | Falha de TLS | `e_civil_war` do V-Dem e UCDP |
| TSE 1989 | Ausente do CDN | Série do estudo 3 começa em 1994 |

## Decisões manuais

O estudo 3 envolve julgamento histórico. Essas decisões ficam versionadas em `data/manual/`, e os scripts nunca as sobrescrevem:

- `p3_revisao_usuario.csv`: códigos de desfecho revisados pelo autor (50 episódios); nos demais vale o pré-código automático das bases;
- `p3_exclusoes.csv`: episódios excluídos por desfecho de invasão externa (França 1934–1940, Ucrânia 2020–2022);
- `p3_subtipos_usuario.csv`: correção do tipo de ruptura onde as bases não registram o evento (Espanha 1936).

## Limitações principais

- Todos os resultados são **ecológicos** (municípios, locais de votação, países), não individuais.
- No estudo 2, raça e renda vêm do entorno censitário do local, não do eleitor.
- No estudo 3, a polarização é a medida de especialistas do V-Dem (`v2cacamps`), sujeita a viés retrospectivo, e não polarização afetiva individual.
- O exercício sobre o Brasil no estudo 3 é condicional ao modelo; não é previsão.

Cada relatório detalha suas limitações.

## Citação e licença

Código e textos sob licença MIT (ver `LICENSE`). Para citar:

> Silva, Paulo Roberto (2026). *O pacto lulista mudou de perfil? Painel municipal, locais de votação e episódios de polarização comparados (Brasil, 1994–2026; mundo, 1900–2025)*, versão 1.0.0. Zenodo. https://doi.org/10.5281/zenodo.23735410

Os metadados completos estão em `CITATION.cff`.
