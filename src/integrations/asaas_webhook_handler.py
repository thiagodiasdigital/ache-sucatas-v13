"""
Asaas Webhook Handler - Processamento de webhooks do Asaas
==========================================================
Handler para receber e processar eventos de pagamento do Asaas.
Criado de forma PARALELA - NAO afeta estrutura existente.

Eventos suportados:
- PAYMENT_CONFIRMED: Pagamento confirmado (boleto compensado, pix recebido)
- PAYMENT_RECEIVED: Pagamento recebido (cartao aprovado)
- PAYMENT_OVERDUE: Pagamento vencido
- PAYMENT_REFUNDED: Pagamento estornado

Documentacao Asaas: https://docs.asaas.com/reference/webhooks
"""

import hashlib
import hmac
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class AsaasEventType(Enum):
    """Tipos de eventos do Asaas que processamos."""

    PAYMENT_CONFIRMED = "PAYMENT_CONFIRMED"
    PAYMENT_RECEIVED = "PAYMENT_RECEIVED"
    PAYMENT_OVERDUE = "PAYMENT_OVERDUE"
    PAYMENT_REFUNDED = "PAYMENT_REFUNDED"
    PAYMENT_DELETED = "PAYMENT_DELETED"
    PAYMENT_CREATED = "PAYMENT_CREATED"
    PAYMENT_UPDATED = "PAYMENT_UPDATED"

    @classmethod
    def from_string(cls, value: str) -> Optional["AsaasEventType"]:
        """Converte string para enum, retorna None se invalido."""
        try:
            return cls(value)
        except ValueError:
            return None


@dataclass
class AsaasPaymentData:
    """Dados estruturados de um pagamento do Asaas."""

    payment_id: str
    customer_id: str
    subscription_id: Optional[str]
    value: float
    net_value: float
    billing_type: str  # BOLETO, PIX, CREDIT_CARD, etc.
    status: str
    customer_name: Optional[str]
    customer_email: Optional[str]
    customer_cpf_cnpj: Optional[str]
    customer_phone: Optional[str]
    due_date: Optional[str]
    payment_date: Optional[str]
    raw_payload: Dict[str, Any]

    @classmethod
    def from_webhook_payload(cls, payload: Dict[str, Any]) -> Optional["AsaasPaymentData"]:
        """
        Extrai dados do payload do webhook.

        O Asaas envia o payload com estrutura:
        {
            "event": "PAYMENT_CONFIRMED",
            "payment": {
                "id": "pay_xxx",
                "customer": "cus_xxx",
                ...
            }
        }
        """
        try:
            payment = payload.get("payment", {})

            if not payment:
                logger.warning("Payload sem campo 'payment'")
                return None

            payment_id = payment.get("id")
            customer_id = payment.get("customer")

            if not payment_id or not customer_id:
                logger.warning(f"Payload incompleto: payment_id={payment_id}, customer_id={customer_id}")
                return None

            return cls(
                payment_id=payment_id,
                customer_id=customer_id,
                subscription_id=payment.get("subscription"),
                value=float(payment.get("value", 0)),
                net_value=float(payment.get("netValue", 0)),
                billing_type=payment.get("billingType", "UNKNOWN"),
                status=payment.get("status", "UNKNOWN"),
                customer_name=payment.get("customerName"),
                customer_email=payment.get("customerEmail"),
                customer_cpf_cnpj=payment.get("customerCpfCnpj"),
                customer_phone=payment.get("customerPhone"),
                due_date=payment.get("dueDate"),
                payment_date=payment.get("paymentDate"),
                raw_payload=payload,
            )
        except Exception:
            logger.exception("Erro ao parsear payload do webhook")
            return None


@dataclass
class WebhookResult:
    """Resultado do processamento de um webhook."""

    success: bool
    message: str
    event_type: Optional[str] = None
    payment_id: Optional[str] = None
    token_created: bool = False
    token_link: Optional[str] = None


class AsaasWebhookHandler:
    """Handler para processar webhooks do Asaas."""

    # Eventos que devem gerar token de acesso
    TOKEN_TRIGGER_EVENTS = {
        AsaasEventType.PAYMENT_CONFIRMED,
        AsaasEventType.PAYMENT_RECEIVED,
    }

    def __init__(self) -> None:
        """
        Inicializa o handler SEM fazer I/O.

        Chame connect() para conectar aos servicos necessarios.
        """
        self.webhook_token = os.getenv("ASAAS_WEBHOOK_TOKEN")
        self.access_token_service: Optional[Any] = None
        self._connected = False

    def connect(self) -> bool:
        """
        Conecta aos servicos necessarios (Supabase via AccessTokenService).

        Returns:
            True se conectou com sucesso, False caso contrario
        """
        try:
            from src.integrations.access_token_service import AccessTokenService

            self.access_token_service = AccessTokenService()
            connected = self.access_token_service.connect_supabase()

            if connected:
                self._connected = True
                logger.info("AsaasWebhookHandler conectado com sucesso")
            else:
                logger.warning("AsaasWebhookHandler: Supabase nao disponivel")

            return connected
        except ImportError:
            logger.exception("Erro ao importar AccessTokenService")
            return False
        except Exception:
            logger.exception("Erro ao conectar AsaasWebhookHandler")
            return False

    def verify_signature(
        self,
        payload_body: bytes,
        signature_header: Optional[str],
    ) -> bool:
        """
        Verifica a assinatura do webhook (HMAC-SHA256).

        Args:
            payload_body: Corpo da requisicao em bytes
            signature_header: Header 'asaas-signature' da requisicao

        Returns:
            True se assinatura valida ou se verificacao desabilitada
        """
        if not self.webhook_token:
            logger.warning("ASAAS_WEBHOOK_TOKEN nao configurado - verificacao desabilitada")
            return True

        if not signature_header:
            logger.warning("Webhook sem header de assinatura")
            return False

        try:
            expected_signature = hmac.new(
                self.webhook_token.encode("utf-8"),
                payload_body,
                hashlib.sha256,
            ).hexdigest()

            is_valid = hmac.compare_digest(expected_signature, signature_header)

            if not is_valid:
                logger.warning("Assinatura do webhook invalida")

            return is_valid
        except Exception:
            logger.exception("Erro ao verificar assinatura do webhook")
            return False

    def handle_webhook(
        self,
        payload: Dict[str, Any],
        signature: Optional[str] = None,
        raw_body: Optional[bytes] = None,
    ) -> WebhookResult:
        """
        Processa um webhook do Asaas.

        Args:
            payload: Payload JSON do webhook
            signature: Header 'asaas-signature' (opcional)
            raw_body: Corpo raw da requisicao para verificacao de assinatura

        Returns:
            WebhookResult com status do processamento
        """
        # Verificar assinatura se raw_body fornecido
        if raw_body and not self.verify_signature(raw_body, signature):
            return WebhookResult(
                success=False,
                message="Assinatura invalida",
            )

        # Extrair tipo de evento
        event_str = payload.get("event")
        if not event_str:
            logger.warning("Webhook sem campo 'event'")
            return WebhookResult(
                success=False,
                message="Payload sem campo 'event'",
            )

        event_type = AsaasEventType.from_string(event_str)
        if not event_type:
            logger.info(f"Evento ignorado (nao suportado): {event_str}")
            return WebhookResult(
                success=True,
                message=f"Evento ignorado: {event_str}",
                event_type=event_str,
            )

        # Parsear dados do pagamento
        payment_data = AsaasPaymentData.from_webhook_payload(payload)
        if not payment_data:
            return WebhookResult(
                success=False,
                message="Falha ao parsear dados do pagamento",
                event_type=event_str,
            )

        logger.info(
            f"Webhook recebido: {event_type.value} | "
            f"payment={payment_data.payment_id} | "
            f"customer={payment_data.customer_id}"
        )

        # Processar evento
        return self._process_event(event_type, payment_data)

    def _process_event(
        self,
        event_type: AsaasEventType,
        payment_data: AsaasPaymentData,
    ) -> WebhookResult:
        """Processa evento especifico."""
        # Eventos que geram token de acesso
        if event_type in self.TOKEN_TRIGGER_EVENTS:
            return self._handle_payment_success(event_type, payment_data)

        # Eventos informativos (apenas log)
        if event_type == AsaasEventType.PAYMENT_OVERDUE:
            logger.info(f"Pagamento vencido: {payment_data.payment_id}")
            return WebhookResult(
                success=True,
                message="Pagamento vencido registrado",
                event_type=event_type.value,
                payment_id=payment_data.payment_id,
            )

        if event_type == AsaasEventType.PAYMENT_REFUNDED:
            logger.info(f"Pagamento estornado: {payment_data.payment_id}")
            # TODO: Invalidar token existente se houver
            return WebhookResult(
                success=True,
                message="Pagamento estornado registrado",
                event_type=event_type.value,
                payment_id=payment_data.payment_id,
            )

        # Outros eventos - apenas confirmar recebimento
        return WebhookResult(
            success=True,
            message=f"Evento {event_type.value} recebido",
            event_type=event_type.value,
            payment_id=payment_data.payment_id,
        )

    def _handle_payment_success(
        self,
        event_type: AsaasEventType,
        payment_data: AsaasPaymentData,
    ) -> WebhookResult:
        """Processa pagamento confirmado/recebido - cria token de acesso."""
        if not self._connected or not self.access_token_service:
            logger.error("AccessTokenService nao conectado")
            return WebhookResult(
                success=False,
                message="Servico de tokens nao disponivel",
                event_type=event_type.value,
                payment_id=payment_data.payment_id,
            )

        if not payment_data.customer_email:
            logger.warning(f"Pagamento sem email do cliente: {payment_data.payment_id}")
            return WebhookResult(
                success=False,
                message="Email do cliente nao informado",
                event_type=event_type.value,
                payment_id=payment_data.payment_id,
            )

        # Criar token de acesso
        token_result = self.access_token_service.create_access_token(
            payment_id=payment_data.payment_id,
            customer_id=payment_data.customer_id,
            cliente_email=payment_data.customer_email,
            cliente_nome=payment_data.customer_name,
            cliente_cpf_cnpj=payment_data.customer_cpf_cnpj,
            cliente_telefone=payment_data.customer_phone,
            subscription_id=payment_data.subscription_id,
            valor_pago=payment_data.net_value,
            forma_pagamento=payment_data.billing_type,
            webhook_payload=payment_data.raw_payload,
        )

        if token_result:
            logger.info(
                f"Token criado com sucesso | "
                f"payment={payment_data.payment_id} | "
                f"email={payment_data.customer_email}"
            )
            return WebhookResult(
                success=True,
                message="Token de acesso criado",
                event_type=event_type.value,
                payment_id=payment_data.payment_id,
                token_created=True,
                token_link=token_result.get("link"),
            )
        else:
            logger.error(f"Falha ao criar token para {payment_data.payment_id}")
            return WebhookResult(
                success=False,
                message="Falha ao criar token de acesso",
                event_type=event_type.value,
                payment_id=payment_data.payment_id,
            )
