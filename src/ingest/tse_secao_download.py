"""Download dos dados do TSE por seção e local de votação (pacto 2.0, Fase A).

Fonte: https://cdn.tse.jus.br/estatistica/sead/odsele/<conjunto>/... (Dados Abertos do TSE).
Disponibilidade conferida em 27/10/2026 (HEAD 200 em todos):
- votacao_secao/votacao_secao_<ano>_<UF>.zip — votos por candidato/votável × seção, cargos da UF
  (deputado federal sai daqui), 1º e 2º turnos. 2026 publicado em 26/10/2026.
- votacao_secao/votacao_secao_<ano>_BR.zip — presidente por seção (os arquivos por UF não trazem
  presidente).
- detalhe_votacao_secao/detalhe_votacao_secao_<ano>.zip — aptos, comparecimento, brancos e nulos por
  seção (arquivo nacional).
- eleitorado_locais_votacao/eleitorado_local_votacao_<ano>.zip — seções, locais de votação, endereço
  e coordenadas.
- perfil_eleitor_secao/perfil_eleitor_secao_<ano>_<UF>.zip — eleitorado por seção × faixa etária,
  gênero, escolaridade etc.
- perfil_comparecimento_abstencao/perfil_comparecimento_abstencao_<ano>.zip — comparecimento e
  abstenção por município × zona × faixa etária × gênero × escolaridade, por turno (Fase C, Critério 4;
  é o menor nível com idade publicado). 2026 com data de 21/10/2026 (HEAD 200 em 27/10/2026).
Destino: data/raw/tse_secao/<conjunto>/ (nunca editado à mão).

Placebo da Fase D (2010 e 2014; HEAD 200 em 27/10/2026): só presidente (_BR), detalhe, locais e perfil
por seção — sem os arquivos por UF de votação (deputado fora do escopo).

Uso: python -m src.ingest.tse_secao_download [ano ...]   (2010 e 2014 baixam o conjunto do placebo)
"""

from __future__ import annotations

import logging
import sys

from src.utils import baixar, caminho, config

log = logging.getLogger("tse_secao_download")
ANOS = [2018, 2022, 2026]
UFS = "AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO".split()


def arquivos(ano: int) -> list[tuple[str, str]]:
    """(conjunto, nome do arquivo) a baixar para o ano."""
    # presidente não está nos arquivos por UF: fica em votacao_secao_<ano>_BR.zip
    out = [("votacao_secao", f"votacao_secao_{ano}_BR.zip"),
           ("detalhe_votacao_secao", f"detalhe_votacao_secao_{ano}.zip"),
           ("eleitorado_locais_votacao", f"eleitorado_local_votacao_{ano}.zip"),
           ("perfil_comparecimento_abstencao", f"perfil_comparecimento_abstencao_{ano}.zip")]
    for uf in UFS:
        out += [("votacao_secao", f"votacao_secao_{ano}_{uf}.zip"),
                ("perfil_eleitor_secao", f"perfil_eleitor_secao_{ano}_{uf}.zip")]
    return out


def arquivos_placebo(ano: int) -> list[tuple[str, str]]:
    out = [("votacao_secao", f"votacao_secao_{ano}_BR.zip"),
           ("detalhe_votacao_secao", f"detalhe_votacao_secao_{ano}.zip"),
           ("eleitorado_locais_votacao", f"eleitorado_local_votacao_{ano}.zip")]
    return out + [("perfil_eleitor_secao", f"perfil_eleitor_secao_{ano}_{uf}.zip") for uf in UFS]


def pasta(conjunto: str):
    return caminho("raw") / "tse_secao" / conjunto


def baixar_ano(ano: int) -> None:
    cdn = config()["tse"]["cdn"]
    for conjunto, nome in (arquivos_placebo(ano) if ano in (2010, 2014) else arquivos(ano)):
        baixar(f"{cdn}/{conjunto}/{nome}", pasta(conjunto) / nome)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    for a in [int(x) for x in sys.argv[1:]] or ANOS:
        baixar_ano(a)
