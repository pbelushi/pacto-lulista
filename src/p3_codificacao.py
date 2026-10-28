"""Fase C do plano3: pré-codificação automática dos desfechos dos episódios de polarização.

Códigos (docs/planos/plano3.md): R1 ruptura vencida por um polo; R2 cesarismo (força apresentada como acima dos polos);
P pacto; D despolarização sem ruptura; C censurado.

Ano de desfecho t: o último ano do episódio, se terminou em ruptura; se terminou por despolarização, a primeira
ruptura até 2 anos depois do fim (regra do plano), se houver. Evidência comparada entre t−1 e t+1:
regime (RoW), nome e forma de acesso do chefe de Estado (v2exnamhos, v2expathhs), dimensão militar
(v2x_ex_military), golpes (V-Dem/Powell e Thyne; e_coups antes de 1950), entradas irregulares (Archigos).

Regras do pré-código (todas as rupturas e pactos saem com revisar = sim, como pede o plano):
1. democratização sem golpe → P proposto (alternativa R1: transição por ruptura/revolução);
2. autocratização com o mesmo chefe de Estado antes e depois → R1 (o polo no poder fecha o regime: autogolpe);
3. golpe ou entrada irregular e chefe de Estado depois nomeado pelos militares ou chegado pela força, sem
   partido (v2exparhos vazio, "technical" ou "independent", rótulos do V-Dem para chefe apartidário) → R2 proposto (alternativa R1: militares alinhados a um dos polos);
4. golpe ou entrada irregular com outro chefe civil/partidário → R1 proposto (alternativa R2);
5. demais mudanças de regime → R1 proposto, a revisar;
6. sem ruptura até 2 anos depois → D (revisar = não); em curso → C.
O pré-código não usa conhecimento histórico externo: onde a base não informa, a evidência diz "a confirmar".

Conflito aberto prévio (insumo de H3), durante o episódio. Estrito: guerra civil ou tentativa de golpe fracassada
(e_pt_coup_attempts − e_pt_coup, só a partir de 1950). Amplo: também violência política frequente
(v2caviol_ord >= 3) em algum ano.

Saídas: outputs/tables/p3_codificacao.{csv,md}; outputs/report/p3_casos_para_revisao.md.
Revisão do usuário (28/10/2026): data/manual/p3_revisao_usuario.csv (cópia em UTF-8 do CSV editado no Excel,
que veio em cp1252). Nunca sobrescrita por script; ao rodar de novo, codigo_final e comentario_revisor são
reaplicados por id. Código final = codigo_final se preenchido; senão, codigo_proposto (regra do usuário).

Uso: python -m src.p3_codificacao
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from src.p3_episodios import REGIME, rupturas
from src.p3_painel import REFERENCIA
from src.utils import caminho

log = logging.getLogger("p3_codificacao")
ACESSO_HOS = {0: "pela força", 1: "nomeado por potência estrangeira", 2: "nomeado pelo partido único",
              3: "nomeado por conselho real", 4: "por sucessão hereditária", 5: "nomeado pelos militares",
              6: "eleito pelo legislativo", 7: "por eleição direta", 8: "outro"}
COLS_FINAIS = ["codigo_final", "comentario_revisor"]
REVISAO = Path(__file__).resolve().parents[1] / "data" / "manual" / "p3_revisao_usuario.csv"


def _nome(x) -> str:
    return x if isinstance(x, str) and x.strip() else "a confirmar"


def _linha(s: pd.DataFrame, ano: int) -> pd.Series | None:
    r = s[s["year"] == ano]
    return r.iloc[0] if len(r) else None


def precodificar(e: pd.DataFrame, p: pd.DataFrame) -> pd.DataFrame:
    p = p.sort_values(["country_id", "year"]).copy()
    p["ruptura"] = rupturas(p)
    out = []
    for ep in e.itertuples():
        s = p[p["country_id"] == ep.country_id]
        seg = s[s["year"].between(ep.inicio, ep.fim)]
        # conflito aberto durante o episódio (H3)
        viol = int((seg["v2caviol_ord"] >= 3).sum())
        conflito = []
        if ep.anos_guerra_civil:
            anos = seg.loc[seg["guerra_civil"] == 1, "year"].astype(int).tolist()
            conflito.append(f"guerra civil em {anos[0]}–{anos[-1]} ({len(anos)} anos)")
        if ep.tentativas_golpe_fracassadas:
            anos = seg.loc[(seg["e_pt_coup_attempts"].fillna(0) - seg["e_pt_coup"].fillna(0)) > 0, "year"].astype(int).tolist()
            conflito.append(f"tentativa(s) de golpe fracassada(s) em {', '.join(map(str, anos))}")
        if viol:
            conflito.append(f"violência política frequente em {viol} ano(s)")
        estrito = bool(ep.anos_guerra_civil or ep.tentativas_golpe_fracassadas)
        reg = {"id": f"{ep.iso}-{ep.inicio}", "pais": ep.pais, "iso": ep.iso, "regiao": ep.regiao, "inicio": ep.inicio,
               "fim": ep.fim, "duracao": ep.duracao, "termino": ep.termino, "regime_inicio": ep.regime_inicio,
               "conflito_previo": "sim" if conflito else "não", "conflito_previo_estrito": "sim" if estrito else "não",
               "evidencia_conflito": "; ".join(conflito)}
        if ep.termino == "em curso":
            out.append({**reg, "ano_desfecho": np.nan, "codigo_proposto": "C", "codigo_alternativo": "",
                        "revisar": "não", "evidencia": "episódio em curso em 2025", "quem_assumiu": "",
                        "justificativa": "censurado: polarização acima do limiar no último ano da base"})
            continue
        if ep.termino == "ruptura":
            t = ep.fim
        else:
            dep = s[(s["year"] > ep.fim) & (s["year"] <= ep.fim + 2) & (s["ruptura"] != "")]
            t = int(dep["year"].iat[0]) if len(dep) else None
        if t is None:
            out.append({**reg, "ano_desfecho": np.nan, "codigo_proposto": "D", "codigo_alternativo": "",
                        "revisar": "não", "evidencia": f"polarização abaixo do limiar a partir de {ep.fim + 1}; "
                        "sem golpe, entrada irregular ou mudança de regime até 2 anos depois",
                        "quem_assumiu": "", "justificativa": "despolarização sem ruptura (regra 6)"})
            continue
        antes, em, depois = _linha(s, t - 1), _linha(s, t), _linha(s, t + 1)
        depois = depois if depois is not None else em
        ev_t = s.loc[s["year"] == t, "ruptura"].iat[0]
        golpe = "golpe" in ev_t or "entrada irregular" in ev_t
        r0 = antes["v2x_regime"] if antes is not None else np.nan
        r1 = depois["v2x_regime"]
        hos0 = _nome(antes["v2exnamhos"]) if antes is not None else "a confirmar"
        em = em if em is not None else depois
        hos_t, hos2 = _nome(em["v2exnamhos"]), _nome(depois["v2exnamhos"])
        # quem assumiu: o chefe de Estado no ano da ruptura, se mudou; senão, o do ano seguinte
        quem = em if hos_t != hos0 else depois
        hos1 = _nome(quem["v2exnamhos"])
        acesso1 = quem["v2expathhs"]
        partido1 = quem["v2exparhos"].strip() if isinstance(quem["v2exparhos"], str) else ""
        # o V-Dem usa "technical" (e "independent") para chefe sem partido: militares, monarcas, tecnocratas
        sem_partido = partido1.lower() in ("", "technical", "independent")
        mil0 = antes["v2x_ex_military"] if antes is not None else np.nan
        mil1 = depois["v2x_ex_military"]
        militar = acesso1 in (0, 5) and sem_partido
        mesmo = hos0 != "a confirmar" and hos0 == hos1
        if pd.notna(r0) and r1 > r0 and not golpe:
            cod, alt, regra = "P", "R1", "democratização sem golpe (regra 1)"
        elif pd.notna(r0) and r1 < r0 and mesmo:
            cod, alt, regra = "R1", "R2", "autocratização com o mesmo chefe de Estado: autogolpe do polo no poder (regra 2)"
        elif golpe and militar:
            cod, alt, regra = "R2", "R1", "golpe/entrada irregular; chefe de Estado depois nomeado pelos militares ou pela força, sem partido (regra 3)"
        elif golpe:
            cod, alt, regra = "R1", "R2", "golpe/entrada irregular; novo chefe civil ou partidário (regra 4)"
        else:
            cod, alt, regra = "R1", "P", "mudança de regime sem golpe nem mesmo chefe (regra 5)"
        arch = s.loc[s["year"] == t, "arch_lider_irregular"].iat[0]
        evid = [f"{t}: {ev_t}" if ev_t else f"{t}: ruptura",
                f"regime {t - 1}: {REGIME.get(r0, 'a confirmar')} → {int(depois['year'])}: {REGIME.get(r1, 'a confirmar')}",
                f"chefe de Estado {t - 1}: {hos0} → {t}: {hos_t} → {int(depois['year'])}: {hos2}; quem assumiu: {hos1} "
                f"({ACESSO_HOS.get(acesso1, 'acesso a confirmar')}{'; sem partido' if sem_partido else '; partido: ' + partido1})",
                f"dimensão militar {mil0:.2f} → {mil1:.2f}" if pd.notna(mil0) and pd.notna(mil1) else "dimensão militar a confirmar"]
        if isinstance(arch, str) and arch:
            evid.append(f"entrada irregular (Archigos): {arch}")
        out.append({**reg, "ano_desfecho": t, "codigo_proposto": cod, "codigo_alternativo": alt, "revisar": "sim",
                    "evidencia": "; ".join(evid),
                    "quem_assumiu": f"{hos1} ({ACESSO_HOS.get(acesso1, 'acesso a confirmar')})" if hos1 != "a confirmar" else "a confirmar",
                    "justificativa": regra})
    c = pd.DataFrame(out)
    for col in COLS_FINAIS:
        c[col] = ""
    return c


def _salvar(df: pd.DataFrame, nome: str) -> None:
    df.to_csv(caminho("tables") / f"{nome}.csv", index=False, encoding="utf-8")
    (caminho("tables") / f"{nome}.md").write_text(df.to_markdown(index=False), encoding="utf-8")


def relatorio_revisao(c: pd.DataFrame) -> str:
    r = c[c["revisar"] == "sim"].copy()
    ref = {iso for _, iso, *_ in REFERENCIA}
    r["prioridade"] = np.where(r["iso"] == "BRA", 0, np.where(r["iso"].isin(ref), 1, 2))
    cont = c["codigo_proposto"].value_counts()
    linhas = [
        "# Plano3, Fase C: casos para revisão manual",
        "",
        f"*Gerado por `src/p3_codificacao.py` em 28/10/2026. {len(r)} de {len(c)} episódios marcados com `revisar = sim`.*",
        "",
        "## Como revisar",
        "",
        "- Em `outputs/tables/p3_codificacao.csv`, preencha a coluna `codigo_final` (R1, R2, P ou D) e, se quiser, "
        "`comentario_revisor`. Linha em branco = aceitar o `codigo_proposto`.",
        "- Também pode responder no chat com as correções (ex.: `CHL-1970: R1`).",
        "- O pré-código usa só as bases (V-Dem, ERT, Archigos). Nenhum fato histórico foi completado de memória; "
        "\"a confirmar\" indica lacuna da base.",
        "- **R1**: um dos polos vence (golpe, revolução, autogolpe). **R2**: força apresentada como acima dos polos "
        "(militares como \"poder moderador\", Brumário). **P**: fim negociado entre os polos. **D**: despolarização sem ruptura.",
        "",
        "## Pré-código, todos os episódios",
        "",
        "| Código | Episódios |",
        "|---|---|",
        *[f"| {k} | {int(cont.get(k, 0))} |" for k in ["R1", "R2", "P", "D", "C"]],
        "",
    ]
    for titulo, sel in [("Brasil", r["prioridade"] == 0), ("Casos de referência do plano", r["prioridade"] == 1),
                        ("Demais casos", r["prioridade"] == 2)]:
        s = r[sel].sort_values(["regiao", "pais", "inicio"]) if titulo == "Demais casos" else r[sel].sort_values(["pais", "inicio"])
        linhas += [f"## {titulo} ({len(s)})", ""]
        if titulo == "Demais casos":
            for reg, g in s.groupby("regiao", sort=False):
                linhas += [f"### {reg} ({len(g)})", "", "| Episódio | Proposto (alt.) | Conflito prévio | Evidência | Regra |",
                           "|---|---|---|---|---|"]
                linhas += [f"| {x.id}: {x.pais} {x.inicio}–{x.fim} | {x.codigo_proposto} ({x.codigo_alternativo}) | "
                           f"{x.conflito_previo} | {x.evidencia} | {x.justificativa} |" for x in g.itertuples()]
                linhas.append("")
        else:
            linhas += ["| Episódio | Proposto (alt.) | Conflito prévio | Evidência | Regra |", "|---|---|---|---|---|"]
            linhas += [f"| {x.id}: {x.pais} {x.inicio}–{x.fim} | {x.codigo_proposto} ({x.codigo_alternativo}) | "
                       f"{x.conflito_previo}{' (' + x.evidencia_conflito + ')' if x.evidencia_conflito else ''} | "
                       f"{x.evidencia} | {x.justificativa} |" for x in s.itertuples()]
            linhas.append("")
    return "\n".join(linhas)


def main() -> None:
    p = pd.read_parquet(caminho("interim") / "p3_painel.parquet")
    e = pd.read_csv(caminho("tables") / "p3_episodios.csv")
    c = precodificar(e, p)
    rev = REVISAO
    if rev.exists():
        r = pd.read_csv(rev, keep_default_na=False, encoding="utf-8-sig").set_index("id")[COLS_FINAIS]
        c = c.drop(columns=COLS_FINAIS).join(r, on="id")
        c[COLS_FINAIS] = c[COLS_FINAIS].fillna("")
        log.info("revisão do usuário reaplicada: %d códigos finais", int((c["codigo_final"] != "").sum()))
    c["codigo"] = np.where(c["codigo_final"].str.strip() != "", c["codigo_final"].str.strip(), c["codigo_proposto"])
    _salvar(c, "p3_codificacao")
    (caminho("report") / "p3_casos_para_revisao.md").write_text(relatorio_revisao(c), encoding="utf-8")
    log.info("pré-código: %s; revisar: %d", c["codigo_proposto"].value_counts().to_dict(), (c["revisar"] == "sim").sum())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    main()
