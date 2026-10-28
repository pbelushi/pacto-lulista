# Pendências e decisões de fonte

## Fase 1 — votação presidencial

### 2026: 2º turno ausente do CDN de Dados Abertos (27/10/2026)
- `votacao_candidato_munzona_2026.zip` e `detalhe_votacao_munzona_2026.zip` foram gerados em 25/10/2026, por volta de 12h30 (horário de Brasília), antes do fim da votação, e só têm o 1º turno.
- **Fallback adotado** (PLANO.md, seção 3): JSON do Portal Resultados, eleição 6258 (federal, 2º turno), um arquivo por município (`src/ingest/tse_portal.py`). Todos os arquivos estão 100% totalizados (`s.st == s.ts`).
- **Ação:** quando o TSE republicar os arquivos de 2026 com o 2º turno, rodar de novo `python -m src.ingest.tse_download` e `python -m src.ingest.tse`. O código detecta o 2º turno no CDN e passa a usá-lo automaticamente. Depois, comparar com a versão do portal.

### Voto em trânsito
- O PLANO pede excluir o voto em trânsito. Só em **2010 e 2014** os arquivos `*_munzona` marcam as seções de trânsito (`ST_VOTO_EM_TRANSITO = 'S'`), e lá elas foram excluídas. Em 2006, 2018 e 2022 a flag é sempre `N`. Nesses anos, e em 2026 (portal), o voto em trânsito fica contado no município onde foi dado e não dá para separá-lo.
- O efeito somado de excluir exterior e trânsito sobre o s_PT nacional é de no máximo 0,05 p.p. (2006 +0,006; 2010 +0,014; 2014 +0,052; 2018 +0,028; 2022 −0,001; 2026 −0,006). O impacto do trânsito se concentra nas capitais. Mesmo assim, é uma inconsistência entre anos a lembrar ao interpretar os swings das capitais (robustez (c), "excluindo capitais").

### Votos nulos
- `nulos` = `QT_VOTOS_NULOS` + `QT_VOTOS_NULOS_TECNICOS` + `QT_VOTOS_ANULADOS_APU_SEP`. Em 2006, o campo `QT_TOTAL_VOTOS_NULOS` do TSE fica 18.645 votos abaixo da soma dos componentes e não fecha a identidade comparecimento = válidos + brancos + nulos. Em 2010, Monte Carmelo/MG teve 272 votos anulados em apuração separada.

### Crosswalk TSE → IBGE
- Usado o config de municípios do Portal Resultados 2026 (`mun-e006258-cm.json`, campos `cd` = código TSE e `cdi` = código IBGE), no lugar de `br_bd_diretorios_brasil.municipio` (não há projeto GCP configurado para a Base dos Dados).

### AMC
- Municípios instalados depois de 2010 foram agregados ao município-mãe (config.yaml, chave `amc`). Isso inclui Boa Esperança do Norte/MT (5101837), instalado em 2025, além dos cinco de 2013.
- Paraíso das Águas/MS foi desmembrado de Costa Rica, Água Clara e Chapadão do Sul, e Boa Esperança do Norte/MT de Sorriso e Nova Ubiratã. Os dois foram atribuídos só ao município-mãe principal (Costa Rica e Sorriso). Isso é uma aproximação: uma AMC exata juntaria todos os municípios de origem.

## Fase 1B — voto proporcional (deputado federal)

### Denominador dos válidos
- Válidos = `QT_VOTOS_NOMINAIS_VALIDOS` + `QT_TOTAL_VOTOS_LEG_VALIDOS`, ambos do arquivo de detalhe. Em 2006–2014, o campo `QT_TOTAL_VOTOS_VALIDOS` desse arquivo traz **só os nominais** e não pode ser usado como total de válidos.
- **2006:** o arquivo de partido tem 154.179 votos de legenda a menos que o de detalhe (0,16% dos válidos; até 3,9% dos válidos em um município). O detalhe fecha a identidade comparecimento = válidos + brancos + nulos, e o arquivo de partido não. Por isso o denominador vem do detalhe, e esses votos de legenda ficam sem partido atribuído: as shares dos partidos somam um pouco menos de 100%.
- **2018:** o arquivo de partido tem 7.048 votos de legenda a mais que o de detalhe, todos no Amazonas (62 municípios, até 1,1% dos válidos). Mesmo tratamento.
- 2010, 2014, 2022 e 2026 batem exatamente, município a município.

### Votos de legenda
- `p_PT`/`p_ANTI` usam nominais + legenda total. Desde 2018, a legenda total inclui os votos nominais de candidatos indeferidos que foram convertidos em legenda. Exemplo: em 2018, 124.647 votos de um candidato do PT na Bahia.
- `leg_PT`/`leg_ANTI` usam só a legenda digitada (`QT_VOTOS_LEGENDA_VALIDOS`), que é o proxy de identificação partidária.

### Federações
- PT: Federação Brasil da Esperança (PT, PCdoB, PV). O número da federação é 2 em 2022 e 101 em 2026.
- **PL em 2026: sem federação** (`NR_FEDERACAO = -1`). A versão `federacao` do antipetista é igual à versão `partido` em todos os anos.
- Atribuição da legenda dentro das federações: o TSE registra o voto de legenda no número do partido digitado (13, 65, 43), então **não há ambiguidade**.
- Na versão `federacao`, todas as federações viram uma unidade (por exemplo, PSDB/Cidadania), o que também muda o líder, as posições e o NEP de outros partidos.

### Checks com fonte independente
- 2026: válidos, PT e PL por UF batem exatamente com o Portal Resultados (eleição 6259, cargo c0006, campos `tvtn` + `tval`). O campo `tvan` inclui votos de candidatos anulados *sub judice* e não deve ser usado.
- 2006–2018: share nacional do PT comparado com uma referência aproximada (0,1 p.p.) **escrita de memória**, não baixada do TSE: 15,0 / 16,9 / 14,0 / 10,3%. Os valores calculados (14,92 / 16,86 / 13,92 / 10,31%) ficam dentro de 0,1 p.p. **A confirmar** com as estatísticas oficiais do TSE. Para 2022 não há referência independente disponível (o portal de 2022 foi retirado do ar). O check interno partido × candidato bate exatamente em todos os anos.

### Puxadores e empates
- `dependencia_puxador` (fração ≥ 50%) vale para cerca de metade dos municípios em todos os anos (PT de 43% a 57%), porque em municípios pequenos um único candidato concentra os votos do partido com facilidade. É um controle bruto. Na Fase 7 vale testar também um limiar mais alto ou exigir um mínimo de votos do partido.
- De 2 a 6 municípios por ano têm empate exato no 1º lugar (`empate_lider = True`). Nesses casos o líder é escolhido de forma arbitrária, e eles devem ser excluídos dos grupos P_*.

## Fase 2 — grupos

### Swing relativo
- Os grupos de swing são **centrados em zero** (zero = acompanhou a maré nacional), com limiar de ±k vezes o DP **não ponderado** dos swings municipais (DP = 10,98 p.p.). A média não ponderada do swing é −1,44 p.p.: municípios pequenos se moveram, em média, um pouco mais contra o PT que o país. O PLANO não diz se o corte é em torno de 0 ou da média; escolhi 0 porque é a referência substantiva.
- Nas variantes por quantil, G_EST é tudo o que fica entre os extremos (Q2–Q4 nos quintis, T2 nos tercis).

### Tipologia 2×2
- A versão principal (`tipo_2x2`) usa a variação bruta de e_PT e e_OP. A variante `tipo_2x2_rel` desconta a variação nacional. Na bruta, "ambos↓" tem só 75 AMCs, porque o comparecimento subiu de 2010 para 2026.

### Clusters de trajetória: decisão de desenho
- O PLANO diz "k-means em séries padronizadas", o que é ambíguo. Implementei dois modos sobre o desvio em relação ao share nacional (d = s_m,t − s_BR,t, 2010–2026):
  - **nível** (d como está): com k = 3, a silhueta é a maior (0,46), mas os clusters só separam PT forte / intermediário / PT fraco. A concordância com os grupos de swing é baixa (V de Cramér = 0,26).
  - **forma** (d centrado na média de cada município): separa o formato da trajetória. A concordância com o swing é maior (V = 0,51).
- **k escolhido para forma = 4**, e não 3, embora a silhueta de 3 seja marginalmente maior (0,289 contra 0,286). Com k = 4 aparecem quatro padrões distintos: ganho até 2018 e recuo parcial; antipetista estável; petista em declínio desde 2018; erosão contínua.
- **A confirmar pelo usuário:** os rótulos dos clusters (config.yaml, `grupos.rotulos_cluster`) são interpretações minhas dos centróides.
- `tslearn` não foi usado: com séries de tamanho igual e distância euclidiana, o `TimeSeriesKMeans` equivale ao `KMeans` do scikit-learn.

### Grupos proporcionais
- O PLANO pede duas definições. A variante com limiar foi separada em duas:
  - `g_prop_margem`: mais votado com margem ≥ 5 p.p.; os demais municípios ficam em P_NENHUM.
  - flags `destaque_p80_PT` e `destaque_p80_ANTI`: p ≥ percentil 80 do partido no ano. As duas flags não são exclusivas, porque PT e antipetista podem estar ambos acima do P80.
- Trajetória proporcional: o PLANO não define "migrante". A regra adotada está no docstring de `src/groups.py`: liderou na fase inicial (2006–2014), o outro polo lidera na fase final (2022–2026) e o polo original não lidera mais. "Intermitente" é o resíduo e fica grande: 3.017 AMCs, 48% do eleitorado.

### Mapas
- Para desenho, a malha é simplificada (tolerância de 0,005°) e os polígonos vão rasterizados dentro do SVG, a 100 dpi; o PNG sai a 300 dpi. Os limites de UF vêm de `geobr.read_state` (2020), porque dissolver a malha municipal simplificada gera ~71 mil anéis internos espúrios. Resultado: SVGs de 1 a 4 MB, contra mais de 100 MB antes.
- A paleta vermelho (PT) / azul (opositor) / cinza (neutro) foi checada em Python com `colorspacious`: ΔE ≥ 25 entre as três cores em todos os tipos de daltonismo. O validador do skill de visualização não pôde rodar porque não há Node instalado.

## Fase 3 — indicadores (fontes leves)

### População (`src/ingest/ibge_pop.py`)
- As estimativas do IBGE (tabela 6579) não formam uma série única. Há um salto em 2013 e, depois de 2022, elas incorporam a correção de cobertura do Censo 2022: a estimativa de 2024 dá 212,6 milhões, contra 203,1 milhões contados no Censo 2022.
- Série coerente na base de contagem dos Censos:
  - Censos de 2000, 2010 e 2022;
  - interpolação geométrica nos anos entre Censos;
  - de 2023 a 2026, Censo 2022 × crescimento das estimativas.
- A estimativa original fica guardada em `pop_estimativa_ibge`.

### Raça e religião (`src/ingest/ibge_censo.py`)
- Raça: tabela SIDRA 9605, com os dois Censos e as mesmas categorias. Foi usada no lugar da 3175 indicada no PLANO.
- Religião: o Censo 2022 só divulgou religião para **pessoas de 10 anos ou mais** (tabela 9537). Para comparar, a religião de 2010 também foi restrita a 10+ (tabela 2103: total − 0 a 4 − 5 a 9).
- Pentecostais só existem em 2010. Em 2022 há apenas o total de evangélicos.

### PIB (`src/ingest/ibge_pib.py`)
- **O IBGE não publicou o VAB por atividade de 2022–2023**, nem no SIDRA (tabela 5938, valor `...`) nem na base do FTP: só o PIB total. O último VAB setorial é de **2021**. As participações setoriais das eleições de 2022 e 2026 vão usar 2021. PIB per capita real vai até 2023.
- Deflator: IPCA, média anual, em R$ de dez/2025 (`src/ingest/ipca.py`). Antes de aplicar, verifiquei (27/10/2026) que os valores do IBGE **não vêm deflacionados**:
  - todas as colunas monetárias da base do FTP e a tabela SIDRA 5938 dizem "a preços correntes";
  - o PIB Brasil nominal cresce 7,35× de 2002 a 2023, contra 3,51× do IPCA.
- Ressalva: deflacionado pelo IPCA, o PIB cresce 2,09× no período, mais que o crescimento em volume do PIB nacional (~1,6×), porque o deflator do PIB subiu mais que o IPCA. O IPCA mede poder de compra, e para comparar municípios entre si o que importa é a uniformidade do deflator. O IBGE não publica volume real por município.
- Bug corrigido: `pivot_table(aggfunc="sum")` transformava valores indisponíveis (`...`, `X`) em 0. Agora usa `aggfunc="first"`, que preserva o NaN.

### Ideb (`src/ingest/inep_ideb.py`)
- Anos iniciais, rede pública, 2005–2025. O MD5 do arquivo foi conferido. Missing por ano de 1,5% a 9,8%: municípios sem Ideb divulgado.

### DATASUS (`src/ingest/datasus.py`): PENDENTE
- O script está pronto (TabNet, SIM e SINASC por residência, taxas trienais e suavização Bayesiana empírica), mas **o TabNet passou a recusar as conexões do cliente Python** (`ConnectionResetError` em todas as tentativas por ~10 min). Uma consulta isolada funcionou antes: 32.238 óbitos infantis em 2022. O `curl` continua conectando.
- Mudar o User-Agent para contornar o bloqueio **foi negado** (contorno de bloqueio de bots) e não foi feito.
- Opções:
  - (a) **microdados oficiais do FTP do DATASUS** (`ftp.datasus.gov.br/dissemin/publicos/SIM` e `/SINASC`, arquivos .dbc por UF e ano). É o canal oficial de dados em massa, mais pesado (~GBs) e exige decodificar .dbc (`pyreaddbc`/PySUS).
  - (b) CSVs do OpenDataSUS.
  - (c) tentar o TabNet de novo mais tarde, com mais intervalo entre consultas.
- Dados de 2024–2025 são preliminares; 2026 não é usado.

### Correções nos dados do IBGE
- População: municípios instalados depois de 2000 (sem Censo 2000) são retroprojetados em 2001–2009 com a própria taxa de crescimento 2010–2022. Limitação: o Censo 2000 do município-mãe inclui o território desmembrado.
- Religião 2010: o resíduo `pct_outras_religioes` foi cortado em 0. Ficava até −0,07 p.p. em 28 municípios, por arredondamento da subtração de faixas etárias.
- Raça: incluída a categoria amarela. A soma das categorias fica entre 96% e 100%; o resto é "sem declaração".
- PIB: Guamaré/RN tem PIB negativo em 2012 nos dados do próprio IBGE. Foi mantido.

### Fontes indisponíveis em 27/10/2026
- **Comex Stat:** o certificado TLS de `balanca.economia.gov.br` **venceu em 03/10/2026**, e a API oficial (`api-comexstat.mdic.gov.br`) responde 503. Não baixei com a verificação de certificado desligada.
  Opções para o usuário:
  - (a) autorizar o download sem verificação TLS, conferindo depois os totais com a série nacional publicada;
  - (b) baixar manualmente pelo navegador os arquivos `EXP_COMPLETA_MUN.zip`, `IMP_COMPLETA_MUN.zip`, `EXP_2025_MUN.csv` e `IMP_2025_MUN.csv` e colocá-los em `data/raw/comex/`;
  - (c) esperar a API voltar.
- **CadÚnico / Bolsa Família:** as ferramentas de dados do MDS (SAGI `misocial`, VIS Data 3) redirecionam para `gov.br/mds/pt-br/avisos`, ou seja, estão fora do ar.
  Fallbacks:
  - (a) API do Portal da Transparência (Bolsa Família / Novo Bolsa Família por município). Exige uma chave gratuita, que o usuário cadastra.
  - (b) download manual do CECAD/VIS Data quando voltar.
  Sem fonte, sem dado: nada foi estimado.
- **IDHM com o Censo 2022:** não encontrei divulgação municipal. As páginas do Atlas Brasil para anos recentes usam a PNAD Contínua, que só vale para UFs. A página de downloads do Atlas é dinâmica e não expõe links diretos.
  Fallback do PLANO:
  - IDHM 2010 do Atlas, que exige download manual ou um link direto do usuário;
  - IFDM (Firjan) como proxy anual;
  - componentes reconstruídos com o Censo 2022 (escolaridade, renda domiciliar), a fazer.
- **RAIS:** adiada por decisão do usuário (sem GCP; microdados por FTP somam dezenas de GB).

## Fase 4 — painel

- Só entram as fontes do IBGE e do INEP (Ideb). Comex, DATASUS, CadÚnico, IDHM e RAIS ficam para depois, por decisão do usuário em 27/10/2026. Entram depois sem mudar a estrutura do painel.
- Alinhamento das covariáveis (config.yaml, `alinhamento`):

  | Eleição | PIB | VAB | Ideb | Censo |
  |---|---|---|---|---|
  | 2006 | 2005 | 2005 | 2005 | 2010 |
  | 2010 | 2009 | 2009 | 2009 | 2010 |
  | 2014 | 2013 | 2013 | 2013 | 2010 |
  | 2018 | 2017 | 2017 | 2017 | (só `_interp`) |
  | 2022 | 2021 | 2021 | 2021 | 2022 |
  | 2026 | 2023 | 2021 | 2025 | 2022 |

- **2006 usa o Censo 2010** para raça e religião, ou seja, um dado posterior à eleição. Isso fica marcado em `ano_ref_censo`. Para uma linha de base estrita em 2006, seria preciso ingerir o Censo 2000.
- **2018:** as colunas principais do Censo ficam vazias. As colunas `*_interp` (interpolação linear 2010–2022) servem só para análises descritivas, como pede o PLANO.
- Agregação em AMC:
  - percentuais do Censo ponderados pela população do município;
  - Ideb ponderado pela população. É uma aproximação: o certo seria ponderar pelas matrículas da rede pública.
- O Ideb de 2005, usado para a eleição de 2006, cobre 90% das AMCs; a partir de 2009, 99% ou mais.

## Fase 6 — modelos

- **Erros-padrão** agrupados por microrregião IBGE (558; `src/ingest/ibge_localidades.py`, API de localidades). O tratamento espacial completo (Conley, SAR/SEM) fica para a Fase 7.
- **Ideb ausente** (10% em 2006): z = 0 mais a dummy `ideb_ausente`, para manter a amostra constante entre os anos.
- **Spec. A** (com Censo) não inclui 2018: o PLANO proíbe interpolar o Censo em regressões. A **spec. B** (sem Censo) inclui 2018, mas sofre viés de variável omitida.
- **Logits multinomiais** usam dummies de macrorregião, não de UF: com UF há separação quase perfeita, porque várias UFs não têm G_PT.
- Em 2014 e 2022, a dummy `ideb_ausente` nunca ocorre em P_ANTI (separação). O otimizador passa de Newton para BFGS: a log-verossimilhança é a mesma, e o coeficiente da dummy não é identificado nem reportado.
- **Oaxaca-Blinder:** feito em unidades originais. As decomposições dependem da referência (β de 2010 ou de 2026), e as duas são reportadas. Dois componentes da composição exigem cautela:
  - Ideb: alta secular no país todo;
  - % negra: reclassificação racial entre os Censos.
- O passo 6 (gradient boosting + SHAP, opcional no PLANO) ainda não foi feito.

## Fase 7 — espacial e robustez

- **Vizinhança:** 8 vizinhos mais próximos pelos centroides (EPSG:5880), e não contiguidade, porque a malha simplificada do geobr tem frestas. Uma alternativa de robustez seria a contiguidade sobre a malha não simplificada (`simplified=False`, download maior).
- **spreg** (GM_Error_Het, GM_Lag) não aceita pesos: as versões espaciais são **sem ponderação**. Compare com a robustez (b). Nos modelos com lag espacial, os coeficientes são efeitos antes do multiplicador espacial; os impactos diretos e indiretos não foram calculados.
- **Conley:** implementado em `src/spatial.py` (kernel de Bartlett, 100 e 250 km, haversine), aplicado aos β por eleição. No modelo empilhado (Δβ), os erros seguem agrupados por microrregião.
- **Robustez (d):** "menos de 5 mil habitantes" usa a população de 2010 e exclui 1.301 AMCs.
- **Robustez (e) e (f):** os grupos G_PT/G_OP são recalculados a partir do novo swing (±1 DP).
- **Robustez (h):** exclui 3.868 AMCs (dependência de puxador na base ou no ano final). Com o limiar de 50% do PLANO, o teste é pouco informativo; sugestão: limiar maior ou mínimo de votos do partido.
- **Robustez (i):** a escala do voto de legenda é muito menor que a de p_PT, então só o sinal é comparável.

## Reincorporação de fontes (27/10/2026, tarde) — decisões do usuário

- **IDHM:** só 2010 (opção c), via Ipeadata (série ADH_IDHM e componentes; Atlas DH). Entra como nível inicial fixo (`idhm_2010`) e numa especificação alternativa das diferenças longas (`fase6_diferencas_longas_idhm2010`). Não há IDHM municipal pós-2010.
- **CadÚnico:** só **beneficiários do Bolsa Família** (Auxílio Brasil em 2021–2023), via Ipeadata (FAM_PBF, VAL_PBF; MDS), como benefícios em dezembro por 100 habitantes. O **% de cadastrados no CadÚnico continua pendente** (VIS Data/CECAD fora do ar).
- **Comex:** arquivos completos baixados **sem verificação TLS** (certificado vencido em 03/10/2026), com autorização do usuário, só nesse domínio.
  - Integridade contra o Ipeadata (`outputs/tables/comex_integridade.csv`):
    - totais nacionais anuais dentro de 1% na maioria dos anos e dentro de 4% em todos;
    - 2023 bate 100% município a município; 2020–2025, entre 92% e 100% do valor.
  - Nos anos antigos (2003–2012), só 47% a 61% do valor fica em pares município × ano que batem dentro de 1%, embora os totais nacionais batam. Isso indica **realocação entre municípios entre safras** do Comex (revisões, domicílio fiscal) e erros de homônimo no Ipeadata (ex.: São Sebastião/SP × AL em 2022). Não há sinal de corrupção. **A atribuição municipal antiga é menos confiável.**
  - O arquivo completo (gerado em maio/2025) só tinha 2025 até abril; o arquivo anual de 2025 o substitui.
  - Códigos de município diferentes do IBGE em SP (+100000), GO (−100000), MS (−200000) e DF (−100000).
- **Comex na análise:** `log_export_commod_pc` (log de 1 + exportações de commodities SH 01–27 per capita, R$ dez/2025) entra nos modelos. Mais da metade das AMCs não exporta, então essa variável é zero para a mediana e o teste de H3 fica fraco. `pct_commodities` e `hhi_exp` só existem para quem exporta e ficam como descritivos.
- **Ausente:** Nazária/PI (2206720) não tem Bolsa Família em 2009 e fica fora das diferenças longas e da análise espacial (5.564 AMCs).
- **Continuam pendentes:** DATASUS (mortalidade infantil, homicídios), % de cadastrados no CadÚnico, RAIS.

## Mercado de trabalho pelo Censo no lugar da RAIS (27/10/2026, tarde) — decisão do usuário

- **PNAD Contínua descartada:** não é representativa por município (só Brasil, UF, capitais e RMs).
- **Censo 2010 e 2022 (amostra) no lugar da RAIS**, tabelas SIDRA conferidas no endpoint de metadados e registradas em `src/ingest/ibge_censo.py`:
  - 2010: 1572 (condição de atividade, 14+), 1577 (posição na ocupação, 10+);
  - 2022: 6580 (força de trabalho, 14+), 10261 (posição na ocupação, 14+).
- **Variáveis:** `taxa_desocupacao` (14+), `pct_informal` (sem carteira + conta própria + não remunerados / ocupados) e `pct_conta_propria` (só descritiva). As duas primeiras entram em `X_CENSO`, portanto só na spec. A (não há 2018) e nas diferenças longas, no logit de grupos e no Oaxaca.
- **Harmonização e ressalvas:**
  - a informalidade de 2010 cobre 10+ (o IBGE não publica 14+ por município na posição na ocupação); a de 2022, 14+;
  - não se usa CNPJ (só 2022) nem contribuição à previdência (só 2010); a definição é a comum aos dois Censos;
  - 2010 exclui do denominador a produção para o próprio consumo, que em 2022 deixou de ser ocupação (19ª CIET);
  - totais nacionais de desocupação: 7,6% (2010) e 5,7% (2022);
  - correlação entre Censos, por município: informalidade 0,88; desocupação só 0,44 (erro amostral alto em municípios pequenos — usar com cautela).
- **O que a RAIS ainda daria e o Censo não:** série anual do emprego formal e renda formal. Fica como opcional; o PLANO a previa só ao lado do Censo.
- **Correção técnica:** o MNLogit em Newton podia declarar convergência com log-verossimilhança NaN (overflow na robustez (d)). Agora isso também aciona o BFGS; colunas constantes na subamostra (ex.: `ideb_ausente`) são descartadas.
- **Continuam pendentes:** DATASUS (mortalidade infantil, homicídios) e % de cadastrados no CadÚnico.

## Pacto 2.0 — Fase A: base por local de votação (27/10/2026)

- **Disponibilidade:** todos os arquivos do TSE por seção existem para 2018, 2022 e 2026 (2026 publicados em 25–26/10/2026, com 1º e 2º turnos). Não há pendência de 2026.
- **Presidente por seção** fica em `votacao_secao_<ano>_BR.zip`; os arquivos por UF trazem só os cargos da UF (deputado federal sai deles).
- **Volume:** ~13 GB compactados em `data/raw/tse_secao/`, mantidos no OneDrive por decisão do usuário.
- **Cor/raça no TSE:** não existe em 2018 (#NE) e, em 2026, ~71% do eleitorado está como "não informado" (amostra AC). Não serve como variável por local; a composição racial virá do Censo 2022 por setor (Fase B).
- **Geocodificação externa:** não feita, por decisão do usuário. Locais sem coordenada são contados e ficam sem entorno. Cobertura de coordenadas em 2018: 79% dos locais e 83% dos votos (lacuna concentrada em MG, BA e ES).
- **Número do local:** o arquivo de votação usa `NR_LOCAL_VOTACAO_ORIGINAL` do cadastro (100% das seções em 2018). `NR_LOCAL_VOTACAO` difere em ~0,5% (seções realocadas depois) e o número no detalhe difere em ~3%. A base usa o número original; o detalhe é casado por seção e turno; as seções realocadas ficam marcadas (`secoes_realocadas`).
- **Escopo (decisão do usuário, 27/10/2026):** só a votação para presidente. O deputado federal sai da base por local e o **Critério 3 do plano2.md (voto proporcional / bloco de esquerda) não será estimado**.
  - **Motivo (do usuário):** a abstenção caiu bastante do 1º para o 2º turno de 2026, e muitos eleitores de Lula no 2º turno não votaram no 1º; portanto também não votaram para deputado. Para a tese do pacto 2.0, centrada em quem decidiu o 2º turno, o voto para deputado (só no 1º turno) diz pouco sobre essa base. A queda da abstenção entre os turnos será quantificada na base por local (comparecimento no 1º e no 2º turno) e é o objeto do Critério 4. Os arquivos por UF já baixados ficam em `data/raw/tse_secao/votacao_secao/`, e a função `camara()` fica no código, sem ser chamada.
- **Cadastro de locais de 2026:** vem em um CSV por UF mais `_BRASIL` e `_ZZ`; coordenadas com vírgula decimal. O primeiro processamento leu só AL e perdeu as coordenadas; corrigido (usa o `_BRASIL`). O detalhe de 2022 e 2026 tem `_BR` (presidente) e `_BRASIL` (todos os cargos): usa-se só o `_BR`.
- **Abstenção nacional de 2026 (referência do usuário, conferida na base por local):** 21,08% no 1º turno e 19,22% no 2º, com exterior; sem exterior (escopo da base por local), 20,84% e 18,99%. A queda de ~1,9 p.p. é a referência agregada do Critério 4; a análise usa o recorte por local.

## Pacto 2.0 — Fase B: entorno censitário (27/10/2026)

- **Fontes:** malha de setores do Censo 2022 com atributos e agregados por setor (básico, cor ou raça, demografia, renda do responsável), baixados por `src/ingest/ibge_setores.py`.
- **Sigilo:** setores com valor "X" (sigilo estatístico) contam como 0; 35,6% dos setores têm algum sigilo em cor/raça e 4,0% ficam sem cor nenhuma (excluídos da média de % negra).
- **Geometrias inválidas** na malha (auto-interseções) corrigidas com `buffer(0)`.
- **Bug corrigido no Voronoi:** locais com coordenada ligeiramente fora do limite municipal herdavam a célula de outro local (dupla contagem). Agora as células saem na ordem dos pontos (`ordered=True`) e são recortadas depois. A Fase B foi recalculada.

## Pacto 2.0 — Fase C: modelos (27/10/2026)

- **Comparecimento por faixa etária (Critério 4):** o menor nível publicado com idade é município × zona eleitoral (`perfil_comparecimento_abstencao_<ano>.zip`); por seção o TSE não publica comparecimento por idade. O arquivo de 2026 foi gerado em 13/10/2026 e **só traz o 1º turno**; 2018 e 2022 têm os dois turnos. A mobilização entre turnos de 2026 é medida por local (Δ comparecimento ~ composição etária do eleitorado do local); a comparação por idade entre turnos fica para 2018 e 2022 até o TSE republicar o arquivo de 2026.
- **PyEI** (inferência ecológica R×C) instalado via pip (pyei 1.1.4, pymc 6.3.2). Rodado em São Paulo, Rio de Janeiro, Salvador e Belo Horizonte (decisão do usuário, pelo tempo de amostragem), com o local como unidade.
- **Cor/raça do eleitor:** o arquivo de comparecimento de 2026 tem `DS_COR_RACA`, mas com a mesma lacuna do perfil (maioria não informada); não usado.
- **PyEI lento:** em São Paulo (2.046 locais) a amostragem passou de 1 hora sem terminar (o modelo multinomial-Dirichlet estima uma matriz por local). Como alternativa rápida, a **regressão ecológica restrita (Goodman)**, com matriz única por cidade, P >= 0, linhas somando 1 e IC por bootstrap dos locais, foi rodada nas quatro capitais (`pacto20_faseC_c4_goodman`). O PyEI segue rodando; se terminar, os dois resultados são comparados.
