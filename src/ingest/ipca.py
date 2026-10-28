"""IPCA para deflacionar valores monetários (base dez/2025, docs/planos/PLANO.md Fase 3).

Tabela SIDRA 1737 "IPCA - Série histórica com número-índice..." (v2266 número-índice, dez/1993 = 100),
nível Brasil, mensal (ID conferido em 27/10/2026).

Fatores:
- `fator_anual`: índice de dez/2025 ÷ média do índice no ano t. Usado para fluxos anuais (PIB, VAB,
  exportações, renda anual): valor_real = valor_nominal_t × fator_anual_t.
- `fator_dez`: índice de dez/2025 ÷ índice de dezembro do ano t (para valores de referência de fim de ano).

Saída: data/interim/ipca.parquet (ano, fator_anual, fator_dez)
"""

from __future__ import annotations

import logging

import pandas as pd

from src.ingest.sidra import consultar
from src.utils import caminho

log = logging.getLogger("ipca")
BASE = 202512


def fatores() -> pd.DataFrame:
    d = consultar(1737, "v/2266/p/all", "indice", nivel="brasil")
    s = pd.Series(d["Valor"].values, index=d["Mês (Código)"].astype(int)).dropna()
    base = s.loc[BASE]
    anos = s.index // 100
    media = s.groupby(anos).mean()
    n = s.groupby(anos).size()
    dez = s[s.index % 100 == 12]
    df = pd.DataFrame({"ano": media.index, "fator_anual": base / media.values, "n_meses": n.values})
    df["fator_dez"] = df["ano"].map(lambda a: base / dez.get(a * 100 + 12, float("nan")))
    return df[df["ano"] >= 2000]


def main() -> None:
    df = fatores()
    log.info("IPCA: fator anual 2010 = %.3f; 2023 = %.3f; 2025 = %.3f",
             *df.set_index("ano").loc[[2010, 2023, 2025], "fator_anual"])
    df.to_parquet(caminho("interim") / "ipca.parquet", index=False)


if __name__ == "__main__":
    main()
