> **Substituída por `relatorio.md` (Fase 8, 27/10/2026)**, que traz os números finais com todas as fontes.

> **Atualização (27/10/2026, tarde):** os números desta nota são da versão *sem* Bolsa Família, Comex e IDHM. As tabelas e figuras em `outputs/` já foram refeitas com essas fontes. Para o que mudou, ver `outputs/report/atualizacao_pbf_comex_idhm.md`.

# Fase 7: espacial e robustez (só IBGE e Ideb)

*Gerado em 27/10/2026 a partir de `src/spatial.py` e `src/robustness.py`. As tabelas estão em `outputs/tables/fase7_*`.*

## 1. Dependência espacial

Vizinhança: 8 vizinhos mais próximos pelos centroides das AMCs. Não se usa contiguidade porque a malha simplificada tem frestas.

| Série | Moran's I |
|---|---|
| s_PT (variável), de 2006 a 2026 | 0,81 → 0,90 |
| swing 2010→2026 (variável) | 0,67 |
| resíduo do s_PT (WLS, EF de UF) | 0,37–0,43 |
| resíduo do hiato lulista | 0,24–0,29 |
| resíduo das diferenças longas | 0,39 |

Todas com p = 0,001 (999 permutações).

- **Os efeitos fixos de UF e as covariáveis absorvem cerca de metade da autocorrelação, mas sobra muita.** Há estrutura regional abaixo da UF: microrregiões e redes políticas locais.
- O voto presidencial no PT ficou **mais concentrado espacialmente** ao longo do tempo (I de 0,81 para 0,90).
- **LISA do swing:**
  - 1.150 AMCs no cluster HH (pró-PT): Nordeste litorâneo e sertão, norte do Pará, partes do RJ e de SP, extremo sul do RS.
  - 1.174 no cluster LL (pró-oposição): arco amazônico e agropecuário (AM, RO, MT, TO), Roraima e Amapá, oeste de SC e do RS.
  - 154 outliers; 3.087 não significativos.

### Erros-padrão de Conley (Bartlett, 100 e 250 km)

Os z dos β centrais quase não mudam em relação aos erros agrupados por microrregião. Exemplos:
- % evangélica em 2026: z = −12,5 (agrupado), −13,4 (100 km), −11,3 (250 km);
- adm. pública em 2026: 9,2 / 9,6 / 7,5;
- % negra em 2010: 12,5 / 10,3 / 8,0.

**A inferência da Fase 6 não depende da escolha do erro-padrão.**

### Modelos SEM / SAR (spreg, sem ponderação)

λ do erro espacial entre 0,72 e 0,82; ρ do lag espacial entre 0,49 e 0,72. Coeficientes de % evangélica por estimador:

| Modelo | MQO | Erro espacial | Lag espacial* |
|---|---|---|---|
| s_PT 2010 | −0,33 | −0,33 | −0,24 |
| s_PT 2026 | −2,80 | −2,13 | −1,89 |
| swing (nível de evangélicos em 2010) | −2,22 | −1,78 | −1,37 |

\* No lag espacial o coeficiente é o efeito direto *antes* do multiplicador espacial, e não é diretamente comparável.

- **A virada religiosa sobrevive ao controle espacial.** O coeficiente encolhe cerca de 25–30%, mas em 2026 continua seis a oito vezes maior que em 2010.
- O mesmo vale para % negra (em 2026: MQO 7,6; erro espacial 5,9) e para adm. pública (3,5; 2,0).
- Atenção: sem ponderação, o efeito de evangélicos em 2026 é menor (−2,8) que no WLS principal (−5,6). Municípios grandes pesam mais na virada religiosa (ver robustez (b)).

## 2. Robustez das estimativas centrais

Figura `fase7_robustez`; tabela `fase7_robustez`. Fora a principal, as especificações são:
- (a) limiares de grupo: ±0,5 DP, quintis e tercis;
- (b) sem ponderação;
- (c) sem capitais;
- (d) sem AMCs com menos de 5 mil habitantes;
- (e) base 2006;
- (f) final 2022;
- (g) versão federação;
- (h) sem dependência de puxador;
- (i) só legenda.

### Robusto em todas as especificações aplicáveis

| Estimativa | Principal | Faixa nas demais | Mesmo sinal? |
|---|---|---|---|
| Δβ % evangélica (voto presidencial PT) | −4,97* | −2,47* (sem peso) a −6,23* (base 2006) | 6/6, todas p < 0,05 |
| Δθ % evangélica (hiato lulista) | −3,61* | −2,16* a −5,29* | 8/8, todas p < 0,05 |
| % evangélica em 2010 → swing (diferenças longas) | −4,28* | −2,22* a −5,47* | 6/6 |
| Ideb em 2010 → swing | −2,35* | −2,28* a −2,60* | 6/6 |
| AME % evangélica → P(G_PT) | −0,08* | −0,08* a −0,13* | 9/9 |
| AME adm. pública → P(G_PT) | +0,05* | +0,03* a +0,07* | 9/9 |
| Δθ log população (hiato) | +2,01* | +0,98* a +2,25* | 8/8 |

- Evangélicos e Ideb vão no mesmo sentido em todas as variantes, assim como a associação dos G_PT com a dependência do Estado.
- O "2026 é ponto fora da curva?" fica descartado: com 2022 como ponto final (f), as estimativas são iguais ou mais fortes (Δβ evangélica −5,41*).

### Frágil: depende de peso e de capitais

| Estimativa | Principal | Sem ponderação | Sem capitais |
|---|---|---|---|
| Δβ adm. pública (voto presidencial) | +1,59 (p = 0,08) | −0,82 | −1,64* |
| Δβ log população (voto presidencial) | +1,31* | +0,29 | −0,22 |
| Δβ % negra (voto presidencial) | −1,77 (p = 0,05) | +0,60 | −1,30 |
| Δθ adm. pública (hiato) | +3,30* | −0,19 | +2,05 |

- **O aparente reforço do pacto (Δβ positivo da dependência do Estado) e a recomposição urbana (H4) vêm das capitais e das grandes cidades.** Basta tirar as 27 capitais para o sinal de log população sumir. Basta tirar a ponderação para o reforço da dependência do Estado sumir.
- Leitura conservadora: **H1 é de persistência, não de reforço.** O β de nível da adm. pública é grande e positivo em todos os anos. A H4 se limita às capitais: o PT melhorou relativamente nas capitais, não nas cidades médias.
- O crescimento do hiato lulista onde há mais dependência do Estado (H5) também depende do peso. Nos municípios pequenos, típicos do pacto, o hiato não cresceu de forma distinguível.

### Voto do PT na Câmara (E5) e identificação partidária

- O Δβ de % evangélica para p_PT é negativo na maioria das especificações (−1,39* principal; −2,08* federação). Some sem ponderação (−0,30) e sem dependência de puxador (−0,68).
- **Só legenda (i):** o voto de *legenda* do PT, proxy de identificação partidária, tem Δβ de % negra = −0,20* e de % evangélica = +0,07*. São sinais opostos aos do voto presidencial. A escala é pequena, porque a legenda é uma fração dos válidos.
  - **Leitura:** a identificação com o PT (legenda) não acompanhou a racialização do voto em Lula. Mais um indício de lulismo descolado do petismo (H5).
- **(h) sem dependência de puxador** exclui 3.868 de 5.565 AMCs (o critério ≥ 50% marca quase todo município pequeno; ver `pendencias.md`). Os resultados ficam imprecisos, e essa robustez é pouco informativa com o limiar atual.

## Síntese para o relatório (Fase 8)

1. **O pacto mudou mais por comportamento que por composição, e o eixo da mudança é religioso.** O coeficiente de % evangélica virou de ~0 para fortemente negativo entre 2014 e 2022. Isso é robusto a tudo o que foi testado: peso, amostra, anos, limiares, erros-padrão espaciais, SEM e SAR.
2. **O núcleo socioeconômico e racial do pacto persiste** (% negra, dependência do Estado e Ideb baixo, sempre associados ao PT). O suposto *reforço* do pacto não é robusto: vem das grandes cidades.
3. **Lulismo ≠ petismo:**
   - o voto do PT na Câmara (e, mais ainda, o voto de legenda) é pouco estruturado por raça e religião;
   - o hiato presidencial − Câmara encolhe onde há evangélicos;
   - a base proporcional do PT encolheu e se aproximou do perfil lulista (Fase 5).
4. **O antipetismo trocou de base:** PSDB → PL, com estruturação social muito maior do voto antipetista na Câmara (Fase 6).
5. **Pendente:** os testes diretos de pobreza (CadÚnico, mortalidade infantil) e de commodities (Comex).
