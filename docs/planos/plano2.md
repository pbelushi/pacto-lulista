Nova etapa do projeto pacto-lulista: testar se há um "pacto lulista 2.0" (base jovem, negra e urbana) usando dados intraurbanos. Siga as convenções do repositório (src/, data/raw intocado, outputs/, pendencias.md, pytest) e trabalhe em fases, mostrando os checks de cada fase antes de seguir.

## Pergunta
Entre 2018, 2022 e 2026, dentro das mesmas cidades, os locais de votação com mais eleitores jovens e mais população negra passaram a votar mais no PT, líquido de renda? Esse alinhamento é durável, se estende ao voto proporcional de esquerda e tem assinatura de mobilização entre o 1º e o 2º turno de 2026?

## Fase A — Base por local de votação
1. Baixar do TSE (Dados Abertos) os votos por seção para presidente (1º e 2º turnos) e deputado federal, em 2018, 2022 e 2026. Para 2026, se os arquivos por seção ainda não estiverem publicados, registrar em pendencias.md e rodar com 2018 e 2022, deixando o código pronto para 2026.
2. Baixar o eleitorado por local de votação, com coordenadas, e o perfil do eleitorado por seção (faixa etária, gênero, escolaridade; cor/raça se existir — verificar e registrar).
3. Agregar seções → local de votação. Chave estável entre eleições: código do local quando persistir; senão, matching por coordenadas (≤ 100 m) e endereço normalizado. Reportar taxa de match entre 2018, 2022 e 2026.
4. Geocodificar locais sem coordenadas (endereço + município). Descartar e contar os não geocodificados.
5. Checks: totais por município batem com os resultados municipais já no painel (tolerância 0,1%); nenhuma seção duplicada; % de locais com coordenada válida dentro do polígono do município (geobr).

## Fase B — Entorno censitário
1. Baixar a malha de setores censitários 2022 e os agregados por setor do Censo 2022: cor/raça, faixa etária, renda (responsável ou domicílio, o que existir), densidade, condição urbana/rural.
2. Atribuir a cada local de votação um entorno de duas formas: (a) polígonos de Voronoi dos locais recortados pelo limite municipal; (b) buffer de 800 m. Agregar os setores ponderando pela área de interseção × população.
3. Variáveis finais por local: % jovens no eleitorado (16–34, do TSE), % pretos e pardos (Censo ou TSE se houver cor/raça), renda média (log, deflacionada), densidade, distância ao centro do município, dummy de capital/região metropolitana.
4. Restringir a análise principal a municípios com ≥ 10 locais de votação (há variação intraurbana); reportar quantos municípios e qual % do eleitorado ficam.

## Fase C — Modelos (critérios do pacto 2.0)
Todos com efeito fixo de município, ponderados pelo eleitorado do local, erros agrupados por município; X padronizados dentro de cada eleição.
1. Critério 1 — associação líquida de renda: s_PT (2º turno, % válidos) ~ jovens + negros + log renda + densidade + interações jovens×renda e negros×renda. O pacto 2.0 exige efeito positivo de jovens/negros também no tercil médio e superior de renda (reportar efeitos marginais por tercil).
2. Critério 2 — tendência: modelo empilhado 2018/2022/2026 com X × ano; testar Δβ 2026−2018 e 2026−2022 para jovens e negros.
3. Critério 3 — voto proporcional: repetir com (a) p_PT e (b) bloco de esquerda para deputado federal (PT, PSOL, PCdoB, PV, Rede; versão alternativa incluindo PSB e PDT). Comparar β com os presidenciais: alinhamento ideológico se jovens/negros também puxam o bloco de esquerda; lulismo personalista se só puxam Lula.
4. Critério 4 — mobilização entre turnos de 2026: Δcomparecimento e Δ voto Lula (sobre aptos) entre 1º e 2º turno ~ mesmos X. Usar também o comparecimento por faixa etária do TSE no menor nível disponível (registrar qual). Inferência ecológica R×C (PyEI) por município grande para estimar o destino dos votos de terceiros e de abstenções do 1º turno, separando os principais terceiros candidatos.
5. Heterogeneidade: estimar o critério 1 separadamente para capitais, demais municípios de RMs e interior; e por macrorregião.

## Fase D — Robustez
- Voronoi vs buffer; sem ponderação; só capitais; excluindo locais com < 300 eleitores; Conley (2 km e 5 km) e Moran's I dos resíduos dentro dos municípios.
- Placebo: os mesmos modelos com s_PT de 2010 e 2014 por seção, se as coordenadas desses anos existirem (senão, via matching de endereço com 2018); se o padrão já existia, não é "2.0".

## Fase E — Saídas
- outputs/tables/pacto20_*.csv e .md; figuras: mapas de 3–4 capitais (SP, RJ, Salvador, BH) com s_PT por local em 2018 e 2026; gráfico de β_t de jovens e negros (presidente e bloco de esquerda) com IC 95%; efeitos marginais por tercil de renda.
- outputs/report/pacto20.md com: veredito por critério (sustentado / parcial / não sustentado), evidência central e limitações. Veredito geral: "pacto 2.0" só se os critérios 1, 2 e 3 forem sustentados; se só 1 e 4, classificar como mobilização conjuntural antibolsonarista.

## Limitações a registrar
Leitura ecológica (locais, não eleitores; o eleitor vota onde está o título, não necessariamente onde mora); entorno censitário é aproximação; idade do TSE ≠ idade do Censo; cor/raça possivelmente só via Censo; alistamento facultativo aos 16–17; geração e idade não se separam sem surveys — anotar como próximo passo o modelo idade-período-coorte com ESEB 2002–2026.

Não invente dados: se uma fonte estiver indisponível, pare, registre em pendencias.md e proponha alternativa.