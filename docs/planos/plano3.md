Nova etapa do projeto pacto-lulista: testar comparativamente um modelo histórico de resolução da polarização. Siga as convenções do repositório (src/, data/raw intocado, outputs/, pendencias.md, pytest, textos em português) e trabalhe em fases, mostrando os checks de cada fase antes de seguir. Prefixo de arquivos desta etapa: `p3_`.

## Pergunta e hipóteses

**Pergunta.** Episódios de polarização política intensa se resolvem necessariamente (por conflito ou por esgotamento), ou podem durar décadas como empate? Onde o Brasil de 2014–2026 se situa nessa distribuição?

**Hipótese do usuário (H0).** A polarização afetiva não é sustentável: termina (a) pelo conflito, com vitória de um dos polos (modelo fevereiro→outubro de 1917; Itália 1922, Alemanha 1933, Espanha 1936–39 com sinal contrário), ou (b) pelo esgotamento, com uma figura de ordem acima dos polos (modelo Termidor→Brumário).

**Hipóteses rivais a testar junto:**
- **H1 — Empate crônico (Portantiero, "empate hegemónico").** A polarização canalizada por instituições pode durar 15 anos ou mais sem resolução (Argentina 1955–1976; EUA desde os anos 1990).
- **H2 — Pacto.** Parte dos episódios termina por acordo negociado entre os polos (Colômbia 1958; Espanha 1977).
- **H3 — Sequência, não alternativa (Brinton).** Conflito e esgotamento são etapas: o esgotamento/cesarismo tende a vir depois de uma fase de conflito.
- **H4 — Condição de regime (McCoy e Somer; Linz; Sartori).** A polarização só é instável quando coloca o próprio regime em jogo; o risco de ruptura depende de instituições, papel dos militares e crise econômica.

Não assuma H0 como verdadeira: o objetivo é medir com que frequência cada desfecho ocorre e quanto duram os episódios.

## Fase A — Dados

1. **V-Dem Country-Year (versão mais recente disponível; Full+Others).** Baixar o CSV oficial (v-dem.net) ou via o repositório GitHub `vdeminstitute/vdemdata`. Registrar versão e data em pendencias.md. Antes de usar cada variável, confirmar nome, cobertura temporal e escala no codebook da versão baixada e registrar no docstring. Variáveis previstas:
   - polarização política: `v2cacamps` (e a versão ordinal `_osp`/`_ord`);
   - polarização da sociedade: `v2smpolsoc` (provavelmente só a partir de 2000 — confirmar; usar como robustez);
   - regime e democracia: `v2x_regime`, `v2x_polyarchy`, `v2x_libdem`;
   - restrições ao Executivo: `v2x_jucon`, `v2xlg_legcon`;
   - institucionalização partidária: `v2xps_party`;
   - papel dos militares na política: confirmar no codebook a variável mais adequada;
   - controles econômicos: PIB per capita e crescimento (variáveis `e_` do V-Dem ou Maddison).
2. **Episódios de transformação de regime (ERT, V-Dem):** episódios de autocratização e democratização, com início, fim e desfecho.
3. **Golpes:** base de Powell e Thyne (tentativas e golpes bem-sucedidos, por data).
4. **Guerras civis:** UCDP/PRIO Armed Conflict Dataset (pós-1946); para antes de 1946, Correlates of War (intra-state wars).
5. **Líderes:** Archigos (forma de entrada e saída do poder: regular/irregular), para identificar quem assumiu depois de cada ruptura.
6. Se alguma base estiver indisponível ou exigir cadastro, parar, registrar em pendencias.md e propor alternativa. Não inventar dados.
7. **Checks:** painel país-ano sem duplicatas; cobertura por variável e década; os casos de referência abaixo estão presentes com as datas esperadas.

## Fase B — Episódios de polarização

1. Definir episódio: anos consecutivos com `v2cacamps` acima de um limiar alto. Principal: percentil 80 da distribuição mundial pós-1900 (ou o ponto da escala ordinal equivalente a "polarização séria" — escolher e justificar com o codebook). Início = primeiro ano acima; fim = segundo ano consecutivo abaixo. Duração mínima: 3 anos. Fundir episódios separados por um único ano abaixo do limiar.
2. Robustez da definição: limiar no percentil 75 e 90; duração mínima de 2 e 5 anos; `v2smpolsoc` no lugar de `v2cacamps` (pós-2000).
3. Episódios em curso no último ano da base = censurados (não têm desfecho; entram na análise de duração).
4. **Validação com casos de referência** (a definição precisa capturar a maioria; reportar quais capturou e com que datas):
   Rússia 1917; França 1789–1799 (se a cobertura do V-Dem permitir); Itália 1919–1922; Alemanha 1919–1933; Espanha 1931–1936; Chile 1970–1973; Argentina 1945–1976; Colômbia 1946–1958; Brasil 1954–1964; Venezuela pós-1999; EUA pós-1990; Brasil pós-2014.
   Se um caso de referência não aparecer, investigar se é limitação do dado ou da definição; não forçar a entrada.
5. Saída: `outputs/tables/p3_episodios.csv` (país, início, fim, duração, censurado, pico e média de polarização, regime no início).

## Fase C — Codificação dos desfechos

Cada episódio encerrado recebe um desfecho:

| Código | Desfecho | Regra principal |
|---|---|---|
| R1 | Ruptura vencida por um polo | Golpe, revolução, guerra civil ou autocratização liderada por um dos lados do conflito, até 2 anos após o fim do episódio |
| R2 | Cesarismo | Ruptura que leva ao poder uma força apresentada como acima dos polos (ex.: militares como "poder moderador", Brumário) |
| P | Pacto | Fim negociado: acordo de partilha de poder, transição pactuada ou coalizão entre os polos |
| D | Despolarização sem ruptura | Polarização cai abaixo do limiar com o regime mantido e sem pacto formal |
| C | Censurado | Episódio em curso |

Procedimento:
1. Gerar um **pré-código automático** a partir de ERT, golpes, guerras civis e Archigos (entrada irregular, autocratização, etc.).
2. Para cada episódio encerrado, preencher `outputs/tables/p3_codificacao.csv` com: código proposto, evidência das bases (com datas), quem assumiu o poder, e uma linha de justificativa. Distinguir R1 de R2 exige julgamento histórico: marcar esses casos e os de P como `revisar = sim`. **Não completar fatos históricos de memória sem sinalizar**: onde a base não informa, escrever `a confirmar`.
3. Gerar `outputs/report/p3_casos_para_revisao.md` com os episódios marcados, para validação manual do usuário antes da Fase D. Parar aqui e pedir a revisão.
4. Codificar também, para os episódios com R1/R2, se houve uma fase prévia de conflito aberto (violência política, tentativa de golpe fracassada) — insumo para H3.

## Fase D — Análise

1. **Descritiva:** número de episódios por década e região; distribuição dos desfechos; duração mediana por desfecho; proporção de episódios com 15 anos ou mais (teste direto de H1 contra H0).
2. **Duração:** curva de Kaplan-Meier da sobrevivência dos episódios (incluindo censurados), geral e por regime no início (democracia × autocracia).
3. **Riscos competitivos:** modelo de riscos competitivos (Fine-Gray ou Cox por causa) para R1, R2, P e D. Covariáveis no início do episódio e variando no tempo: nível de democracia, restrições ao Executivo, institucionalização partidária, papel dos militares, crescimento do PIB, golpe anterior no país, presidencialismo. Erros agrupados por país.
4. **Sequência (H3):** entre os episódios com R2, que fração teve fase prévia de conflito aberto? Comparar com R1.
5. **Brasil:** série de `v2cacamps` 1900–último ano, com os episódios marcados; comparar 1954–1964 com o episódio atual nas covariáveis do modelo; probabilidades previstas de cada desfecho para o perfil atual do Brasil, com intervalo de confiança. Apresentar como exercício condicional, não previsão.
6. **Robustez:** todas as definições alternativas de episódio da Fase B; só democracias no início; só pós-1945; excluindo episódios em guerra entre Estados.

## Fase E — Indicadores brasileiros de esgotamento × conflito (opcional, se houver tempo)

Série nacional e por UF, 1989–2026, a partir do TSE e do painel já existente: abstenção, brancos e nulos, votos de terceiros candidatos no 1º turno, R² da estrutura social no voto presidencial e Moran's I municipal. Esgotamento esperaria abstenção, brancos/nulos e terceiros em alta, e R² em queda; conflito esperaria o contrário. Tabela e gráfico de linhas por indicador.

## Saídas

- `outputs/tables/p3_*.csv` e `.md`; figuras em PNG 300 dpi e SVG.
- Figuras principais: mapa-múndi ou linha do tempo dos episódios; Kaplan-Meier; incidência acumulada por desfecho; série do Brasil com os dois episódios destacados.
- `outputs/report/p3_relatorio.md`: veredito sobre H0 e H1–H4 (sustentada / parcial / não sustentada), evidência central, posição do Brasil, limitações.

## Limitações a registrar

- **Viés retrospectivo do V-Dem:** especialistas codificam sabendo o desfecho, o que pode inflar a polarização medida antes de rupturas. Verificar se o pico de polarização coincide suspeitamente com o ano da ruptura.
- **N pequeno** de rupturas e de pactos; poucos casos por desfecho limitam o modelo de riscos competitivos — reportar contagens ao lado de cada estimativa.
- **Polarização afetiva ≠ `v2cacamps`:** a variável mede campos antagônicos na sociedade, não afeto individual; para o Brasil recente, complementar com surveys (ESEB) se disponíveis.
- **Codificação de R2 e P** depende de julgamento histórico e da revisão manual.
- **França 1789–1799** e Rússia 1917 podem ter cobertura ou medição frágeis; tratar como ilustração, não como base da inferência.
- A análise do Brasil é condicional ao modelo; não é previsão eleitoral.

## Literatura de referência (para o relatório)

Linz (1978), *The Breakdown of Democratic Regimes*; Sartori (1976), *Parties and Party Systems*; McCoy, Rahman e Somer (2018), *American Behavioral Scientist*; McCoy e Somer (2019), *Annals of the AAPSS*; Brinton (1938), *The Anatomy of Revolution*; Marx (1852), *O 18 de Brumário de Luís Bonaparte*; Gramsci, *Cadernos do cárcere* (cesarismo); Portantiero (1977), empate hegemónico; Santos (1986), *Sessenta e quatro: anatomia da crise*; Stepan (1971), *The Military in Politics*. Conferir referências completas antes de citar.