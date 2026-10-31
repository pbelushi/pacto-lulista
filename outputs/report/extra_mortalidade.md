# Mortalidade e voto: homicídios e Covid

Extra do estudo 1, com microdados do SIM e do SINASC. Código: `src/ingest/sim.py` e `src/extra_mortalidade.py`. Tabelas: `outputs/tables/extra_sim_*`. Os modelos principais não mudam.

## Resumo

- **Homicídios:** a relação com o voto no PT inverteu. Em 2006, AMCs mais violentas votavam mais no PT, líquido das covariáveis; desde 2018 votam menos. A mudança de 2010 para 2026 é significativa e não altera os demais coeficientes do relatório.
- **Covid:** não há evidência robusta de que municípios mais atingidos tenham punido Bolsonaro. A associação positiva bruta existe, mas some ou encolhe muito com controles, e o placebo falha: as mesmas medidas preveem o swing de 2014→2018, anterior à pandemia.
- **Mortalidade infantil:** a associação simples com o voto no PT enfraquece de 2010 para 2026, mas a mudança não é significativa. Com as covariáveis, ela é nula nas duas eleições. Não muda nenhum coeficiente principal nem a leitura da H1. Sem dado para 2018, porque o arquivo de nascidos vivos de 2015 está truncado.

## Dados

Microdados do SIM e do SINASC, 2003–2026, por município de residência, baixados de dadosabertos.saude.gov.br e salvos em `data/manual/` (o TabNet recusa acesso automatizado).

- **Definições:** homicídios = CID-10 X85–Y09; intervenção legal = Y35–Y36, à parte; Covid = B34.2 e U07.
- **Anos incompletos:** 2025 é preliminar (janeiro a setembro) e 2026 é segunda prévia (janeiro a agosto). Ficam fora das taxas. Na eleição de 2026, a janela de homicídios é 2022–2024.
- **Taxas:** média de três anos terminando em eleição − 1, por AMC, com suavização Bayesiana empírica.
- **Validação:** óbitos infantis de 2022 = 32.238, igual à consulta ao TabNet registrada no projeto.
- **Perda:** 0,28% dos óbitos e 0,006% dos nascimentos têm município ignorado e foram descartados.
- **2015 truncado:** `DNBR2015.csv` termina no meio de um registro. Faltam cerca de 230 mil nascimentos, com perda de 80% a 96% em AP, AC, RO, RR e AM e perda parcial em TO, CE, PA, PE e RS. Os outros 47 arquivos estão íntegros. O ano não foi estimado: a mortalidade infantil fica vazia nas janelas com 2015, o que tira a eleição de 2018 dessa medida. Homicídios e Covid não são afetados, porque vêm do SIM.

A taxa nacional de homicídios sobe de 25,9 por 100 mil em 2005 para 31,8 em 2017 e cai para 19,2 em 2024. A mortalidade infantil nacional cai de 18,8 por mil em 2003 para 12,2 em 2018 e fica em 12,5 em 2024. A pandemia aparece como queda em 2020 (11,5), que coincide com menos nascimentos e não foi investigada aqui.

## Homicídios

Coeficiente da taxa de homicídios sobre o voto no PT no 2º turno (p.p. por DP, EF de UF, peso = aptos, EP por microrregião):

| Eleição | Janela | Spec. B (sem Censo) | Spec. A (com Censo) |
|---|---|---|---|
| 2006 | 2003–2005 | +1,98*** | +0,83*** |
| 2010 | 2007–2009 | +0,70 | +0,12 |
| 2014 | 2011–2013 | +0,23 | −0,26 |
| 2018 | 2015–2017 | −1,24*** | n/d |
| 2022 | 2019–2021 | −1,55*** | −1,29*** |
| 2026 | 2022–2024 | −1,41*** | −1,32*** |

\*\*\* p < 0,01. A spec. A não existe em 2018, porque o PLANO proíbe interpolar o Censo em regressões.

A diferença entre coeficientes, no modelo empilhado com a spec. A, é de −1,44 entre 2010 e 2026 (EP 0,39; p = 0,0002) e de −2,15 entre 2006 e 2026 (EP 0,37; p < 0,0001).

**Os coeficientes principais ficam estáveis.** A mudança mediana é de 0,10 p.p. por DP. O único sinal trocado é `log_pop` em 2006 na spec. B, que não é significativo com nem sem homicídios. Em 2026, na spec. A, evangélicos vão de −5,26 para −5,07, Bolsa Família de 6,15 para 6,13 e % negra de 6,03 para 6,45. A maior mudança nessa spec. em 2026 é `part_vab_adm_publica`, de 2,56 para 2,05.

**Leitura.** A inflexão coincide com a chegada de Bolsonaro em 2018, e é compatível com a segurança pública ter virado clivagem eleitoral. Os dados não provam isso: é uma associação ecológica, e a causalidade pode ter outras origens, como presença de atividades ilegais, expansão de fronteira ou crime organizado. O sinal é o inverso da correlação bruta (+0,25 em 2026), que reflete a violência alta no Nordeste. O resultado vale dentro de cada UF, líquido das covariáveis.

## Mortalidade infantil (H1)

A H1 do PLANO inclui a mortalidade infantil entre as medidas de pobreza do pacto: a associação com o voto no PT se mantém de 2010 para 2026? Coeficiente sobre o voto no PT no 2º turno (p.p. por DP, peso = aptos, EP por microrregião):

| Eleição | Janela | Só EF de UF | Spec. B (sem Censo) | Spec. A (com Censo) |
|---|---|---|---|---|
| 2006 | 2003–2005 | +1,51*** | +1,02*** | +0,71*** |
| 2010 | 2007–2009 | +1,01*** | +0,41 | +0,22 |
| 2014 | 2011–2013 | +2,00*** | +0,89*** | +0,38 |
| 2018 | n/d | n/d | n/d | n/d |
| 2022 | 2019–2021 | +0,65* | +0,29 | 0,00 |
| 2026 | 2022–2024 | +0,26 | +0,21 | +0,11 |

\* p < 0,10; \*\*\* p < 0,01.

- **Queda não significativa.** A diferença entre 2026 e 2010 é de −0,75 só com EF de UF (EP 0,58; p = 0,19) e de −0,11 na spec. A (EP 0,38; p = 0,77).
- **O coeficiente cai numericamente, mas isso não basta para dizer que a associação mudou.** O IC é largo, e 2014 está acima de 2010.
- **Renda e Bolsa Família já captam a maior parte.** Com as covariáveis, o coeficiente fica perto de zero desde 2010.
- **Os coeficientes principais não mudam.** A mudança mediana é de 0,03 p.p. por DP. Em 2026, na spec. A, Bolsa Família fica em 6,16 contra 6,15, e evangélicos em −5,26 nos dois modelos. O único sinal trocado é `log_pib_pc` em 2014 na spec. B, não significativo.

**Leitura para a H1.** A medida direta do pacto segue sendo o Bolsa Família, cujo coeficiente sobe de 3,66 para 6,15 na spec. A. A mortalidade infantil não contradiz isso nem acrescenta explicação própria.

## Covid

**Medida.** Excesso de mortalidade: óbitos observados contra o esperado pela taxa de 2015–2019 do mesmo mês, multiplicada pela população do ano. Por AMC, o excesso médio em 2020–2021 é de 25,9% (DP 7,3).

**Modelo.** Swing relativo do PT por 1 DP da medida (p.p.), com três conjuntos de controles: só EF de UF (M0), voto anterior (M1) e covariáveis (M2).

| Medida | 2018→2022 M0 | M1 | M2 | Placebo 2014→2018 M2 | 2022→2026 M2 |
|---|---|---|---|---|---|
| Excesso 2020–2021 | +0,70*** | +0,41*** | +0,11 | −0,79*** | +0,04 |
| Excesso, 1ª onda (mar–dez/2020) | +0,76*** | +0,62*** | +0,14** | −0,53*** | +0,11** |
| Excesso, jan/2020–set/2022 | +0,35** | +0,13 | +0,04 | −0,57*** | +0,03 |
| Óbitos notificados por Covid, 2020–2021 | +1,53*** | +1,02*** | +0,28*** | −1,16*** | +0,25*** |

\*\* p < 0,05; \*\*\* p < 0,01.

**Por que não dá para concluir que houve punição.**

1. **O placebo falha.** O efeito não pode vir da pandemia se aparece antes dela. Em 2014→2018, essas mesmas AMCs se moveram contra o PT, com magnitude maior que a do "efeito" de 2018→2022. A hipótese mais simples é reversão à média: lugares que abandonaram o PT em 2018 voltaram em parte em 2022, e coincidem com lugares mais atingidos pela Covid. Controlar pelo swing anterior não resolve (M1 e M2). Essa explicação não foi testada à parte.
2. **O efeito encolhe com controles.** No excesso de 2020–2021, cai de +0,70 para +0,11 e deixa de ser significativo.
3. **Os dois casos que sobrevivem são os mais frágeis.** A 1ª onda fica no limite (p = 0,049), numa tabela com 45 regressões. Os óbitos notificados dependem da capacidade local de testar e notificar, e esse era justamente o problema que o excesso de mortalidade evitava.
4. **Mesmo que real, seria pequeno.** 0,14 p.p. por DP.

## Limitações

- Todos os resultados são ecológicos, por AMC, e não individuais.
- O excesso não é padronizado por idade, e a tendência de envelhecimento 2015–2019 não é projetada. Isso subestima o esperado no nível; o EF de UF absorve só a parte comum a cada estado.
- Por isso as janelas mais longas, como jan/2020–set/2022, são mais afetadas.
- Causalidade reversa: municípios mais bolsonaristas podem ter tido mais mortes. Esse viés iria contra achar punição, mas o placebo mostra que há confusão de tendência de qualquer modo.
- A suavização Bayesiana é global, sem levar em conta vizinhança nem UF.
- Os dados de 2024 podem ainda ser revistos, e as taxas de 2022–2024 dependem deles.
- Nascidos vivos caem 5,8% de 2023 para 2024, com queda de 6% a 9,5% em todas as UFs. Não há sinal de UF faltando, mas o número não foi conferido com fonte externa.

Fonte: DATASUS, SIM; TSE; IBGE. Elaboração própria.
