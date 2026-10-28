"""Pacto 2.0 — Fase A: base por local de votação (2018, 2022, 2026). Plano em plano2.md.

Entradas (data/raw/tse_secao/, baixadas por src.ingest.tse_secao_download):
- votacao_secao_<ano>_BR.zip: presidente por seção, 1º e 2º turnos (NR_VOTAVEL = número do candidato;
  95 branco, 96 nulo, 97 anulado).
- votacao_secao_<ano>_<UF>.zip: deputado federal (CD_CARGO 6), 1º turno — FORA DO ESCOPO (decisão do
  usuário em 27/10/2026: só presidente); a função camara() fica no código, mas não é chamada. Partido = NR_VOTAVEL // 100
  para votos nominais (candidatos têm 4 dígitos) e o próprio número para legenda (2 dígitos).
- detalhe_votacao_secao_<ano>.zip: aptos, comparecimento, nominais, brancos e nulos por seção; presidente
  só no CSV _BR (os CSVs por UF trazem os demais cargos).
- eleitorado_local_votacao_<ano>.zip: seção → local de votação, endereço, bairro, CEP e coordenadas
  (NR_LATITUDE/NR_LONGITUDE; −1 = sem coordenada). Linhas do 1º turno.
- perfil_eleitor_secao_<ano>_<UF>.zip: eleitorado por seção × faixa etária, gênero, escolaridade e
  cor/raça. Cor/raça não existe em 2018 e, em 2026, ~70% é "não informado" (amostra AC): fica de fora;
  a composição racial do entorno vem do Censo 2022 (Fase B).
Unidade: local de votação = (município TSE, zona, NR_LOCAL_VOTACAO) no ano. Exterior (UF ZZ) excluído.

Chave entre anos (referência: locais de 2026), em ordem:
  1. mesmo (município, zona, número do local) e (distância ≤ 100 m, ou endereço ou nome normalizado igual);
  2. local de 2026 mais próximo no mesmo município, a ≤ 100 m;
  3. endereço normalizado igual no mesmo município.
Locais sem coordenada não são geocodificados (decisão do usuário, 27/10/2026): ficam na base com
coordenada ausente e são contados; só entram no passo 1 ou 3 do matching.

Saídas:
- data/interim/pacto20_locais_<ano>.parquet — uma linha por local: votos, comparecimento, perfil etário
- data/interim/pacto20_match.parquet — chave estável (local_2026) para locais de 2018 e 2022
- outputs/tables/pacto20_faseA_*.csv/.md — taxas de match, cobertura de coordenadas, checks
"""

from __future__ import annotations

import logging
import re
import unicodedata
import zipfile

import numpy as np
import pandas as pd

from src.ingest.tse import crosswalk
from src.ingest.tse_secao_download import UFS, pasta
from src.utils import caminho, config

log = logging.getLogger("pacto20_base")
ANOS = [2018, 2022, 2026]
CHAVE = ["cd_mun_tse", "nr_zona", "nr_local"]
SECAO = ["cd_mun_tse", "nr_zona", "nr_secao"]
# partidos do voto proporcional (bloco de esquerda do plano: PT, PSOL, PCdoB, PV, Rede; ampliado: + PSB, PDT)
PARTIDOS = {13: "PT", 50: "PSOL", 65: "PCdoB", 43: "PV", 18: "REDE", 40: "PSB", 12: "PDT", 17: "PSL", 22: "PL"}
JOVENS = ["16 anos", "17 anos", "18 anos", "19 anos", "20 anos", "21 a 24 anos", "25 a 29 anos", "30 a 34 anos"]
CHUNK = 4_000_000


def _csvs(z: zipfile.ZipFile, so_br: bool | None = None) -> list[str]:
    n = [x for x in z.namelist() if x.lower().endswith(".csv")]
    nac = lambda x: x.upper().endswith(("_BR.CSV", "_BRASIL.CSV"))  # noqa: E731 — arquivo nacional
    if so_br is True:
        return [x for x in n if nac(x)]
    if so_br is False:
        return [x for x in n if not nac(x)]
    return n


def _ler(z: zipfile.ZipFile, arq: str, usecols: list[str], filtro=None):
    """Lê um CSV do TSE em blocos, aplica `filtro` e devolve a concatenação (sem exterior)."""
    partes = []
    for ch in pd.read_csv(z.open(arq), sep=";", encoding="latin-1", usecols=usecols, chunksize=CHUNK,
                          dtype={"SG_UF": str}, low_memory=False):
        if "SG_UF" in ch:
            ch = ch[ch["SG_UF"] != "ZZ"]
        if filtro is not None:
            ch = filtro(ch)
        partes.append(ch)
    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame(columns=usecols)


def _ren(d: pd.DataFrame) -> pd.DataFrame:
    return d.rename(columns={"CD_MUNICIPIO": "cd_mun_tse", "NR_ZONA": "nr_zona", "NR_SECAO": "nr_secao",
                             "NR_LOCAL_VOTACAO": "nr_local", "NR_TURNO": "turno"})


# ---------------------------------------------------------------- presidente
def presidente(ano: int) -> pd.DataFrame:
    """Votos por seção × turno, uma coluna por candidato (c_<número>) + brancos e nulos."""
    z = zipfile.ZipFile(pasta("votacao_secao") / f"votacao_secao_{ano}_BR.zip")
    cols = ["SG_UF", "NR_TURNO", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "CD_CARGO", "NR_VOTAVEL", "QT_VOTOS",
            "NR_LOCAL_VOTACAO"]
    d = _ren(_ler(z, _csvs(z)[0], cols, lambda c: c[c["CD_CARGO"] == 1]))
    dup = d.duplicated(SECAO + ["turno", "NR_VOTAVEL"]).sum()
    w = d.pivot_table(index=SECAO + ["nr_local", "turno"], columns="NR_VOTAVEL", values="QT_VOTOS",
                      aggfunc="sum", fill_value=0)
    w.columns = [f"c_{c}" for c in w.columns]
    w = w.rename(columns={"c_95": "brancos", "c_96": "nulos", "c_97": "anulados"}).reset_index()
    w.attrs["linhas_duplicadas"] = int(dup)
    return w


def detalhe(ano: int) -> pd.DataFrame:
    z = zipfile.ZipFile(pasta("detalhe_votacao_secao") / f"detalhe_votacao_secao_{ano}.zip")
    cols = ["SG_UF", "NR_TURNO", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "CD_CARGO", "QT_APTOS",
            "QT_COMPARECIMENTO", "QT_ABSTENCOES", "QT_VOTOS_NOMINAIS", "QT_VOTOS_BRANCOS", "QT_VOTOS_NULOS",
            "NR_LOCAL_VOTACAO"]
    # presidente: o _BR.csv; 2022+ também têm _BRASIL.csv (todos os cargos) — usar só um dos dois
    nac = _csvs(z, so_br=True)
    arqs = [x for x in nac if x.upper().endswith("_BR.CSV")][:1] or nac[:1] or _csvs(z)
    d = pd.concat([_ler(z, a, cols, lambda c: c[c["CD_CARGO"] == 1]) for a in arqs], ignore_index=True)
    # o número do local no detalhe difere do da votação em ~3% das seções: casar só por seção e turno
    d = _ren(d).drop(columns=["CD_CARGO", "SG_UF", "nr_local"])
    d.columns = [c.lower().replace("qt_votos_", "").replace("qt_", "") for c in d.columns]
    return d


# ---------------------------------------------------------------- deputado federal
def camara(ano: int) -> pd.DataFrame:
    """Votos válidos para deputado federal por local × partido (1º turno)."""
    partes, dups = [], 0
    for uf in UFS:
        z = zipfile.ZipFile(pasta("votacao_secao") / f"votacao_secao_{ano}_{uf}.zip")
        cols = ["SG_UF", "NR_TURNO", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "CD_CARGO", "NR_VOTAVEL", "QT_VOTOS",
                "NR_LOCAL_VOTACAO"]
        d = _ren(_ler(z, _csvs(z)[0], cols, lambda c: c[(c["CD_CARGO"] == 6) & (c["NR_TURNO"] == 1)]))
        dups += int(d.duplicated(SECAO + ["NR_VOTAVEL"]).sum())
        d = d[~d["NR_VOTAVEL"].isin([95, 96, 97])]
        d["partido"] = np.where(d["NR_VOTAVEL"] >= 1000, d["NR_VOTAVEL"] // 100, d["NR_VOTAVEL"])
        partes.append(d.groupby(CHAVE + ["partido"])["QT_VOTOS"].sum())
        log.info("câmara %d %s: %s votos válidos", ano, uf, f"{d['QT_VOTOS'].sum():,}")
    w = pd.concat(partes).unstack("partido", fill_value=0)
    out = pd.DataFrame({"validos_camara": w.sum(axis=1)})
    for num, sigla in PARTIDOS.items():
        out[f"cam_{sigla}"] = w[num] if num in w.columns else 0
    out = out.reset_index()
    out.attrs["linhas_duplicadas"] = dups
    return out


# ---------------------------------------------------------------- locais e perfil
def secoes_cadastro(ano: int) -> pd.DataFrame:
    """Cadastro de seções (1º turno). O número do local usado nos resultados é NR_LOCAL_VOTACAO_ORIGINAL
    (bate com o arquivo de votação em 100% das seções de 2018); NR_LOCAL_VOTACAO difere em ~0,5%
    (seções realocadas depois) e é guardado como nr_local_atual. Coordenadas, nome e endereço do cadastro."""
    z = zipfile.ZipFile(pasta("eleitorado_locais_votacao") / f"eleitorado_local_votacao_{ano}.zip")
    cols = ["NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "NR_LOCAL_VOTACAO",
            "NR_LOCAL_VOTACAO_ORIGINAL", "NM_LOCAL_VOTACAO_ORIGINAL", "DS_ENDERECO_LOCVT_ORIGINAL",
            "NM_BAIRRO", "NR_CEP", "NR_LATITUDE", "NR_LONGITUDE", "QT_ELEITOR_SECAO"]
    # 2018/2022: um CSV nacional; 2026: um por UF (+ _BR e _ZZ) → usa o _BR se houver, senão todos
    arqs = _csvs(z, so_br=True) or [a for a in _csvs(z) if not a.upper().endswith("_ZZ.CSV")]
    d = pd.concat([_ler(z, a, cols, lambda c: c[pd.to_numeric(c["NR_TURNO"], errors="coerce") == 1]) for a in arqs],
                  ignore_index=True)
    d = d.rename(columns={"NR_LOCAL_VOTACAO": "nr_local_atual", "NR_LOCAL_VOTACAO_ORIGINAL": "NR_LOCAL_VOTACAO",
                          "NM_LOCAL_VOTACAO_ORIGINAL": "NM_LOCAL_VOTACAO", "DS_ENDERECO_LOCVT_ORIGINAL": "DS_ENDERECO"})
    return _ren(d)


def locais(ano: int) -> pd.DataFrame:
    d = secoes_cadastro(ano)
    for c in ["NR_LATITUDE", "NR_LONGITUDE"]:  # 2026 usa vírgula decimal
        d[c] = pd.to_numeric(d[c].astype(str).str.replace(",", ".", regex=False), errors="coerce")
    ruim = (d["NR_LATITUDE"].abs() < 0.01) | (d["NR_LATITUDE"] == -1) | (d["NR_LONGITUDE"] == -1) | \
        ~d["NR_LATITUDE"].between(-34, 6) | ~d["NR_LONGITUDE"].between(-75, -28)
    d.loc[ruim, ["NR_LATITUDE", "NR_LONGITUDE"]] = np.nan
    g = d.groupby(CHAVE)
    out = g.agg(nm_local=("NM_LOCAL_VOTACAO", "first"), endereco=("DS_ENDERECO", "first"),
                bairro=("NM_BAIRRO", "first"), cep=("NR_CEP", "first"), sg_uf=("SG_UF", "first"),
                lat=("NR_LATITUDE", "median"), lon=("NR_LONGITUDE", "median"),
                n_secoes=("nr_secao", "nunique"), eleitores_cadastro=("QT_ELEITOR_SECAO", "sum")).reset_index()
    # seções cujo local mudou depois da eleição: coordenada do cadastro pode ser a do novo local
    real = d[d["nr_local_atual"] != d["nr_local"]].groupby(CHAVE).size().rename("secoes_realocadas")
    out = out.merge(real.reset_index(), on=CHAVE, how="left")
    out["secoes_realocadas"] = out["secoes_realocadas"].fillna(0).astype(int)
    out.attrs["secoes_duplicadas"] = int(d.duplicated(SECAO).sum())
    return out


def perfil(ano: int) -> pd.DataFrame:
    partes = []
    for uf in UFS:
        z = zipfile.ZipFile(pasta("perfil_eleitor_secao") / f"perfil_eleitor_secao_{ano}_{uf}.zip")
        arq = _csvs(z)[0]
        cab = z.open(arq).readline().decode("latin-1")
        qt = "QT_ELEITORES" if '"QT_ELEITORES"' in cab else "QT_ELEITORES_PERFIL"
        cols = ["CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "DS_FAIXA_ETARIA", "DS_GRAU_ESCOLARIDADE",
                "DS_GENERO", qt]
        d = _ren(_ler(z, arq, cols)).rename(columns={qt: "n"})
        d["DS_FAIXA_ETARIA"] = d["DS_FAIXA_ETARIA"].str.strip()
        d["jovem"] = d["DS_FAIXA_ETARIA"].isin(JOVENS)
        d["j1624"] = d["DS_FAIXA_ETARIA"].isin(JOVENS[:6])
        d["sup"] = d["DS_GRAU_ESCOLARIDADE"].str.strip().str.upper().eq("SUPERIOR COMPLETO")
        d["fem"] = d["DS_GENERO"].str.strip().str.upper().eq("FEMININO")
        idade = d["DS_FAIXA_ETARIA"].str.extract(r"^(\d+)")[0].astype(float)
        d["v60"] = idade >= 60
        agg = {"eleitores_perfil": d.groupby(SECAO)["n"].sum()}
        for k in ["jovem", "j1624", "sup", "fem", "v60"]:
            agg[k] = d["n"].where(d[k], 0).groupby([d[c] for c in SECAO]).sum()
        partes.append(pd.DataFrame(agg))
    # seção → local (número original) pelo cadastro
    p = pd.concat(partes).reset_index()
    cad = secoes_cadastro(ano)[SECAO + ["nr_local"]]
    p = p.merge(cad, on=SECAO, how="left")
    log.info("perfil %d: %.3f%% do eleitorado em seções fora do cadastro", ano,
             100 * p.loc[p["nr_local"].isna(), "eleitores_perfil"].sum() / p["eleitores_perfil"].sum())
    p = p.dropna(subset=["nr_local"]).astype({"nr_local": int}).groupby(CHAVE).sum(numeric_only=True).drop(
        columns=["nr_secao"])
    out = pd.DataFrame({"eleitores_perfil": p["eleitores_perfil"]})
    for k, nome in [("jovem", "pct_jovens_16_34"), ("j1624", "pct_jovens_16_24"), ("sup", "pct_superior"),
                    ("fem", "pct_mulheres"), ("v60", "pct_60mais")]:
        out[nome] = 100 * p[k] / p["eleitores_perfil"]
    return out.reset_index()


# ---------------------------------------------------------------- base do ano
def base_ano(ano: int) -> pd.DataFrame:
    pres = presidente(ano)
    dup_pres = pres.attrs.get("linhas_duplicadas", 0)
    det = detalhe(ano).drop(columns=["brancos", "nulos"])  # brancos e nulos já vêm dos votos (95/96)
    dup_det = int(det.duplicated(SECAO + ["turno"]).sum())
    pres = pres.merge(det, on=SECAO + ["turno"], how="outer", indicator=True)
    sem_det = int((pres["_merge"] != "both").sum())
    pres = pres.drop(columns="_merge")
    # seções só do detalhe (sem votos apurados) não têm nr_local: vem do cadastro, para não perder os aptos
    cad = secoes_cadastro(ano)[SECAO + ["nr_local"]].rename(columns={"nr_local": "nr_local_cad"})
    pres = pres.merge(cad, on=SECAO, how="left")
    pres["nr_local"] = pres["nr_local"].fillna(pres["nr_local_cad"])
    pres = pres.drop(columns="nr_local_cad").dropna(subset=["nr_local"]).astype({"nr_local": int})
    cand = [c for c in pres.columns if c.startswith("c_")]
    agg = pres.groupby(CHAVE + ["turno"])[cand + ["aptos", "comparecimento", "abstencoes", "nominais"]].sum()
    t1 = agg.xs(1, level="turno").add_suffix("_t1")
    t2 = agg.xs(2, level="turno")[["c_13", f"c_{config()['presidencial'][ano]['op']}", "aptos", "comparecimento",
                                   "abstencoes", "nominais"]].add_suffix("_t2")
    t1 = t1.loc[:, (t1 != 0).any()]
    out = t1.join(t2, how="outer").reset_index()
    # deputado federal fora do escopo por decisão do usuário (27/10/2026): só presidente; camara() fica disponível
    out = out.merge(perfil(ano), on=CHAVE, how="left")
    loc = locais(ano)
    out = out.merge(loc, on=CHAVE, how="left")
    xw = crosswalk()[["cd_tse", "id_municipio"]].rename(columns={"cd_tse": "cd_mun_tse"})
    out = out.merge(xw, on="cd_mun_tse", how="left")
    out["ano"] = ano
    out.attrs.update({"pres_linhas_duplicadas": dup_pres, "detalhe_secoes_duplicadas": dup_det,
                      "secoes_sem_detalhe": sem_det, "locais_secoes_duplicadas": loc.attrs.get("secoes_duplicadas", 0)})
    log.info("%d: %d locais; %s aptos (2º turno)", ano, len(out), f"{out['aptos_t2'].sum():,.0f}")
    return out


# ---------------------------------------------------------------- matching entre anos
def normalizar(s: pd.Series) -> pd.Series:
    def f(x):
        if not isinstance(x, str):
            return ""
        x = unicodedata.normalize("NFKD", x).encode("ascii", "ignore").decode().upper()
        x = re.sub(r"[^A-Z0-9 ]", " ", x)
        for a, b in [(r"\bR\b", "RUA"), (r"\bAV\b", "AVENIDA"), (r"\bTRAV\b|\bTV\b", "TRAVESSA"),
                     (r"\bPCA\b|\bPC\b", "PRACA"), (r"\bROD\b", "RODOVIA"), (r"\bEST\b", "ESTRADA"),
                     (r"\bS N\b|\bSN\b", "SN"), (r"\bN\b|\bNO\b|\bNUMERO\b", "")]:
            x = re.sub(a, b, x)
        return re.sub(r"\s+", " ", x).strip()
    return s.map(f)


def _dist_m(lat1, lon1, lat2, lon2):
    r = 6_371_000
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def casar(a: pd.DataFrame, ref: pd.DataFrame, raio: float = 100.0) -> pd.DataFrame:
    """Casa os locais de `a` com os de `ref` (mesmo município). Devolve CHAVE de `a` + chave de ref + método."""
    from sklearn.neighbors import BallTree

    a, ref = a.copy(), ref.copy()
    for d in (a, ref):
        d["end_n"] = normalizar(d["endereco"])
        d["nome_n"] = normalizar(d["nm_local"])
    ref = ref.reset_index(drop=True)
    refk = ref[CHAVE].astype(int).astype(str).agg("-".join, axis=1)
    out = pd.DataFrame({"chave": a[CHAVE].astype(int).astype(str).agg("-".join, axis=1), "ref": None, "metodo": None})
    # 1. mesmo código + (≤ raio ou endereço/nome igual)
    m = a.reset_index().merge(ref.reset_index(), on=CHAVE, suffixes=("", "_r"))
    d = _dist_m(m["lat"], m["lon"], m["lat_r"], m["lon_r"])
    ok = (d <= raio) | (m["end_n"] == m["end_n_r"]) & (m["end_n"] != "") | (m["nome_n"] == m["nome_n_r"])
    out.loc[m.loc[ok, "index"].values, "ref"] = refk.loc[m.loc[ok, "index_r"]].values
    out.loc[m.loc[ok, "index"].values, "metodo"] = "código"
    # 2. coordenada ≤ raio no mesmo município
    falta = out["ref"].isna() & a["lat"].notna()
    rc = ref[ref["lat"].notna()]
    if falta.any() and len(rc):
        tree = BallTree(np.radians(rc[["lat", "lon"]].values), metric="haversine")
        q = a.loc[falta]
        dist, idx = tree.query(np.radians(q[["lat", "lon"]].values), k=5)
        for i, (row, dd, ii) in enumerate(zip(q.itertuples(), dist, idx)):
            for dk, ik in zip(dd * 6_371_000, ii):
                if dk > raio:
                    break
                cand = rc.iloc[ik]
                if cand["cd_mun_tse"] == row.cd_mun_tse:
                    out.loc[row.Index, ["ref", "metodo"]] = [refk.loc[cand.name], "coordenada"]
                    break
    # 3. endereço normalizado igual no mesmo município
    falta = out["ref"].isna() & (a["end_n"] != "")
    if falta.any():
        e = ref[ref["end_n"] != ""].drop_duplicates(["cd_mun_tse", "end_n"])
        m = a.loc[falta].reset_index().merge(e.reset_index(), on=["cd_mun_tse", "end_n"], suffixes=("", "_r"))
        out.loc[m["index"].values, "ref"] = refk.loc[m["index_r"]].values
        out.loc[m["index"].values, "metodo"] = "endereço"
    return out


def taxas_match(bases: dict[int, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    ref = bases[max(bases)]
    linhas, tabs = [], []
    pares = [(a, max(bases)) for a in bases if a != max(bases)] + [(min(bases), sorted(bases)[1])]
    for a, b in pares:
        m = casar(bases[a], bases[b])
        m["ano"], m["ano_ref"] = a, b
        tabs.append(m)
        el = bases[a]["aptos_t2"].fillna(0).values
        for met in ["código", "coordenada", "endereço"]:
            s = (m["metodo"] == met).values
            linhas.append({"ano": a, "referencia": b, "metodo": met, "pct_locais": 100 * s.mean(),
                           "pct_eleitorado": 100 * el[s].sum() / el.sum()})
        s = m["ref"].notna().values
        linhas.append({"ano": a, "referencia": b, "metodo": "total", "pct_locais": 100 * s.mean(),
                       "pct_eleitorado": 100 * el[s].sum() / el.sum()})
    return pd.DataFrame(linhas), pd.concat(tabs, ignore_index=True)


def herdar_coordenadas(bases: dict[int, pd.DataFrame], m: pd.DataFrame) -> None:
    """Locais sem coordenada no ano herdam a do mesmo local em outro ano (só dados do TSE; sem
    geocodificação externa), quando o casamento foi por código ou endereço: 2018 e 2022 ← 2026;
    o que faltar em 2018 ← 2022. Marca a origem em `coord_origem`."""
    chave = lambda d: d[CHAVE].astype(int).astype(str).agg("-".join, axis=1)  # noqa: E731
    for ano, b in bases.items():
        b["coord_origem"] = np.where(b["lat"].notna(), f"tse_{ano}", None)
    for ano, ref in [(2018, 2026), (2022, 2026), (2018, 2022)]:
        b, r = bases[ano], bases[ref]
        mm = m[(m["ano"] == ano) & (m["ano_ref"] == ref) & m["metodo"].isin(["código", "endereço"])]
        rc = r.assign(k=chave(r)).set_index("k")[["lat", "lon", "coord_origem"]].dropna(subset=["lat"])
        alvo = b.assign(k=chave(b))["k"].map(dict(zip(mm["chave"], mm["ref"])))
        pode = b["lat"].isna() & alvo.isin(rc.index)
        b.loc[pode, ["lat", "lon"]] = rc.loc[alvo[pode], ["lat", "lon"]].values
        b.loc[pode, "coord_origem"] = rc.loc[alvo[pode], "coord_origem"].values
        log.info("%d ← %d: %d locais herdaram coordenada", ano, ref, int(pode.sum()))


def placebo(anos: tuple[int, ...] = (2010, 2014)) -> None:
    """Bases do placebo da Fase D (2010 e 2014): mesma construção da Fase A; locais sem coordenada
    herdam a do local de 2018 casado por código ou endereço (só dados do TSE)."""
    ref = pd.read_parquet(caminho("interim") / "pacto20_locais_2018.parquet")
    chave = lambda d: d[CHAVE].astype(int).astype(str).agg("-".join, axis=1)  # noqa: E731
    rc = ref.assign(k=chave(ref)).set_index("k")[["lat", "lon"]].dropna()
    tx, chk, cob = [], [], []
    for ano in anos:
        b = base_ano(ano)
        m = casar(b, ref)
        m["ano"], m["ano_ref"] = ano, 2018
        el = b["aptos_t2"].fillna(0).values
        for met in ["código", "coordenada", "endereço", "total"]:
            s = (m["ref"].notna() if met == "total" else m["metodo"] == met).values
            tx.append({"ano": ano, "referencia": 2018, "metodo": met, "pct_locais": 100 * s.mean(),
                       "pct_eleitorado": 100 * el[s].sum() / el.sum()})
        b["coord_origem"] = np.where(b["lat"].notna(), f"tse_{ano}", None)
        alvo = pd.Series(np.where(m["metodo"].isin(["código", "endereço"]), m["ref"], None), index=b.index)
        pode = b["lat"].isna() & alvo.isin(rc.index)
        b.loc[pode, ["lat", "lon"]] = rc.loc[alvo[pode], ["lat", "lon"]].values
        b.loc[pode, "coord_origem"] = "tse_2018"
        log.info("%d ← 2018: %d locais herdaram coordenada", ano, int(pode.sum()))
        b.to_parquet(caminho("interim") / f"pacto20_locais_{ano}.parquet", index=False)
        m.to_parquet(caminho("interim") / f"pacto20_match_placebo_{ano}.parquet", index=False)
        chk.append(check_municipal(b, ano))
        cob.append(check_coordenadas(b))
    for n, df in [("match", pd.DataFrame(tx)), ("check_municipal", pd.concat(chk)), ("coordenadas", pd.DataFrame(cob))]:
        df.to_csv(caminho("tables") / f"pacto20_faseD_placebo_{n}.csv", index=False, encoding="utf-8")
        (caminho("tables") / f"pacto20_faseD_placebo_{n}.md").write_text(df.to_markdown(index=False, floatfmt=".4g"),
                                                                          encoding="utf-8")


# ---------------------------------------------------------------- checks
def check_municipal(b: pd.DataFrame, ano: int) -> pd.DataFrame:
    """Totais por AMC (2º turno) × painel (tse_presidencial). Diferença relativa."""
    from src.ingest.tse import tse_para_amc

    amc = tse_para_amc()[["cd_tse", "id_amc"]].rename(columns={"cd_tse": "cd_mun_tse"})
    op = config()["presidencial"][ano]["op"]
    s = b.merge(amc, on="cd_mun_tse").groupby("id_amc")[["c_13_t2", f"c_{op}_t2", "nominais_t2", "aptos_t2"]].sum()
    p = pd.read_parquet(caminho("interim") / "tse_presidencial.parquet")
    p = p[p["ano"] == ano].set_index("id_amc")
    m = s.join(p[["votos_pt", "votos_op", "validos", "aptos"]], how="outer")
    out = pd.DataFrame({"dif_pt": m["c_13_t2"] / m["votos_pt"] - 1, "dif_op": m[f"c_{op}_t2"] / m["votos_op"] - 1,
                        "dif_validos": m["nominais_t2"] / m["validos"] - 1, "dif_aptos": m["aptos_t2"] / m["aptos"] - 1})
    return out.assign(ano=ano).reset_index()


def check_coordenadas(b: pd.DataFrame) -> dict:
    """% de locais com coordenada e % dentro do polígono do próprio município (geobr 2022 simplificado;
    também com tolerância de 500 m, porque a malha simplificada desloca as bordas)."""
    import geopandas as gpd

    from src.ingest.malhas import baixar_malha

    mal = baixar_malha()[["code_muni", "geometry"]].to_crs(5880)
    mal["id_municipio"] = mal["code_muni"].astype(int)
    c = b[b["lat"].notna() & b["id_municipio"].notna()]
    pts = gpd.GeoDataFrame(c[["id_municipio"]].astype(int), geometry=gpd.points_from_xy(c["lon"], c["lat"]),
                           crs=4326).to_crs(5880)
    geo = mal.set_index("id_municipio").geometry.reindex(pts["id_municipio"].values)
    dentro = np.array([g is not None and g.contains(p) for g, p in zip(geo.values, pts.geometry.values)])
    perto = np.array([g is not None and g.distance(p) <= 500 for g, p in zip(geo.values, pts.geometry.values)])
    el = b["aptos_t2"].fillna(0)
    return {"ano": int(b["ano"].iloc[0]), "locais": len(b), "pct_locais_com_coord": 100 * b["lat"].notna().mean(),
            "pct_eleitorado_com_coord": 100 * el[b["lat"].notna()].sum() / el.sum(),
            "pct_com_coord_dentro_municipio": 100 * dentro.mean(),
            "pct_com_coord_ate_500m_do_municipio": 100 * perto.mean()}


def main(recalcular: list[int] | None = None) -> None:
    """recalcular: anos a reconstruir (padrão: todos); os demais são lidos do parquet já salvo."""
    bases = {}
    for ano in ANOS:
        arq = caminho("interim") / f"pacto20_locais_{ano}.parquet"
        if recalcular is None or ano in recalcular or not arq.exists():
            b = base_ano(ano)
            b.to_parquet(arq, index=False)
            pd.DataFrame([b.attrs]).to_parquet(arq.with_suffix(".attrs.parquet"), index=False)
        else:
            b = pd.read_parquet(arq)
            att = arq.with_suffix(".attrs.parquet")
            b.attrs = pd.read_parquet(att).iloc[0].to_dict() if att.exists() else {}
        bases[ano] = b
    tx, m = taxas_match(bases)
    m.to_parquet(caminho("interim") / "pacto20_match.parquet", index=False)
    herdar_coordenadas(bases, m)
    for ano, b in bases.items():
        att = b.attrs
        b.to_parquet(caminho("interim") / f"pacto20_locais_{ano}.parquet", index=False)
        b.attrs = att
    tab = lambda df, n: (df.to_csv(caminho("tables") / f"pacto20_faseA_{n}.csv", index=False, encoding="utf-8"),  # noqa: E731
                         (caminho("tables") / f"pacto20_faseA_{n}.md").write_text(df.to_markdown(index=False, floatfmt=".4g"), encoding="utf-8"))
    tab(tx, "match")
    tab(pd.DataFrame([check_coordenadas(b) for b in bases.values()]), "coordenadas")
    tab(pd.concat([check_municipal(b, a) for a, b in bases.items()]), "check_municipal")
    tab(pd.DataFrame([{"ano": a, **b.attrs} for a, b in bases.items()]), "duplicidades")


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # sem argumentos: reconstrói tudo; "match": só refaz matching, herança de coordenadas e checks; anos: só esses
    args = sys.argv[1:]
    if args == ["placebo"]:
        placebo()
    else:
        main([] if args == ["match"] else ([int(x) for x in args] or None))
