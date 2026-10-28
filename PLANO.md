# Plano de pesquisa — O "pacto lulista" mudou de perfil? (2010–2026)

> Arquivo-guia para execução no VSCode via Claude Code. Sugestão: salvar na raiz do repositório como `PLANO.md` e referenciá-lo no `CLAUDE.md` ("siga PLANO.md fase a fase; não avance de fase sem validar os checks da fase anterior").

---

## 0. Pergunta, hipótese e enquadramento

**Pergunta.** A base territorial do voto petista no 2º turno presidencial, que André Singer descreveu como o realinhamento lulista da primeira década do século XXI (subproletariado, Nordeste, municípios pobres e dependentes de transferências), se manteve, se deslocou ou se dissolveu entre 2010 e 2026?

**Disputas de 2º turno analisadas**

| Ano | Candidato PT | Opositor | Partido antipetista (presidente e Câmara) |
|---|---|---|---|
| 2006 | Lula | Geraldo Alckmin | PSDB |
| 2010 | Dilma Rousseff | José Serra | PSDB |
| 2014 | Dilma Rousseff | Aécio Neves | PSDB |
| 2018 | Fernando Haddad | Jair Bolsonaro | PSL |
| 2022 | Lula | Jair Bolsonaro | PL |
| 2026 | Lula | Flávio Bolsonaro | PL |

Além do 2º turno presidencial, cada eleição inclui o **voto para deputado federal** (nominal + legenda) do PT e do partido antipetista da tabela (ver seção 1A).

Âncora recomendada: incluir **2006** (Lula × Alckmin) como linha de base, porque é a eleição do realinhamento na tese de Singer. 2002 é opcional (pré-realinhamento, contraste).

**Hipóteses operacionais**

- **H1 — Persistência do pacto.** A associação entre voto PT e pobreza (CadÚnico, renda do trabalho, IDHM, mortalidade infantil) mantém sinal e magnitude entre 2010 e 2026.
- **H2 — Clivagem religiosa.** O peso dos evangélicos na explicação do voto anti-PT cresce ao longo do período, líquido de renda e região.
- **H3 — Clivagem produtiva.** Municípios com VAB agropecuário alto e pauta exportadora de commodities migram contra o PT; municípios de serviços/administração pública migram a favor ou ficam estáveis.
- **H4 — Recomposição urbana/racial.** O PT ganha em municípios grandes, metropolitanos e com maior % de população negra fora do Nordeste, sugerindo uma base menos regional e mais racial/urbana.
- **H5 — Lulismo × petismo.** Singer distingue o lulismo, base eleitoral do líder, do petismo, a identificação partidária. Se o pacto é lulista e não petista, o hiato entre o voto presidencial do PT e o voto do PT para a Câmara deve ser maior justamente nos municípios pobres do pacto. Já a base proporcional do PT deve se parecer mais com o perfil da "velha" base petista (urbana, sindical, Sul/Sudeste). O teste é ver se esse hiato encolhe ou cresce entre 2006 e 2026.
- **H6 — Enraizamento do antipetismo.** Se a migração para o bolsonarismo é partidária e não só presidencial, os municípios em que o opositor cresceu no 2º turno também devem mostrar o PSL/PL como mais votado na proporcional a partir de 2018. O PSDB de 2006–2014 deve ter tido um enraizamento proporcional mais fraco nesses mesmos municípios.
- **H0 de mudança de perfil.** "O pacto mudou" = coeficientes padronizados das variáveis de pobreza caem e os de religião/estrutura produtiva/tamanho sobem de forma estatisticamente distinguível entre 2010 e 2026.

---

## 1. Decisão de desenho crítica: o 2º turno é soma zero

Em votos válidos, "PT cresceu" e "opositor cresceu" são o **mesmo evento com sinal trocado**. Para que os dois grupos signifiquem algo distinto, usar três operacionalizações em paralelo:

1. **Swing relativo (principal).** `swing_m = (s_PT,m,2026 − s_PT,m,2010) − (s_PT,BR,2026 − s_PT,BR,2010)`, onde `s` = % de votos válidos. Remove a maré nacional. Grupos:
   - **G_PT**: swing ≥ +1 desvio-padrão (ou quintil superior)
   - **G_OP**: swing ≤ −1 desvio-padrão (ou quintil inferior)
   - **G_EST**: faixa central (grupo de controle)
2. **Votos sobre o eleitorado apto.** `e_PT = votos_PT / aptos`, `e_OP = votos_OP / aptos`. Aqui ambos podem crescer (queda de abstenção/nulos) ou cair. Tipologia 2×2: PT↑OP↓, PT↓OP↑, ambos↑, ambos↓.
3. **Trajetória completa.** Vetor `(s_2010, s_2014, s_2018, s_2022, s_2026)` por município → clusterização (k-means em séries padronizadas ou modelos de trajetória por grupo, `tslearn`/`sklearn`). Identifica padrões como "PT forte e estável", "erosão contínua", "queda em 2018 e recuperação".

Todos os resultados devem ser reportados nas três versões; conclusões só valem se robustas a pelo menos duas.

---

## 1A. Voto proporcional (deputado federal)

**Variáveis por município × eleição (2006, 2010, 2014, 2018, 2022, 2026)**

- `p_PT` = (votos nominais em candidatos do PT + votos de legenda 13) / votos válidos para deputado federal (nominais + legenda de todos os partidos; excluir brancos e nulos).
- `p_ANTI` = mesma conta para o partido antipetista do ano: PSDB (45) em 2006–2014, PSL (17) em 2018, PL (22) em 2022–2026.
- `leg_PT`, `leg_ANTI` = só votos de legenda / válidos. Funciona como proxy de identificação partidária, menos contaminada por candidatos locais.
- `rank_PT`, `rank_ANTI` = posição de cada partido no município.
- `margem_PT` = p_PT − p do segundo colocado (negativa se o PT não lidera).
- `NEP` = número efetivo de partidos (Laakso-Taagepera) na votação para a Câmara. É controle obrigatório: em municípios muito fragmentados, ser "mais votado" com 15% significa pouco.
- `hiato_lulista` = s_PT (presidente, 2º turno, % válidos) − p_PT (Câmara). É a medida operacional de H5.
- `hiato_anti` = s_OP − p_ANTI. Mede o quanto o candidato opositor se descola do próprio partido.

**Federações (2022 e 2026).** O PT integra a Federação Brasil da Esperança (PT, PCdoB, PV). Do lado antipetista, o partido de referência em 2022 e 2026 é o PL, que concorreu sem federação em 2022. Para 2026, verificar no TSE se o PL integrou alguma federação. Calcular duas versões para o PT (e para o PL, se houver federação em 2026):

- **(a) só o partido** (principal, comparável com 2006–2018);
- **(b) a federação inteira** (robustez).

Antes de calcular, conferir como o TSE atribui os votos de legenda dentro das federações e registrar em `pendencias.md` se houver ambiguidade.

**Grupos proporcionais por eleição**

- **P_PT**: PT foi o partido mais votado para deputado federal.
- **P_ANTI**: o partido antipetista do ano foi o mais votado.
- **P_OUTRO**: outro partido liderou. É o caso típico do MDB/PSD/PP no interior, um grupo relevante por si: são os municípios onde nenhum dos polos se enraizou.
- Variante com limiar: "destacou-se" = mais votado **e** margem ≥ 5 p.p., ou p ≥ percentil 80 da distribuição nacional do partido naquele ano. Reportar as duas definições.

**Trajetórias proporcionais.** Para cada município, contar em quantas das 6 eleições o PT e o antipetista lideraram. Classificar em:

- **enraizado PT** (≥ 4 de 6);
- **enraizado anti** (PSDB → PSL/PL);
- **migrante PT → anti**, ou o inverso;
- **nunca polarizado**.

**Cruzamento com o presidencial.** Matriz grupo presidencial (G_PT/G_EST/G_OP) × grupo proporcional (P_PT/P_ANTI/P_OUTRO) em 2010 e em 2026. As células fora da diagonal são as mais informativas:

- **"Lula sem PT"**: G_PT com P_OUTRO ou P_ANTI. É o lulismo puro.
- **"bolsonarismo sem PL"**: G_OP com P_OUTRO.

**Fontes.** TSE: `votacao_partido_munzona` (traz votos nominais e de legenda por partido) e `votacao_candidato_munzona`. Via Base dos Dados: `br_tse_eleicoes.resultados_partido_municipio` e `resultados_candidato_municipio`.

**Checks.**
- O total nacional de votos válidos para deputado federal e a votação nacional de PT e antipetista batem com o TSE.
- Soma de nominais + legenda = válidos em cada município.

---

## 2. Unidade de análise e compatibilização territorial

- Unidade: município (5.570). Excluir votos do exterior e em trânsito.
- **Crosswalk TSE ↔ IBGE**: o TSE usa código próprio. Usar o diretório de municípios da Base dos Dados (`br_bd_diretorios_brasil.municipio`, colunas `id_municipio` e `id_municipio_tse`).
- Municípios instalados em 2013 (Mojuí dos Campos/PA, Pescaria Brava/SC, Balneário Rincão/SC, Pinto Bandeira/RS, Paraíso das Águas/MS) não existiam em 2010: usar **Áreas Mínimas Comparáveis (AMC)** agregando-os ao município-mãe, ou excluí-los e documentar.
- Ponderação: análises descritivas reportadas com e sem peso do eleitorado apto; regressões com peso por eleitorado como especificação principal.

---

## 3. Fontes e disponibilidade por indicador

| Indicador | Fonte | Anos com dado municipal | Acesso | Cuidados |
|---|---|---|---|---|
| Votação 2º turno | TSE Dados Abertos | 2006–2022; 2026 | `basedosdados` (`br_tse_eleicoes.resultados_candidato_municipio`) ou CDN TSE | 2026: arquivos consolidados podem demorar semanas após 25/10; fallback = JSON do Portal Resultados. Validar totais nacionais. |
| Eleitorado apto, abstenção, brancos/nulos | TSE | idem | `br_tse_eleicoes.detalhes_votacao_municipio` | Necessário para operacionalização 2. |
| População | IBGE: Censos 2010/2022 + estimativas anuais | anual | SIDRA (tabelas 6579, 9514) / `br_ibge_populacao` | Estimativas pós-2022 foram rebaseadas; usar série única coerente. |
| % população negra (pretos + pardos) | Censo 2010 e 2022 | 2010, 2022 | SIDRA 3175 (2010), 9605 (2022) | Só 2 pontos; tratar como variação intercensitária. |
| Balança comercial | Comex Stat (MDIC/SECEX) | 1997–2025 | API Comex Stat / `br_me_comex_stat.municipio_exportacao` e `_importacao` | **Município = domicílio fiscal da empresa**, não local de produção (viés de sede). Calcular exportações per capita, saldo, % commodities (SH 01–27 + minérios) e índice de concentração HHI. |
| PIB municipal pela ótica da oferta | IBGE — PIB dos Municípios | 2002–2023 (último disponível) | SIDRA 5938 / `br_ibge_pib.municipio` | VAB agro, indústria, serviços, administração pública; usar **participações** e VAB per capita a preços constantes (deflator implícito UF). |
| IDHM | Atlas Brasil (PNUD/Ipea/FJP) | 1991, 2000, 2010 | download Atlas Brasil | Não há IDHM municipal pós-2010 consolidado. Verificar se saiu edição com Censo 2022; se não, usar **IFDM (Firjan)** como proxy anual e reconstruir componentes do IDHM com Censo 2022 (escolaridade, renda domiciliar). |
| Renda média do trabalho | RAIS (formal) + Censo (todas as ocupações) | RAIS anual; Censo 2010/2022 | `br_me_rais.microdados_vinculos` (agregar) | RAIS cobre só formais — viés grave em municípios pobres. Reportar as duas fontes. Deflacionar pelo IPCA. |
| Ideb | INEP | 2005–2023 bienal (2025 se divulgado) | `br_inep_ideb.municipio` | Usar anos iniciais da rede pública como principal; muitos missings em municípios pequenos. |
| Mortalidade infantil | DATASUS: SIM (óbitos < 1 ano) + SINASC (nascidos vivos) | anual | `br_ms_sim`, `br_ms_sinasc` ou PySUS | Instabilidade em municípios pequenos: médias trienais + suavização Bayesiana empírica. |
| % população no CadÚnico | MDS — VIS Data / CECAD | ~2012 em diante (série municipal) | VIS Data (download CSV) | Para 2010, usar famílias beneficiárias do Bolsa Família como proxy. Denominador = população estimada. Distinguir % cadastrados e % beneficiários. |
| Religião | Censo 2010 e 2022 | 2010, 2022 | SIDRA 137 (2010) e tabelas de religião do Censo 2022 | Agregar: católicos, evangélicos (total, pentecostais quando possível), sem religião, outras. |
| Taxa de homicídios | DATASUS SIM (CID-10 X85–Y09, Y35–Y36) / Atlas da Violência (Ipea) | anual | `br_ms_sim` | Por 100 mil hab., médias trienais; considerar mortes por intervenção legal separadamente. Local de **ocorrência** vs **residência**: usar residência. |

**Alinhamento temporal.** Definir para cada eleição *t* os covariáveis no ano mais próximo anterior disponível (ex.: eleição 2026 ↔ PIB 2023, CadÚnico 2025, homicídios 2022–2024). Indicadores censitários: 2010 para eleições 2010/2014; 2022 para 2022/2026; interpolação linear para 2018 apenas em análises descritivas, nunca em regressões.

---

## 4. Estrutura do repositório

```
pacto-lulista/
├── CLAUDE.md                # instruções curtas + ponteiro para PLANO.md
├── PLANO.md                 # este arquivo
├── pyproject.toml           # dependências
├── config.yaml              # anos, caminhos, billing project GCP, limiares de grupos
├── data/
│   ├── raw/                 # downloads intocados (gitignored)
│   ├── interim/             # limpos por fonte
│   └── processed/           # painel_municipal.parquet
├── src/
│   ├── ingest/              # 1 script por fonte (tse.py, ibge_pop.py, comex.py, ...)
│   ├── build_panel.py       # junta tudo por id_municipio × ano
│   ├── groups.py            # swing, tipologia 2x2, clusters de trajetória
│   ├── descriptives.py
│   ├── models.py
│   └── spatial.py
├── notebooks/               # só exploração; nada de lógica de produção
├── outputs/
│   ├── figures/
│   ├── tables/
│   └── report/
└── tests/                   # checks de integridade
```

**Stack:** Python 3.11+, `pandas`, `pyarrow`, `basedosdados` (requer projeto GCP com billing — cota gratuita costuma bastar), `geobr` (malhas municipais), `geopandas`, `statsmodels`, `linearmodels`, `libpysal`/`esda`/`spreg` (espacial), `scikit-learn`, `tslearn`, `matplotlib`/`seaborn`, `pysus` (opcional).

---

## 5. Fases de execução

### Fase 1 — Votação (fundação)
1. Baixar 2º turno presidencial 2006, 2010, 2014, 2018, 2022, 2026 por município.
2. Calcular `s_PT` (válidos), `e_PT`, `e_OP` (aptos), abstenção, brancos+nulos.
3. Aplicar crosswalk TSE→IBGE e AMC.
4. **Checks:** totais nacionais por candidato batem com o TSE (tolerância 0,01 p.p.); 5.570 municípios (ou N de AMC) em todos os anos; sem duplicatas.

### Fase 1B — Votação proporcional
1. Baixar votação por partido e por candidato para deputado federal, 2006–2026.
2. Calcular as variáveis da seção 1A, nas versões partido e federação.
3. Para diagnosticar puxadores locais: identificar, por município, o candidato mais votado do PT e do antipetista e a fração do partido que ele concentra. Marcar `dependencia_puxador` quando essa fração for ≥ 50%.
4. Rodar os checks da seção 1A.

### Fase 2 — Grupos
1. Calcular swing relativo 2010→2026 e classificar G_PT / G_EST / G_OP.
2. Tipologia 2×2 sobre aptos.
3. Clusters de trajetória (testar k = 3–6; escolher por silhueta + interpretabilidade).
4. Grupos proporcionais P_PT / P_ANTI / P_OUTRO por eleição e trajetórias proporcionais (seção 1A).
5. Mapas (`geobr`) de todos os esquemas; tabela de concordância entre esquemas; matriz presidencial × proporcional em 2010 e 2026.

### Fase 3 — Ingestão dos indicadores
Um script por fonte em `src/ingest/`, cada um salvando `data/interim/<fonte>.parquet` com `id_municipio`, `ano`, variáveis. Cada script deve: logar N de municípios e % de missing por ano; deflacionar valores monetários (IPCA, base dez/2025); documentar a tabela/consulta exata usada em docstring.

### Fase 4 — Painel
`build_panel.py` gera `painel_municipal.parquet` (município × ano) e `painel_eleicoes.parquet` (município × eleição, com covariáveis alinhadas conforme seção 3). Gerar dicionário de variáveis em `outputs/tables/dicionario.csv`.

### Fase 5 — Análise descritiva das trajetórias
Para cada grupo (G_PT, G_EST, G_OP e clusters):
- Mediana e intervalo interquartil de cada indicador por ano (gráficos de linha, uma faceta por indicador).
- Diferença de trajetórias: Δ indicador 2010→último ano, por grupo, com teste de diferença (bootstrap).
- Perfil inicial (2010) vs perfil final: onde estavam os municípios que se moveram?
- Quebrar por macrorregião (o Nordeste domina o voto PT; sem esse corte os resultados confundem região com perfil).
- Repetir todo o bloco para os grupos proporcionais (P_PT, P_ANTI, P_OUTRO) **em cada eleição**. Pergunta-guia: o perfil médio dos municípios P_PT em 2026 se parece mais com o dos P_PT de 2006 ou com o dos G_PT presidenciais?
- Perfil das células fora da diagonal da matriz presidencial × proporcional ("Lula sem PT", "bolsonarismo sem PL").
- Comparar o perfil P_ANTI-PSDB (2006–2014) com o P_ANTI-PSL/PL (2018–2026). Isso mostra se o antipetismo proporcional trocou de base social e não só de partido.

### Fase 6 — Modelos
1. **Coeficientes ao longo do tempo (teste central de H0/H1).** Para cada eleição t:
   `s_PT,m,t = α_UF + β_t · X_m,t + ε`
   com X padronizado (z-score dentro de cada ano). Plotar β_t de 2006 a 2026 com IC 95%. O pacto "mudou de perfil" se os β de pobreza encolhem e os de religião/estrutura produtiva crescem — testar igualdade de coeficientes entre 2010 e 2026 com modelo empilhado e interações `X × ano`.
2. **Diferenças longas.** `swing_m = α_UF + γ · X_m,2010 + δ · ΔX_m + ε`: o que explica o deslocamento — o ponto de partida (níveis 2010) ou a mudança (Δ)?
3. **Pertencimento a grupo.** Logit multinomial G_PT / G_EST / G_OP sobre X_2010 e ΔX.
4. **Decomposição composição × comportamento.** Oaxaca-Blinder do voto PT médio 2010 vs 2026: quanto da mudança vem de os municípios terem mudado de perfil (ΔX) e quanto de o mesmo perfil passar a votar diferente (Δβ). Esta é a forma mais direta de responder "o pacto mudou ou o Brasil mudou?".
5. **Voto proporcional.**
   - Repetir o modelo 1 com `p_PT` e `p_ANTI` como dependentes. Comparar os β_t presidenciais com os β_t proporcionais: perfis divergentes indicam lulismo descolado do petismo.
   - Modelo para o `hiato_lulista`: `hiato_m,t = α_UF + θ_t · X_m,t + λ · NEP_m,t + ε`. Se H5 vale, os θ de pobreza e CadÚnico são positivos. A mudança de θ entre 2006 e 2026 indica se o lulismo se "petizou" ou se descolou ainda mais.
   - Logit multinomial de P_PT / P_ANTI / P_OUTRO sobre X, por eleição, controlando NEP e `dependencia_puxador`.
6. **Exploratório (opcional).** Gradient boosting + SHAP para detectar não linearidades e interações (ex.: evangélicos × renda). Só para gerar hipóteses, não para inferência.

### Fase 7 — Espacial e robustez
- Moran's I global dos resíduos; LISA dos swings.
- Reestimar modelos centrais com erro espacial (SEM) ou lag espacial (SAR) via `spreg`; erros-padrão Conley como alternativa.
- Robustez: (a) limiares alternativos de grupo (±0,5 DP, quintis, tercis); (b) sem ponderação; (c) excluindo capitais; (d) excluindo municípios < 5 mil hab.; (e) 2006 em vez de 2010 como base; (f) 2022 em vez de 2026 como ponto final (verifica se 2026 é ponto fora da curva); (g) voto proporcional por federação em vez de partido; (h) excluindo municípios com `dependencia_puxador`; (i) só voto de legenda em vez de nominal + legenda.

### Fase 8 — Relatório
`outputs/report/relatorio.md` com: resumo executivo; mapas dos grupos; painel de trajetórias; gráfico de β_t; tabela de decomposição; seção de limitações. Cada figura com fonte e ano dos dados no rodapé.

---

## 6. Limitações a declarar desde o início

- **Falácia ecológica:** os resultados descrevem municípios, não eleitores. Não afirmar que "evangélicos votaram em X"; afirmar que "municípios com maior % de evangélicos deslocaram-se para X". Complementar, se possível, com microdados de surveys (ESEB 2010, 2014, 2018, 2022).
- **Mudança do opositor:** de PSDB (2010/2014) para bolsonarismo (2018–2026). Parte do "deslocamento" pode ser da oferta, não da base — isso é substantivo para a hipótese, não ruído.
- **Indicadores censitários com dois pontos** (raça, religião, IDHM): só permitem variação 2010→2022.
- **Comex Stat** mede domicílio fiscal; **RAIS** mede emprego formal; **mortalidade e homicídios** são instáveis em municípios pequenos.
- **Voto proporcional é fragmentado e personalista.** Um candidato com base local pode fazer de qualquer partido o "mais votado" num município. Por isso o NEP, o voto de legenda e o diagnóstico de puxadores entram como controles obrigatórios.
- **O antipetismo proporcional mudou de partido três vezes** (PSDB → PSL → PL). Na versão principal, a comparação é sempre com o partido do candidato presidencial opositor. A versão alternativa soma os partidos do campo antipetista de cada ano (ex.: PL + Novo + União em 2022/2026) e deve ser tratada só como robustez.
- **Defasagem do PIB municipal:** o último ano disponível é anterior à eleição de 2026.

---

## 7. Instruções de trabalho para o Claude Code

- Executar uma fase por vez; ao final de cada uma, rodar `pytest tests/` e mostrar os checks antes de seguir.
- Nunca editar `data/raw/`. Todo download deve ser reproduzível por script.
- Antes de usar qualquer tabela SIDRA ou da Base dos Dados, confirmar nome/ID atual da tabela (IDs mudam) e registrar no docstring.
- Se uma fonte estiver indisponível (ex.: dados de 2026 ainda não consolidados, IDHM 2022 inexistente), parar, registrar em `outputs/pendencias.md` e propor o fallback descrito na seção 3, sem inventar dados.
- Figuras em PNG 300 dpi e SVG; tabelas em CSV e Markdown.
- Comentários e textos de saída em português.