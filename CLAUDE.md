# pacto-lulista

Siga `PLANO.md` fase a fase; não avance de fase sem validar os checks da fase anterior (`pytest tests/`).

- Nunca editar `data/raw/`; todo download é feito por script em `src/ingest/`.
- Fonte de votação: CDN do TSE (`cdn.tse.jus.br/estatistica/sead/odsele/`), sem Base dos Dados (não há projeto GCP configurado).
- Fonte indisponível → registrar em `outputs/pendencias.md` e propor fallback; nunca inventar dados.
- Comentários e textos de saída em português.
- Parâmetros (anos, limiares, partidos) ficam em `config.yaml`.
