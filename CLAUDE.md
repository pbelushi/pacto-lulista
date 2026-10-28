# pacto-lulista

Três estudos, cada um com seu plano em `docs/planos/` (`PLANO.md`, `plano2.md`, `plano3.md`). Siga o plano fase a fase; não avance de fase sem validar os checks da fase anterior (`pytest tests/`). Reprodução completa: `python -m src.pipeline` (nova etapa → acrescentar em `src/pipeline.py`).

- Nunca editar `data/raw/`; todo download é feito por script em `src/ingest/`.
- Fonte de votação: CDN do TSE (`cdn.tse.jus.br/estatistica/sead/odsele/`), sem Base dos Dados (não há projeto GCP configurado).
- Fonte indisponível → registrar em `outputs/pendencias.md` e propor fallback; nunca inventar dados.
- Comentários e textos de saída em português.
- Parâmetros (anos, limiares, partidos) ficam em `config.yaml`.
- Decisões manuais do autor ficam em `data/manual/` e nunca são sobrescritas por script.
