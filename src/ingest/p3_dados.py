"""Fase A do plano3 (polarização comparada): download das bases internacionais.

Destino: data/raw/p3/ (nunca editado à mão). Fontes conferidas em 28/10/2026:
- V-Dem Country-Year v16 (Full+Others): repositório oficial vdeminstitute/vdemdata, data/vdem.RData
  e data/codebook.RData (pacote R versão 16.0). O site v-dem.net não responde desta rede (TLS);
  o pacote do GitHub é distribuição oficial do V-Dem Institute.
- Episodes of Regime Transformation (ERT) v16: vdeminstitute/ERT, data/episodes.rda.
- UCDP/PRIO Armed Conflict Dataset v25.1 (1946–2024): ucdp.uu.se/downloads.
- Archigos 4.1 (líderes, 1875–2015): rochester.edu/college/faculty/hgoemans/Archigos_4.1_stata14.dta.
Indisponíveis desta rede (registrado em outputs/pendencias.md):
- Powell e Thyne (golpes): uky.edu responde 403 a download automático; não contornado. Alternativa:
  e_pt_coup / e_pt_coup_attempts do próprio V-Dem (mesma fonte, país-ano).
- Correlates of War (guerras intraestatais): correlatesofwar.org falha no TLS. Alternativa: variáveis de
  conflito interno do V-Dem (e_civil_war etc.; conferir no codebook).
O commit de cada repositório GitHub é salvo em data/raw/p3/versoes.json.

Uso: python -m src.ingest.p3_dados
"""

from __future__ import annotations

import json
import logging

import requests

from src.utils import baixar, caminho

log = logging.getLogger("p3_dados")
GH = "https://raw.githubusercontent.com/vdeminstitute"
ARQUIVOS = {
    "vdem.RData": ("vdemdata", "data/vdem.RData"),
    "vdem_codebook.RData": ("vdemdata", "data/codebook.RData"),
    "ert_episodes.rda": ("ERT", "data/episodes.rda"),
}
OUTROS = {
    "ucdp_prio_acd_251_csv.zip": "https://ucdp.uu.se/downloads/ucdpprio/ucdp-prio-acd-251-csv.zip",
    "Archigos_4.1_stata14.dta": "https://www.rochester.edu/college/faculty/hgoemans/Archigos_4.1_stata14.dta",
    "Archigos_4.1.pdf": "https://www.rochester.edu/college/faculty/hgoemans/Archigos_4.1.pdf",
}


def pasta():
    return caminho("raw") / "p3"


def _commit(repo: str) -> dict:
    r = requests.get(f"https://api.github.com/repos/vdeminstitute/{repo}/commits/master", timeout=60)
    r.raise_for_status()
    j = r.json()
    desc = requests.get(f"{GH}/{repo}/{j['sha']}/DESCRIPTION", timeout=60).text
    versao = next((l.split(":", 1)[1].strip() for l in desc.splitlines() if l.startswith("Version:")), None)
    return {"sha": j["sha"], "data": j["commit"]["committer"]["date"], "versao_pacote": versao}


def main() -> None:
    versoes = {repo: _commit(repo) for repo in {r for r, _ in ARQUIVOS.values()}}
    for nome, (repo, caminho_repo) in ARQUIVOS.items():
        baixar(f"{GH}/{repo}/{versoes[repo]['sha']}/{caminho_repo}", pasta() / nome)
    for nome, url in OUTROS.items():
        baixar(url, pasta() / nome)
    (pasta() / "versoes.json").write_text(json.dumps(versoes, indent=2), encoding="utf-8")
    log.info("versões: %s", versoes)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    main()
