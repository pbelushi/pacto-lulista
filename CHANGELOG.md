# Histórico de versões

## Não lançado

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
