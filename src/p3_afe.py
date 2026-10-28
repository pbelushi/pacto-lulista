"""Extra do plano3: análise fatorial exploratória (AFE) das variáveis do V-Dem ligadas à polarização.

Pergunta: além de v2cacamps, quais variáveis do V-Dem medem o mesmo construto latente da polarização?

Universo: todas as variáveis codificadas por especialistas (vartype C ou A,C no codebook v16) convertidas em
intervalo pelo modelo de medida (estimativa pontual do modelo bayesiano); exclui as do V-Dem histórico (v3*) e
as recodificações (*_rec). Países-ano independentes (v2svindep = 1). Duas amostras:
- 1900–2025: variáveis com cobertura ≥ 90% no período (as de sociedade digital, v2sm*, só existem desde 2000);
- 2000–2025: idem, o que inclui v2smpolsoc ("Polarization of society") e v2smpolhate.
Casos completos em cada amostra (variáveis condicionais, como as de eleição ou de chefe de governo separado,
ficam fora pela regra de cobertura).

Método: extração minres, rotação oblimin (fatores correlacionados), número de fatores pela análise paralela
(autovalores acima do percentil 95 de dados aleatórios do mesmo tamanho; 10 réplicas, semente fixa). O "fator
de polarização" é, entre os fatores comuns (≥ 3 variáveis com |carga| ≥ 0,40; fatores de uma ou duas variáveis
são superextração), aquele em que v2cacamps tem a maior carga absoluta; se essa carga fica abaixo de 0,40, a
especificação não tem fator de polarização. Sinais alinhados para v2cacamps > 0 (carga positiva = a variável
sobe junto com a polarização na escala original do V-Dem). Pertinente = |carga| ≥ 0,40 nesse fator.
Robustez: k da análise paralela ± 4; e AFE intra-país (variáveis centradas na média de cada país), que retira
diferenças estruturais entre países e pergunta o que varia junto com a polarização ao longo do tempo, com o k da
análise paralela intra-país e com o k da especificação principal.

Compatibilidade: factor_analyzer 0.5.1 chama sklearn.utils.check_array com um argumento removido no
scikit-learn 1.8; o módulo substitui essa chamada pela conversão direta (os dados já chegam completos).

Saídas: outputs/tables/p3_afe_{amostras,polarizacao,fatores}; p3_afe_cargas_<amostra>.csv (matriz completa da
especificação principal); p3_afe_phi_<amostra>.csv (correlações entre fatores).

Uso: python -m src.p3_afe
"""

from __future__ import annotations

import logging
import warnings

import numpy as np
import pandas as pd
import pyreadr
import factor_analyzer.factor_analyzer as _fa
from factor_analyzer import FactorAnalyzer
from factor_analyzer.factor_analyzer import calculate_kmo

from src.utils import caminho

log = logging.getLogger("p3_afe")
_fa.check_array = lambda X, **_: np.array(X, dtype=float, copy=True)

AMOSTRAS = {"1900–2025": 1900, "2000–2025": 2000}
COBERTURA = 0.90
LIMIAR = 0.40
ANCORA = "v2cacamps"
SEMENTE = 20261028
FONTE = "Fonte: V-Dem v16 (países independentes). Elaboração própria."


def _raw():
    return caminho("raw") / "p3"


def universo() -> pd.DataFrame:
    cb = pyreadr.read_r(_raw() / "vdem_codebook.RData")["codebook"]
    cb = cb[cb["vartype"].isin(["C", "A,C"]) & cb["scale"].str.contains("converted to interval", na=False)
            & ~cb["tag"].str.startswith("v3") & ~cb["tag"].str.endswith("_rec")].copy()
    cb["name"] = cb["name"].str.strip()
    cb["escala_0"] = cb["responses"].astype(str).str.extract(r"0:\s*([^.0-9]{1,80})", expand=False).str.strip()
    return cb.set_index("tag")[["name", "years", "escala_0"]]


def dados(cb: pd.DataFrame, ano0: int) -> pd.DataFrame:
    v = pyreadr.read_r(_raw() / "vdem.RData")["vdem"]
    v = v[(v["year"] >= ano0) & (v["v2svindep"] == 1)]
    cob = v[cb.index].notna().mean()
    x = v[["country_id", "year", *cob[cob >= COBERTURA].index]].dropna()
    x = x.set_index(["country_id", "year"]).astype(float)
    return x.loc[:, x.std() > 0]


def paralela(x: pd.DataFrame, reps: int = 10) -> int:
    ev = np.linalg.eigvalsh(np.corrcoef(x.values.T))[::-1]
    rng = np.random.default_rng(SEMENTE)
    sim = [np.linalg.eigvalsh(np.corrcoef(rng.standard_normal(x.shape).T))[::-1] for _ in range(reps)]
    return int(np.argmin(ev > np.percentile(sim, 95, axis=0)))


def afe(x: pd.DataFrame, k: int) -> dict:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fa = FactorAnalyzer(n_factors=k, rotation="oblimin", method="minres").fit(x.values)
    L = pd.DataFrame(fa.loadings_, index=x.columns, columns=[f"F{i + 1}" for i in range(k)])
    comuns = L.columns[L.abs().ge(LIMIAR).sum() >= 3]
    f = L.loc[ANCORA, comuns].abs().idxmax()
    L[f] *= np.sign(L.loc[ANCORA, f])
    if L.loc[ANCORA, f] < LIMIAR:
        f = None
    return {"L": L, "fator": f, "h2": pd.Series(fa.get_communalities(), index=x.columns),
            "var": fa.get_factor_variance()[2][-1], "phi": fa.phi_}


def rodar(nome: str, ano0: int, cb: pd.DataFrame) -> tuple[list[dict], pd.DataFrame, pd.DataFrame]:
    x = dados(cb, ano0)
    intra = x - x.groupby(level="country_id").transform("mean")
    intra = intra.loc[:, intra.std() > 0]
    kmo = calculate_kmo(x)[1]
    k, ki = paralela(x), paralela(intra)
    log.info("%s: %d variáveis, %d país-anos, KMO %.3f, k = %d (intra-país %d)", nome, x.shape[1], len(x), kmo, k, ki)
    espec = {"principal": (x, k), "k-4": (x, k - 4), "k+4": (x, k + 4), "intra-país": (intra, ki),
             "intra-país, k da principal": (intra, k)}
    linhas, cargas, princ = [], {}, None
    for rot, (d, kk) in espec.items():
        r = afe(d, kk)
        princ = princ or r
        c = r["L"][r["fator"]] if r["fator"] else pd.Series(np.nan, index=d.columns)
        cargas[rot] = c
        linhas.append({"amostra": nome, "especificacao": rot, "variaveis": d.shape[1], "pais_anos": len(d),
                       "paises": d.index.get_level_values(0).nunique(), "kmo": kmo if d is x else np.nan,
                       "fatores": kk, "variancia_explicada": r["var"], "fator_polarizacao": r["fator"] or "nenhum",
                       "carga_v2cacamps": c[ANCORA], "h2_v2cacamps": r["h2"][ANCORA],
                       "pertinentes": int((c.abs() >= LIMIAR).sum())})
        log.info("  %s (k=%d): fator %s, carga de v2cacamps %.2f, %d pertinentes", rot, kk, r["fator"],
                 c[ANCORA], linhas[-1]["pertinentes"])
    C = pd.DataFrame(cargas)
    perm = C.abs().ge(LIMIAR).sum(axis=1)
    pol = C[perm > 0].copy()
    pol.columns = [f"carga {c}" for c in pol.columns]
    pol.insert(0, "h2", princ["h2"].reindex(pol.index))
    pol.insert(0, "sentido", np.where(C["principal"].reindex(pol.index) > 0, "valor alto = mais polarização",
                                      "valor baixo = mais polarização"))
    pol.insert(0, "especificacoes_ge_040", perm[perm > 0])
    pol = pol.join(cb[["name", "escala_0"]]).rename(columns={"name": "nome"})
    pol.insert(0, "amostra", nome)
    pol = pol.rename_axis("variavel").reset_index()
    pol = pol.sort_values(["especificacoes_ge_040", "carga principal"], key=lambda s: -s.abs())
    # rótulo dos fatores da solução principal: três maiores cargas de cada um
    L = princ["L"]
    fat = pd.DataFrame([{"amostra": nome, "fator": f, "polarizacao": f == princ["fator"],
                         "principais_variaveis": "; ".join(f"{t} {cb.loc[t, 'name']} ({L.loc[t, f]:+.2f})"
                                                           for t in L[f].abs().nlargest(4).index)}
                        for f in L.columns])
    sufixo = str(ano0)
    L.join(cb["name"]).rename_axis("variavel").reset_index().to_csv(
        caminho("tables") / f"p3_afe_cargas_{sufixo}.csv", index=False, encoding="utf-8")
    pd.DataFrame(princ["phi"], index=L.columns, columns=L.columns).to_csv(
        caminho("tables") / f"p3_afe_phi_{sufixo}.csv", encoding="utf-8")
    return linhas, pol, fat


def _salvar(df: pd.DataFrame, nome: str, nota: str) -> None:
    df.to_csv(caminho("tables") / f"{nome}.csv", index=False, encoding="utf-8")
    md = df.to_markdown(index=False, floatfmt=".2f") + f"\n\n{nota}\n\n{FONTE}\n"
    (caminho("tables") / f"{nome}.md").write_text(md, encoding="utf-8")
    log.info("tabela %s (%d linhas)", nome, len(df))


def main() -> None:
    cb = universo()
    log.info("universo: %d variáveis de especialistas", len(cb))
    res = [rodar(n, a, cb) for n, a in AMOSTRAS.items()]
    _salvar(pd.DataFrame([l for r in res for l in r[0]]), "p3_afe_amostras",
            "AFE por amostra e especificação (minres, oblimin). Fator de polarização = maior carga absoluta de "
            "v2cacamps. Pertinentes = |carga| ≥ 0,40 nesse fator. KMO só na amostra em nível.")
    _salvar(pd.concat([r[1] for r in res], ignore_index=True), "p3_afe_polarizacao",
            "Variáveis com |carga| ≥ 0,40 no fator de polarização em ao menos uma das 5 especificações (k de cada "
            "uma em p3_afe_amostras). "
            "Sinais alinhados para v2cacamps > 0: carga positiva = a variável sobe com a polarização na escala "
            "original (escala_0 = significado do valor 0). h2 = comunalidade na especificação principal.")
    _salvar(pd.concat([r[2] for r in res], ignore_index=True), "p3_afe_fatores",
            "Fatores da especificação principal e suas quatro maiores cargas.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    main()
