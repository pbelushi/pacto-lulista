"""Extra raça, Fase A: % preta e % parda no entorno dos locais de votação (docs/planos/prompt_raca_margem.md).

Refaz o entorno de src/pacto20_entorno.py com as colunas de cor separadas: mesma regra do pct_negra (sigilo "X" conta
como 0 na categoria; só setores com cor_total > 0; peso = população × fração da área; Voronoi e buffer de 800 m). O
Censo é sempre o de 2022, mesmo para 2010 e 2014.

Não altera data/interim/pacto20_entorno_<ano>.parquet nem pacto20_setores.parquet. Grava
data/interim/extra_raca_entorno_<ano>.parquet, com pct_negra recalculado para conferência com o publicado.

Uso: python -m src.extra_raca_entorno [ano ...]   (sem anos: 2010, 2014, 2018, 2022 e 2026; ~27 min por ano)
"""

from __future__ import annotations

import logging
import sys

import numpy as np
import pandas as pd

from src.pacto20_entorno import CHAVE, _csv, _num, entorno_ano, setores
from src.utils import caminho

log = logging.getLogger("extra_raca_entorno")
ANOS = [2010, 2014, 2018, 2022, 2026]
PRETA, PARDA = "V01318", "V01320"


def setores_raca(st=None):
    """Setores do pacto 2.0 mais a contagem de pretos e pardos e as marcas de sigilo."""
    st = setores() if st is None else st
    c = _csv("Agregados_por_setores_cor_ou_raca_BR.zip", ["CD_SETOR", PRETA, PARDA])
    c = pd.DataFrame({"CD_SETOR": c["CD_SETOR"], "cor_preta": _num(c[PRETA]).fillna(0), "cor_parda": _num(c[PARDA]).fillna(0),
                      "preta_sigilo": c[PRETA].eq("X"), "parda_sigilo": c[PARDA].eq("X")})
    return st.merge(c, on="CD_SETOR", how="left")


def main(anos: list[int]) -> None:
    st = setores_raca()
    for ano in anos:
        e = entorno_ano(ano, st)
        cols = [f"pct_{c}_{s}" for c in ["preta", "parda", "negra"] for s in ["vor", "buf"]]
        e = e[CHAVE + ["id_municipio", "ano"] + cols]
        old = pd.read_parquet(caminho("interim") / f"pacto20_entorno_{ano}.parquet").merge(e, on=CHAVE, suffixes=("_old", ""))
        for s in ["vor", "buf"]:
            dif = (old[f"pct_negra_{s}"] - old[f"pct_negra_{s}_old"]).abs().max()
            soma = (old[f"pct_preta_{s}"] + old[f"pct_parda_{s}"] - old[f"pct_negra_{s}"]).abs().max()
            log.info("%d %s: dif. máx. contra o publicado %.2e; preta + parda − negra %.2e", ano, s, dif, soma)
            assert np.nan_to_num(dif) < 1e-6 and np.nan_to_num(soma) < 1e-6
        e.to_parquet(caminho("interim") / f"extra_raca_entorno_{ano}.parquet", index=False)
        log.info("%d: %d locais", ano, len(e))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    main([int(x) for x in sys.argv[1:]] or ANOS)
