"""Fase B do plano3: episódios de polarização (país-ano, 1900–2025).

Definição principal:
- acima do limiar: v2cacamps >= percentil 80 da distribuição mundial 1900–2025 (0,975 no V-Dem v16). No codebook
  a escala ordinal é 3 = "mais hostil que amistoso" e 4 = "geralmente hostil"; o p80 cai na parte alta da
  categoria 3 (a categoria 4 começa em ~1,3 na escala latente, ~p86). O p90 (≈ categoria 4) entra como robustez.
- episódio: anos consecutivos acima do limiar; um único ano abaixo não interrompe (fusão); o episódio termina
  quando há dois anos seguidos abaixo (fim = último ano acima). Duração mínima: 3 anos.
- **ruptura encerra o episódio** (decisão do usuário, 28/10/2026: no Brasil há duas rupturas, 1964 e 1984–85):
  se num ano do episódio ocorre ruptura, o episódio termina nesse ano; se a polarização segue alta, começa outro
  episódio no ano seguinte. Ruptura = golpe bem-sucedido; entrada irregular do chefe do Executivo (Archigos);
  mudança de categoria do RoW (v2x_regime), exceto entre democracia eleitoral e liberal. O início de guerra civil
  NÃO encerra o episódio: é fase de conflito aberto, não resolução (Espanha 1936 se resolve em 1939); fica
  registrado como atributo do episódio (anos de guerra civil, tentativas de golpe fracassadas), insumo de H3.
- episódios que chegam ao último ano da série do país sem ruptura são censurados (2025, ou fim do Estado).
Só Estados independentes (v2svindep = 1): país-anos coloniais ou dependentes não entram em episódios (interrompem a
contagem); o percentil do limiar é calculado também só sobre Estados independentes.
Robustez: limiar p75 e p90; duração mínima 2 e 5; v2smpolsoc (2000–2025) no lugar de v2cacamps.

Saídas: outputs/tables/p3_episodios.{csv,md}; p3_faseB_robustez; p3_faseB_referencia.

Uso: python -m src.p3_episodios
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from src.p3_painel import REFERENCIA
from src.utils import caminho

log = logging.getLogger("p3_episodios")
REGIME = {0: "autocracia fechada", 1: "autocracia eleitoral", 2: "democracia eleitoral", 3: "democracia liberal"}


def rupturas(p: pd.DataFrame) -> pd.Series:
    """Texto com as rupturas do país-ano ('' se nenhuma)."""
    p = p.sort_values(["country_id", "year"])
    g = p.groupby("country_id")
    reg0 = g["v2x_regime"].shift()
    ev = pd.DataFrame(index=p.index)
    ev["golpe"] = np.where(p["golpe"].fillna(0) > 0, "golpe", "")
    ev["irregular"] = np.where(p["arch_entrada_irregular"].fillna(0) > 0, "entrada irregular de líder", "")
    muda = p["v2x_regime"].notna() & reg0.notna() & (p["v2x_regime"] != reg0) & \
        ~(p["v2x_regime"].isin([2, 3]) & reg0.isin([2, 3]))
    ev["regime"] = np.where(muda, "regime: " + reg0.map(REGIME).fillna("") + " → " + p["v2x_regime"].map(REGIME).fillna(""), "")
    return ev.apply(lambda r: "; ".join(x for x in r if x), axis=1)


def episodios(p: pd.DataFrame, var: str = "v2cacamps", limiar: float | None = None, q: float = 0.8,
              dur_min: int = 3) -> pd.DataFrame:
    p = p.sort_values(["country_id", "year"]).copy()
    indep = p["v2svindep"] == 1
    if limiar is None:
        limiar = p.loc[indep, var].quantile(q)
    p["acima"] = (p[var] >= limiar) & indep
    p["ruptura"] = rupturas(p)
    out = []
    for cid, s in p.groupby("country_id"):
        s = s.reset_index(drop=True)
        anos, acima, rup = s["year"].values, s["acima"].values, s["ruptura"].values
        ultimo = anos[s[var].notna().values].max() if s[var].notna().any() else None
        i, n = 0, len(s)
        while i < n:
            if not acima[i]:
                i += 1
                continue
            ini = i
            j = i
            fim_por = None
            while j < n:
                if rup[j]:  # ruptura encerra o episódio no ano em que ocorre
                    fim_por = "ruptura"
                    break
                if j + 1 < n and acima[j + 1] and anos[j + 1] == anos[j] + 1:
                    j += 1
                    continue
                # um único ano abaixo, seguido de ano acima, não interrompe
                if j + 2 < n and not acima[j + 1] and acima[j + 2] and anos[j + 2] == anos[j] + 2 and not rup[j + 1]:
                    j += 2
                    continue
                break
            fim = min(j, n - 1)
            if fim_por is None:
                fim_por = "em curso" if anos[fim] == 2025 else ("fim da série" if anos[fim] == ultimo else "despolarização")
            dur = int(anos[fim] - anos[ini] + 1)
            if dur >= dur_min:
                seg = s.iloc[ini:fim + 1]
                depois = s[(s["year"] > anos[fim]) & (s["year"] <= anos[fim] + 2)]
                out.append({
                    "pais": s["country_name"].iat[0], "iso": s["country_text_id"].iat[0], "country_id": cid,
                    "regiao": s["regiao"].iat[0], "inicio": int(anos[ini]), "fim": int(anos[fim]), "duracao": dur,
                    "termino": fim_por, "censurado": fim_por in ("em curso", "fim da série"),
                    "eventos_termino": rup[fim] if fim_por == "ruptura" else "",
                    "rupturas_ate_2_anos_depois": "; ".join(f"{int(a)}: {r}" for a, r in zip(depois["year"], depois["ruptura"]) if r)
                    if fim_por == "despolarização" else "",
                    "pico": seg[var].max(), "media": seg[var].mean(),
                    "ano_pico": int(seg.loc[seg[var].idxmax(), "year"]),
                    "anos_guerra_civil": int(seg["guerra_civil"].fillna(0).sum()),
                    "tentativas_golpe_fracassadas": int((seg["e_pt_coup_attempts"].fillna(0) - seg["e_pt_coup"].fillna(0)).clip(lower=0).sum()),
                    "regime_inicio": REGIME.get(seg["v2x_regime"].iat[0], np.nan),
                    "polyarchy_inicio": seg["v2x_polyarchy"].iat[0],
                })
            i = fim + 1
    e = pd.DataFrame(out)
    e.attrs["limiar"] = float(limiar)
    return e


def salto_ruptura(p: pd.DataFrame) -> pd.DataFrame:
    """Diagnóstico de viés retrospectivo: v2cacamps médio de t−3 a t+2 em torno de rupturas (t = ano da ruptura),
    só a primeira ruptura de cada país em janelas de 6 anos."""
    p = p.sort_values(["country_id", "year"]).copy()
    p["ruptura"] = rupturas(p)
    linhas = []
    for cid, s in p.groupby("country_id"):
        s = s.set_index("year")
        ult = -99
        for t in s.index[s["ruptura"] != ""]:
            if t - ult < 6:
                continue
            ult = t
            for k in range(-3, 3):
                if t + k in s.index:
                    linhas.append({"k": k, "v2cacamps": s.at[t + k, "v2cacamps"]})
    d = pd.DataFrame(linhas)
    return d.groupby("k")["v2cacamps"].agg(media="mean", mediana="median", n="size").reset_index().rename(
        columns={"k": "anos_em_relacao_a_ruptura"})


def validar(e: pd.DataFrame) -> pd.DataFrame:
    out = []
    for nome, iso, a0, a1 in REFERENCIA:
        s = e[(e["iso"] == iso) & (e["fim"] >= a0) & (e["inicio"] <= a1)]
        out.append({"caso": nome, "capturado": len(s) > 0,
                    "episodios": "; ".join(f"{r.inicio}–{r.fim} ({r.termino}{': ' + r.eventos_termino if r.eventos_termino else ''})"
                                           for r in s.itertuples()) or "—"})
    return pd.DataFrame(out)


def _salvar(df: pd.DataFrame, nome: str) -> None:
    df.to_csv(caminho("tables") / f"{nome}.csv", index=False, encoding="utf-8")
    (caminho("tables") / f"{nome}.md").write_text(df.to_markdown(index=False, floatfmt=".3g"), encoding="utf-8")


def main() -> None:
    p = pd.read_parquet(caminho("interim") / "p3_painel.parquet")
    e = episodios(p)
    log.info("principal: limiar %.3f; %d episódios", e.attrs["limiar"], len(e))
    _salvar(e, "p3_episodios")
    _salvar(validar(e), "p3_faseB_referencia")
    _salvar(salto_ruptura(p), "p3_faseB_salto_ruptura")
    # robustez: v2smpolsoc tem sinal invertido (menor = mais polarizado): usa-se o negativo
    p["v2smpolsoc_inv"] = -p["v2smpolsoc"]
    variantes = {"principal (p80, mín. 3)": dict(), "limiar p75": dict(q=0.75), "limiar p90": dict(q=0.9),
                 "duração mínima 2": dict(dur_min=2), "duração mínima 5": dict(dur_min=5),
                 "v2smpolsoc (2000–2025, p80)": dict(var="v2smpolsoc_inv")}
    rob, refs = [], []
    for nome, kw in variantes.items():
        ev = episodios(p, **kw)
        ev.to_csv(caminho("interim") / f"p3_episodios_{nome.split(' ')[0].replace('ç', 'c').replace('ã', 'a')}_{kw.get('q', '')}{kw.get('dur_min', '')}.csv",
                  index=False, encoding="utf-8")
        cont = ev["termino"].value_counts()
        rob.append({"variante": nome, "limiar": ev.attrs["limiar"], "episodios": len(ev), "paises": ev["iso"].nunique(),
                    "duracao_mediana": ev["duracao"].median(), "pct_15_anos_ou_mais": 100 * (ev["duracao"] >= 15).mean(),
                    **{f"termino_{k}": int(cont.get(k, 0)) for k in ["ruptura", "despolarização", "em curso", "fim da série"]},
                    "referencias_capturadas": int(validar(ev)["capturado"].sum())})
        refs.append(validar(ev).set_index("caso")["capturado"].rename(nome))
    _salvar(pd.DataFrame(rob), "p3_faseB_robustez")
    _salvar(pd.concat(refs, axis=1).reset_index(), "p3_faseB_referencia_variantes")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    main()
