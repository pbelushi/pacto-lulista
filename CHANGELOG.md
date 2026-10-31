# Histórico de versões

## Não lançado

- **Estudo 1, Fase 1:** o 2º turno presidencial de 2026 passa a vir dos arquivos `*_munzona_2026` do CDN do TSE, republicados em 30–31/10/2026 (antes, do Portal Resultados). Resultados idênticos município a município; o portal fica como fallback e crosswalk. `src/p3_brasil.py` lê 2026 como os demais anos.
- **Estudo 2:** boletins de urna do 2º turno de 2026 baixados (`src/ingest/tse_bu.py`, com conferência do SHA-512) e comparados seção a seção com os arquivos usados na base (`src/pacto20_bu.py`): 499.205 seções idênticas. A base não muda.
- **Reprodutibilidade:** semente fixa nas permutações do Moran global (`src/spatial.py`, `src/p3_brasil.py`). O `z` de `fase7_espacial_moran` muda; o I e o p não.
- **Estudo 3, extra:** análise fatorial exploratória das variáveis do V-Dem ligadas à polarização (`src/p3_afe.py`, etapa 3.08; nota em `outputs/report/p3_afe.md`). Nova dependência: `factor_analyzer`.

## 1.0.0 — 28/10/2026

Primeira versão pública, para arquivamento no Zenodo.

- **Estudo 1 (pacto lulista, 2006–2026):** Fases 1–8 do `docs/planos/PLANO.md`, mais o extra de coortes etárias (Censo e TSE). Relatório em `outputs/report/relatorio.md`.
- **Estudo 2 (pacto 2.0):** Fases A–E do `docs/planos/plano2.md`. Inclui o placebo 2010–2014, a mobilização entre turnos em cinco eleições, a regressão ecológica de Goodman e o comparecimento por sexo. Relatório em `outputs/report/pacto20.md`.
- **Estudo 3 (polarização comparada):** Fases A–E do `docs/planos/plano3.md`, com a revisão manual de desfechos em `data/manual/`. Relatório em `outputs/report/p3_relatorio.md`.
- **Reprodução:**
  - `src/pipeline.py` executa as 46 etapas em ordem;
  - `src/manifesto.py` registra o SHA-256 dos dados usados;
  - `requirements.txt` fixa as versões exatas.
- **Organização:**
  - planos movidos para `docs/planos/`;
  - notas parciais substituídas pelos relatórios movidas para `outputs/report/superadas/`.
