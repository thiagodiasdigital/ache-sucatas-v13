#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Ache Sucatas DaaS - Script de Saneamento Retroativo
====================================================
Identifica e corrige falsos positivos de link_leiloeiro já persistidos.

Versão: 1.0
Data: 2026-01-21

Características:
    - Idempotente: segunda execução não causa alterações adicionais
    - Preserva evidência: move link para link_leiloeiro_raw
    - Auditável: registra todos os registros afetados
    - Seguro: não deleta dados, apenas marca como inválidos

Uso:
    python sanitize_invalid_links.py --dry-run      # Apenas lista afetados
    python sanitize_invalid_links.py --execute      # Executa saneamento
    python sanitize_invalid_links.py --report       # Gera relatório JSON
"""

import argparse
import json
import logging
import os
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("Sanitizer")


# ============================================================
# PADRÕES DE FALSO POSITIVO
# ============================================================

# Regex para detectar TLD colado em palavra
# Exemplo: "VENEZUELANO-ED.COMEMORA" onde ".COM" está colado em "EMORA"
#
# IMPORTANTE: Esta regex só detecta casos ESPECÍFICOS de falso positivo:
# - TLD seguido de 3+ letras que NÃO formam outro TLD válido
# - Usa negative lookahead para excluir .com.br, .net.br, etc
#
# NÃO usamos CO/IO como TLDs porque causam falsos positivos em .com/.io válidos
REGEX_TLD_COLADO = re.compile(
    r'[A-Za-z0-9][\.\-][A-Za-z]+\.(COM|NET|ORG)(?!\.br|\.ar|\.mx|\.co|/)[A-Za-z]{3,}',
    re.IGNORECASE
)

# Lista de domínios conhecidos como falsos positivos
DOMINIOS_FALSOS_POSITIVOS = [
    "venezuelano-ed.com",
    "venezuelano",
    # Adicione outros domínios conhecidos aqui
]

# Whitelist de domínios VALIDADOS manualmente (não sanear)
# Adicionados em 2026-01-21 por validação do usuário
DOMINIOS_WHITELIST = [
    "bllcompras.com",
    "campinas.sp.gov.br",
    "atende.net",  # Cobre pomerode, janiopolis, consorciojacui, santarosadosul, terraroxa
    "sobradinho-rs.com.br",
]

# Padrões regex para identificação de falsos positivos
PADROES_FALSOS_POSITIVOS = [
    # TLD colado sem separador real
    (r'[A-Za-z]-[A-Za-z]+\.(com|net|org)[A-Za-z]', "tld_colado_hifen"),
    # Palavras concatenadas com TLD
    (r'[A-Za-z]{5,}\.(com|net|org)[A-Za-z]{3,}', "tld_colado_palavra"),
    # Domínios claramente inválidos
    (r'https?://[A-Za-z]+-[A-Za-z]+\.(com|net)(?!/)', "dominio_invalido_formato"),
]


# ============================================================
# ESTRUTURAS DE DADOS
# ============================================================

@dataclass
class RegistroAfetado:
    """Registro identificado para saneamento."""
    pncp_id: str
    link_atual: str
    motivo: str
    evidencia: Optional[str] = None
    status: str = "pendente"  # pendente, saneado, erro


@dataclass
class ResultadoSaneamento:
    """Resultado do processo de saneamento."""
    data_execucao: str
    modo: str  # dry-run ou execute
    total_analisados: int
    total_identificados: int
    total_saneados: int
    total_erros: int
    registros: List[dict]


# ============================================================
# IDENTIFICADOR DE FALSOS POSITIVOS
# ============================================================

class FalsoPositivoIdentificador:
    """Identifica falsos positivos em links de leiloeiro."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.padroes_compilados = [
            (re.compile(padrao, re.IGNORECASE), motivo)
            for padrao, motivo in PADROES_FALSOS_POSITIVOS
        ]

    def identificar(self, link: str) -> Optional[str]:
        """
        Identifica se o link é um falso positivo.

        Args:
            link: URL a verificar

        Returns:
            Motivo da rejeição ou None se válido
        """
        if not link:
            return None

        link_lower = link.lower()

        # PRIMEIRO: Verificar whitelist de domínios validados manualmente
        for dominio_ok in DOMINIOS_WHITELIST:
            if dominio_ok in link_lower:
                return None  # Domínio validado, não é falso positivo

        # Verificar domínios conhecidos como falsos positivos
        for dominio_fp in DOMINIOS_FALSOS_POSITIVOS:
            if dominio_fp in link_lower:
                return f"dominio_conhecido_invalido:{dominio_fp}"

        # Verificar padrões regex
        for regex, motivo in self.padroes_compilados:
            if regex.search(link):
                return motivo

        # Verificar TLD colado (verificação adicional)
        if REGEX_TLD_COLADO.search(link):
            return "tld_colado_generico"

        # Verificar se link não tem path e não é de plataforma conhecida
        if self._link_suspeito(link):
            return "link_suspeito_sem_indicador"

        return None

    def _link_suspeito(self, link: str) -> bool:
        """Verifica se link é suspeito (sem indicadores de leilão)."""
        link_lower = link.lower()

        # Indicadores de plataforma de leilão válida
        indicadores_validos = [
            "leilao", "leiloes", "leilão", "leilões",
            "bid", "lance", "franca", "sold", "hasta",
            "arremate", "superbid", "mega", "vip",
        ]

        # Extensões de TLD brasileiras válidas
        if ".com.br" in link_lower or ".net.br" in link_lower:
            # Tem TLD brasileiro, verificar se tem indicador
            for indicador in indicadores_validos:
                if indicador in link_lower:
                    return False  # Provavelmente válido
            # TLD brasileiro sem indicador - pode ser suspeito
            # Mas não marcar automaticamente como falso positivo
            return False

        # Links sem indicadores e sem TLD brasileiro
        for indicador in indicadores_validos:
            if indicador in link_lower:
                return False

        # Link sem nenhum indicador - suspeito
        return True


# ============================================================
# SANEADOR SUPABASE
# ============================================================

class SaneadorSupabase:
    """Executa saneamento no Supabase."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.client = None
        self.enable_supabase = False

        supabase_url = os.environ.get("SUPABASE_URL", "")
        supabase_key = os.environ.get("SUPABASE_SERVICE_KEY", os.environ.get("SUPABASE_KEY", ""))

        if not supabase_url or not supabase_key:
            self.logger.warning("Credenciais Supabase não configuradas")
            return

        try:
            from supabase import create_client
            self.client = create_client(supabase_url, supabase_key)
            self.enable_supabase = True
            self.logger.info("Supabase conectado")
        except ImportError:
            self.logger.error("Biblioteca supabase não instalada")
        except Exception as e:
            self.logger.error(f"Erro ao conectar Supabase: {e}")

    def buscar_links_para_verificar(self, limite: int = 1000) -> List[dict]:
        """
        Busca todos os links para verificação.

        Retorna registros que:
        - Têm link_leiloeiro preenchido
        - Ainda não foram processados pelo V19 (link_leiloeiro_valido IS NULL)
        - Ou foram marcados como válidos mas podem ser falsos positivos
        """
        if not self.enable_supabase:
            return []

        try:
            # Buscar registros com link que ainda não foram validados pelo V19
            response = (
                self.client.table("editais_leilao")
                .select("pncp_id, link_leiloeiro, link_leiloeiro_raw, link_leiloeiro_valido")
                .not_.is_("link_leiloeiro", "null")
                .neq("link_leiloeiro", "")
                .neq("link_leiloeiro", "N/D")
                .limit(limite)
                .execute()
            )
            return response.data

        except Exception as e:
            self.logger.error(f"Erro ao buscar registros: {e}")
            return []

    def sanear_registro(self, pncp_id: str, motivo: str) -> bool:
        """
        Saneia um registro marcado como falso positivo.

        Ações:
        1. Move link_leiloeiro para link_leiloeiro_raw (se não existir)
        2. Define link_leiloeiro_valido = false
        3. Define link_leiloeiro = null
        4. Registra origem_tipo como 'unknown' (pré-V19)

        Este método é IDEMPOTENTE:
        - Se já foi saneado (link_leiloeiro_valido = false), não faz nada
        - Se link_leiloeiro já é null, não faz nada
        """
        if not self.enable_supabase:
            return False

        try:
            # Primeiro, buscar o registro atual para verificar estado
            response = (
                self.client.table("editais_leilao")
                .select("link_leiloeiro, link_leiloeiro_raw, link_leiloeiro_valido")
                .eq("pncp_id", pncp_id)
                .single()
                .execute()
            )

            registro = response.data
            if not registro:
                self.logger.warning(f"Registro não encontrado: {pncp_id}")
                return False

            # Verificar se já foi saneado (idempotência)
            if registro.get("link_leiloeiro_valido") is False:
                self.logger.debug(f"Registro já saneado: {pncp_id}")
                return True  # Sucesso - já está no estado correto

            # Verificar se link_leiloeiro já é null
            link_atual = registro.get("link_leiloeiro")
            if not link_atual:
                self.logger.debug(f"Registro sem link: {pncp_id}")
                return True  # Sucesso - nada a fazer

            # Preparar dados para atualização
            dados_update = {
                "link_leiloeiro_valido": False,
                "link_leiloeiro": None,
                "link_leiloeiro_origem_tipo": "unknown",
                "link_leiloeiro_confianca": 0,
                "updated_at": datetime.now().isoformat(),
            }

            # Preservar link original em raw se ainda não existe
            if not registro.get("link_leiloeiro_raw"):
                dados_update["link_leiloeiro_raw"] = link_atual

            # Adicionar evidência do motivo na ref
            dados_update["link_leiloeiro_origem_ref"] = f"saneamento:{motivo}:{datetime.now().isoformat()}"

            # Executar update
            self.client.table("editais_leilao").update(dados_update).eq(
                "pncp_id", pncp_id
            ).execute()

            self.logger.info(f"Saneado: {pncp_id} (motivo: {motivo})")
            return True

        except Exception as e:
            self.logger.error(f"Erro ao sanear {pncp_id}: {e}")
            return False


# ============================================================
# EXECUTOR PRINCIPAL
# ============================================================

class SanitizadorPrincipal:
    """Coordena o processo de saneamento."""

    def __init__(self):
        self.identificador = FalsoPositivoIdentificador()
        self.saneador = SaneadorSupabase()
        self.logger = logging.getLogger(__name__)

    def executar(
        self,
        modo: str = "dry-run",
        limite: int = 1000,
        salvar_relatorio: bool = False
    ) -> ResultadoSaneamento:
        """
        Executa o processo de saneamento.

        Args:
            modo: "dry-run" (apenas lista) ou "execute" (aplica correções)
            limite: Número máximo de registros a processar
            salvar_relatorio: Se True, salva relatório JSON

        Returns:
            ResultadoSaneamento com estatísticas
        """
        self.logger.info("=" * 70)
        self.logger.info("ACHE SUCATAS - SANEAMENTO DE LINKS INVÁLIDOS")
        self.logger.info("=" * 70)
        self.logger.info(f"Modo: {modo.upper()}")
        self.logger.info(f"Limite: {limite}")
        self.logger.info("=" * 70)

        # Buscar registros
        registros = self.saneador.buscar_links_para_verificar(limite)
        self.logger.info(f"Registros encontrados para análise: {len(registros)}")

        # Identificar falsos positivos
        afetados: List[RegistroAfetado] = []

        for reg in registros:
            link = reg.get("link_leiloeiro")
            pncp_id = reg.get("pncp_id")

            if not link:
                continue

            motivo = self.identificador.identificar(link)
            if motivo:
                afetados.append(RegistroAfetado(
                    pncp_id=pncp_id,
                    link_atual=link,
                    motivo=motivo,
                ))

        self.logger.info(f"Falsos positivos identificados: {len(afetados)}")

        # Processar ou apenas listar
        total_saneados = 0
        total_erros = 0

        if modo == "execute":
            for registro in afetados:
                sucesso = self.saneador.sanear_registro(
                    pncp_id=registro.pncp_id,
                    motivo=registro.motivo
                )
                if sucesso:
                    registro.status = "saneado"
                    total_saneados += 1
                else:
                    registro.status = "erro"
                    total_erros += 1
        else:
            # Dry-run: apenas listar
            for registro in afetados:
                self.logger.info(
                    f"[DRY-RUN] {registro.pncp_id}: {registro.link_atual} "
                    f"(motivo: {registro.motivo})"
                )

        # Gerar resultado
        resultado = ResultadoSaneamento(
            data_execucao=datetime.now().isoformat(),
            modo=modo,
            total_analisados=len(registros),
            total_identificados=len(afetados),
            total_saneados=total_saneados,
            total_erros=total_erros,
            registros=[asdict(r) for r in afetados],
        )

        # Imprimir resumo
        self._imprimir_resumo(resultado)

        # Salvar relatório se solicitado
        if salvar_relatorio:
            self._salvar_relatorio(resultado)

        return resultado

    def _imprimir_resumo(self, resultado: ResultadoSaneamento):
        """Imprime resumo do saneamento."""
        self.logger.info("=" * 70)
        self.logger.info("RESUMO DO SANEAMENTO")
        self.logger.info("=" * 70)
        self.logger.info(f"Modo: {resultado.modo}")
        self.logger.info(f"Total analisados: {resultado.total_analisados}")
        self.logger.info(f"Falsos positivos identificados: {resultado.total_identificados}")
        self.logger.info(f"Registros saneados: {resultado.total_saneados}")
        self.logger.info(f"Erros: {resultado.total_erros}")
        self.logger.info("=" * 70)

        # Agrupar por motivo
        motivos = {}
        for reg in resultado.registros:
            motivo = reg["motivo"]
            motivos[motivo] = motivos.get(motivo, 0) + 1

        if motivos:
            self.logger.info("Distribuição por motivo:")
            for motivo, count in sorted(motivos.items(), key=lambda x: -x[1]):
                self.logger.info(f"  - {motivo}: {count}")

    def _salvar_relatorio(self, resultado: ResultadoSaneamento):
        """Salva relatório JSON."""
        filename = f"saneamento_relatorio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(asdict(resultado), f, ensure_ascii=False, indent=2)
        self.logger.info(f"Relatório salvo: {filename}")


# ============================================================
# ENTRY POINT
# ============================================================

def main():
    """Ponto de entrada do script de saneamento."""
    parser = argparse.ArgumentParser(
        description="Ache Sucatas - Saneamento de Links Inválidos"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Apenas lista registros afetados (sem alterações)"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Executa o saneamento (aplica correções)"
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Gera relatório JSON"
    )
    parser.add_argument(
        "--limite",
        type=int,
        default=1000,
        help="Número máximo de registros a processar (default: 1000)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Ativa modo debug"
    )

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Determinar modo
    if args.execute:
        modo = "execute"
    else:
        modo = "dry-run"
        if not args.dry_run:
            logger.warning("Nenhum modo especificado. Usando --dry-run por segurança.")

    # Executar
    sanitizador = SanitizadorPrincipal()
    resultado = sanitizador.executar(
        modo=modo,
        limite=args.limite,
        salvar_relatorio=args.report,
    )

    # Código de saída
    if resultado.total_erros > 0:
        exit(1)
    exit(0)


if __name__ == "__main__":
    main()
