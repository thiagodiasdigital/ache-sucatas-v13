"""
Conector Leilões Judiciais - leiloesjudiciais.com.br

Este módulo implementa o scraping do site de leilões judiciais,
extraindo dados de veículos e sucatas para o Ache Sucatas.
"""

from .config import Config
from .discover import LeilaoDiscovery
from .fetch import LeilaoFetcher
from .parse import LeilaoParser
from .normalize import LeilaoNormalizer
from .emit import LeilaoEmitter

__all__ = [
    "Config",
    "LeilaoDiscovery",
    "LeilaoFetcher",
    "LeilaoParser",
    "LeilaoNormalizer",
    "LeilaoEmitter",
]

__version__ = "1.0.0"
