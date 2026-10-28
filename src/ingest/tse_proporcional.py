"""Fase 1B — voto proporcional para deputado federal, 2006–2026 (docs/planos/PLANO.md, seção 1A).

Fontes (TSE, Dados Abertos, CDN, arquivos <conjunto>_<ano>_BRASIL.csv, CD_CARGO = 6, 1º turno):
- votacao_partido_munzona: votos nominais e de legenda por partido.
  2006–2014: QT_VOTOS_NOMINAIS, QT_VOTOS_LEGENDA.
  2018–2026: QT_VOTOS_NOMINAIS_VALIDOS, QT_VOTOS_LEGENDA_VALIDOS (legenda digitada) e
  QT_TOTAL_VOTOS_LEG_VALIDOS (legenda + nominais de candidatos indeferidos convertidos em legenda).
- detalhe_votacao_munzona: denominador dos válidos = QT_VOTOS_NOMINAIS_VALIDOS + QT_TOTAL_VOTOS_LEG_VALIDOS.
  O denominador vem deste arquivo, e não da soma do arquivo de partido, porque em 2006 o arquivo
  de partido deixa sem atribuição 154.179 votos de legenda (ver outputs/pendencias.md).
- votacao_candidato_munzona: votos por candidato, para o diagnóstico de puxadores.
  2018–2026: só linhas com NM_TIPO_DESTINACAO_VOTOS = 'Válido' (QT_VOTOS_NOMINAIS_VALIDOS).

Duas versões (coluna `versao`):
- 'partido': cada partido é uma unidade (principal; comparável com 2006–2018).
- 'federacao': em 2022 e 2026, partidos da mesma federação viram uma unidade (robustez).
  Antes de 2022 é idêntica à versão 'partido'. Os votos de legenda são registrados pelo TSE no
  número do partido digitado, então a atribuição dentro da federação não é ambígua.

Saídas:
- data/interim/tse_proporcional_unidades.parquet: votos por AMC × eleição × versão × unidade
- data/interim/tse_proporcional.parquet: variáveis da seção 1A por AMC × eleição × versão
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from src.ingest.tse import _ler_brasil, colunas, tse_para_amc
from src.utils import caminho, config

log = logging.getLogger("tse_proporcional")
CARGO = 6  # Deputado Federal
PT = 13


def _partido(ano: int) -> pd.DataFrame:
    cols = colunas("votacao_partido_munzona", ano)
    if "QT_VOTOS_NOMINAIS_VALIDOS" in cols:
        mapa = {"QT_VOTOS_NOMINAIS_VALIDOS": "nominal", "QT_VOTOS_LEGENDA_VALIDOS": "legenda",
                "QT_TOTAL_VOTOS_LEG_VALIDOS": "legenda_total"}
    else:
        mapa = {"QT_VOTOS_NOMINAIS": "nominal", "QT_VOTOS_LEGENDA": "legenda"}
    base = ["NR_TURNO", "CD_CARGO", "SG_UF", "CD_MUNICIPIO", "NR_PARTIDO", "SG_PARTIDO"]
    usar = base + list(mapa) + (["NR_FEDERACAO"] if "NR_FEDERACAO" in cols else [])
    df = _ler_brasil("votacao_partido_munzona", ano, usar, cargo=CARGO, turno=1).rename(columns=mapa)
    if "legenda_total" not in df:
        df["legenda_total"] = df["legenda"]
    if "NR_FEDERACAO" not in df:
        df["NR_FEDERACAO"] = -1
    return df.rename(columns={"CD_MUNICIPIO": "cd_tse", "NR_PARTIDO": "nr_partido",
                              "SG_PARTIDO": "sg_partido", "NR_FEDERACAO": "nr_federacao"})


def _detalhe(ano: int) -> pd.DataFrame:
    base = ["NR_TURNO", "CD_CARGO", "SG_UF", "CD_MUNICIPIO"]
    q = ["QT_VOTOS_NOMINAIS_VALIDOS", "QT_TOTAL_VOTOS_LEG_VALIDOS"]
    df = _ler_brasil("detalhe_votacao_munzona", ano, base + q, cargo=CARGO, turno=1)
    df["validos"] = df[q].sum(axis=1)
    df["validos_nominais"] = df["QT_VOTOS_NOMINAIS_VALIDOS"]
    return (df.groupby("CD_MUNICIPIO")[["validos", "validos_nominais"]].sum()
            .reset_index().rename(columns={"CD_MUNICIPIO": "cd_tse"}))


def _candidatos(ano: int) -> pd.DataFrame:
    """Votos válidos por candidato × município (cd_tse)."""
    cols = colunas("votacao_candidato_munzona", ano)
    base = ["NR_TURNO", "CD_CARGO", "SG_UF", "CD_MUNICIPIO", "SQ_CANDIDATO", "NR_PARTIDO"]
    if "QT_VOTOS_NOMINAIS_VALIDOS" in cols:
        df = _ler_brasil("votacao_candidato_munzona", ano,
                         base + ["NM_TIPO_DESTINACAO_VOTOS", "QT_VOTOS_NOMINAIS_VALIDOS"], cargo=CARGO, turno=1)
        log.info("%d destinações: %s", ano, df.groupby("NM_TIPO_DESTINACAO_VOTOS")["QT_VOTOS_NOMINAIS_VALIDOS"].sum().to_dict())
        df = df[df["NM_TIPO_DESTINACAO_VOTOS"] == "Válido"].rename(columns={"QT_VOTOS_NOMINAIS_VALIDOS": "votos"})
    else:
        df = _ler_brasil("votacao_candidato_munzona", ano, base + ["QT_VOTOS_NOMINAIS"], cargo=CARGO, turno=1)
        df = df.rename(columns={"QT_VOTOS_NOMINAIS": "votos"})
    return (df.groupby(["CD_MUNICIPIO", "NR_PARTIDO", "SQ_CANDIDATO"])["votos"].sum().reset_index()
            .rename(columns={"CD_MUNICIPIO": "cd_tse", "NR_PARTIDO": "nr_partido", "SQ_CANDIDATO": "sq_candidato"}))


def _unidade(partidos: pd.DataFrame, versao: str) -> pd.Series:
    """Chave da unidade de competição: 'P13' (partido) ou 'F101' (federação)."""
    p = "P" + partidos["nr_partido"].astype(str)
    if versao == "partido":
        return p
    return p.where(partidos["nr_federacao"] <= 0, "F" + partidos["nr_federacao"].astype(str))


def _ano(ano: int, xw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    par = _partido(ano).merge(xw[["cd_tse", "id_amc"]], on="cd_tse", how="left")
    det = _detalhe(ano).merge(xw[["cd_tse", "id_amc"]], on="cd_tse", how="left")
    cand = _candidatos(ano).merge(xw[["cd_tse", "id_amc"]], on="cd_tse", how="left")
    for nome, df in [("partido", par), ("detalhe", det), ("candidato", cand)]:
        assert df["id_amc"].notna().all(), f"{ano} {nome}: código TSE sem IBGE"
    par["votos"] = par["nominal"] + par["legenda_total"]
    # Composição partido → federação do ano (um partido tem uma só federação por eleição)
    fed = par.groupby("nr_partido")["nr_federacao"].max()
    cand["nr_federacao"] = cand["nr_partido"].map(fed).fillna(-1).astype(int)
    det = det.groupby("id_amc")[["validos", "validos_nominais"]].sum()
    return par, det, cand


def _indicadores(par: pd.DataFrame, det: pd.DataFrame, cand: pd.DataFrame, ano: int, versao: str):
    anti = config()["partido_anti"][ano]
    par = par.assign(unidade=_unidade(par, versao))
    cand = cand.assign(unidade=_unidade(cand, versao))
    und = (par.groupby(["id_amc", "unidade"])[["votos", "nominal", "legenda", "legenda_total"]].sum()
           .reset_index())
    und = und[und["votos"] > 0]
    # unidade do PT e do antipetista nesta versão
    chave = {rotulo: par.loc[par["nr_partido"] == nr, "unidade"].iloc[0] for rotulo, nr in [("pt", PT), ("anti", anti)]}

    und = und.merge(det["validos"], left_on="id_amc", right_index=True)
    und["p"] = 100 * und["votos"] / und["validos"]
    und["rank"] = und.groupby("id_amc")["votos"].rank(ascending=False, method="min").astype(int)

    tot = und.groupby("id_amc")["votos"].transform("sum")
    out = pd.DataFrame(index=det.index)
    out["validos"] = det["validos"]
    out["validos_nominais"] = det["validos_nominais"]
    out["votos_partidos"] = und.groupby("id_amc")["votos"].sum()
    out["nep"] = 1 / ((und["votos"] / tot) ** 2).groupby(und["id_amc"]).sum()
    lider = und.sort_values(["id_amc", "votos"], ascending=[True, False]).groupby("id_amc").head(2)
    primeiro = lider.groupby("id_amc").nth(0).set_index("id_amc")
    segundo = lider.groupby("id_amc").nth(1).set_index("id_amc")
    out["lider"] = primeiro["unidade"]
    out["p_lider"] = primeiro["p"]
    out["p_segundo"] = segundo["p"].reindex(out.index).fillna(0)
    out["empate_lider"] = np.isclose(out["p_lider"], out["p_segundo"])

    # Puxador: candidato mais votado da unidade e a fração dos votos da unidade que ele concentra
    c = cand.groupby(["id_amc", "unidade", "sq_candidato"])["votos"].sum().reset_index()
    top = c.sort_values("votos", ascending=False).drop_duplicates(["id_amc", "unidade"])
    top = top.set_index(["id_amc", "unidade"])

    u = und.set_index(["id_amc", "unidade"])
    for rotulo in ["pt", "anti"]:
        k = chave[rotulo]
        sel = u.xs(k, level="unidade") if k in u.index.get_level_values("unidade") else u.iloc[:0].droplevel(1)
        sufixo = rotulo.upper()
        out[f"votos_{sufixo}"] = sel["votos"].reindex(out.index).fillna(0).astype(int)
        out[f"p_{sufixo}"] = 100 * out[f"votos_{sufixo}"] / out["validos"]
        out[f"leg_{sufixo}"] = 100 * sel["legenda"].reindex(out.index).fillna(0) / out["validos"]
        # sem votos: posição = (nº de unidades com voto) + 1
        n_und = u.groupby(level="id_amc").size().reindex(out.index)
        out[f"rank_{sufixo}"] = sel["rank"].reindex(out.index).fillna(n_und + 1).astype(int)
        # margem = p − maior p entre as demais unidades (negativa se não lidera)
        outros_max = np.where(out["lider"] == k, out["p_segundo"], out["p_lider"])
        out[f"margem_{sufixo}"] = out[f"p_{sufixo}"] - outros_max
        t = top.xs(k, level="unidade") if k in top.index.get_level_values("unidade") else top.iloc[:0].droplevel(1)
        out[f"puxador_{sufixo}"] = t["sq_candidato"].reindex(out.index)
        out[f"frac_puxador_{sufixo}"] = (t["votos"].reindex(out.index) / out[f"votos_{sufixo}"]).where(out[f"votos_{sufixo}"] > 0)
        out[f"dependencia_puxador_{sufixo}"] = out[f"frac_puxador_{sufixo}"].fillna(0) >= 0.5
        out[f"unidade_{sufixo}"] = k

    out = out.reset_index()
    out["ano"], out["versao"] = ano, versao
    und = und.assign(ano=ano, versao=versao)
    sg = par.drop_duplicates("nr_partido").set_index("nr_partido")["sg_partido"]
    und["sigla"] = und["unidade"].map(lambda x: sg.get(int(x[1:]), x) if x.startswith("P") else x)
    return out, und


def main() -> None:
    xw = tse_para_amc()
    saidas, unidades = [], []
    for ano in config()["anos_eleicao"]:
        par, det, cand = _ano(ano, xw)
        # check partido × candidato: votos nominais do partido = soma dos candidatos (por AMC)
        a = par.groupby(["id_amc", "nr_partido"])["nominal"].sum()
        b = cand.groupby(["id_amc", "nr_partido"])["votos"].sum()
        dif = a.sub(b, fill_value=0)
        log.info("%d: nominais partido − candidatos: total %d, pares AMC×partido com diferença %d",
                 ano, int(dif.sum()), int((dif != 0).sum()))
        pd.DataFrame({"ano": ano, "dif_nominal_partido_cand": dif}).reset_index().to_parquet(
            caminho("interim") / f"_check_partido_candidato_{ano}.parquet", index=False)
        for versao in ["partido", "federacao"]:
            out, und = _indicadores(par, det, cand, ano, versao)
            saidas.append(out)
            unidades.append(und)
        log.info("%d: %d AMCs; p_PT nacional = %.2f%%; p_ANTI = %.2f%%", ano, len(out),
                 100 * saidas[-2]["votos_PT"].sum() / saidas[-2]["validos"].sum(),
                 100 * saidas[-2]["votos_ANTI"].sum() / saidas[-2]["validos"].sum())

    df = pd.concat(saidas, ignore_index=True)
    pres = pd.read_parquet(caminho("interim") / "tse_presidencial.parquet")[["ano", "id_amc", "s_pt"]]
    df = df.merge(pres, on=["ano", "id_amc"], how="left")
    df["s_op"] = 100 - df["s_pt"]
    df["hiato_lulista"] = df["s_pt"] - df["p_PT"]
    df["hiato_anti"] = df["s_op"] - df["p_ANTI"]
    df.to_parquet(caminho("interim") / "tse_proporcional.parquet", index=False)
    pd.concat(unidades, ignore_index=True).to_parquet(
        caminho("interim") / "tse_proporcional_unidades.parquet", index=False)


if __name__ == "__main__":
    main()
