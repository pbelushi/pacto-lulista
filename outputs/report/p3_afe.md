# Que variáveis do V-Dem medem a polarização? Análise fatorial exploratória

Extra do estudo 3 (`docs/planos/plano3.md`). Código: `src/p3_afe.py` (etapa 3.08 do pipeline). Tabelas: `outputs/tables/p3_afe_*`.

## Pergunta e método

O estudo 3 define episódios de polarização com uma única variável, `v2cacamps`. Esta nota pergunta quais outras variáveis do V-Dem medem o mesmo construto latente.

**Universo.** Todas as variáveis codificadas por especialistas no V-Dem v16 que o modelo de medida converte em intervalo, sem as do V-Dem histórico nem as recodificações: 229 variáveis. Entram só países independentes.

**Amostras.**

| Amostra | Variáveis (cobertura ≥ 90%) | País-anos completos | Países | KMO | Fatores (análise paralela) |
|---|---|---|---|---|---|
| 1900–2025 | 138 | 10.858 | 169 | 0,98 | 12 |
| 2000–2025 (inclui sociedade digital, `v2sm*`) | 193 | 3.342 | 158 | 0,98 | 16 |

**Estimação.** Extração minres, rotação oblimin, que permite fatores correlacionados.

**Regra de identificação.** O fator de polarização é, entre os fatores com ao menos 3 variáveis salientes, aquele em que `v2cacamps` tem a maior carga. Uma variável é pertinente quando tem |carga| ≥ 0,40 nesse fator.

**Robustez.** Cinco especificações:
- a principal, com o k da análise paralela;
- k − 4;
- k + 4;
- intra-país (variáveis centradas na média de cada país), com o k da análise paralela intra-país;
- intra-país com o k da especificação principal.

## Resultado

**Núcleo estável, 1900–2025.** Cinco variáveis passam de 0,40 nas cinco especificações:

| Variável | O que mede | Carga | h² |
|---|---|---|---|
| `v2cademmob` | Mobilização de massas pró-democracia | 0,71 | 0,60 |
| `v2cagenmob` | Mobilização de massas (geral) | 0,69 | 0,58 |
| `v2caviol` | Violência política de atores não estatais | 0,65 | 0,50 |
| `v2cacamps` | Polarização política | 0,61 | 0,48 |
| `v2csantimv` | Movimentos antissistema | 0,59 | 0,46 |

`v2regoppgroupssize` (tamanho dos grupos de oposição ao regime) é limítrofe: passa de 0,40 em 3 das 5 especificações e tem carga de 0,38 na principal.

**2000–2025.** O mesmo núcleo se repete. Entram também as variáveis de sociedade digital, todas em escala invertida (valor baixo = mais polarização):

| Variável | O que mede | Carga | Especificações ≥ 0,40 |
|---|---|---|---|
| `v2smpolsoc` | Polarização da sociedade | −0,65 | 3 de 5 |
| `v2smorgviol` | Redes sociais usadas para organizar violência | −0,55 | 3 de 5 |
| `v2smpolhate` | Discurso de ódio de partidos | −0,46 | 2 de 5 |
| `v2smmefra` | Fragmentação da mídia online | −0,41 | 2 de 5 |

`v2caautmob` (mobilização pró-autocracia) só passa de 0,40 em duas especificações.

**Nenhuma variável institucional entra.** Ficam fora as variáveis de democracia eleitoral, liberal, deliberativa ou de Judiciário, e também as de partido, corrupção ou desinformação. O fator de polarização se correlaciona no máximo 0,41 com os demais fatores; a correlação mais alta é com o fator de corrupção, em 1900–2025.

## Leitura

1. **O que o fator mede.** Não é polarização pura: é polarização mais política contenciosa. Isso inclui polarização entre campos, mobilização de rua, violência política e movimentos antissistema. Na base, essas coisas andam juntas.
2. **`v2cacamps` também tem informação própria.** Sua comunalidade é de cerca de 0,5, ou seja, metade da sua variância não é compartilhada com o fator. Não por acaso, a medida fica isolada em duas situações:
   - na amostra 2000–2025 com 20 fatores, forma um fator só seu;
   - na análise intra-país de 2000–2025 com o k da análise paralela (28), nenhum fator comum reúne `v2cacamps` com outras variáveis.

   Na variação recente dentro de cada país, a polarização entre campos se move em boa parte sozinha. Com o k da especificação principal, ela volta ao núcleo, com carga de 0,41.
3. **Implicação para o estudo 3.** Um índice com o fator inteiro confundiria polarização com mobilização. Mobilização pró-democracia, por exemplo, tem a carga mais alta e captura transições de regime. Por isso a análise mantém `v2cacamps` sozinha para definir episódios.
4. **Variáveis para robustez.** As variáveis do núcleo servem para robustez ou como covariáveis de "conflito aberto":
   - `v2caviol` e `v2csantimv` em toda a série;
   - `v2smpolsoc` e `v2smpolhate` a partir de 2000, que a Fase A já previa como robustez.

## Limitações

- País-anos não são independentes. A AFE descreve covariâncias e não serve para inferência.
- Nas duas amostras, a análise paralela com amostras grandes tende a superextrair. Por isso as especificações k ± 4 estão nas tabelas.
- Os casos completos excluem as variáveis condicionais, como as de eleição, de legislatura ou de chefe de governo separado.
- As estimativas do V-Dem vêm de um modelo de medida com codificadores parcialmente comuns entre variáveis. Parte da covariância pode refletir o mesmo especialista codificando vários itens.
- O `factor_analyzer` 0.5.1 é incompatível com o scikit-learn 1.8+ numa chamada de validação. O módulo substitui essa chamada pela conversão direta dos dados; a estimação não muda.

Fonte: V-Dem v16. Elaboração própria.
