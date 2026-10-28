> **Substituída por `relatorio.md` (Fase 8, 27/10/2026)**, que traz os números finais com todas as fontes.

# Atualização: Bolsa Família, Comex e IDHM 2010

*27/10/2026. Fases 4 a 7 refeitas com as três fontes. Decisões e ressalvas de dados em `outputs/pendencias.md`.*

## O que entrou

| Variável | Fonte | Uso |
|---|---|---|
| `pbf_100hab`: benefícios do Bolsa Família (dez/t−1) por 100 habitantes | MDS via Ipeadata | covariável em todos os modelos (pobreza direta, H1) |
| `log_export_commod_pc`: log(1 + exportações de commodities SH 01–27 per capita, R$ dez/2025) | Comex Stat | covariável em todos os modelos (H3) |
| `pct_commodities`, `hhi_exp`, `export_pc_real`, `saldo_pc_real` | Comex Stat | painel e descritivas (`pct_commodities` e `hhi_exp` só existem para quem exporta) |
| `idhm_2010` e componentes | Atlas DH via Ipeadata | nível inicial; especificação alternativa das diferenças longas |

## O que muda nos achados

### 1. H1 (persistência do pacto): agora testada com pobreza direta e reforçada

- O β do Bolsa Família no voto presidencial do PT (spec. A, por DP):
  - **1,4 (2006) e 3,1 (2010)** → **7,3 (2022) e 6,7 (2026)**;
  - Δ 2026 − 2010 = **+3,6 (p < 0,001)**.
  - Com Conley a 250 km: z = 11,5 em 2026.
- O efeito antes atribuído ao % do VAB da administração pública era, em boa parte, Bolsa Família. Com os dois no modelo, o β da adm. pública fica estável (≈ 3) e sem mudança significativa.
- Robustez: o Δβ do Bolsa Família segue positivo e significativo sem capitais (+2,9), sem AMCs pequenas (+3,7), com base 2006 (+5,3) e com final 2022 (+4,2). **Some sem ponderação (+0,5, n.s.).** Como antes, o *reforço* está nos municípios com mais eleitores; a *persistência* (β positivo e grande) aparece em todas as versões.
- **Descritiva:**
  - mediana de benefícios por 100 hab. nos G_PT: 13,8 (2010) → 18,8 (2025);
  - nos G_OP: 5,3 → 4,6.
  - O PT ganhou terreno relativo onde o Bolsa Família se expandiu: diferença das medianas de Δ = +4,8 [4,4; 5,2], positiva em todas as regiões, menos o Sudeste.

### 2. Raça: a associação enfraquece quando se controla pobreza

- O β de % negra cai de 9,7 (2010) para 6,6 (2026). Δ = −3,1 (p = 0,001), robusto exceto sem ponderação.
- Antes, sem o Bolsa Família no modelo, a queda era menor (−1,8, p = 0,05).
- **Leitura:** parte da associação racial do voto petista passa pela pobreza. A pobreza (medida pelo Bolsa Família) ganhou peso, e a raça líquida perdeu.

### 3. H2 (religião): inalterada

Δβ de % evangélica = **−4,7 (p < 0,001)**, robusto em todas as especificações, inclusive sem ponderação (−2,5*). Continua sendo a mudança mais nítida e mais robusta.

### 4. H3 (commodities): não sustentada pelo Comex

- O β das exportações de commodities per capita é pequeno e estável (−0,4 a −0,7 por DP), sem mudança 2026 × 2010 (p = 0,77).
- Ressalvas:
  - mais da metade das AMCs não exporta;
  - o Comex mede o domicílio fiscal da empresa, não o local de produção;
  - a % do VAB agropecuário também não mostra mudança condicional.
- O padrão descritivo (G_OP mais agrícolas) continua passando por renda, raça e religião.

### 5. H5 (lulismo × petismo) e o antipetismo

- O hiato lulista cresceu onde há mais Bolsa Família: Δθ = +3,7 (p = 0,001). No voto do PT para a Câmara, o β do Bolsa Família fica ≈ 0 em todos os anos.
  - **O Bolsa Família estrutura o voto em Lula, não o voto no PT para deputado.** É a evidência mais direta de lulismo ≠ petismo até aqui.
- **Antipetismo na Câmara:** o β do Bolsa Família no voto do partido antipetista vai de +0,7 (PSDB 2006) a **−3,9 (PL 2026)**. A base do PL está nos municípios com menos benefícios; a do PSDB não tinha esse corte.

### 6. Oaxaca-Blinder (s_PT 2010 → 2026, Δ = −4,7 p.p.)

| Referência | Composição | Comportamento |
|---|---|---|
| β 2010 | **+4,2** [1,3; 6,6] | **−8,9** [−11,5; −5,8] |
| β 2026 | +0,7 [−1,4; 2,2] | **−5,4** [−7,9; −3,0] |

- **O comportamento puxa contra o PT com as duas referências.** O "pacto mudou" fica ainda mais nítido.
- A composição agora é neutra ou favorável ao PT. Em boa parte isso é a expansão do Bolsa Família (+1,8 / +2,5 p.p.), que compensa o crescimento evangélico (−0,3 / −2,7).

### 7. Diferenças longas e IDHM

- Bolsa Família em 2010: +2,5 p.p. de swing por DP (p < 0,001). Crescimento do Bolsa Família 2010→2026: +1,3 (p < 0,001).
- R² completo: 0,57 (0,56 antes).
- **Especificação alternativa:** com o IDHM 2010 no lugar de PIB per capita e Ideb, o IDHM fica **sem efeito próprio** (+0,2, p = 0,79), absorvido por Bolsa Família, raça e religião. O R² praticamente não muda (0,566).

## Síntese revista

1. **O pacto mudou mais por comportamento que por composição**, com dois movimentos simultâneos e robustos:
   - o voto no PT **se ancorou ainda mais na pobreza direta** (Bolsa Família), sobretudo nos municípios com mais eleitores;
   - o voto no PT **se descolou da população evangélica**, em todas as especificações.
2. A raça perdeu peso líquido, porque parte dela passava pela pobreza.
3. Lulismo ≠ petismo: a pobreza estrutura o voto em Lula, não o voto no PT para a Câmara.
4. O antipetismo trocou de base (PSDB → PL), agora com corte nítido de pobreza, raça e religião.
5. **H3 (commodities) segue sem sustentação** com os dados municipais disponíveis.

---

## Adendo: desocupação e informalidade (Censos 2010 e 2022)

*27/10/2026, fim da tarde. Fases 4 a 7 refeitas de novo com `pct_informal` e `taxa_desocupacao` na spec. A. Os números acima (seções 1–7) são da versão sem essas duas variáveis; abaixo, o que muda.*

**1. O Bolsa Família continua o principal marcador do reforço, um pouco menor.**
- Δβ do Bolsa Família (2026 − 2010): **+2,5 (p = 0,003)**, contra +3,6 antes. β 3,7 (2010) → 6,2 (2026).
- Robusto como antes: sem capitais +2,3*, sem AMCs pequenas +2,4*, base 2006 +4,3*, final 2022 +3,0*. Some sem ponderação (+0,6, n.s.).
- **A informalidade não absorve o efeito do Bolsa Família.** Absorve só uma parte do reforço.

**2. Informalidade: sinal pequeno e que depende do tamanho do município.**
- β da informalidade no voto presidencial: −1,4 (2006) e −0,9 (2010) → +0,8 (2022) e +0,5 (2026); Δ = **+1,4 (p = 0,035)**.
- Diferenças longas: informalidade em 2010 → swing **+1,6 p.p. por DP (p = 0,004)**; crescimento da informalidade +0,8 (p = 0,02).
- **Mas é frágil e muda de sinal:** sem ponderação, o nível de 2010 vai a **−1,3 (p < 0,001)**; sem capitais, +0,4 (n.s.). No logit de grupos (não ponderado), mais informalidade em 2010 aumenta P(G_OP) em +5,8 p.p. e reduz P(G_PT) em −3,7 p.p.
- **Leitura:** a "informalidade" mede coisas diferentes conforme o município.
  - Nas grandes cidades, é o subproletariado urbano de Singer, que se moveu a favor do PT.
  - Nos municípios pequenos do Norte e do Centro-Oeste, é sobretudo conta própria rural e de fronteira agrícola, que se moveu contra.
  - Separar conta própria agrícola de não agrícola (há seção de atividade na tabela 10262 de 2022, mas não há equivalente municipal de 2010 no SIDRA) seria o teste direto. Por ora, fica como hipótese.

**3. Desocupação:** Δβ +1,5 (p = 0,001) no voto presidencial. Em 2010 ela não explicava o voto no PT; em 2026, municípios com mais desemprego são um pouco mais petistas. Ressalva: a estimativa municipal é ruidosa (correlação de 0,44 entre os Censos).

**4. O resto não muda:**
- % evangélica: Δβ −4,6 (p < 0,001);
- % negra: Δβ −3,3 (p < 0,001);
- Oaxaca: comportamento −8,9 / −4,5 p.p.; a contribuição da composição de informalidade e desocupação é ≈ 0 (a da desocupação, −0,8 com β de 2026);
- R² das diferenças longas: 0,573 (antes 0,566);
- H5: o Bolsa Família segue estruturando o hiato lulista (Δθ +3,2, p = 0,007), e informalidade e desocupação não (n.s.). No PL (p_ANTI) o Δβ do Bolsa Família é −3,4 (p = 0,001).
