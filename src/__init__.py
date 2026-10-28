"""Pacote do projeto pacto-lulista.

Figuras reprodutíveis: o SVG do matplotlib grava a data de geração e sorteia identificadores internos a cada
execução. Fixam-se a data (SOURCE_DATE_EPOCH = 28/10/2026, data da versão 1.0.0) e a semente dos identificadores,
para que rodar de novo gere arquivos idênticos.
"""

import os

os.environ.setdefault("SOURCE_DATE_EPOCH", "1793145600")
try:
    import matplotlib

    matplotlib.rcParams["svg.hashsalt"] = "pacto-lulista"
except ImportError:  # pragma: no cover
    pass
