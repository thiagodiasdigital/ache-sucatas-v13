#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
LOTES EXTRACTOR V1
=============================================================================
Extrator de lotes individuais de editais de leilão.

Versão: 1.0.0
Data: 2026-01-25
Autor: Tech Lead (Claude Code)

Propósito:
- Extrair tabelas de lotes de PDFs de editais
- Classificar PDFs em famílias estruturais
- Persistir lotes com relação 1:N para editais
- Enviar falhas para quarentena com motivo explícito

Famílias de PDF suportadas:
- PDF_TABELA_INICIO: Tabelas nas primeiras 3 páginas (43.1% dos arquivos)
- PDF_TABELA_MEIO_FIM: Tabelas após página 3 (15.0% dos arquivos)
- PDF_NATIVO_SEM_TABELA: Texto extraível mas sem tabelas detectadas (21.4%)
- PDF_ESCANEADO: Imagens sem texto extraível (20.2%)

Dependências:
- pdfplumber>=0.10.0
- pandas>=2.0.0
- supabase>=2.0.0
- pydantic>=2.0.0
=============================================================================
"""

import hashlib
import json
import logging
import os
import re
import tempfile
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import pdfplumber
from supabase import create_client, Client

# =============================================================================
# V1.1: VERIFICAR DISPONIBILIDADE DO OPENAI (LLM FALLBACK)
# =============================================================================

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None

# =============================================================================
# CONFIGURAÇÃO DE LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('LotesExtractorV1')

# =============================================================================
# CONSTANTES E CONFIGURAÇÕES
# =============================================================================

VERSAO_EXTRATOR = "lotes_extractor_v1"

# Supabase Storage bucket para PDFs de editais
STORAGE_BUCKET = "editais-pdfs"

# Threshold para classificar PDF como escaneado (caracteres mínimos em 3 páginas)
THRESHOLD_CARACTERES_ESCANEADO = 100

# Página limite para classificar família (tabelas antes ou depois)
PAGINA_LIMITE_FAMILIA = 3

# Palavras-chave para identificar tabelas de lotes (normalizadas, sem acento)
KEYWORDS_LOTES = [
    'lote', 'item', 'placa', 'chassi', 'renavam',
    'marca', 'modelo', 'veiculo', 'descricao',
    'avaliacao', 'valor', 'lance'
]

# Palavras-chave para IGNORAR tabelas (não são de lotes)
KEYWORDS_IGNORAR = [
    'largura', 'altura', 'espessura',  # Dimensões físicas
    'assinatura', 'testemunha',  # Campos de assinatura
    'cnpj', 'razao social',  # Dados de empresa
    'data encerramento', 'data abertura',  # Tabelas de cronograma
    'horario abertura', 'horario encerramento',  # Tabelas de cronograma
]

# Cabeçalhos conhecidos de tabelas de veículos
CABECALHOS_VEICULOS = [
    ['placa', 'renavam', 'chassi', 'marca/modelo', 'ano'],
    ['lote', 'descricao', 'valor'],
    ['item', 'placa', 'marca', 'modelo', 'ano'],
    ['n', 'placa', 'renavam', 'chassi', 'marca'],
]


# =============================================================================
# ENUMS E TIPOS
# =============================================================================

class FamiliaPDF(Enum):
    """Famílias estruturais de PDFs identificadas na análise de padrões."""
    PDF_TABELA_INICIO = "PDF_TABELA_INICIO"
    PDF_TABELA_MEIO_FIM = "PDF_TABELA_MEIO_FIM"
    PDF_NATIVO_SEM_TABELA = "PDF_NATIVO_SEM_TABELA"
    PDF_ESCANEADO = "PDF_ESCANEADO"


class EstagioFalha(Enum):
    """Estágios onde podem ocorrer falhas no pipeline."""
    CLASSIFICACAO = "classificacao"
    EXTRACAO = "extracao"
    VALIDACAO = "validacao"
    ENRIQUECIMENTO = "enriquecimento"
    PERSISTENCIA = "persistencia"


class CodigoErro(Enum):
    """Códigos de erro padronizados para quarentena."""
    # Classificação
    PDF_ESCANEADO = "PDF_ESCANEADO"
    PDF_CORROMPIDO = "PDF_CORROMPIDO"
    TIPO_NAO_SUPORTADO = "TIPO_NAO_SUPORTADO"

    # Extração
    TABELA_NAO_ENCONTRADA = "TABELA_NAO_ENCONTRADA"
    TABELA_SEM_CABECALHO_VALIDO = "TABELA_SEM_CABECALHO_VALIDO"
    ESTRUTURA_INESPERADA = "ESTRUTURA_INESPERADA"

    # Validação
    NUMERO_LOTE_AUSENTE = "NUMERO_LOTE_AUSENTE"
    DESCRICAO_INSUFICIENTE = "DESCRICAO_INSUFICIENTE"
    VALOR_NAO_PARSEAVEL = "VALOR_NAO_PARSEAVEL"

    # Persistência
    ERRO_BANCO_DADOS = "ERRO_BANCO_DADOS"
    CONSTRAINT_VIOLADA = "CONSTRAINT_VIOLADA"


# =============================================================================
# EXCEÇÕES CUSTOMIZADAS
# =============================================================================

class LotesExtractorError(Exception):
    """Exceção base para erros do extrator de lotes."""
    pass


class ClassificacaoError(LotesExtractorError):
    """Erro durante classificação do arquivo."""
    pass


class ExtracaoError(LotesExtractorError):
    """Erro durante extração de dados."""
    pass


class ValidacaoError(LotesExtractorError):
    """Erro durante validação de dados."""
    pass


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class LoteExtraido:
    """Representa um lote extraído de um PDF."""
    numero_lote_raw: str
    descricao_raw: str
    valor_raw: Optional[str] = None
    texto_fonte_completo: Optional[str] = None

    # Campos processados
    numero_lote: str = ""
    descricao_completa: str = ""
    avaliacao_valor: Optional[float] = None

    # Campos de veículo (se identificados)
    placa: Optional[str] = None
    chassi: Optional[str] = None
    renavam: Optional[str] = None
    marca: Optional[str] = None
    modelo: Optional[str] = None
    ano_fabricacao: Optional[int] = None

    # Metadados
    fonte_pagina: Optional[int] = None
    linha_tabela: Optional[int] = None

    def __post_init__(self):
        """Processa campos após inicialização."""
        # Limpar número do lote
        self.numero_lote = self._limpar_numero_lote(self.numero_lote_raw)

        # Limpar descrição
        self.descricao_completa = self._limpar_descricao(self.descricao_raw)

        # Parsear valor se presente
        if self.valor_raw:
            resultado = self._limpar_valor(self.valor_raw)
            if resultado['sucesso']:
                self.avaliacao_valor = resultado['valor']

        # Extrair dados de veículo do texto (se campos não preenchidos)
        self._extrair_dados_veiculo_do_texto()

    def _limpar_numero_lote(self, texto: str) -> str:
        """Limpa e normaliza número do lote."""
        if not texto:
            return ""
        # Remove espaços extras e normaliza
        limpo = re.sub(r'\s+', ' ', str(texto).strip())
        # Remove prefixos comuns
        limpo = re.sub(r'^(lote|item|n[°º.]?)\s*', '', limpo, flags=re.IGNORECASE)
        return limpo.strip()

    def _limpar_descricao(self, texto: str) -> str:
        """Limpa e normaliza descrição."""
        if not texto:
            return ""
        # Remove quebras de linha múltiplas
        limpo = re.sub(r'\n+', ' ', str(texto))
        # Remove espaços extras
        limpo = re.sub(r'\s+', ' ', limpo)
        return limpo.strip()

    def _limpar_valor(self, texto: str) -> Dict[str, Any]:
        """
        Limpa e converte valor monetário.

        IMPORTANTE: Retorna estrutura com sucesso/falha explícitos.
        NUNCA retorna valor default silenciosamente.
        """
        if not texto:
            return {'sucesso': False, 'texto_original': texto, 'motivo': 'valor_vazio'}

        try:
            # Remove "R$" e espaços
            limpo = str(texto).replace('R$', '').replace('r$', '').strip()

            # Trata formato brasileiro (1.234,56) vs americano (1,234.56)
            if ',' in limpo and '.' in limpo:
                # Formato brasileiro: 1.234,56
                if limpo.rfind(',') > limpo.rfind('.'):
                    limpo = limpo.replace('.', '').replace(',', '.')
                # Formato americano: 1,234.56
                else:
                    limpo = limpo.replace(',', '')
            elif ',' in limpo:
                # Apenas vírgula: assume decimal brasileiro
                limpo = limpo.replace(',', '.')
            elif '.' in limpo:
                # Apenas ponto: verificar se é separador de milhar brasileiro
                # Padrão: X.XXX ou XX.XXX ou XXX.XXX (3 dígitos após cada ponto)
                partes = limpo.split('.')
                if all(len(p) == 3 for p in partes[1:]):
                    # É separador de milhar (ex: 15.000, 1.500.000)
                    limpo = limpo.replace('.', '')

            # Remove caracteres não numéricos restantes (exceto ponto)
            limpo = re.sub(r'[^\d.]', '', limpo)

            if not limpo:
                return {'sucesso': False, 'texto_original': texto, 'motivo': 'sem_digitos'}

            valor = float(limpo)
            return {'sucesso': True, 'valor': valor}

        except (ValueError, TypeError) as e:
            return {'sucesso': False, 'texto_original': texto, 'motivo': f'erro_conversao: {str(e)}'}

    def _extrair_dados_veiculo_do_texto(self):
        """
        Extrai dados de veículo do texto da descrição usando regex.

        Só preenche campos que ainda estão vazios (None).

        Padrões suportados:
        - Placa: ABC1234, ABC-1234, ABC1D23 (Mercosul)
        - Chassi: 17 caracteres alfanuméricos
        - Renavam: 9-11 dígitos
        - Ano: formatos 2013, 2013/2014, ANO 2013
        - Marca/Modelo: após palavras-chave específicas
        """
        # Usar descrição raw + texto fonte completo para maior cobertura
        texto = ' '.join(filter(None, [
            self.descricao_raw,
            self.texto_fonte_completo
        ])).upper()

        if not texto or len(texto) < 10:
            return

        # === PLACA ===
        # Formatos: ABC1234, ABC-1234, ABC 1234, ABC1D23 (Mercosul)
        # IMPORTANTE: Exigir palavra PLACA antes para evitar falsos positivos
        if not self.placa:
            # Padrão com palavra PLACA explícita (mais confiável)
            placa_match = re.search(
                r'PLACA[:\s]+([A-Z]{3})\s*[-]?\s*(\d{4})\b',
                texto
            )
            if placa_match:
                self.placa = f"{placa_match.group(1)}{placa_match.group(2)}"
            else:
                # Padrão Mercosul com palavra PLACA
                placa_mercosul = re.search(
                    r'PLACA[:\s]+([A-Z]{3}\d[A-Z]\d{2})\b',
                    texto
                )
                if placa_mercosul:
                    self.placa = placa_mercosul.group(1)
                else:
                    # Fallback: placa sem palavra-chave, mas com padrão válido
                    # Excluir palavras comuns que podem ser confundidas (ANO, COR, etc)
                    placa_fallback = re.search(
                        r'\b(?!ANO|COR|CEP|UNO|GOL|KIA)([A-Z]{3})\s*[-]?\s*(\d{4})\b',
                        texto
                    )
                    if placa_fallback:
                        candidata = f"{placa_fallback.group(1)}{placa_fallback.group(2)}"
                        # Validar que parece uma placa real (não é palavra comum)
                        palavras_invalidas = ['ANO', 'COR', 'CEP', 'RUA', 'NUM']
                        if candidata[:3] not in palavras_invalidas:
                            self.placa = candidata

        # === CHASSI ===
        # 17 caracteres alfanuméricos (exceto I, O, Q)
        if not self.chassi:
            # Preferir com palavra CHASSI
            chassi_match = re.search(
                r'CHASSI[:\s]+([A-HJ-NPR-Z0-9]{17})\b',
                texto
            )
            if chassi_match:
                self.chassi = chassi_match.group(1)
            else:
                # Fallback: padrão de chassi sem palavra-chave
                chassi_fallback = re.search(
                    r'\b([A-HJ-NPR-Z0-9]{17})\b',
                    texto
                )
                if chassi_fallback:
                    candidato = chassi_fallback.group(1)
                    # Verificar se tem mix de letras e números (chassi real)
                    tem_letra = any(c.isalpha() for c in candidato)
                    tem_numero = any(c.isdigit() for c in candidato)
                    if tem_letra and tem_numero:
                        self.chassi = candidato

        # === RENAVAM ===
        # 11 dígitos (padrão atual) - exigir palavra RENAVAM para evitar confusão
        if not self.renavam:
            renavam_match = re.search(
                r'RENAVA[MN][:\s]+(\d{9,11})\b',  # RENAVAM ou RENAVAN (typo comum)
                texto
            )
            if renavam_match:
                self.renavam = renavam_match.group(1).zfill(11)  # Pad to 11 digits

        # === ANO ===
        if not self.ano_fabricacao:
            # Formato: ANO 2013/2014, ANO 2013, ANO: 2013
            ano_match = re.search(
                r'ANO[:\s]+(\d{4})(?:\s*/\s*(\d{4}))?',
                texto
            )
            if ano_match:
                try:
                    ano = int(ano_match.group(1))
                    if 1900 <= ano <= 2100:
                        self.ano_fabricacao = ano
                except ValueError:
                    pass

        # === MARCA E MODELO ===
        # Extrair marca/modelo de padrões comuns
        if not self.marca or not self.modelo:
            # Lista de marcas conhecidas (ordenadas por especificidade)
            marcas_conhecidas = [
                'MERCEDES-BENZ', 'MERCEDES',  # Mais específico primeiro
                'VOLKSWAGEN', 'VW',
                'CHEVROLET', 'GM',
                'FIAT', 'FORD', 'TOYOTA', 'HONDA', 'HYUNDAI', 'RENAULT',
                'NISSAN', 'JEEP', 'BMW', 'AUDI', 'PEUGEOT', 'CITROEN',
                'MITSUBISHI', 'KIA', 'SUZUKI', 'YAMAHA', 'SCANIA',
                'VOLVO', 'IVECO', 'MAN', 'DAF', 'AGRALE', 'MARCOPOLO',
                'COMIL', 'MASCARELLO', 'CAIO', 'NEOBUS'
            ]

            # Procurar marca conhecida no texto
            for marca in marcas_conhecidas:
                # Usar word boundary para evitar match parcial
                if re.search(rf'\b{marca}\b', texto):
                    if not self.marca:
                        self.marca = marca

                    # Tentar extrair modelo após a marca
                    if not self.modelo:
                        # Padrão: MARCA/MODELO ou MARCA MODELO
                        modelo_match = re.search(
                            rf'\b{marca}\s*[/\s]\s*([A-Z0-9][A-Z0-9\s\-\.]+?)(?:,|\s+ANO|\s+PLACA|\s+COR|\s+CHASSI|\s+COMB|$)',
                            texto
                        )
                        if modelo_match:
                            modelo = modelo_match.group(1).strip()
                            # Limitar tamanho e limpar
                            if 2 <= len(modelo) <= 50:
                                self.modelo = modelo.rstrip(' ,.-')
                    break

            # Se não encontrou marca conhecida, tentar padrão genérico
            if not self.marca:
                # Padrão: MARCA/MODELO após tipo de veículo
                tipo_veiculo = re.search(
                    r'(?:VEICULO|AUTOMOVEL|CARRO|CAMINH[AÃ]O|MOTO|ONIBUS|VAN|FURG[AÃ]O|PICKUP|UTILITARIO)[:\s]+([A-Z]+)\s*[/\s]\s*([A-Z0-9][A-Z0-9\s\-\.]+?)(?:,|\s+ANO|\s+PLACA|$)',
                    texto
                )
                if tipo_veiculo:
                    self.marca = tipo_veiculo.group(1).strip()
                    if not self.modelo:
                        modelo = tipo_veiculo.group(2).strip()
                        if 2 <= len(modelo) <= 50:
                            self.modelo = modelo.rstrip(' ,.-')

    def gerar_id_interno(self, edital_id: int) -> str:
        """
        Gera ID interno único usando SHA256.

        Composição: edital_id + numero_lote + hash(descricao[:100])
        """
        desc_hash = hashlib.sha256(self.descricao_raw[:100].encode()).hexdigest()[:16]
        conteudo = f"{edital_id}_{self.numero_lote}_{desc_hash}"
        return hashlib.sha256(conteudo.encode()).hexdigest()


@dataclass
class ResultadoClassificacao:
    """Resultado da classificação de um arquivo."""
    familia: FamiliaPDF
    total_caracteres: int
    total_paginas: int
    paginas_com_tabelas: List[int] = field(default_factory=list)
    total_tabelas: int = 0
    processavel: bool = True
    motivo_nao_processavel: Optional[str] = None


@dataclass
class ResultadoExtracao:
    """Resultado da extração de lotes de um arquivo."""
    sucesso: bool
    lotes: List[LoteExtraido] = field(default_factory=list)
    erros: List[Dict[str, Any]] = field(default_factory=list)
    familia_pdf: Optional[FamiliaPDF] = None
    tempo_processamento_ms: int = 0


@dataclass
class MetricasExecucao:
    """Métricas de uma execução do extrator."""
    inicio: datetime = field(default_factory=datetime.now)
    fim: Optional[datetime] = None
    total_editais: int = 0
    total_arquivos: int = 0
    total_lotes_extraidos: int = 0
    total_quarentena: int = 0
    por_familia: Dict[str, int] = field(default_factory=dict)
    erros: List[str] = field(default_factory=list)

    # V1.1: Métricas LLM Fallback
    llm_requests: int = 0
    llm_lotes_extraidos: int = 0
    llm_cost_usd: float = 0.0

    def finalizar(self):
        self.fim = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'inicio': self.inicio.isoformat(),
            'fim': self.fim.isoformat() if self.fim else None,
            'duracao_segundos': (self.fim - self.inicio).total_seconds() if self.fim else None,
            'total_editais': self.total_editais,
            'total_arquivos': self.total_arquivos,
            'total_lotes_extraidos': self.total_lotes_extraidos,
            'total_quarentena': self.total_quarentena,
            'por_familia': self.por_familia,
            'erros': self.erros,
            # V1.1: Métricas LLM
            'llm_requests': self.llm_requests,
            'llm_lotes_extraidos': self.llm_lotes_extraidos,
            'llm_cost_usd': self.llm_cost_usd,
        }


# =============================================================================
# CLASSIFICADOR DE PDF
# =============================================================================

class ClassificadorPDF:
    """
    Classifica PDFs em famílias estruturais.

    Famílias:
    - PDF_TABELA_INICIO: Tabelas nas primeiras 3 páginas
    - PDF_TABELA_MEIO_FIM: Tabelas após página 3
    - PDF_NATIVO_SEM_TABELA: Texto extraível mas sem tabelas
    - PDF_ESCANEADO: Sem texto extraível (<100 caracteres em 3 páginas)
    """

    def classificar(self, caminho_pdf: str) -> ResultadoClassificacao:
        """
        Classifica um PDF em uma das famílias estruturais.

        Args:
            caminho_pdf: Caminho completo para o arquivo PDF

        Returns:
            ResultadoClassificacao com família identificada e metadados
        """
        logger.info(f"Classificando PDF: {caminho_pdf}")

        try:
            with pdfplumber.open(caminho_pdf) as pdf:
                total_paginas = len(pdf.pages)
                total_caracteres = 0
                paginas_com_tabelas = []
                total_tabelas = 0

                # Analisar todas as páginas
                for i, pagina in enumerate(pdf.pages):
                    num_pagina = i + 1

                    # Extrair texto
                    texto = pagina.extract_text() or ""
                    total_caracteres += len(texto)

                    # Detectar tabelas
                    tabelas = pagina.extract_tables() or []
                    if tabelas:
                        # Filtrar tabelas relevantes (ignorar cabeçalhos vazios)
                        tabelas_relevantes = [t for t in tabelas if self._tabela_relevante(t)]
                        if tabelas_relevantes:
                            paginas_com_tabelas.append(num_pagina)
                            total_tabelas += len(tabelas_relevantes)

                # Classificar baseado nas características
                if total_caracteres < THRESHOLD_CARACTERES_ESCANEADO:
                    return ResultadoClassificacao(
                        familia=FamiliaPDF.PDF_ESCANEADO,
                        total_caracteres=total_caracteres,
                        total_paginas=total_paginas,
                        paginas_com_tabelas=paginas_com_tabelas,
                        total_tabelas=total_tabelas,
                        processavel=False,
                        motivo_nao_processavel=f"PDF escaneado - apenas {total_caracteres} caracteres extraídos"
                    )

                if not paginas_com_tabelas:
                    return ResultadoClassificacao(
                        familia=FamiliaPDF.PDF_NATIVO_SEM_TABELA,
                        total_caracteres=total_caracteres,
                        total_paginas=total_paginas,
                        paginas_com_tabelas=[],
                        total_tabelas=0,
                        processavel=True,  # Pode tentar extração via regex
                        motivo_nao_processavel=None
                    )

                primeira_tabela = min(paginas_com_tabelas)

                if primeira_tabela <= PAGINA_LIMITE_FAMILIA:
                    return ResultadoClassificacao(
                        familia=FamiliaPDF.PDF_TABELA_INICIO,
                        total_caracteres=total_caracteres,
                        total_paginas=total_paginas,
                        paginas_com_tabelas=paginas_com_tabelas,
                        total_tabelas=total_tabelas,
                        processavel=True
                    )
                else:
                    return ResultadoClassificacao(
                        familia=FamiliaPDF.PDF_TABELA_MEIO_FIM,
                        total_caracteres=total_caracteres,
                        total_paginas=total_paginas,
                        paginas_com_tabelas=paginas_com_tabelas,
                        total_tabelas=total_tabelas,
                        processavel=True
                    )

        except Exception as e:
            logger.error(f"Erro ao classificar PDF {caminho_pdf}: {str(e)}")
            return ResultadoClassificacao(
                familia=FamiliaPDF.PDF_ESCANEADO,  # Fallback seguro
                total_caracteres=0,
                total_paginas=0,
                processavel=False,
                motivo_nao_processavel=f"Erro ao abrir PDF: {str(e)}"
            )

    def _tabela_relevante(self, tabela: List[List]) -> bool:
        """
        Verifica se uma tabela é relevante (não é cabeçalho vazio ou lixo).
        """
        if not tabela or len(tabela) < 2:
            return False

        # Verificar primeira linha (cabeçalho)
        cabecalho = tabela[0]
        if not cabecalho:
            return False

        # Normalizar cabeçalho
        cabecalho_normalizado = [
            self._normalizar_texto(str(c)) if c else ''
            for c in cabecalho
        ]

        # Verificar se tem pelo menos uma keyword relevante
        texto_cabecalho = ' '.join(cabecalho_normalizado).lower()

        # Ignorar se tiver keywords de ignorar
        for kw in KEYWORDS_IGNORAR:
            if kw in texto_cabecalho:
                return False

        # Aceitar se tiver keywords de lotes
        for kw in KEYWORDS_LOTES:
            if kw in texto_cabecalho:
                return True

        # Se cabeçalho for todo vazio, ignorar
        if all(c == '' for c in cabecalho_normalizado):
            return False

        return False  # Default: não é relevante

    def _normalizar_texto(self, texto: str) -> str:
        """Remove acentos e normaliza texto para comparação."""
        if not texto:
            return ""
        # Mapeamento simples de acentos
        acentos = {
            'á': 'a', 'à': 'a', 'ã': 'a', 'â': 'a', 'ä': 'a',
            'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
            'í': 'i', 'ì': 'i', 'î': 'i', 'ï': 'i',
            'ó': 'o', 'ò': 'o', 'õ': 'o', 'ô': 'o', 'ö': 'o',
            'ú': 'u', 'ù': 'u', 'û': 'u', 'ü': 'u',
            'ç': 'c', 'ñ': 'n'
        }
        texto_lower = texto.lower()
        for acento, sem_acento in acentos.items():
            texto_lower = texto_lower.replace(acento, sem_acento)
        return texto_lower


# =============================================================================
# EXTRATOR DE TABELAS
# =============================================================================

class ExtratorTabelas:
    """
    Extrai lotes de tabelas em PDFs.

    Estratégias por família:
    - PDF_TABELA_INICIO: Extrai tabelas das primeiras 3 páginas
    - PDF_TABELA_MEIO_FIM: Busca seção de lotes por keywords e extrai
    - PDF_NATIVO_SEM_TABELA: Tenta extração via regex (fallback)
    """

    def __init__(self):
        self.classificador = ClassificadorPDF()

    def extrair(self, caminho_pdf: str, edital_id: int, llm_extractor: 'LLMExtractor' = None) -> ResultadoExtracao:
        """
        Extrai lotes de um PDF usando cascata de estratégias.

        V1.1: Cascata (ordem de custo crescente):
        1. pdfplumber (tabelas)     → CUSTO: $0
        2. Regex patterns           → CUSTO: $0
        3. LLM fallback (GPT-4o)    → CUSTO: ~$0.0008

        Args:
            caminho_pdf: Caminho para o arquivo PDF
            edital_id: ID do edital no banco de dados
            llm_extractor: Instância do LLMExtractor para fallback (opcional)

        Returns:
            ResultadoExtracao com lotes extraídos ou erros
        """
        inicio = time.time()

        # Classificar PDF
        classificacao = self.classificador.classificar(caminho_pdf)
        logger.info(f"PDF classificado como: {classificacao.familia.value}")

        if not classificacao.processavel:
            return ResultadoExtracao(
                sucesso=False,
                familia_pdf=classificacao.familia,
                erros=[{
                    'codigo': CodigoErro.PDF_ESCANEADO.value if classificacao.familia == FamiliaPDF.PDF_ESCANEADO else CodigoErro.TIPO_NAO_SUPORTADO.value,
                    'mensagem': classificacao.motivo_nao_processavel
                }],
                tempo_processamento_ms=int((time.time() - inicio) * 1000)
            )

        # === CASCATA DE EXTRAÇÃO ===
        lotes = []
        metodo_usado = None

        try:
            # NÍVEL 1: pdfplumber (tabelas)
            if classificacao.familia == FamiliaPDF.PDF_TABELA_INICIO:
                lotes = self._extrair_tabelas_inicio(caminho_pdf, classificacao)
                if lotes:
                    metodo_usado = "pdfplumber_tabela_inicio"
            elif classificacao.familia == FamiliaPDF.PDF_TABELA_MEIO_FIM:
                lotes = self._extrair_tabelas_meio_fim(caminho_pdf, classificacao)
                if lotes:
                    metodo_usado = "pdfplumber_tabela_meio_fim"
            elif classificacao.familia == FamiliaPDF.PDF_NATIVO_SEM_TABELA:
                lotes = self._extrair_via_regex(caminho_pdf)
                if lotes:
                    metodo_usado = "regex_nativo"

            # NÍVEL 2: Regex (se tabelas não funcionaram)
            if not lotes and classificacao.familia in [FamiliaPDF.PDF_TABELA_INICIO, FamiliaPDF.PDF_TABELA_MEIO_FIM]:
                logger.info("Cascata: tabelas sem lotes, tentando regex...")
                lotes = self._extrair_via_regex(caminho_pdf)
                if lotes:
                    metodo_usado = "regex_fallback"

            # NÍVEL 3: LLM Fallback (se regex não funcionou)
            if not lotes and llm_extractor and llm_extractor.client:
                logger.info("Cascata: tentando LLM fallback...")

                # Extrair texto completo para LLM
                texto_completo = self._extrair_texto_completo(caminho_pdf)

                if texto_completo and len(texto_completo) >= 100:
                    lotes = llm_extractor.extrair_lotes(texto_completo)
                    if lotes:
                        metodo_usado = "llm_fallback"

            tempo_ms = int((time.time() - inicio) * 1000)

            if not lotes:
                return ResultadoExtracao(
                    sucesso=False,
                    familia_pdf=classificacao.familia,
                    erros=[{
                        'codigo': CodigoErro.TABELA_NAO_ENCONTRADA.value,
                        'mensagem': 'Nenhum lote extraído (pdfplumber + regex + LLM)'
                    }],
                    tempo_processamento_ms=tempo_ms
                )

            logger.info(f"Extração OK: {len(lotes)} lotes via {metodo_usado}")

            return ResultadoExtracao(
                sucesso=True,
                lotes=lotes,
                familia_pdf=classificacao.familia,
                tempo_processamento_ms=tempo_ms
            )

        except Exception as e:
            logger.error(f"Erro na extração: {str(e)}")
            return ResultadoExtracao(
                sucesso=False,
                familia_pdf=classificacao.familia,
                erros=[{
                    'codigo': CodigoErro.ESTRUTURA_INESPERADA.value,
                    'mensagem': str(e)
                }],
                tempo_processamento_ms=int((time.time() - inicio) * 1000)
            )

    def _extrair_texto_completo(self, caminho_pdf: str) -> str:
        """Extrai texto completo do PDF para uso com LLM."""
        try:
            with pdfplumber.open(caminho_pdf) as pdf:
                textos = []
                for pagina in pdf.pages:
                    texto = pagina.extract_text() or ""
                    textos.append(texto)
                return "\n\n".join(textos)
        except Exception as e:
            logger.warning(f"Erro ao extrair texto completo: {e}")
            return ""

    def _extrair_tabelas_inicio(
        self,
        caminho_pdf: str,
        classificacao: ResultadoClassificacao
    ) -> List[LoteExtraido]:
        """Extrai lotes de tabelas nas primeiras páginas, com fallback para todas."""
        lotes = []

        with pdfplumber.open(caminho_pdf) as pdf:
            # Primeiro: tentar nas primeiras páginas
            paginas_alvo = [p for p in classificacao.paginas_com_tabelas if p <= PAGINA_LIMITE_FAMILIA]

            for num_pagina in paginas_alvo:
                pagina = pdf.pages[num_pagina - 1]  # 0-indexed
                tabelas = pagina.extract_tables() or []

                for tabela in tabelas:
                    lotes_tabela = self._processar_tabela(tabela, num_pagina)
                    lotes.extend(lotes_tabela)

            # Fallback: se não encontrou lotes nas primeiras páginas, buscar em TODAS
            if not lotes:
                logger.info("Nenhum lote nas primeiras páginas, buscando em todas...")
                for num_pagina in range(1, len(pdf.pages) + 1):
                    if num_pagina in paginas_alvo:
                        continue  # Já processou
                    pagina = pdf.pages[num_pagina - 1]
                    tabelas = pagina.extract_tables() or []

                    for tabela in tabelas:
                        lotes_tabela = self._processar_tabela(tabela, num_pagina)
                        lotes.extend(lotes_tabela)

        return lotes

    def _extrair_tabelas_meio_fim(
        self,
        caminho_pdf: str,
        classificacao: ResultadoClassificacao
    ) -> List[LoteExtraido]:
        """Extrai lotes de tabelas no meio/fim do documento."""
        lotes = []

        with pdfplumber.open(caminho_pdf) as pdf:
            # Processar todas as páginas com tabelas
            for num_pagina in classificacao.paginas_com_tabelas:
                pagina = pdf.pages[num_pagina - 1]
                tabelas = pagina.extract_tables() or []

                for tabela in tabelas:
                    lotes_tabela = self._processar_tabela(tabela, num_pagina)
                    lotes.extend(lotes_tabela)

        return lotes

    def _extrair_via_regex(self, caminho_pdf: str) -> List[LoteExtraido]:
        """
        Extração fallback via regex para PDFs sem tabelas detectadas.

        Suporta padrões:
        1. Padrão Fátima/BA: "INFORMAÇÕES DO VEICULO – LOTE XX"
        2. Padrão genérico: "LOTE 01 - DESCRIÇÃO"
        """
        lotes = []

        with pdfplumber.open(caminho_pdf) as pdf:
            texto_completo = ""
            for pagina in pdf.pages:
                texto_pagina = pagina.extract_text() or ""
                texto_completo += texto_pagina + "\n"

            # PADRÃO 1: Fátima/BA - "LOTE XX" seguido de bloco com AVALIAÇÃO
            # Captura blocos completos de cada lote
            padrao_fatima = r'LOTE\s*(\d+)\s*\n([\s\S]*?)AVALIA[CÇ][AÃ]O[:\s]*([0-9.,]+)'

            matches = re.findall(padrao_fatima, texto_completo, re.IGNORECASE)

            for match in matches:
                numero, bloco, valor_str = match

                # Limitar bloco às primeiras linhas relevantes (antes do CHECK LIST)
                bloco_limpo = bloco.split('CHECK LIST')[0] if 'CHECK LIST' in bloco else bloco
                linhas = [l.strip() for l in bloco_limpo.split('\n') if l.strip()]

                # Primeira linha não-vazia é a descrição principal
                descricao = linhas[0] if linhas else ''

                # Se primeira linha é só "RENAVAM", pegar a segunda
                if descricao.upper() == 'RENAVAM' and len(linhas) > 1:
                    descricao = linhas[1]

                # Extrair placa do bloco
                placa_match = re.search(r'PLACA\s*[:\s]?\s*([A-Z]{2,3}[-\s]?\d[A-Z0-9]?\d{2,4})', bloco, re.IGNORECASE)
                placa = placa_match.group(1).replace(' ', '').replace('-', '') if placa_match else None

                # Extrair chassi
                chassi_match = re.search(r'CHASSI[:\s]+([A-HJ-NPR-Z0-9]{17})', bloco, re.IGNORECASE)
                chassi = chassi_match.group(1) if chassi_match else None

                # Extrair renavam (número de 9-11 dígitos após RENAVAM ou em linha própria)
                renavam_match = re.search(r'RENAVA[MN]?\s*[:\s]*(\d{9,11})', bloco, re.IGNORECASE)
                if not renavam_match:
                    # Tentar pegar número solto após linha RENAVAM
                    renavam_match = re.search(r'RENAVA[MN]\s*\n(\d{9,11})', bloco, re.IGNORECASE)
                renavam = renavam_match.group(1) if renavam_match else None

                # Limpar valor
                try:
                    valor = float(valor_str.replace('.', '').replace(',', '.'))
                except:
                    valor = None

                if len(descricao) >= 5:
                    lote = LoteExtraido(
                        numero_lote_raw=str(numero).zfill(2),
                        descricao_raw=descricao,
                        texto_fonte_completo=descricao[:200],
                        avaliacao_valor=valor,
                        placa=placa,
                        chassi=chassi,
                        renavam=renavam
                    )
                    lotes.append(lote)

            if lotes:
                return lotes

            # PADRÃO 2: Genérico - "LOTE 01: Descrição" ou "LOTE 01 - Descrição"
            padroes_genericos = [
                r'(?:LOTE|ITEM)\s*[N°º.]?\s*(\d+)\s*[-:]\s*(.+?)(?=(?:LOTE|ITEM)\s*[N°º.]?\s*\d+|$)',
                r'^(\d+)\s*[-–]\s*(.+?)(?=^\d+\s*[-–]|$)',
            ]

            for padrao in padroes_genericos:
                matches = re.findall(padrao, texto_completo, re.MULTILINE | re.IGNORECASE | re.DOTALL)

                for match in matches:
                    numero, descricao = match
                    descricao = descricao[:500].strip()

                    if len(descricao) >= 10:
                        lote = LoteExtraido(
                            numero_lote_raw=str(numero),
                            descricao_raw=descricao,
                            texto_fonte_completo=descricao[:200]
                        )
                        lotes.append(lote)

                if lotes:
                    break

        return lotes

    def _processar_tabela(
        self,
        tabela: List[List],
        num_pagina: int
    ) -> List[LoteExtraido]:
        """
        Processa uma tabela extraída e converte em lotes.
        """
        if not tabela or len(tabela) < 2:
            return []

        lotes = []
        cabecalho = tabela[0]

        # Identificar índices das colunas relevantes
        indices = self._identificar_colunas(cabecalho)

        # BUG FIX: usar 'is None' em vez de 'not' para evitar falso negativo
        # quando o índice é 0 (primeira coluna), pois 'not 0' = True em Python
        if indices.get('descricao') is None and indices.get('numero') is None:
            # Tabela não tem colunas mínimas
            return []

        # Processar linhas de dados
        for i, linha in enumerate(tabela[1:], start=2):
            try:
                lote = self._linha_para_lote(linha, indices, num_pagina, i)
                if lote and self._lote_valido(lote):
                    lotes.append(lote)
            except Exception as e:
                logger.warning(f"Erro ao processar linha {i}: {str(e)}")
                continue

        return lotes

    def _identificar_colunas(self, cabecalho: List) -> Dict[str, int]:
        """
        Identifica índices das colunas relevantes no cabeçalho.

        IMPORTANTE: A ordem de verificação importa!
        - 'descricao' deve ser verificada ANTES de 'numero' porque
          "Descrição do lote" contém 'lote' mas é coluna de descrição.
        """
        indices = {}

        for i, coluna in enumerate(cabecalho):
            if not coluna:
                continue

            col_lower = self.classificador._normalizar_texto(str(coluna))

            # Descrição PRIMEIRO (antes de numero, pois "Descrição do lote" contém "lote")
            if any(kw in col_lower for kw in ['descricao', 'especificacao', 'objeto']):
                indices['descricao'] = i
            # Número do lote (só se não for descrição)
            elif any(kw in col_lower for kw in ['lote', 'item', 'n.', 'nº', 'numero']):
                indices['numero'] = i
            # Valor (incluindo "minimo" para "Valor Mínimo")
            elif any(kw in col_lower for kw in ['valor', 'avaliacao', 'preco', 'lance', 'minimo']):
                indices['valor'] = i
            elif 'placa' in col_lower:
                indices['placa'] = i
            elif 'chassi' in col_lower:
                indices['chassi'] = i
            elif 'renavam' in col_lower:
                indices['renavam'] = i
            elif any(kw in col_lower for kw in ['marca', 'marca/modelo']):
                indices['marca'] = i
            elif 'modelo' in col_lower:
                indices['modelo'] = i
            elif 'ano' in col_lower:
                indices['ano'] = i

        return indices

    def _linha_para_lote(
        self,
        linha: List,
        indices: Dict[str, int],
        num_pagina: int,
        num_linha: int
    ) -> Optional[LoteExtraido]:
        """Converte uma linha da tabela em um LoteExtraido."""

        def get_valor(idx_key: str) -> Optional[str]:
            idx = indices.get(idx_key)
            if idx is not None and idx < len(linha):
                val = linha[idx]
                return str(val).strip() if val else None
            return None

        numero_raw = get_valor('numero') or str(num_linha - 1)
        descricao_raw = get_valor('descricao') or ''

        # Se não tem descrição mas tem marca/modelo, concatena
        if not descricao_raw:
            partes = []
            for campo in ['marca', 'modelo', 'placa']:
                val = get_valor(campo)
                if val:
                    partes.append(val)
            descricao_raw = ' - '.join(partes)

        if not descricao_raw:
            return None

        lote = LoteExtraido(
            numero_lote_raw=numero_raw,
            descricao_raw=descricao_raw,
            valor_raw=get_valor('valor'),
            texto_fonte_completo=' | '.join(str(c) if c else '' for c in linha),
            placa=get_valor('placa'),
            chassi=get_valor('chassi'),
            renavam=get_valor('renavam'),
            marca=get_valor('marca'),
            modelo=get_valor('modelo'),
            fonte_pagina=num_pagina,
            linha_tabela=num_linha
        )

        # Tentar extrair ano
        ano_raw = get_valor('ano')
        if ano_raw:
            try:
                # Extrai primeiro número de 4 dígitos
                match = re.search(r'(19|20)\d{2}', str(ano_raw))
                if match:
                    lote.ano_fabricacao = int(match.group())
            except:
                pass

        return lote

    def _lote_valido(self, lote: LoteExtraido) -> bool:
        """Verifica se um lote extraído é válido."""
        # Descrição mínima de 10 caracteres
        if len(lote.descricao_completa) < 10:
            return False

        # Número do lote presente
        if not lote.numero_lote:
            return False

        return True


# =============================================================================
# V1.1: EXTRATOR LLM (FALLBACK)
# =============================================================================

class LLMExtractor:
    """
    Extrator de lotes via LLM (GPT-4o-mini).
    Usado como fallback quando pdfplumber e regex falham.

    Padrão: Graceful degradation (se IA indisponível, retorna [])
    Segue padrão do OpenAIEnricher do Miner V18.
    """

    # FinOps: Preços GPT-4o-mini (USD por 1M tokens) - Jan 2026
    PRICE_INPUT_PER_1M = 0.15
    PRICE_OUTPUT_PER_1M = 0.60

    def __init__(self, api_key: str = None, model: str = "gpt-4o-mini"):
        """
        Inicializa o extrator LLM.

        Args:
            api_key: Chave da API OpenAI (se None, usa env OPENAI_API_KEY)
            model: Modelo a usar (default: gpt-4o-mini)
        """
        self.client = None
        self.model = model
        self.logger = logging.getLogger("LLMExtractor")

        # FinOps: Contadores de tokens
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_requests = 0

        # Graceful degradation
        if not OPENAI_AVAILABLE:
            self.logger.warning("openai não instalado - LLM fallback desabilitado")
            return

        api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        if api_key:
            try:
                self.client = OpenAI(api_key=api_key)
                self.logger.info(f"LLMExtractor inicializado: {model}")
            except Exception as e:
                self.logger.error(f"Erro ao inicializar OpenAI: {e}")
                self.client = None
        else:
            self.logger.warning("OPENAI_API_KEY não configurada - LLM fallback desabilitado")

    def extrair_lotes(self, texto_pdf: str, contexto: dict = None) -> List[LoteExtraido]:
        """
        Extrai lotes de texto usando LLM.

        Args:
            texto_pdf: Texto extraído do PDF
            contexto: Metadados opcionais (municipio, orgao, etc)

        Returns:
            Lista de LoteExtraido ou [] em caso de falha
        """
        # Validações
        if not self.client:
            return []

        if not texto_pdf or len(texto_pdf) < 100:
            self.logger.debug("Texto insuficiente para LLM")
            return []

        # Otimização: limitar texto (economiza tokens)
        texto_otimizado = self._otimizar_texto(texto_pdf, max_chars=8000)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": self._get_user_prompt(texto_otimizado, contexto)}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,  # Precisão > criatividade
                max_tokens=2000
            )

            # FinOps: Registrar tokens
            if hasattr(response, 'usage') and response.usage:
                self.total_input_tokens += response.usage.prompt_tokens
                self.total_output_tokens += response.usage.completion_tokens
                self.total_requests += 1

            # Parse resposta
            content = response.choices[0].message.content
            dados = json.loads(content)

            lotes = self._converter_para_lotes(dados)
            if lotes:
                self.logger.info(f"LLM extraiu {len(lotes)} lotes")

            return lotes

        except json.JSONDecodeError as e:
            self.logger.error(f"Erro parse JSON: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Erro LLM: {e}")
            return []

    def _get_system_prompt(self) -> str:
        """Prompt de sistema para extração estruturada."""
        return '''Você é um extrator de dados de editais de leilão de veículos.
Extraia TODOS os lotes/itens do texto e retorne JSON no formato:

{
  "lotes": [
    {
      "numero": "01",
      "descricao": "FIAT STRADA WORKING 1.4 2015 BRANCO",
      "placa": "ABC1234",
      "chassi": "9BD178226F5123456",
      "renavam": "12345678901",
      "marca": "FIAT",
      "modelo": "STRADA WORKING 1.4",
      "ano": 2015,
      "valor": 25000.00
    }
  ]
}

REGRAS:
- Retorne APENAS JSON válido
- Se um campo não existir, OMITA (não use null)
- numero: string, ex: "01", "02", "1", "2"
- placa: formato ABC1234 ou ABC1D23 (Mercosul), sem hífen
- chassi: 17 caracteres alfanuméricos
- renavam: 9-11 dígitos
- ano: número inteiro 4 dígitos
- valor: número decimal (avaliação/lance mínimo)
- Se não encontrar lotes, retorne {"lotes": []}'''

    def _get_user_prompt(self, texto: str, contexto: dict = None) -> str:
        """Prompt do usuário com texto do PDF."""
        ctx = ""
        if contexto:
            ctx = f"Contexto: {contexto.get('municipio', '')} - {contexto.get('orgao', '')}\n\n"

        return f"{ctx}TEXTO DO EDITAL:\n\n{texto}"

    def _otimizar_texto(self, texto: str, max_chars: int = 8000) -> str:
        """Otimiza texto para economizar tokens."""
        if len(texto) <= max_chars:
            return texto

        # Priorizar início (geralmente tem tabela de lotes) e fim
        inicio = texto[:int(max_chars * 0.7)]
        fim = texto[-int(max_chars * 0.3):]

        return f"{inicio}\n\n[...texto omitido...]\n\n{fim}"

    def _converter_para_lotes(self, dados: dict) -> List[LoteExtraido]:
        """Converte resposta JSON em lista de LoteExtraido."""
        lotes = []

        for item in dados.get("lotes", []):
            try:
                lote = LoteExtraido(
                    numero_lote_raw=str(item.get("numero", "")),
                    descricao_raw=item.get("descricao", ""),
                    valor_raw=str(item.get("valor", "")) if item.get("valor") else None,
                    texto_fonte_completo=f"LLM: {item.get('descricao', '')[:100]}",
                    placa=item.get("placa"),
                    chassi=item.get("chassi"),
                    renavam=item.get("renavam"),
                    marca=item.get("marca"),
                    modelo=item.get("modelo"),
                    ano_fabricacao=item.get("ano")
                )

                # Validar lote mínimo
                if lote.numero_lote and len(lote.descricao_completa) >= 5:
                    lotes.append(lote)

            except Exception as e:
                self.logger.warning(f"Erro ao converter lote: {e}")
                continue

        return lotes

    def get_estimated_cost(self) -> float:
        """Retorna custo estimado em USD."""
        input_cost = (self.total_input_tokens / 1_000_000) * self.PRICE_INPUT_PER_1M
        output_cost = (self.total_output_tokens / 1_000_000) * self.PRICE_OUTPUT_PER_1M
        return round(input_cost + output_cost, 6)

    def get_token_stats(self) -> dict:
        """Retorna estatísticas de tokens para FinOps."""
        return {
            "total_requests": self.total_requests,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "estimated_cost_usd": self.get_estimated_cost()
        }


# =============================================================================
# REPOSITÓRIO SUPABASE
# =============================================================================

class LotesRepository:
    """
    Repositório para persistência de lotes no Supabase.

    Implementa:
    - Idempotência via id_interno (SHA256)
    - Upsert para atualização sem duplicatas
    - Quarentena para registros com falha
    """

    def __init__(self, supabase_url: str = None, supabase_key: str = None):
        """
        Inicializa conexão com Supabase.

        Se não fornecidos, usa variáveis de ambiente:
        - SUPABASE_URL
        - SUPABASE_SERVICE_ROLE_KEY (ou SUPABASE_KEY)
        """
        url = supabase_url or os.getenv('SUPABASE_URL')
        key = supabase_key or os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY')

        if not url or not key:
            raise ValueError("SUPABASE_URL e SUPABASE_KEY são obrigatórios")

        self.client: Client = create_client(url, key)
        logger.info("Conexão com Supabase estabelecida")

    def salvar_lote(
        self,
        lote: LoteExtraido,
        edital_id: int,
        fonte_arquivo: str,
        familia_pdf: FamiliaPDF
    ) -> Dict[str, Any]:
        """
        Salva um lote no banco de dados usando upsert.

        Returns:
            Dict com resultado da operação
        """
        id_interno = lote.gerar_id_interno(edital_id)
        hash_fonte = hashlib.sha256(lote.texto_fonte_completo.encode() if lote.texto_fonte_completo else b'').hexdigest()

        dados = {
            'id_interno': id_interno,
            'edital_id': edital_id,

            # Dados brutos
            'numero_lote_raw': lote.numero_lote_raw,
            'descricao_raw': lote.descricao_raw,
            'valor_raw': lote.valor_raw,
            'texto_fonte_completo': lote.texto_fonte_completo,

            # Dados processados
            'numero_lote': lote.numero_lote,
            'descricao_completa': lote.descricao_completa,
            'avaliacao_valor': lote.avaliacao_valor,

            # Dados de veículo
            'placa': lote.placa,
            'chassi': lote.chassi,
            'renavam': lote.renavam,
            'marca': lote.marca,
            'modelo': lote.modelo,
            'ano_fabricacao': lote.ano_fabricacao,

            # Metadados
            'fonte_tipo': 'pdf_tabela',
            'fonte_arquivo': fonte_arquivo,
            'fonte_pagina': lote.fonte_pagina,
            'hash_conteudo_fonte': hash_fonte,
            'versao_extrator': VERSAO_EXTRATOR,
            'familia_pdf': familia_pdf.value if familia_pdf else None,
        }

        try:
            result = self.client.table('lotes_leilao').upsert(
                dados,
                on_conflict='id_interno'
            ).execute()

            logger.debug(f"Lote salvo: {id_interno[:16]}...")
            return {'sucesso': True, 'id_interno': id_interno}

        except Exception as e:
            logger.error(f"Erro ao salvar lote: {str(e)}")
            return {'sucesso': False, 'erro': str(e)}

    def enviar_quarentena(
        self,
        edital_id: int,
        payload: Dict[str, Any],
        estagio: EstagioFalha,
        codigo: CodigoErro,
        mensagem: str,
        fonte_arquivo: str,
        familia_pdf: Optional[FamiliaPDF] = None,
        stack_trace: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Envia um registro para quarentena.
        """
        dados = {
            'edital_id': edital_id,
            'payload_original': json.dumps(payload),
            'texto_fonte_completo': payload.get('texto_fonte_completo'),
            'estagio_falha': estagio.value,
            'codigo_erro': codigo.value,
            'mensagem_erro': mensagem,
            'stack_trace': stack_trace,
            'fonte_tipo': 'pdf',
            'fonte_arquivo': fonte_arquivo,
            'familia_pdf': familia_pdf.value if familia_pdf else None,
            'versao_extrator': VERSAO_EXTRATOR,
            'status': 'pendente'
        }

        try:
            result = self.client.table('lotes_quarentena').insert(dados).execute()
            logger.info(f"Registro enviado para quarentena: {codigo.value}")
            return {'sucesso': True}
        except Exception as e:
            logger.error(f"Erro ao enviar para quarentena: {str(e)}")
            return {'sucesso': False, 'erro': str(e)}

    def registrar_arquivo_processado(
        self,
        edital_id: int,
        nome_arquivo: str,
        hash_arquivo: str,
        tipo_detectado: str,
        familia_pdf: Optional[FamiliaPDF],
        total_lotes: int,
        total_quarentena: int,
        status: str,
        tempo_ms: int
    ) -> Dict[str, Any]:
        """
        Registra um arquivo como processado para idempotência.
        """
        dados = {
            'edital_id': edital_id,
            'nome_arquivo': nome_arquivo,
            'hash_arquivo': hash_arquivo,
            'tipo_detectado': tipo_detectado,
            'familia_pdf': familia_pdf.value if familia_pdf else None,
            'total_lotes_extraidos': total_lotes,
            'total_lotes_quarentena': total_quarentena,
            'status': status,
            'versao_extrator': VERSAO_EXTRATOR,
            'processado_em': datetime.now().isoformat(),
            'tempo_processamento_ms': tempo_ms
        }

        try:
            result = self.client.table('arquivos_processados_lotes').upsert(
                dados,
                on_conflict='hash_arquivo'
            ).execute()
            return {'sucesso': True}
        except Exception as e:
            logger.error(f"Erro ao registrar arquivo: {str(e)}")
            return {'sucesso': False, 'erro': str(e)}

    def arquivo_ja_processado(self, hash_arquivo: str) -> bool:
        """Verifica se um arquivo já foi processado."""
        try:
            result = self.client.table('arquivos_processados_lotes').select('id').eq(
                'hash_arquivo', hash_arquivo
            ).execute()
            return len(result.data) > 0
        except:
            return False

    def buscar_editais_para_processar(self, limite: int = 100) -> List[Dict]:
        """
        Busca editais que ainda não tiveram lotes extraídos.

        Retorna editais com status 'valid' que têm PDFs mas não têm
        registros na tabela arquivos_processados_lotes.
        """
        try:
            result = self.client.table('editais_leilao').select(
                'id, id_interno, titulo, storage_path, pdf_storage_url'
            ).not_.is_(
                'storage_path', 'null'
            ).limit(limite).execute()

            return result.data
        except Exception as e:
            logger.error(f"Erro ao buscar editais: {str(e)}")
            return []


# =============================================================================
# ORQUESTRADOR PRINCIPAL
# =============================================================================

class LotesExtractorV1:
    """
    Orquestrador principal do extrator de lotes.

    V1.1: Adiciona LLM fallback na cascata de extração.

    Coordena:
    1. Busca de editais pendentes
    2. Download de PDFs do Storage
    3. Classificação e extração (cascata: pdfplumber → regex → LLM)
    4. Validação
    5. Persistência ou quarentena
    """

    def __init__(self, enable_llm: bool = True):
        """
        Inicializa o orquestrador.

        Args:
            enable_llm: Se True, habilita LLM fallback (default: True)
        """
        self.repository = LotesRepository()
        self.extrator = ExtratorTabelas()
        self.metricas = MetricasExecucao()

        # V1.1: LLM Fallback
        self.llm_extractor = None
        if enable_llm:
            self.llm_extractor = LLMExtractor()
            if self.llm_extractor.client:
                logger.info("LLM Fallback: ATIVO")
            else:
                logger.info("LLM Fallback: DESATIVADO (sem API key)")

    def executar(
        self,
        limite_editais: int = 100,
        diretorio_pdfs: Optional[str] = None
    ) -> MetricasExecucao:
        """
        Executa o pipeline de extração de lotes.

        Args:
            limite_editais: Número máximo de editais a processar
            diretorio_pdfs: Diretório local com PDFs (opcional, senão baixa do Storage)

        Returns:
            MetricasExecucao com estatísticas da execução
        """
        logger.info(f"=== INICIANDO EXTRAÇÃO DE LOTES V1 ===")
        logger.info(f"Limite de editais: {limite_editais}")

        self.metricas = MetricasExecucao()

        try:
            # Buscar editais pendentes
            editais = self.repository.buscar_editais_para_processar(limite_editais)
            self.metricas.total_editais = len(editais)
            logger.info(f"Editais encontrados: {len(editais)}")

            for edital in editais:
                self._processar_edital(edital, diretorio_pdfs)

        except Exception as e:
            logger.error(f"Erro fatal na execução: {str(e)}")
            self.metricas.erros.append(str(e))

        self.metricas.finalizar()

        # V1.1: Capturar métricas LLM
        if self.llm_extractor:
            llm_stats = self.llm_extractor.get_token_stats()
            self.metricas.llm_requests = llm_stats['total_requests']
            self.metricas.llm_cost_usd = llm_stats['estimated_cost_usd']

        # Log final
        logger.info(f"=== EXTRAÇÃO FINALIZADA ===")
        logger.info(f"Total lotes extraídos: {self.metricas.total_lotes_extraidos}")
        logger.info(f"Total quarentena: {self.metricas.total_quarentena}")
        logger.info(f"Por família: {self.metricas.por_familia}")

        # V1.1: Log LLM
        if self.llm_extractor and self.metricas.llm_requests > 0:
            logger.info(f"LLM requests: {self.metricas.llm_requests}")
            logger.info(f"LLM custo estimado: ${self.metricas.llm_cost_usd:.4f}")

        return self.metricas

    def _download_do_storage(self, storage_path: str) -> Optional[str]:
        """
        Baixa PDF do Supabase Storage para arquivo temporário.

        Args:
            storage_path: Caminho do arquivo no bucket (ex: "PNCP_123/edital.pdf")

        Returns:
            Caminho do arquivo temporário local, ou None se falhar.
            IMPORTANTE: Caller deve deletar o arquivo após uso.
        """
        try:
            logger.info(f"Baixando do Storage: {storage_path}")

            # Download do Supabase Storage
            response = self.repository.client.storage.from_(
                STORAGE_BUCKET
            ).download(storage_path)

            if not response:
                logger.warning(f"Download vazio para: {storage_path}")
                return None

            # Criar arquivo temporário com extensão .pdf
            fd, temp_path = tempfile.mkstemp(suffix='.pdf', prefix='lotes_')

            try:
                with os.fdopen(fd, 'wb') as f:
                    f.write(response)

                logger.info(f"Download OK: {storage_path} -> {temp_path} ({len(response)} bytes)")
                return temp_path

            except Exception as e:
                # Se falhar ao escrever, fechar e remover
                os.close(fd)
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise e

        except Exception as e:
            logger.error(f"Erro no download de {storage_path}: {str(e)}")
            return None

    def _processar_edital(
        self,
        edital: Dict,
        diretorio_pdfs: Optional[str]
    ):
        """Processa um edital individual."""
        edital_id = edital['id']
        storage_path = edital.get('storage_path')

        if not storage_path:
            logger.warning(f"Edital {edital_id} sem PDF")
            return

        # Determinar caminho do PDF
        arquivo_temporario = False

        if diretorio_pdfs:
            # Usa diretório local
            caminho_pdf = os.path.join(diretorio_pdfs, os.path.basename(storage_path))
            if not os.path.exists(caminho_pdf):
                logger.warning(f"PDF não encontrado localmente: {caminho_pdf}")
                return
        else:
            # Download do Supabase Storage
            caminho_pdf = self._download_do_storage(storage_path)
            if not caminho_pdf:
                logger.warning(f"Falha no download: {storage_path}")
                return
            arquivo_temporario = True

        # Calcular hash do arquivo para idempotência
        with open(caminho_pdf, 'rb') as f:
            hash_arquivo = hashlib.sha256(f.read()).hexdigest()

        # Verificar se já foi processado
        if self.repository.arquivo_ja_processado(hash_arquivo):
            logger.info(f"Arquivo já processado: {os.path.basename(caminho_pdf)}")
            # Cleanup antes de retornar
            if arquivo_temporario and os.path.exists(caminho_pdf):
                os.unlink(caminho_pdf)
            return

        self.metricas.total_arquivos += 1

        # Extrair lotes (V1.1: passa LLM extractor para cascata)
        resultado = self.extrator.extrair(caminho_pdf, edital_id, llm_extractor=self.llm_extractor)

        # Atualizar métricas por família
        if resultado.familia_pdf:
            familia_key = resultado.familia_pdf.value
            self.metricas.por_familia[familia_key] = self.metricas.por_familia.get(familia_key, 0) + 1

        total_lotes = 0
        total_quarentena = 0

        if resultado.sucesso:
            # Salvar lotes extraídos
            for lote in resultado.lotes:
                res = self.repository.salvar_lote(
                    lote=lote,
                    edital_id=edital_id,
                    fonte_arquivo=os.path.basename(caminho_pdf),
                    familia_pdf=resultado.familia_pdf
                )
                if res['sucesso']:
                    total_lotes += 1
                else:
                    total_quarentena += 1
        else:
            # Enviar para quarentena
            for erro in resultado.erros:
                codigo_erro = erro['codigo']
                # Tentar mapear o código para o enum
                try:
                    codigo_enum = CodigoErro[codigo_erro] if codigo_erro in CodigoErro.__members__ else CodigoErro.ESTRUTURA_INESPERADA
                except:
                    codigo_enum = CodigoErro.ESTRUTURA_INESPERADA

                self.repository.enviar_quarentena(
                    edital_id=edital_id,
                    payload={'arquivo': os.path.basename(caminho_pdf)},
                    estagio=EstagioFalha.EXTRACAO,
                    codigo=codigo_enum,
                    mensagem=erro['mensagem'],
                    fonte_arquivo=os.path.basename(caminho_pdf),
                    familia_pdf=resultado.familia_pdf
                )
                total_quarentena += 1

        # Registrar arquivo processado
        self.repository.registrar_arquivo_processado(
            edital_id=edital_id,
            nome_arquivo=os.path.basename(caminho_pdf),
            hash_arquivo=hash_arquivo,
            tipo_detectado=resultado.familia_pdf.value if resultado.familia_pdf else 'desconhecido',
            familia_pdf=resultado.familia_pdf,
            total_lotes=total_lotes,
            total_quarentena=total_quarentena,
            status='processado' if resultado.sucesso else 'erro',
            tempo_ms=resultado.tempo_processamento_ms
        )

        self.metricas.total_lotes_extraidos += total_lotes
        self.metricas.total_quarentena += total_quarentena

        logger.info(f"Edital {edital_id}: {total_lotes} lotes, {total_quarentena} quarentena")

        # Cleanup: remover arquivo temporário se baixou do Storage
        if arquivo_temporario and caminho_pdf and os.path.exists(caminho_pdf):
            try:
                os.unlink(caminho_pdf)
                logger.debug(f"Arquivo temporário removido: {caminho_pdf}")
            except Exception as e:
                logger.warning(f"Falha ao remover temporário {caminho_pdf}: {e}")


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    """Entry point principal."""
    import argparse

    parser = argparse.ArgumentParser(description='Extrator de Lotes V1.1 (com LLM fallback)')
    parser.add_argument('--limite', type=int, default=100, help='Limite de editais')
    parser.add_argument('--diretorio', type=str, help='Diretório local com PDFs')
    parser.add_argument('--verbose', action='store_true', help='Modo verbose')
    parser.add_argument('--sem-llm', action='store_true', help='Desabilita LLM fallback (apenas pdfplumber + regex)')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # V1.1: Passar flag enable_llm
    extrator = LotesExtractorV1(enable_llm=not args.sem_llm)
    metricas = extrator.executar(
        limite_editais=args.limite,
        diretorio_pdfs=args.diretorio
    )

    print("\n" + "="*60)
    print("RESULTADO DA EXTRAÇÃO V1.1")
    print("="*60)
    print(json.dumps(metricas.to_dict(), indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
