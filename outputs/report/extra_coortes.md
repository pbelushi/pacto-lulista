# Teste extra: a coorte de 1970–1990 concentra o antipetismo?

*27/10/2026. Fora do PLANO. Código: `src/ingest/ibge_idade.py` (dados) e `src/coortes.py` (análise). Tabelas `outputs/tables/extra_coortes_*`; figuras `extra_coortes_perfis` e `extra_coortes_betas`.*

**Resposta curta: só em parte, com efeito pequeno.** Com controles, municípios com mais adultos nascidos entre 1970 e 1990 votam um pouco menos no PT em 2022 e 2026, comparados tanto aos mais jovens quanto aos mais velhos. Na comparação bruta, porém, os municípios mais opositores são **mais velhos**, não de meia-idade. E a mesma coorte estava associada a **mais** voto no PT em 2006 e 2010.

## Dados

- Idade simples da população residente, Censos 2010 (SIDRA 1378) e 2022 (SIDRA 9514), universo.
- Coortes entre os adultos (18+), pela data de referência do Censo (31/07):
  - nascidos a partir de ago/1990;
  - nascidos de ago/1970 a jul/1990 (2022: 32–51 anos; 2010: 20–39);
  - nascidos até jul/1970.
- **Nenhuma AMC tem maioria absoluta da coorte de 1970–1990 em 2022 (só 2 de 5.570).** A participação dela varia pouco: mediana de 37,7%, DP de 2,7 p.p. Por isso a comparação é relativa: cada AMC recebe o "perfil" da coorte cuja participação está mais acima da média.

## Descritiva (sem controles)

| Quintil de s_PT 2026 | s_PT mediano | 1991+ | 1970–1990 | até 1969 |
|---|---|---|---|---|
| Q1 (mais opositor) | 30,4 | 24,7 | 37,6 | 37,7 |
| Q5 (mais lulista) | 79,7 | 28,3 | 37,9 | 33,7 |

- A coorte do meio tem praticamente o mesmo peso nos municípios mais lulistas e nos mais opositores.
- O que separa os extremos é jovens × idosos: os mais opositores são mais velhos (Sul e interior do Sudeste), e os mais lulistas, mais jovens (Nordeste e Norte).
- Por perfil relativo, o "perfil 1970–1990" reúne as cidades grandes e médias (58% do eleitorado):
  - s_PT 2026 de 50,1, contra 60,1 no perfil jovem e 48,3 no perfil idoso;
  - G_OP: 17,8% das AMCs do perfil 1970–1990, contra 21,8% do perfil idoso.
- Dentro das regiões, o perfil 1970–1990 tem o menor s_PT no Nordeste (66,1, contra 73,5 e 76,5) e no Sul (34,5, contra 37,6 e 41,1). No Norte, tem o maior swing contra o PT (−9,0 p.p.). No Centro-Oeste e no Sudeste, o padrão não se repete.

## Regressões (WLS por aptos, EF de UF, erros por microrregião)

β = p.p. de s_PT por 1 p.p. de adultos transferido entre coortes. Com as covariáveis da spec. A: Bolsa Família, raça, religião, renda, Ideb, trabalho etc.

| Contraste | 2006 | 2010 | 2014 | 2022 | 2026 |
|---|---|---|---|---|---|
| 1970–90 vs. até 1969, com controles | +0,28* | +0,32* | +0,05 | **−0,34*** | **−0,42*** |
| 1970–90 vs. 1991+, com controles | +0,43 | +0,65 | −1,29* | **−0,53*** | **−0,45*** |
| 1970–90 vs. até 1969, só EF de UF | +0,49* | −0,01 | −0,43* | −1,81* | −1,31* |

\* p < 0,05. Em 2006–2014 as coortes vêm do Censo 2010, em que "1991+" são só os de 18–19 anos; o contraste com eles é impreciso.

- **Magnitude:** 1 DP a mais da coorte do meio (2,7 p.p.) equivale a cerca de −1,1 a −1,4 p.p. de s_PT em 2026. Para comparar, 1 DP de % evangélica equivale a −5,3.
- **A associação virou de sinal.** Em 2006–2010, municípios com mais adultos dessa coorte (então com 16 a 39 anos) eram ligeiramente **mais** petistas, com controles. Em 2022–2026, ligeiramente menos. Não é um traço geracional fixo: é uma coorte que se moveu contra o PT ao longo do período. Com dados municipais não dá para separar efeito de coorte de efeito de idade (hoje são adultos de 36 a 56 anos em 2026).
- **Antipetismo na Câmara (p_ANTI, PL):** sem controles, mais coorte do meio está associada a mais voto no PL em 2026 (+0,99*). Com controles, o efeito some (+0,21, n.s.).
- **Hiato lulista:** nada com controles.
- **Diferenças longas** (swing 2010→2026 sobre as coortes do Censo 2010, com os controles da Fase 6): 1970–90 vs. até 1969 = −0,49* por p.p., cerca de −2,8 p.p. de swing por DP (5,7 p.p. em 2010). É o resultado mais forte. Mas em 2010 essa coorte (20–39 anos) se concentrava nas fronteiras de migração (MT, RO, sul do PA), justamente as áreas G_OP; parte do efeito pode ser migração, não geração.

## Limitações

- **Ecológico.** "Municípios com mais adultos nascidos em 1970–1990" não equivale a "eleitores nascidos em 1970–1990". Para testar a hipótese no nível individual, o certo é usar surveys (ESEB, Datafolha) com ano de nascimento.
- **Pouca variação.** A participação da coorte do meio varia pouco entre municípios, e a estrutura etária se confunde com fecundidade, pobreza e migração; os resultados dependem dos controles.
- **População, não eleitorado.** A base são os adultos (18+) do Censo; o eleitorado por faixa etária do TSE seria a alternativa direta.

---

## Com o eleitorado do TSE (perfil do eleitorado)

*Código: `src/ingest/tse_perfil.py` e `src/coortes_tse.py`; tabelas `extra_tse_coortes_*`; figuras `extra_tse_coortes_jovens` e `extra_tse_coortes_betas`.*

- **Fonte:** eleitorado apto de cada eleição por faixa etária e município (2010–2026; em 2006 o TSE não informa a idade).
- **Coortes:** as faixas de 5 anos são repartidas entre as coortes pela sobreposição com o intervalo de nascimento, supondo distribuição uniforme dentro da faixa. Base: todo o eleitorado (16+).
- **Validação:**
  - os totais batem com os aptos (diferença abaixo de 0,01%);
  - as coortes têm correlação de 0,72 a 0,93 com as do Censo, por AMC.

### Eleitores nascidos a partir de 1991

| Eleição | Nascidos 1991+ | % do eleitorado | % 1970–1990 | % até 1969 |
|---|---|---|---|---|
| 2010 | 7,5 mi | 5,5 | 48,5 | 46,0 |
| 2014 | 19,2 mi | 13,5 | 45,4 | 41,1 |
| 2018 | 30,7 mi | 20,9 | 42,6 | 36,5 |
| 2022 | 42,9 mi | 27,5 | 40,3 | 32,2 |
| 2026 | 51,5 mi | 32,7 | 38,8 | 28,5 |

### Onde eles são mais representativos (s_PT; Q5 − Q1 de % nascidos 1991+)

| Eleição | Quintis nacionais, ponderado | Dentro da UF, ponderado | Dentro da UF, sem ponderação |
|---|---|---|---|
| 2010 | +20,9 | +10,1 | +8,2 |
| 2014 | +29,2 | +5,3 | +8,5 |
| 2018 | +30,3 | +2,9 | +9,5 |
| 2022 | +18,8 | −3,4 | +6,6 |
| 2026 | +16,0 | −3,1 | +5,4 |

- **Brasil:** os municípios mais jovens votam muito mais no PT, mas isso é região: os municípios mais jovens estão no Norte e no Nordeste. A distância caiu de +30 p.p. (2018) para +16 (2026).
- **Dentro da mesma UF, os municípios mais jovens seguem mais petistas** (sem ponderação: +5 a +10 p.p. em todas as eleições), com distância menor desde 2018.
- **A inversão na versão ponderada (−3 em 2022–2026) vem das capitais.** As capitais e cidades grandes são as menos jovens de cada estado e caem no Q1 (16 das 26 capitais em 2026), e o PT ganhou terreno relativo nelas (H4). Com peso pelo eleitorado, elas dominam o Q1.

### Regressões (β por 1 p.p. do eleitorado transferido entre coortes; s_PT; com controles)

| Contraste | 2010 | 2014 | 2018* | 2022 | 2026 |
|---|---|---|---|---|---|
| 1991+ vs. 1970–90 | +0,98 | +1,02 | +1,71 | +1,18 | +1,04 |
| 1991+ vs. até 1969 | +1,18 | +0,93 | +0,95 | +0,48 | +0,11 (n.s.) |
| 1970–90 vs. até 1969 | +0,20 (n.s.) | −0,09 (n.s.) | −0,75 | −0,70 | −0,93 |

\* 2018 com a spec. B (sem Censo). Os valores sem "n.s." têm p < 0,05.

- **Com controles, a coorte de 1970–1990 é a menos petista desde 2018**, abaixo tanto da mais jovem quanto da mais velha. É o padrão que a hipótese prevê, mais nítido que com o Censo: cerca de −2 p.p. de s_PT por DP da coorte do meio em 2026, contra a mais velha.
- **A vantagem petista dos municípios jovens sobre os velhos encolheu:** de +1,18 por p.p. (2010) para +0,11 (2026, n.s.). Em 2026, jovens e velhos se igualam, e a coorte do meio fica abaixo dos dois.
- **Câmara (p_ANTI):** sem controles, mais coorte do meio está associada a mais voto no PL (+1,22 em 2026) e mais jovens, a menos. Com controles, quase nada fica significativo.
- **Ressalvas:**
  - o eleitor vota onde tem o título, que pode não ser onde mora (jovens migrantes, sobretudo);
  - aos 16 e 17 anos, o alistamento é facultativo;
  - as coortes vêm de faixas de 5 anos, então o corte é aproximado (cerca de ±1 ano).
