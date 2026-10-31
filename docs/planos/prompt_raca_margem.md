Novo teste extra do projeto pacto-lulista: decompor o efeito racial entre os turnos de 2026. Siga as convenções do repositório (src/, data/raw intocado, outputs/, pendencias.md, pytest, textos em português, etapa registrada em `src/pipeline.py`, CHANGELOG em "Não lançado"). Prefixo: `extra_raca_`. Trabalhe em fases e mostre os checks de cada fase antes de seguir. Não altere tabelas ou modelos já publicados: tudo sai em arquivos novos.

## Motivação

A nota `outputs/report/extra_entre_turnos.md` mostra que, no modelo por AMC, a população negra tem efeito de +0,72 p.p. por DP sobre o crescimento de Lula entre os turnos de 2026, contra +0,06 em 2022. No nível do voto, porém, o gradiente racial do PT caiu desde 2010 (Fase 6 e pacto 2.0). A literatura sugere uma leitura que reconcilia os dois resultados (De Micheli, *World Politics* 2021 e *LAPS* 2023; Freeman, Telles et al., *PNAS* 2025):
- a consciência racial politizada se concentra em **pretos**, sobretudo **escolarizados**;
- **pardos** votam como brancos e acompanham o deslocamento evangélico.

Se for assim, o efeito entre turnos de 2026 vem dos pretos, e o enfraquecimento do gradiente no nível vem dos pardos. Hoje `pct_negra` soma as duas categorias e não permite ver isso.

## Hipóteses

- **R1 (pretos × pardos).** No Δ Lula entre turnos de 2026, o coeficiente de % preta é positivo e maior que o de % parda; em 2022, nenhum dos dois se destaca.
- **R2 (escolaridade).** O efeito de % preta no Δ de 2026 é maior onde há mais eleitores com ensino superior (interação positiva).
- **R3 (geração).** O efeito de % preta no Δ de 2026 é maior onde há mais eleitores de 16 a 34 anos (interação positiva).
- **R4 (nível).** No voto do PT no 2º turno (nível), a queda do gradiente racial entre 2010 e 2026 vem sobretudo de % parda.

Reportar as quatro, mesmo que não se sustentem.

## Fase A — Variáveis

1. **Entorno dos locais (Censo 2022 por setor):** em `src/pacto20_entorno.py`, `pct_negra` soma preta e parda. Criar, sem mudar as colunas existentes, `pct_preta` e `pct_parda` com a mesma regra (só setores sem sigilo, mesmo denominador e mesma ponderação Voronoi; buffer de 800 m como robustez). Conferir que `pct_preta + pct_parda == pct_negra` dentro da tolerância numérica.
2. **AMCs:** % preta e % parda dos Censos 2010 e 2022 (amostra), com as regras de alinhamento de `config.yaml`. Se já estiverem no painel com outro nome, reusar. Conferir que somam a `pct_negra` do painel.
3. **Escolaridade:**
   - nos locais, `pct_superior` (perfil do eleitorado do TSE), já usada em `extra_entre_turnos`;
   - nas AMCs, % de adultos com superior completo do Censo; se não houver para 2022, usar o perfil do eleitorado do TSE agregado por AMC e registrar a escolha.
4. **Juventude:** `pct_jovens_16_34` nos locais; nas AMCs, a mesma faixa do perfil do eleitorado do TSE.
5. **Checks:** cobertura por variável; correlação entre `pct_preta` do entorno e % preta da AMC; descritivas de `pct_preta` e `pct_parda` por região. Registrar em `pendencias.md` qualquer sigilo que afete pretos mais que pardos: pretos são minoria em muitos setores e podem cair em sigilo com mais frequência. Medir esse viés antes de seguir.

## Fase B — Modelos entre turnos (R1–R3)

Mesma especificação de `extra_entre_turnos.modelo`:
- Δ Lula em p.p. dos aptos, por 1 DP;
- EF de UF (AMC) ou de município (locais);
- peso = aptos;
- EP agrupado por microrregião (AMC) ou município (locais);
- controles de voto disponível (terceiros e abstenção no 1º turno).

1. **R1:** substituir `pct_negra` por `pct_preta` + `pct_parda`, em 2026 e em 2022, para AMCs e para locais.
   - Em locais, 2022 usa a base pacto 2.0 de 2022, se o entorno de 2022 existir com Censo 2022; senão, só AMC para 2022.
   - Testar a igualdade dos dois coeficientes (Wald).
2. **R2:** acrescentar `pct_preta × pct_superior` e `pct_parda × pct_superior`, com termos principais e variáveis centradas antes da interação. Reportar o efeito marginal de % preta no 1º e no 4º quartil de % superior, com IC.
3. **R3:** mesma estrutura com `pct_jovens_16_34`.
4. **Desfechos alternativos**, só para R1:
   - Δ comparecimento entre turnos;
   - taxa de captura;
   - Δ Flávio Bolsonaro, como contraste: a previsão é efeito nulo de % preta.
5. **Robustez:**
   - sem Goiás (efeito Caiado);
   - locais com ≥ 300 aptos;
   - buffer de 800 m;
   - só capitais e regiões metropolitanas, contra o resto;
   - sem ponderação.

## Fase C — Nível do voto (R4)

No s_PT do 2º turno, spec. A da Fase 6 (Censo 2010 para 2010 e 2014; Censo 2022 para 2022 e 2026; 2018 fica fora, como no PLANO):
- substituir `pct_negra` por `pct_preta` + `pct_parda`;
- estimar por eleição e no modelo empilhado com interação X × ano;
- testar a diferença 2026 − 2010 de cada coeficiente.

Repetir no nível intraurbano (s_PT por local, 2010–2026, EF de município × ano), com entorno do Censo 2022. Mesma ressalva do pacto 2.0: em 2010 e 2014, composição de 2022 aplicada a anos anteriores.

## Saídas

- **Tabelas:** `outputs/tables/extra_raca_*.csv` e `.md`.
- **Figuras** (PNG 300 dpi e SVG):
  - coeficientes de % preta e % parda por eleição, no nível e entre turnos, com IC 95%;
  - efeito marginal de % preta por quartil de % superior e de % jovens.
- **Nota:** `outputs/report/extra_raca.md`, no padrão de `extra_entre_turnos.md`, com:
  - veredito sobre R1–R4 (sustentada / parcial / não sustentada) e a evidência central de cada uma;
  - um parágrafo dizendo se os resultados apoiam a leitura "consciência racial como recurso da margem do pacto, não da base";
  - limitações.
- **Testes** em `tests/test_extra_raca.py`:
  - preta + parda = negra;
  - nenhuma coluna antiga do painel ou do entorno alterada;
  - os coeficientes de `extra_turnos_amc_modelo` reproduzidos quando se usa `pct_negra`.

## Limitações a registrar

- Leitura ecológica: lugares, não eleitores. "Locais com mais pretos cresceram mais" não implica que pretos votaram mais em Lula.
- Autodeclaração muda ao longo do tempo, e pardo/preto não são estáveis entre censos (reclassificação). Comparações 2010–2026 no nível misturam mudança de voto com mudança de classificação.
- O eleitor vota onde está o título, não necessariamente onde mora; o entorno censitário é uma aproximação.
- `pct_superior` e `pct_jovens_16_34` descrevem o eleitorado do local, não o entorno.
- Sigilo de setores pode sub-representar pretos em áreas de baixa presença (Fase A, item 5).
- Sem dado individual: o teste de mecanismo exige survey com cor e escolaridade (AmericasBarometer, surveys eleitorais nacionais).