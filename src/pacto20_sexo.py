"""Comparecimento por sexo entre o 1º e o 2º turno (extra do pacto 2.0).

Pergunta: o comparecimento feminino subiu mais que o masculino do 1º para o 2º turno de 2026?

1. Dado direto (TSE, perfil_comparecimento_abstencao_<ano>.zip, município × zona × sexo × faixa etária):
   comparecimento por sexo, faixa e turno. Em 2026 o arquivo (gerado em 13/10/2026) só traz o 1º turno;
   quando o TSE republicar com o 2º, a variação entre turnos sai daqui sem mudar o código.
2. Estimativa ecológica por local de votação: Δcomparecimento (p.p.) ~ fração de mulheres no eleitorado,
   EF de município, peso = aptos (com e sem controles de idade e escolaridade). O coeficiente estimaria
   Δ mulheres − Δ homens se as variações por sexo fossem constantes entre locais.
   Validação: em 2018 e 2022 o dado direto existe; a tabela compara estimativa e verdade.

Uso: python -m src.pacto20_sexo
"""

from __future__ import annotations

import logging
import zipfile

import numpy as np
import pandas as pd
import pyfixest as pf

from src.pacto20_modelos import _salvar
from src.utils import caminho

log = logging.getLogger("pacto20_sexo")
ANOS = [2018, 2022, 2026]
FAIXAS = {"16 a 34": ["16 anos", "17 anos", "18 anos", "19 anos", "20 anos", "21 a 24 anos", "25 a 29 anos",
                      "30 a 34 anos"],
          "35 a 59": ["35 a 39 anos", "40 a 44 anos", "45 a 49 anos", "50 a 54 anos", "55 a 59 anos"]}
SEXO = {"FEMININO": "mulheres", "MASCULINO": "homens"}
ESPEC = {"sem controles": "d_comp ~ f",
         "com idade e escolaridade": "d_comp ~ f + pct_jovens_16_34 + pct_60mais + pct_superior"}


def verdade(ano: int) -> pd.DataFrame:
    """Aptos e comparecimento por turno × sexo × faixa (Brasil sem exterior)."""
    mapa = {f: g for g, fs in FAIXAS.items() for f in fs}
    z = zipfile.ZipFile(caminho("raw") / "tse_secao" / "perfil_comparecimento_abstencao"
                        / f"perfil_comparecimento_abstencao_{ano}.zip")
    nomes = [n for n in z.namelist() if n.upper().endswith(".CSV")]
    br = [n for n in nomes if n.upper().endswith("_BRASIL.CSV")]
    nomes = br or [n for n in nomes if not n.upper().endswith("_ZZ.CSV")]
    partes = []
    for n in nomes:
        for ch in pd.read_csv(z.open(n), sep=";", encoding="latin1", chunksize=2_000_000,
                              usecols=["NR_TURNO", "SG_UF", "DS_GENERO", "DS_FAIXA_ETARIA", "QT_APTOS",
                                       "QT_COMPARECIMENTO"]):
            ch = ch[(ch["SG_UF"] != "ZZ") & ch["DS_GENERO"].isin(SEXO) & ~ch["DS_FAIXA_ETARIA"].str.contains("Inv", na=False)]
            ch["faixa"] = ch["DS_FAIXA_ETARIA"].str.strip().map(mapa).fillna("60 ou mais")
            ch["sexo"] = ch["DS_GENERO"].map(SEXO)
            partes.append(ch.groupby(["NR_TURNO", "sexo", "faixa"])[["QT_APTOS", "QT_COMPARECIMENTO"]].sum())
    g = pd.concat(partes).groupby(level=[0, 1, 2]).sum()
    tot = g.groupby(level=[0, 1]).sum().assign(faixa="todas").set_index("faixa", append=True)
    g = pd.concat([g, tot]).reset_index().rename(columns={"NR_TURNO": "turno"})
    g["comparecimento_pct"] = 100 * g["QT_COMPARECIMENTO"] / g["QT_APTOS"]
    w = g.pivot_table(index=["sexo", "faixa"], columns="turno", values="comparecimento_pct").add_prefix("comp_t")
    if "comp_t2" not in w:
        w["comp_t2"] = np.nan
    w["delta_t2_t1"] = w["comp_t2"] - w["comp_t1"]
    w = w.reset_index()
    w.insert(0, "ano", ano)
    log.info("verdade %d: turnos %s", ano, sorted(g["turno"].unique()))
    return w


def ecologico(ano: int) -> list[dict]:
    d = pd.read_parquet(caminho("interim") / f"pacto20_locais_{ano}.parquet")
    d = d[(d["aptos_t1"] >= 100) & (d["aptos_t2"] >= 100) & d["pct_mulheres"].notna() & d["id_municipio"].notna()].copy()
    d["d_comp"] = 100 * (d["comparecimento_t2"] / d["aptos_t2"] - d["comparecimento_t1"] / d["aptos_t1"])
    d["f"] = d["pct_mulheres"] / 100
    mu, fb = np.average(d["d_comp"], weights=d["aptos_t2"]), np.average(d["f"], weights=d["aptos_t2"])
    out = []
    for nome, fml in ESPEC.items():
        m = pf.feols(f"{fml} | id_municipio", data=d, weights="aptos_t2", vcov={"CRV1": "id_municipio"})
        b, ep = m.coef()["f"], m.se()["f"]
        out.append({"ano": ano, "especificacao": nome, "dif_mulheres_menos_homens_est": b, "ep": ep,
                    "delta_mulheres_est": mu + b * (1 - fb), "delta_homens_est": mu - b * fb,
                    "delta_medio": mu, "locais": m._N})
    return out


def main() -> None:
    v = pd.concat([verdade(a) for a in ANOS], ignore_index=True)
    _salvar(v, "extra_sexo_comparecimento",
            "Comparecimento por sexo e faixa etária, 1º e 2º turnos (TSE, Brasil sem exterior)",
            "Dado direto do TSE (perfil de comparecimento e abstenção, município × zona). "
            "Em 2026 o arquivo publicado (gerado em 13/10/2026) só traz o 1º turno.")
    e = pd.DataFrame([r for a in ANOS for r in ecologico(a)])
    t = v[v["faixa"] == "todas"].pivot(index="ano", columns="sexo", values="delta_t2_t1")
    e["dif_mulheres_menos_homens_real"] = e["ano"].map(t["mulheres"] - t["homens"])
    e["erro_estimativa"] = e["dif_mulheres_menos_homens_est"] - e["dif_mulheres_menos_homens_real"]
    _salvar(e, "extra_sexo_ecologico",
            "Variação do comparecimento entre turnos por sexo: estimativa ecológica por local × dado direto",
            "Estimativa: Δcomparecimento do local ~ fração de mulheres no eleitorado, EF de município, peso = aptos, "
            "locais com ≥ 100 aptos. 'real' vem do TSE (vazio em 2026: 2º turno não publicado). "
            "Se o erro em 2018 e 2022 é grande, a estimativa de 2026 não é confiável.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    main()
