> **Substituída por `relatorio.md` (Fase 8, 27/10/2026)**, que traz os números finais com todas as fontes.

> **Atualização (27/10/2026, tarde):** os números desta nota são da versão *sem* Bolsa Família, Comex e IDHM. As tabelas e figuras em `outputs/` já foram refeitas com essas fontes. Para o que mudou, ver `outputs/report/atualizacao_pbf_comex_idhm.md`.

# Fase 5: achados descritivos (só IBGE e Ideb)

*Gerado em 27/10/2026 a partir de `src/descriptives.py`. Unidade: AMC (5.565). Comex, DATASUS, CadÚnico, IDHM e RAIS ainda não entraram (ver `outputs/pendencias.md`).*

> **Leitura ecológica.** Os resultados descrevem municípios, não eleitores. "Municípios com mais evangélicos se deslocaram para X" não implica que "evangélicos votaram em X".
>
> **Tudo aqui é descritivo e sem controles.** A região confunde quase todos os contrastes. Por exemplo, 29% das AMCs do Nordeste são G_PT, contra 2,5% G_OP. O teste com efeito fixo de UF é o da Fase 6.

## 1. Quem se moveu: o perfil dos grupos de swing (2010→2026)

Medianas das AMCs (tabela `fase5_perfil_inicial_final`; figura `fase5_trajetorias_g_swing`). As colunas trazem o primeiro e o último ano disponível de cada indicador.

| Indicador | G_PT (início → fim) | G_EST | G_OP |
|---|---|---|---|
| PIB per capita (R$ mil dez/2025), 2010→2023 | 12,4 → 18,3 | 21,3 → 31,8 | 34,9 → 51,6 |
| % VAB adm. pública, 2010→2021 | 50,6 → 46,5 | 31,3 → 27,3 | 20,2 → 17,7 |
| % VAB agropecuária, 2010→2021 | 13,4 → 13,3 | 17,4 → 18,5 | 25,4 → 30,0 |
| % preta + parda, 2010→2022 | 67,7 → 71,1 | 56,1 → 60,8 | 26,8 → 33,0 |
| % evangélica (10+), 2010→2022 | 10,0 → 16,1 | 15,9 → 22,3 | 18,4 → 24,6 |
| Ideb anos iniciais, 2009→2025 | 3,5 → 5,6 | 4,6 → 6,2 | 5,1 → 6,6 |
| População (mil), 2010→2026 | 11,1 → 11,0 | 11,7 → 11,8 | 8,1 → 8,7 |

- **Os municípios em que o PT ganhou terreno relativo têm o perfil do "pacto" de Singer.** São mais pobres, mais dependentes da administração pública, com mais população negra, menos evangélicos e Ideb mais baixo.
- Os G_OP são o oposto: mais ricos, mais agropecuários, mais brancos e mais evangélicos.
- Isso é compatível com H1 (persistência) e com a direção esperada de H2, H3 e H4. Ainda **não separa região de perfil**.
- **Distribuição regional** (`fase5_grupos_por_regiao`):
  - G_PT: 29% das AMCs do Nordeste e 14% do Norte;
  - G_OP: 45% das AMCs do Sul, 24% do Norte e 21% do Centro-Oeste.

## 2. O que mudou dentro de cada grupo: Δ comparados (G_PT − G_OP, IC bootstrap 95%)

Tabela `fase5_deltas_bootstrap`; figura `fase5_deltas_gpt_menos_gop`.

| Indicador | Δ mediano G_PT | Δ mediano G_OP | Diferença [IC 95%] |
|---|---|---|---|
| PIB per capita real (%, log), 2010→2023 | +38,0 | +38,0 | 0,0 [−2,5; 2,3] |
| % VAB agro (p.p.), 2010→2021 | +0,1 | +2,1 | −2,0 [−2,8; −1,3] |
| % VAB indústria (p.p.) | −0,3 | −1,2 | +0,9 [0,6; 1,2] |
| População (%, log), 2010→2026 | +1,1 | +4,9 | −3,8 [−5,3; −2,6] |
| Ideb (pontos), 2009→2025 | +2,0 | +1,5 | +0,5 [0,4; 0,6] |
| % evangélica (p.p.), 2010→2022 | +5,8 | +4,8 | +1,0 [0,6; 1,4] |
| % preta + parda (p.p.) | +3,6 | +4,8 | −1,2 [−1,5; −0,8] |

- **O crescimento da renda não distingue os grupos.** O PIB per capita real cresceu igual nos dois. Quem se moveu foi definido pelo **nível** de partida, não pela trajetória econômica.
- **A agropecuária ganhou peso só onde o voto migrou contra o PT** (H3). Esses municípios também cresceram mais em população.
- **Evangélicos cresceram *mais* nos G_PT**, ao contrário de uma leitura ingênua de H2. Isso vem da base menor: G_PT partiu de 10%.
  - No **Nordeste** o sinal se inverte: −2,5 p.p. [−3,6; −1,4]. Lá, onde os evangélicos mais cresceram, o PT ganhou menos.
  - É o tipo de interação (religião × região) que a Fase 6 precisa testar.

## 3. Base proporcional do PT: "petização do lulismo"?

Perfil em z-score dentro de cada eleição (posição relativa); tabela `fase5_perfil_proporcional_z`; figura `fase5_perfil_proporcional`.

| P_PT (PT mais votado para a Câmara) | 2006 | 2010 | 2014 | 2018 | 2022 | 2026 |
|---|---|---|---|---|---|---|
| log população | +0,41 | +0,21 | +0,13 | −0,06 | −0,05 | −0,08 |
| PIB per capita | +0,20 | +0,07 | −0,05 | −0,20 | −0,03 | −0,13 |
| % VAB adm. pública | −0,21 | −0,10 | −0,06 | +0,20 | +0,03 | +0,21 |
| % negra | −0,17 | −0,01 | +0,07 | +0,21 | −0,04 | +0,26 |
| % evangélica | +0,25 | +0,05 | −0,01 | −0,25 | −0,29 | −0,34 |
| nº de AMCs (% do eleitorado) | 444 (24%) | 849 (31%) | 890 (21%) | 795 (13%) | 612 (13%) | 474 (8%) |

- Em 2006, os municípios onde o PT liderava a Câmara eram **maiores e mais ricos que a média**, com menos população negra: a "velha" base petista, urbana. Em 2026 eles são **menores, mais pobres, mais dependentes do Estado e com mais população negra**.
- Distância entre perfis (`fase5_distancias_perfis`): o P_PT de 2026 fica **mais perto do G_PT presidencial (0,91)** que do P_PT de 2006 (1,08).
- **Leitura:** a base proporcional do PT convergiu para a base territorial do lulismo, encolhendo de 24% para 8% do eleitorado. É relevante para H5, que prevê o contrário (base proporcional parecida com a velha base petista). O teste formal é o modelo do `hiato_lulista` na Fase 6.
- Ressalva: em 2006, raça e religião vêm do Censo 2010.

## 4. Antipetismo proporcional: PSDB → PSL → PL

- **PSDB (2006–2014):** perfil pouco distinto, exceto Ideb alto (z de +0,29 a +0,51).
- **PSL 2018: um ponto fora da curva.** Base muito urbana, rica, branca e evangélica, com pouca administração pública (z: log pop +0,92; PIB +0,75; adm. pública −0,87; evangélica +0,65; negra −0,65).
- **PL 2022–2026:** mesma direção do PSL, mas bem menos extremo. O perfil do PL fica **mais perto do PSDB de 2014 (distância 0,29 em 2022; 0,41 em 2026)** que do PSL de 2018 (1,26 e 1,32).
- **Leitura:** em posição relativa, o PL ocupou um território parecido com o do antigo PSDB e o ampliou muito: lidera em 1.908 AMCs (53% do eleitorado) em 2026. O PSL de 2018 foi um fenômeno metropolitano. Isso dialoga com H6 (enraizamento do antipetismo) e com o "troca de partido ou de base" da Fase 5.

## 5. Células fora da diagonal (2026)

Figura `fase5_perfil_celulas_2026`.

- **"Lula sem PT"** (G_PT com outro partido liderando a Câmara): 505 AMCs, 6% do eleitorado.
  - Mesmo perfil lulista do "Lula com PT" (77 AMCs, 1%), só que **ainda mais dependente da administração pública** (z +0,94 contra +0,66) e um pouco menor.
  - Onde o PT é mais forte, ele **quase nunca lidera a Câmara**. É o padrão "lulismo sem petismo".
  - Com 100 AMCs em que o próprio PL lidera (8% do eleitorado), o total de G_PT sem o PT liderando sobe para 605 AMCs.
- **"Bolsonarismo sem PL"** (G_OP com outro partido liderando): 444 AMCs, 5% do eleitorado.
  - Comparado ao G_OP com PL (513 AMCs, 9%): **menor e mais agropecuário** (z agro +0,55 contra +0,14).
  - É o interior agrícola onde partidos locais seguram a Câmara mesmo com o voto presidencial antipetista.

## Limitações específicas desta fase

- Sem controles: região e UF confundem tudo. Ver Fase 6.
- O VAB setorial de 2026 é de 2021 (o IBGE não divulgou 2022–2023). Em 2006, raça e religião vêm do Censo 2010. O Censo de 2018 é interpolado.
- O Ideb da AMC é ponderado pela população, não pelas matrículas.
- Faltam os indicadores de pobreza mais diretos do PLANO (CadÚnico, mortalidade infantil) e o comércio exterior. A conclusão sobre H1 ainda depende deles.
