"""Óbitos e nascidos vivos por município de residência, microdados do SIM e do SINASC (DATASUS), 2003–2026.

Fonte: arquivos Mortalidade_Geral_<ano>_csv.zip de dadosabertos.saude.gov.br, baixados pelo usuário e salvos em
data/manual/ (o TabNet recusa acesso automatizado; ver outputs/pendencias.md). Não são versionados por causa do tamanho (1,4 GB); os hashes
ficam em data/manifesto_dados.csv. Nomes de coluna variam entre anos (minúsculas em 2023); CODMUNRES tem 7 dígitos
em 2003–2005 e 6 depois; zeros à esquerda de IDADE somem em 2022–2023.

Definições (todas com TIPOBITO = 2, não fetal, e pela causa básica CAUSABAS):
- obitos_infantis: idade < 1 ano (IDADE com 3 dígitos; 1º dígito de 0 a 3 = minutos, horas, dias ou meses);
- homicidios: CID-10 X85–Y09; mortes_intervencao_legal: Y35–Y36, separadas como pede o PLANO;
- obitos_covid: B34.2 (codificação da Covid-19 no SIM) e U07.

Completude: 2025 é preliminar (só janeiro a setembro) e 2026 é segunda prévia (só janeiro a agosto). Ficam na saída
marcados `ano_completo = False` e não entram nas taxas anuais (config.yaml, sim.ultimo_ano_completo).
Registros com município ignorado (código de UF, como 330000): ~0,3%, descartados e contados no log.

Nascidos vivos: arquivos DNBR<ano>_csv.zip (2003–2015) e SINASC_<ano>_csv.zip (2016–2026), da mesma origem, com
nomes de coluna e aspas que variam entre anos. Contagem por CODMUNRES e ano de DTNASC; registros com data inválida
(3 no total) saem. 2026 vai só até agosto e 2025 tem os 12 meses, mas nenhum dos dois entra na taxa de mortalidade
infantil, porque o numerador (SIM) só está completo até 2024. DNBR2015.csv está truncado (config.yaml,
sim.nv_anos_truncados): fica na saída, mas o painel não o usa, e a taxa não existe nas janelas com 2015.

Saídas: data/interim/sim.parquet (município × ano); data/interim/sim_mensal.parquet (município × ano × mês);
data/interim/sinasc.parquet (município × ano).

Uso: python -m src.ingest.sim
"""

from __future__ import annotations

import logging
import re
import zipfile

import pandas as pd

from src.utils import caminho, config

log = logging.getLogger("sim")
COLS = {"TIPOBITO", "DTOBITO", "IDADE", "CODMUNRES", "CAUSABAS"}
CONTAGENS = ["obitos_total", "obitos_infantis", "homicidios", "mortes_intervencao_legal", "obitos_covid"]


def ler_ano(f) -> pd.DataFrame:
    z = zipfile.ZipFile(f)
    nome = next(n for n in z.namelist() if n.lower().endswith(".csv"))
    cab = pd.read_csv(z.open(nome), sep=";", encoding="latin-1", nrows=0).columns
    usar = [c for c in cab if c.upper() in COLS]
    d = pd.read_csv(z.open(nome), sep=";", encoding="latin-1", usecols=usar, dtype=str)
    return d.rename(columns=str.upper)


def classificar(d: pd.DataFrame) -> pd.DataFrame:
    d = d[d["TIPOBITO"].str.strip() == "2"]
    cb = d["CAUSABAS"].str.strip().str.upper().fillna("")
    data = d["DTOBITO"].str.strip().str.zfill(8)
    return pd.DataFrame({
        "cod6": d["CODMUNRES"].str.strip().str[:6],
        "ano": pd.to_numeric(data.str[4:8], errors="coerce"),
        "mes": pd.to_numeric(data.str[2:4], errors="coerce"),
        "obitos_total": 1,
        "obitos_infantis": d["IDADE"].str.strip().str.zfill(3).str[0].isin(list("0123")).astype(int),
        "homicidios": cb.str.match(r"X8[5-9]|X9\d|Y0\d").astype(int),
        "mortes_intervencao_legal": cb.str.match(r"Y3[56]").astype(int),
        "obitos_covid": cb.str.match(r"B342|U07").astype(int),
    })


def nascidos(cod6: dict) -> pd.DataFrame:
    partes = []
    for f in sorted(caminho("manual").glob("*_csv.zip")):
        if not re.match(r"(DNBR|SINASC_)\d{4}_csv", f.name):
            continue
        z = zipfile.ZipFile(f)
        nome = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        cab = pd.read_csv(z.open(nome), sep=";", encoding="latin-1", nrows=0).columns
        usar = [c for c in cab if c.upper() in {"CODMUNRES", "DTNASC"}]
        d = pd.read_csv(z.open(nome), sep=";", encoding="latin-1", usecols=usar, dtype=str).rename(columns=str.upper)
        data = d["DTNASC"].str.strip().str.zfill(8)
        c = pd.DataFrame({"cod6": d["CODMUNRES"].str.strip().str[:6], "ano": pd.to_numeric(data.str[4:8], errors="coerce")})
        partes.append(c[c["ano"] == int(re.search(r"(\d{4})_csv", f.name).group(1))])
        log.info("%s: %d nascidos vivos", f.name, len(c))
    n = pd.concat(partes, ignore_index=True)
    n["id_municipio"] = n["cod6"].map(cod6)
    ign = n["id_municipio"].isna()
    log.info("nascidos vivos com município ignorado, descartados: %d (%.3f%%)", ign.sum(), 100 * ign.mean())
    t = n[~ign].groupby(["id_municipio", "ano"]).size().rename("nascidos_vivos").reset_index()
    t["ano"] = t["ano"].astype(int)
    return t


def main() -> None:
    arqs = sorted(caminho("manual").glob("Mortalidade_Geral_*_csv.zip"))
    assert arqs, "microdados do SIM ausentes em data/manual/ (ver README, Decisões manuais)"
    mensal = []
    for f in arqs:
        c = classificar(ler_ano(f))
        mensal.append(c.groupby(["cod6", "ano", "mes"], as_index=False)[CONTAGENS].sum())
        log.info("%s: %d óbitos", f.name, len(c))
    m = pd.concat(mensal, ignore_index=True)
    pop = pd.read_parquet(caminho("interim") / "ibge_pop.parquet")[["id_municipio", "ano", "pop"]]
    cod6 = {str(i)[:6]: i for i in pop["id_municipio"].unique()}
    m["id_municipio"] = m["cod6"].map(cod6)
    ign = m["id_municipio"].isna()
    log.info("óbitos com município ignorado, descartados: %d (%.2f%%)", m.loc[ign, "obitos_total"].sum(),
             100 * m.loc[ign, "obitos_total"].sum() / m["obitos_total"].sum())
    m = m[~ign].drop(columns="cod6")
    m["id_municipio"] = m["id_municipio"].astype(pop["id_municipio"].dtype)
    m["ano"], m["mes"] = m["ano"].astype(int), m["mes"].astype(int)
    m.to_parquet(caminho("interim") / "sim_mensal.parquet", index=False)
    # município sem óbito da causa no ano = 0, para todo município com população no ano
    anos = sorted(m["ano"].unique())
    base = pop[pop["ano"].isin(anos) & pop["pop"].notna()][["id_municipio", "ano"]]
    a = base.merge(m.groupby(["id_municipio", "ano"], as_index=False)[CONTAGENS].sum(), on=["id_municipio", "ano"],
                   how="left")
    a[CONTAGENS] = a[CONTAGENS].fillna(0).astype(int)
    a["ano_completo"] = a["ano"] <= config()["sim"]["ultimo_ano_completo"]
    a.to_parquet(caminho("interim") / "sim.parquet", index=False)
    nv = nascidos(cod6)
    nv["id_municipio"] = nv["id_municipio"].astype(pop["id_municipio"].dtype)
    nv.to_parquet(caminho("interim") / "sinasc.parquet", index=False)
    log.info("totais:\n%s", a.groupby("ano")[CONTAGENS].sum().to_string())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    main()
