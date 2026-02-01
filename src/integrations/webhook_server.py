"""
Webhook Server - Servidor para receber webhooks do Asaas
========================================================
Servidor FastAPI para processar webhooks de pagamento.

Para rodar localmente:
    uvicorn src.integrations.webhook_server:app --reload --port 8000

Para expor na internet (desenvolvimento):
    ngrok http 8000

Endpoints:
    POST /webhooks/asaas  - Recebe webhooks do Asaas
    GET  /health          - Health check
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# Handler global (inicializado no startup)
webhook_handler: Optional[Any] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle: conecta serviços no startup."""
    global webhook_handler

    logger.info("Iniciando servidor de webhooks...")

    try:
        from src.integrations.asaas_webhook_handler import AsaasWebhookHandler

        webhook_handler = AsaasWebhookHandler()
        connected = webhook_handler.connect()

        if connected:
            logger.info("Webhook handler conectado ao Supabase")
        else:
            logger.warning("Webhook handler sem conexão ao Supabase")

    except Exception:
        logger.exception("Erro ao inicializar webhook handler")
        webhook_handler = None

    yield  # Servidor rodando

    # Shutdown
    logger.info("Encerrando servidor de webhooks...")


# Criar app FastAPI
app = FastAPI(
    title="Ache Sucatas - Webhook Server",
    description="Servidor para processar webhooks do Asaas",
    version="1.0.0",
    lifespan=lifespan,
)


# ============================================================================
# Models
# ============================================================================


class HealthResponse(BaseModel):
    """Resposta do health check."""

    status: str
    supabase_connected: bool
    version: str = "1.0.0"


class WebhookResponse(BaseModel):
    """Resposta do webhook."""

    success: bool
    message: str
    event_type: Optional[str] = None
    payment_id: Optional[str] = None


# ============================================================================
# Endpoints
# ============================================================================


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check do servidor.

    Retorna status e se está conectado ao Supabase.
    """
    supabase_ok = webhook_handler is not None and webhook_handler._connected

    return HealthResponse(
        status="healthy" if supabase_ok else "degraded",
        supabase_connected=supabase_ok,
    )


@app.post(
    "/webhooks/asaas",
    response_model=WebhookResponse,
    responses={
        200: {"description": "Webhook processado com sucesso"},
        400: {"description": "Payload inválido"},
        401: {"description": "Assinatura inválida"},
        500: {"description": "Erro interno"},
    },
)
async def receive_asaas_webhook(
    request: Request,
    asaas_signature: Optional[str] = Header(None, alias="asaas-signature"),
):
    """
    Recebe webhooks do Asaas.

    Headers esperados:
        - asaas-signature: HMAC-SHA256 do payload (opcional, mas recomendado)

    Body:
        JSON com estrutura do webhook Asaas:
        {
            "event": "PAYMENT_CONFIRMED",
            "payment": { ... }
        }
    """
    # Verificar se handler está disponível
    if webhook_handler is None:
        logger.error("Webhook handler não inicializado")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Servidor não configurado corretamente",
        )

    # Ler body raw (para verificação de assinatura)
    try:
        raw_body = await request.body()
        payload: Dict[str, Any] = await request.json()
    except Exception:
        logger.exception("Erro ao ler payload do webhook")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload JSON inválido",
        )

    # Log do evento recebido
    event_type = payload.get("event", "UNKNOWN")
    payment_id = payload.get("payment", {}).get("id", "UNKNOWN")
    logger.info(f"Webhook recebido: {event_type} | payment={payment_id}")

    # Processar webhook
    try:
        result = webhook_handler.handle_webhook(
            payload=payload,
            signature=asaas_signature,
            raw_body=raw_body,
        )

        # Assinatura inválida
        if not result.success and "Assinatura" in result.message:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=result.message,
            )

        return WebhookResponse(
            success=result.success,
            message=result.message,
            event_type=result.event_type,
            payment_id=result.payment_id,
        )

    except HTTPException:
        raise
    except Exception:
        logger.exception("Erro ao processar webhook")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao processar webhook",
        )


# ============================================================================
# Endpoint de teste (apenas desenvolvimento)
# ============================================================================


@app.post("/webhooks/asaas/test")
async def test_webhook():
    """
    Endpoint de teste - simula um webhook PAYMENT_CONFIRMED.

    APENAS PARA DESENVOLVIMENTO - remover em produção!
    """
    if os.getenv("ENVIRONMENT", "development") == "production":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )

    test_payload = {
        "event": "PAYMENT_CONFIRMED",
        "payment": {
            "id": "pay_test_123",
            "customer": "cus_test_456",
            "value": 99.90,
            "netValue": 95.00,
            "billingType": "PIX",
            "status": "CONFIRMED",
            "customerName": "Cliente Teste",
            "customerEmail": "teste@example.com",
            "customerCpfCnpj": "12345678900",
        },
    }

    if webhook_handler is None:
        return {"error": "Handler não disponível"}

    result = webhook_handler.handle_webhook(payload=test_payload)

    return {
        "test": True,
        "result": {
            "success": result.success,
            "message": result.message,
            "token_created": result.token_created,
            "token_link": result.token_link,
        },
    }


# ============================================================================
# Rodar diretamente (desenvolvimento)
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("WEBHOOK_PORT", "8000"))
    uvicorn.run(
        "src.integrations.webhook_server:app",
        host="0.0.0.0",
        port=port,
        reload=True,
    )
