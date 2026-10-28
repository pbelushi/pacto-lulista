"""Reprodução completa dos três estudos, na ordem em que as etapas foram executadas.

Cada etapa é um módulo do projeto chamado como `python -m <módulo> [args]`, exatamente como durante o
desenvolvimento. As etapas de download (marcadas `rede`) gravam em data/raw/ e pulam arquivos já baixados com o
mesmo tamanho; as demais leem data/raw/ e data/manual/ e escrevem em data/interim/, data/processed/ e outputs/.

Estudos:
  1  O pacto lulista mudou de perfil? Painel municipal 2006–2026 (docs/planos/PLANO.md) + extra de coortes
  2  Pacto lulista 2.0: locais de votação 2018–2026, com placebo 2010–2014 (docs/planos/plano2.md)
  3  A polarização se resolve? Episódios de polarização 1900–2025 e o Brasil (docs/planos/plano3.md)

Uso:
  python -m src.pipeline --listar                 # mostra as etapas
  python -m src.pipeline                          # roda tudo (algumas horas; ~22 GB em data/raw/)
  python -m src.pipeline --estudo 3               # só um estudo (depende das etapas anteriores que ele usa)
  python -m src.pipeline --sem-rede               # pula downloads (data/raw/ já preenchido)
  python -m src.pipeline --a-partir-de 2.05       # retoma a partir de uma etapa
  python -m src.pipeline --testes                 # roda pytest ao fim
Dependências entre estudos: o 2 usa o painel e a malha do 1 (Fases 1–4); o 3 usa o painel e a malha do 1 na Fase E.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass, field

from src.utils import RAIZ


@dataclass
class Etapa:
    id: str
    descricao: str
    modulo: str
    args: list[str] = field(default_factory=list)
    rede: bool = False       # baixa dados
    opcional: bool = False   # falha não interrompe (fonte indisponível conhecida)
    nota: str = ""


ETAPAS = [
    # ---------------- Estudo 1: painel municipal 2006–2026
    Etapa("1.01", "TSE: resultados por município × zona (2006–2026)", "src.ingest.tse_download", rede=True),
    Etapa("1.02", "TSE: Portal Resultados (2º turno de 2026; deputado federal por UF)", "src.ingest.tse_portal", rede=True),
    Etapa("1.03", "Fase 1: 2º turno presidencial por AMC", "src.ingest.tse"),
    Etapa("1.04", "Fase 1B: voto proporcional (deputado federal)", "src.ingest.tse_proporcional"),
    Etapa("1.05", "Malha municipal e AMCs (geobr)", "src.ingest.malhas", rede=True),
    Etapa("1.06", "Fase 2: grupos de municípios", "src.groups"),
    Etapa("1.07", "Fase 2: mapas", "src.mapas"),
    Etapa("1.08", "Fase 3: IPCA", "src.ingest.ipca", rede=True),
    Etapa("1.09", "Fase 3: localidades IBGE", "src.ingest.ibge_localidades", rede=True),
    Etapa("1.10", "Fase 3: população", "src.ingest.ibge_pop", rede=True),
    Etapa("1.11", "Fase 3: PIB municipal", "src.ingest.ibge_pib", rede=True),
    Etapa("1.12", "Fase 3: Censo (raça, religião, trabalho)", "src.ingest.ibge_censo", rede=True),
    Etapa("1.13", "Fase 3: Ideb", "src.ingest.inep_ideb", rede=True),
    Etapa("1.14", "Fase 3: Ipeadata (Bolsa Família, IDHM)", "src.ingest.ipeadata", rede=True),
    Etapa("1.15", "Fase 3: Comex Stat (download)", "src.ingest.comex_download", rede=True,
          nota="TLS sem verificação só para balanca.economia.gov.br (certificado incompleto do servidor)"),
    Etapa("1.16", "Fase 3: Comex Stat por AMC", "src.ingest.comex"),
    Etapa("1.17", "Fase 3: DATASUS", "src.ingest.datasus", rede=True, opcional=True,
          nota="TabNet bloqueia acesso automatizado; pendente (outputs/pendencias.md)"),
    Etapa("1.18", "Fase 4: painéis", "src.build_panel"),
    Etapa("1.19", "Fase 5: descritiva", "src.descriptives"),
    Etapa("1.20", "Fase 6: modelos", "src.models"),
    Etapa("1.21", "Fase 7: espacial", "src.spatial"),
    Etapa("1.22", "Fase 7: robustez", "src.robustness"),
    Etapa("1.23", "Extra coortes: idade simples do Censo (SIDRA)", "src.ingest.ibge_idade", rede=True),
    Etapa("1.24", "Extra coortes: análise com o Censo", "src.coortes"),
    Etapa("1.25", "Extra coortes: perfil do eleitorado (TSE)", "src.ingest.tse_perfil", rede=True),
    Etapa("1.26", "Extra coortes: análise com o TSE", "src.coortes_tse"),
    # ---------------- Estudo 2: pacto 2.0
    Etapa("2.01", "TSE por seção e locais de votação (2018, 2022, 2026)", "src.ingest.tse_secao_download",
          ["2018", "2022", "2026"], rede=True, nota="~16 GB com o placebo"),
    Etapa("2.02", "Fase A: base por local de votação", "src.pacto20_base"),
    Etapa("2.03", "Setores censitários 2022 (malha e agregados)", "src.ingest.ibge_setores", rede=True, nota="~2 GB"),
    Etapa("2.04", "Fase B: entorno censitário (Voronoi e buffer)", "src.pacto20_entorno", nota="~80 min"),
    Etapa("2.05", "Fase C: critérios 1, 2, 4, 5, comparecimento por idade e regressão ecológica",
          "src.pacto20_modelos", ["c1", "c2", "c4", "idade", "c5", "goodman"],
          nota="o PyEI (parte 'ei') não termina em tempo útil e fica fora; ver pendencias.md"),
    Etapa("2.06", "Fase D: variantes, Conley e Moran", "src.pacto20_robustez", ["variantes", "conley", "moran"]),
    Etapa("2.07", "Placebo: TSE por seção 2010 e 2014", "src.ingest.tse_secao_download", ["2010", "2014"], rede=True),
    Etapa("2.08", "Placebo: bases de 2010 e 2014", "src.pacto20_base", ["placebo"]),
    Etapa("2.09", "Placebo: entorno de 2010 e 2014", "src.pacto20_entorno", ["2010", "2014"], nota="~55 min"),
    Etapa("2.10", "Fase D: placebo", "src.pacto20_robustez", ["placebo"]),
    Etapa("2.11", "Fase C: mobilização entre turnos em cinco eleições", "src.pacto20_modelos", ["c4comp"]),
    Etapa("2.12", "Extra: comparecimento por sexo", "src.pacto20_sexo"),
    Etapa("2.13", "Fase E: figuras", "src.pacto20_saidas"),
    # ---------------- Estudo 3: polarização comparada
    Etapa("3.01", "V-Dem v16, ERT v16, UCDP/PRIO 25.1, Archigos 4.1", "src.ingest.p3_dados", rede=True),
    Etapa("3.02", "Fase A: painel país-ano", "src.p3_painel"),
    Etapa("3.03", "Fase B: episódios de polarização", "src.p3_episodios"),
    Etapa("3.04", "Fase C: pré-codificação + revisão do usuário (data/manual/)", "src.p3_codificacao"),
    Etapa("3.05", "Fase D: análise (inclui recorte democrático)", "src.p3_analise", nota="~4 min (bootstrap)"),
    Etapa("3.06", "Fase E: TSE 1994–2002", "src.ingest.tse_download",
          ["detalhe_votacao_munzona", "votacao_candidato_munzona", "1994", "1998", "2002"], rede=True),
    Etapa("3.07", "Fase E: indicadores brasileiros 1994–2026", "src.p3_brasil", nota="~5 min"),
    Etapa("3.08", "Extra: análise fatorial exploratória das variáveis de polarização do V-Dem", "src.p3_afe",
          nota="~5 min"),
]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--listar", action="store_true")
    ap.add_argument("--estudo", choices=["1", "2", "3"])
    ap.add_argument("--sem-rede", action="store_true", help="pula as etapas de download")
    ap.add_argument("--a-partir-de", metavar="ID")
    ap.add_argument("--testes", action="store_true", help="roda pytest ao fim")
    a = ap.parse_args()
    etapas = [e for e in ETAPAS if (not a.estudo or e.id.startswith(a.estudo + "."))
              and (not a.a_partir_de or float(e.id) >= float(a.a_partir_de))
              and not (a.sem_rede and e.rede)]
    if a.listar:
        for e in etapas:
            marca = "".join(["R" if e.rede else " ", "o" if e.opcional else " "])
            print(f"{e.id} [{marca}] {e.descricao}\n           python -m {e.modulo} {' '.join(e.args)}"
                  f"{'   # ' + e.nota if e.nota else ''}")
        print("\nR = baixa dados; o = opcional (falha não interrompe)")
        return
    for e in etapas:
        print(f"\n=== {e.id} {e.descricao}", flush=True)
        t = time.time()
        r = subprocess.run([sys.executable, "-m", e.modulo, *e.args], cwd=RAIZ)
        if r.returncode != 0:
            if e.opcional:
                print(f"--- {e.id} falhou (opcional, segue): código {r.returncode}")
                continue
            sys.exit(f"--- {e.id} falhou: código {r.returncode}. Retome com --a-partir-de {e.id}")
        print(f"--- {e.id} ok ({time.time() - t:.0f} s)")
    if a.testes:
        sys.exit(subprocess.run([sys.executable, "-m", "pytest", "tests", "-q"], cwd=RAIZ).returncode)


if __name__ == "__main__":
    main()
