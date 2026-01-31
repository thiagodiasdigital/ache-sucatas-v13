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

logger = logging.getLogger("AccessTokenService")


class AccessTokenService:
      """Servico para gerenciar tokens de acesso de assinantes."""

    def __init__(self):
              self.client = None
              self.enable_supabase = False
              self._init_supabase()

        # Configuracoes
              self.token_expiry_hours = int(os.getenv("TOKEN_EXPIRY_HOURS", "24"))
              self.base_url = os.getenv("APP_BASE_URL", "https://seusite.com")

    def _init_supabase(self):
              """Inicializa conexao com Supabase."""
              SUPABASE_URL = os.getenv("SUPABASE_URL")
              SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

        if not SUPABASE_URL or not SUPABASE_KEY:
                      logger.warning("Credenciais Supabase nao encontradas")
                      return

        try:
                      from supabase import create_client, Client
                      self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
                      self.enable_supabase = True
                      logger.info("Supabase conectado com sucesso")
except Exception as e:
              logger.error(f"Erro ao conectar Supabase: {e}")

    def generate_token(self) -> str:
              """Gera um token unico e seguro."""
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
        webhook_payload: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
              """
                      Cria um novo token de acesso para o assinante.

                                      Returns:
                                                  Dict com token, link e data de expiracao
                                                          """
              if not self.enable_supabase:
                            logger.error("Supabase nao disponivel")
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
                      "webhook_payload": webhook_payload
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
                                  "cliente_nome": cliente_nome
                              }
except Exception as e:
            logger.error(f"Erro ao criar token: {e}")

        return None

    def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
              """
                      Valida um token e retorna os dados do assinante.

                                      Returns:
                                                  Dict com dados do assinante se token valido, None caso contrario
                                                          """
              if not self.enable_supabase:
                            return None

              try:
                            response = self.client.table("assinantes_tokens_acesso").select("*").eq("token", token).eq("token_ativo", True).execute()

            if not response.data:
                              logger.warning(f"Token nao encontrado ou inativo")
                              return None

            registro = response.data[0]
            expira_em = datetime.fromisoformat(registro["token_expira_em"].replace("Z", "+00:00"))

            if datetime.utcnow().replace(tzinfo=expira_em.tzinfo) > expira_em:
                              logger.warning(f"Token expirado")
                              return None

            return {
                              "valido": True,
                              "cliente_email": registro["cliente_email"],
                              "cliente_nome": registro["cliente_nome"],
                              "asaas_customer_id": registro["asaas_customer_id"]
            }
except Exception as e:
            logger.error(f"Erro ao validar token: {e}")

        return None

    def mark_token_used(self, token: str) -> bool:
              """Marca o token como usado."""
              if not self.enable_supabase:
                            return False

              try:
            self.client.table("assinantes_tokens_acesso").update({
                              "token_usado_em": datetime.utcnow().isoformat(),
                              "token_ativo": False
            }).eq("token", token).execute()

            logger.info(f"Token marcado como usado")
                  return True
except Exception as e:
            logger.error(f"Erro ao marcar token: {e}")

        return False
