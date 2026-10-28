> **Substituída por `relatorio.md` (Fase 8, 27/10/2026)**, que traz os números finais com todas as fontes.

> **Atualização (27/10/2026, tarde):** os números desta nota são da versão *sem* Bolsa Família, Comex e IDHM. As tabelas e figuras em `outputs/` já foram refeitas com essas fontes. Para o que mudou, ver `outputs/report/atualizacao_pbf_comex_idhm.md`.

# Fase 6: modelos (só IBGE e Ideb)

*Gerado em 27/10/2026 a partir de `src/models.py`. As tabelas estão em `outputs/tables/fase6_*`.*

**Especificação comum**
- WLS ponderada pelo eleitorado apto, com efeito fixo de UF.
- Covariáveis em z-score dentro de cada eleição: β = p.p. do voto por 1 desvio-padrão.
- Erros-padrão agrupados por microrregião (558 clusters). A autocorrelação espacial completa fica para a Fase 7.
- Covariáveis disponíveis: população, PIB per capita, % do VAB agropecuário e da administração pública, Ideb, % negra, % evangélica, % sem religião.
- **Faltam os indicadores diretos de pobreza do PLANO (CadÚnico, mortalidade infantil).** O % do VAB da administração pública funciona como proxy de dependência do Estado.
- **Spec. A** (com Censo) cobre 2006, 2010, 2014, 2022 e 2026. Em 2006, raça e religião vêm do Censo 2010.
- **Spec. B** (sem Censo) é a única que inclui 2018. Os saltos de B em 2018 refletem viés de variável omitida (sem raça e religião) e não devem ser lidos como mudança real.

## 1. β_t do voto presidencial no PT (spec. A)

| Covariável (1 DP) | 2006 | 2010 | 2014 | 2022 | 2026 | β₂₀₂₆ − β₂₀₁₀ (p) |
|---|---|---|---|---|---|---|
| % negra | 11,0 | 10,5 | 9,9 | 8,6 | 8,7 | −1,8 (0,054) |
| % evangélica | +0,6 | −0,7 | −1,5 | −6,1 | −5,6 | **−5,0 (<0,001)** |
| % VAB adm. pública | 2,6 | 4,7 | 3,0 | 7,9 | 6,3 | +1,6 (0,075) |
| log população | −0,5 | +0,1 | −0,7 | +0,9 | +1,4 | **+1,3 (0,002)** |
| Ideb | −0,3 | −0,3 | −2,5 | −2,1 | −1,2 | −0,8 (0,23) |
| log PIB per capita | 1,6 | 2,1 | −0,3 | 3,2 | 1,5 | −0,6 (0,50) |
| % VAB agro | −1,6 | +0,7 | +0,8 | +2,1 | +1,1 | +0,5 (0,36) |

- R² entre 0,73 e 0,82 em todos os anos. O teste conjunto de igualdade dos β (2026 × 2010 e 2026 × 2006) dá p < 0,001.
- **H1 (persistência): sustentada no núcleo.**
  - A associação com % negra segue a mais forte de todas, só um pouco menor (de 10,5 para 8,7).
  - A associação com a dependência do Estado (% do VAB da adm. pública) **cresceu** (de 4,7 para 6,3; p = 0,075).
  - O pacto não se dissolveu. Falta testar com CadÚnico e renda do trabalho.
- **H2 (clivagem religiosa): a mudança mais forte e mais nítida.**
  - O coeficiente de % evangélica vai de ≈ 0 (2006–2010) a −6 p.p. por DP (2022–2026), líquido de UF, renda, raça e estrutura produtiva.
  - A virada ocorre entre 2014 e 2022. Pela spec. B não dá para localizar 2018, porque raça e religião ficam de fora.
- **H3 (clivagem produtiva): não aparece nos níveis condicionais.**
  - Com UF, renda e dependência do Estado controladas, % do VAB agro tem β *positivo* e pequeno.
  - O padrão descritivo (G_OP mais agrícola) parece passar por renda, raça e religião, não pelo agro em si.
  - O Comex (commodities), ainda pendente, é o teste mais direto.
- **H4 (recomposição urbana): sinal de mudança.** O β de log população passou de ≈ 0 para +1,4: municípios maiores ficaram relativamente mais petistas, condicional ao resto.

## 2. Presidencial × Câmara (H5) e hiato lulista

- **p_PT (Câmara):**
  - β de % negra = 0,7 em 2010 e 2,2 em 2026, contra 8,7 no presidencial.
  - β de % evangélica = −0,9 em 2026, contra −5,6.
  - **O voto no PT para a Câmara é muito menos estruturado por raça e religião que o voto presidencial.** O perfil do lulismo segue mais nítido que o do petismo.
- **Hiato lulista** (s_PT − p_PT, com controle de NEP), θ₂₀₂₆ − θ₂₀₁₀:
  - adm. pública +3,3 (p = 0,001);
  - log população +2,0 (p < 0,001);
  - agro +1,4 (p = 0,001);
  - % negra −3,2 (p = 0,005);
  - % evangélica −3,6 (p < 0,001).
- **Leitura:**
  - O hiato **cresceu nos municípios mais dependentes do Estado e nos maiores**: o lulismo se descolou ainda mais do petismo justamente onde está o núcleo do pacto, o que é coerente com H5.
  - O hiato **encolheu onde há mais evangélicos e mais população negra**. Nos municípios evangélicos, isso acontece porque o voto presidencial no PT caiu, e não porque o voto no PT para a Câmara subiu.

## 3. Antipetismo proporcional (p_ANTI)

| Covariável (1 DP) | PSDB 2006 | PSDB 2010 | PSDB 2014 | PL 2022 | PL 2026 |
|---|---|---|---|---|---|
| % negra | −2,9 | −1,8 | −3,0 | −4,1 | −4,9 |
| % evangélica | −0,9 | −0,4 | −0,8 | +1,8 | +3,3 |
| % VAB adm. pública | +0,1 | +2,0 | +0,6 | −0,8 | −2,3 |

- R² de 0,28–0,39 (PSDB) para **0,62 (PL 2026)**: o voto do partido antipetista na Câmara ficou muito mais estruturado socialmente.
- **O antipetismo trocou de base, não só de partido** (H6). O PL é mais branco, evangélico e menos dependente do Estado que o PSDB jamais foi.
- Logit multinomial (efeitos marginais por DP):
  - o efeito de % negra sobre P_ANTI vai de −0,056 (2006) a −0,138 (2026);
  - sobre P_PT, vai de −0,003 a +0,070;
  - % evangélica: P_ANTI +0,032 e P_PT −0,031 em 2026, contra ≈ 0 em 2006.
  - A partir de 2014–2022, **a Câmara também se polarizou por raça e religião**.

## 4. Diferenças longas e pertencimento a grupo

- Swing 2010→2026 ~ X₂₀₁₀ + ΔX + EF UF (n = 5.565).
  - R² só com EF de UF: 0,40; + níveis de 2010: 0,55; + mudanças: 0,45; completo: 0,56.
  - **O ponto de partida explica bem mais que as mudanças.**
- Níveis de 2010 (p.p. de swing por DP):
  - % evangélica −4,3 [−5,5; −3,1];
  - adm. pública +3,4;
  - Ideb −2,4;
  - % negra −3,2;
  - população +1,6.
- Mudanças: Δ % evangélica ≈ 0 (p = 0,87). **Pesa o estoque de evangélicos em 2010, não o crescimento.** Δ sem religião +1,2; Δ adm. pública +1,0.
  - O % negra *negativo*, condicional ao resto, sugere reversão à média: municípios muito negros já eram muito petistas em 2010.
- Logit G_PT / G_EST / G_OP (só dummies de macrorregião; pseudo-R² 0,22), por DP de 2010:
  - % evangélica: G_PT −8,2 p.p. e G_OP +3,7 p.p.;
  - Ideb: G_PT −7,0 e G_OP +5,5;
  - adm. pública: G_PT +4,7.

## 5. Oaxaca-Blinder: o pacto mudou ou o Brasil mudou?

O s_PT médio (ponderado por aptos) caiu 4,7 p.p. de 2010 para 2026 [IC −6,9; −2,5].

| Referência | Composição (ΔX·β) | Comportamento (Δβ) |
|---|---|---|
| β de 2010 | +2,1 [−0,6; 4,3] | −6,8 [−9,5; −3,8] |
| β de 2026 | −2,3 [−4,0; −0,8] | −2,5 [−4,9; −0,0] |

- **Com qualquer referência, a mudança de comportamento (Δβ) puxa contra o PT.** O "pacto mudou" é robusto. O efeito da composição ("o Brasil mudou") **depende da referência**, e o motivo está no detalhe:
  - **% evangélica:** com β de 2026, o crescimento dos evangélicos responde por −2,9 p.p.; com β de 2010, só −0,4. O aumento de evangélicos só vira problema para o PT porque o coeficiente virou. Composição e comportamento se reforçam.
  - **% negra:** +2,5 / +2,2 p.p. a favor do PT. Atenção: parte do aumento de pretos e pardos de 2010 para 2022 é reclassificação (autodeclaração), não demografia.
  - **Ideb:** −0,5 / −2,0. É provável que seja artefato: o Ideb subiu no país todo, e o β negativo transversal não significa que melhorar a escola reduza o voto no PT.
  - **PIB per capita:** +1,0 / +0,7.

## Pontos para a Fase 7 (robustez)

- Erros-padrão espaciais (Conley) e modelos SAR/SEM. Com 558 microrregiões a inferência já está agrupada, mas ainda pode ser otimista.
- Exclusão de capitais, de municípios com menos de 5 mil habitantes e sem ponderação.
- 2022 como ponto final, para ver se 2026 é ponto fora da curva. Versão federação.
- Reestimar quando CadÚnico, DATASUS e Comex entrarem: são os testes diretos de H1 e H3.
