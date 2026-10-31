# Onde Lula mais cresceu entre o 1º e o 2º turno de 2026

Extra que complementa o Critério 4 do pacto 2.0 (`outputs/report/pacto20.md`, seção 4). Código: `src/extra_entre_turnos.py`. Tabelas: `outputs/tables/extra_turnos_*`.

## Resumo

Lula foi de 53,7 milhões de votos no 1º turno para 64,1 milhões no 2º, sem exterior. Flávio Bolsonaro foi de 56,0 para 59,7 milhões. Os lugares de maior crescimento de Lula têm este perfil:

- **Mais negros e mais pobres que a média**, com menos eleitores de ensino superior. Isso vale entre municípios e dentro da mesma cidade.
- **Mais jovens e com menos idosos**, com mais mulheres no eleitorado.
- **Periferias e cidades médias de regiões metropolitanas**, não o campo: menos agropecuária em todos os recortes.
- **Já eram favoráveis a Lula no 1º turno.** O crescimento reforçou bases existentes, em vez de abrir território novo.
- **O comparecimento subiu mais ali**, cerca do dobro. Flávio Bolsonaro cresceu quase o mesmo que nos demais lugares.

O dado novo mais importante é a comparação com 2022: o efeito da população negra só aparece em 2026. Em regressão por município, é +0,72 p.p. por DP em 2026 e nulo em 2022.

## Medida

**Δ Lula** = votos no 2º turno menos votos no 1º, em p.p. dos aptos, como no Critério 4. **Maior crescimento** = os lugares de maior Δ que somam 10% do eleitorado, contra os outros 90%.

**Voto disponível.** Lula só cresce onde há voto a ganhar. O ranking simples pode premiar quem tinha mais terceiros. O caso claro é Goiás: Ronaldo Caiado teve 12,3% no estado, contra 1 a 5% nas demais UFs, e isso coloca Luziânia, Águas Lindas e Aparecida de Goiânia entre as cidades de maior Δ, com Flávio crescendo ainda mais ali (+4,5 a +6,9). Por isso uso também a **taxa de captura**: Δ Lula dividido pelo voto disponível (tudo que não foi de Lula nem de Flávio no 1º turno, incluindo abstenção).

## Perfil por local de votação

Média dos locais de maior crescimento contra os demais. 77.725 locais, 2.523 municípios, 87% dos aptos.

| Variável | Brasil | Dentro do município | Decil de captura | Demais (Brasil) |
|---|---|---|---|---|
| Δ Lula (p.p.) | 10,5 | 9,2 | 9,4 | 6,3 |
| Δ Flávio Bolsonaro (p.p.) | 2,3 | 1,6 | 1,2 | 2,4 |
| Δ comparecimento (p.p.) | 3,9 | 3,1 | 3,3 | 1,7 |
| % negra no entorno | 64,2 | 63,4 | 70,1 | 52,6 |
| Renda média no entorno (R$) | 2.630 | 2.401 | 2.320 | 3.801 |
| % eleitores com superior | 6,1 | 4,9 | 6,7 | 12,4 |
| % eleitores 16–34 | 34,4 | 35,9 | 33,4 | 30,7 |
| % eleitores 60+ | 19,4 | 19,5 | 19,7 | 24,0 |
| % eleitoras | 54,2 | 53,4 | 54,0 | 53,0 |
| Lula no 1º turno (% aptos) | 39,7 | 38,8 | 47,2 | 33,2 |

A coluna "dentro do município" compara cada local com a média da própria cidade, sem efeito regional. O perfil é o mesmo, com uma diferença: densidade e % urbana deixam de distinguir os locais. Nas capitais, densidade alta explica o recorte nacional. Dentro da cidade, o que importa é renda, raça, idade e escolaridade. Com ≥ 300 aptos, os números ficam praticamente iguais.

## Perfil por município (AMC)

| Variável | Ponderado | Sem ponderar | Decil de captura | Demais (ponderado) |
|---|---|---|---|---|
| AMCs no grupo | 162 | 556 | n/d | n/d |
| Δ Lula (p.p.) | 9,7 | 8,7 | 8,6 | 6,4 |
| % negra | 69,2 | 62,3 | 70,7 | 54,8 |
| PIB per capita (R$) | 42.543 | 39.936 | 36.674 | 61.016 |
| % VAB agropecuário | 3,9 | 15,2 | 5,2 | 9,5 |
| % evangélica | 26,5 | 20,0 | 23,9 | 26,7 |
| % sem religião | 12,1 | 6,3 | 9,9 | 9,0 |
| Bolsa Família (por 100 hab.) | 9,9 | 12,6 | 13,8 | 9,3 |
| Homicídios (por 100 mil) | 28,9 | 21,7 | 35,7 | 20,1 |
| Mortalidade infantil (por mil) | 13,5 | 12,7 | 13,2 | 12,3 |
| Excesso de mortalidade 2020–21 (%) | 28,9 | 23,7 | 25,1 | 28,1 |

Na coluna "sem ponderar", os valores de comparação são outros (os 90% restantes das AMCs, sem peso): por exemplo, 55,3% de negros e 24,9% de VAB agro. Ver `extra_turnos_perfil`.

**Os dados novos acrescentam pouco.** Homicídios e mortalidade infantil são mais altos no grupo ponderado, mas isso quase desaparece sem ponderar (+0,13 e 0,00 DP). Refletem as grandes cidades do grupo, não um traço geral. Excesso de mortalidade não distingue o grupo de modo consistente; o sinal até muda entre recortes.

**Bolsa Família só distingue pela captura** (+0,81 DP). No ranking simples, é quase igual (+0,10), porque o Sudeste metropolitano entra no grupo. Isso sugere dois caminhos: mobilização em periferias metropolitanas e conversão de voto disponível em áreas pobres, sobretudo no Nordeste. Essa distinção é uma leitura descritiva, não testada à parte.

**Cidades de ≥ 100 mil aptos com maior Δ.** Salvador (+10,7), Lauro de Freitas (+10,6), Taboão da Serra (+10,1), Embu das Artes (+9,9), Francisco Morato (+9,6) e Itapecerica da Serra (+9,5). Lista completa em `extra_turnos_maiores`.

**Por UF.** Δ maior em GO, PE, PB, SP e SE. A captura é maior em PE, PB, SE e CE (0,29). GO cai para 0,22, com o efeito Caiado descontado. AC (0,05), AP (0,07) e RR (0,09) têm as menores capturas.

## Modelo por município: 2026 contra 2022

Δ Lula (p.p. dos aptos) por 1 DP, EF de UF, peso = aptos, EP por microrregião, 5.565 AMCs, com controle de voto disponível.

| Variável | 2026 | 2022 |
|---|---|---|
| % negra | +0,72*** | +0,06 |
| % evangélica | −0,43*** | −0,26*** |
| % sem religião | +0,19*** | −0,05 |
| Bolsa Família | −0,09 | −0,20*** |
| log PIB per capita | −0,16*** | −0,03 |
| % informal | −0,49*** | +0,03 |
| % VAB agro | +0,12*** | −0,03 |
| log população | +0,13*** | +0,11*** |
| Terceiros no 1º turno | +1,21*** | +0,68*** |
| Abstenção no 1º turno | +0,25*** | +0,22*** |

\*\*\* p < 0,01.

- **Raça é a principal novidade.** O coeficiente passa de nulo a +0,72.
- **Evangélicos freiam o crescimento nas duas eleições, mais em 2026.** No perfil bruto, % evangélica quase não distingue o grupo; o efeito aparece líquido das demais variáveis.
- **O informal surpreende.** Com controles, mais trabalho informal reduz o crescimento em 2026, embora a pobreza medida por PIB aumente. Isso pode refletir o peso de regiões do Norte, sem que tenha sido testado.
- **O voto disponível importa muito.** Terceiros têm o maior coeficiente da tabela. Em 2026, sem esse controle, % negra seria +0,58 e Bolsa Família −0,22 (p = 0,045).
- O sinal positivo de VAB agro só aparece com o controle de voto disponível; sem ele é nulo. Não deve ser lido como ganho de Lula no campo: no perfil, o agro é menor no grupo de maior crescimento.

## Limitações

- **Ecológico.** Descreve lugares, não eleitores. Mais comparecimento num local onde Lula cresceu não prova que os novos votantes votaram em Lula, nem que os eleitores de Caiado migraram.
- **Entorno censitário é aproximação.** O eleitor vota onde está o título, não necessariamente onde mora.
- **Locais não cobrem cidades pequenas.** A base de entorno tem 2.523 municípios; os demais estão só no nível de AMC.
- **Grupos ponderados são dominados por grandes cidades.** Por isso a coluna sem ponderar.
- **Sem dado por sexo e idade no 2º turno.** O perfil de comparecimento do TSE segue só com o 1º turno. "% eleitoras" descreve o eleitorado do local, não quem compareceu.
- **Dados de saúde.** Taxas de 2022–2024; 2024 pode ser revisado.

Fonte: TSE; IBGE, Censo 2022 por setor; DATASUS, SIM e SINASC; Atlas DH; Comex Stat. Elaboração própria.
