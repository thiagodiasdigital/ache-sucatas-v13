"""
Access Token Service - Gerenciamento de tokens de acesso
=========================================================
Servico para gerar e validar tokens unicos de acesso para assinantes.
Criado de forma PARALELA - NAO afeta estrutura existente.
"""

import os
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class AccessTokenService:
    """Servico para gerenciar tokens de acesso de assinantes."""

    def __init__(
        self,
        token_expiry_hours: Optional[int] = None,
        base_url: Optional[str] = None,
    ) -> None:
        """
        Inicializa o servico SEM fazer I/O.

        Args:
            token_expiry_hours: Horas ate o token expirar (default: env ou 24)
            base_url: URL base para links de acesso (default: env ou https://seusite.com)
        """
        self.token_expiry_hours = token_expiry_hours or int(
            os.getenv("TOKEN_EXPIRY_HOURS", "24")
        )
        self.base_url = base_url or os.getenv(
            "APP_BASE_URL", "https://seusite.com"
        )
        self.enable_supabase = False
        self.client: Optional[Any] = None

    def connect_supabase(self) -> bool:
        """
        Conecta ao Supabase. Deve ser chamado explicitamente apos __init__.

        Returns:
            True se conectou com sucesso, False caso contrario
        """
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

        if not supabase_url or not supabase_key:
            logger.warning("Credenciais Supabase nao encontradas (SUPABASE_URL ou SUPABASE_SERVICE_KEY)")
            self.enable_supabase = False
            self.client = None
            return False

        try:
            from supabase import create_client

            self.client = create_client(supabase_url, supabase_key)
            self.enable_supabase = True
            logger.info("Supabase conectado com sucesso")
            return True
        except ImportError:
            logger.exception("Pacote 'supabase' nao instalado. Execute: pip install supabase")
            self.enable_supabase = False
            self.client = None
            return False
        except Exception:
            logger.exception("Erro ao conectar Supabase")
            self.enable_supabase = False
            self.client = None
            return False

    def _ensure_connected(self) -> bool:
        """Garante que esta conectado ao Supabase."""
        if not self.enable_supabase or self.client is None:
            logger.error("Supabase nao conectado. Chame connect_supabase() primeiro.")
            return False
        return True

    def generate_token(self) -> str:
        """Gera um token unico e seguro (32 bytes URL-safe)."""
        return secrets.token_urlsafe(32)

    def create_access_token(
        self,
        payment_id: str,
        customer_id: str,
        cliente_email: str,
        cliente_nome: Optional[str] = None,
        cliente_cpf_cnpj: Optional[str] = None,
        cliente_telefone: Optional[str] = None,
        subscription_id: Optional[str] = None,
        valor_pago: Optional[float] = None,
        forma_pagamento: Optional[str] = None,
        webhook_payload: Optional[Dict] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Cria um novo token de acesso para o assinante.

        Returns:
            Dict com token, link e data de expiracao, ou None se falhar
        """
        if not self._ensure_connected():
            return None

        token = self.generate_token()
        expira_em = datetime.utcnow() + timedelta(hours=self.token_expiry_hours)

        data = {
            "asaas_payment_id": payment_id,
            "asaas_customer_id": customer_id,
            "asaas_subscription_id": subscription_id,
            "cliente_nome": cliente_nome,
            "cliente_email": cliente_email,
            "cliente_cpf_cnpj": cliente_cpf_cnpj,
            "cliente_telefone": cliente_telefone,
            "token": token,
            "token_expira_em": expira_em.isoformat(),
            "token_ativo": True,
            "valor_pago": valor_pago,
            "forma_pagamento": forma_pagamento,
            "webhook_payload": webhook_payload,
        }

        try:
            response = self.client.table("assinantes_tokens_acesso").insert(data).execute()

            if response.data:
                link = f"{self.base_url}/login?token={token}"
                logger.info(f"Token criado para {cliente_email}")
                return {
                    "token": token,
                    "link": link,
                    "expira_em": expira_em.isoformat(),
                    "cliente_email": cliente_email,
                    "cliente_nome": cliente_nome,
                }
        except Exception:
            logger.exception(f"Erro ao criar token para {cliente_email}")

        return None

    def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Valida um token e retorna os dados do assinante.

        Returns:
            Dict com dados do assinante se token valido, None caso contrario
        """
        if not self._ensure_connected():
            return None

        try:
            response = (
                self.client.table("assinantes_tokens_acesso")
                .select("*")
                .eq("token", token)
                .eq("token_ativo", True)
                .execute()
            )

            if not response.data:
                logger.warning("Token nao encontrado ou inativo")
                return None

            registro = response.data[0]
            expira_em = datetime.fromisoformat(
                registro["token_expira_em"].replace("Z", "+00:00")
            )

            if datetime.utcnow().replace(tzinfo=expira_em.tzinfo) > expira_em:
                logger.warning("Token expirado")
                return None

            return {
                "valido": True,
                "cliente_email": registro["cliente_email"],
                "cliente_nome": registro["cliente_nome"],
                "asaas_customer_id": registro["asaas_customer_id"],
            }
        except Exception:
            logger.exception("Erro ao validar token")

        return None

    def mark_token_used(self, token: str) -> bool:
        """
        Marca o token como usado (desativa).

        Returns:
            True se marcou com sucesso, False caso contrario
        """
        if not self._ensure_connected():
            return False

        try:
            self.client.table("assinantes_tokens_acesso").update(
                {
                    "token_usado_em": datetime.utcnow().isoformat(),
                    "token_ativo": False,
                }
            ).eq("token", token).execute()

            logger.info("Token marcado como usado")
            return True
        except Exception:
            logger.exception("Erro ao marcar token como usado")

        return False
