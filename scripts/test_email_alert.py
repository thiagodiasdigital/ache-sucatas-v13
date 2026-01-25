#!/usr/bin/env python3
"""
Teste de envio de email de alerta via Gmail SMTP.

USO:
    python scripts/test_email_alert.py

REQUISITOS:
    Configurar variáveis de ambiente:
    - EMAIL_ADDRESS: Seu email do Gmail
    - EMAIL_APP_PASSWORD: Senha de App do Gmail (16 caracteres)

    Para criar uma senha de App:
    1. Ative "Verificação em duas etapas" na sua conta Google
    2. Acesse: https://myaccount.google.com/apppasswords
    3. Crie uma senha de app para "Email"
    4. Use essa senha de 16 caracteres (sem espaços)
"""

import os
import sys

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

# Carrega .env
load_dotenv("config/.env")

from src.core.email_notifier import EmailNotifier, send_alert_email


def main():
    print("=" * 60)
    print("TESTE DE EMAIL DE ALERTA - Gmail SMTP")
    print("=" * 60)

    # Verificar configuração
    notifier = EmailNotifier()

    print(f"\nConfiguração detectada:")
    print(f"  EMAIL_ADDRESS: {notifier.gmail_user or 'NÃO CONFIGURADO'}")
    print(f"  EMAIL_APP_PASSWORD: {'*' * 16 if notifier.gmail_password else 'NÃO CONFIGURADO'}")
    print(f"  ALERT_EMAIL_TO: {notifier.email_to or 'NÃO CONFIGURADO'}")
    print(f"  Emails habilitados: {'SIM' if notifier.enabled else 'NÃO'}")

    if not notifier.enabled:
        print("\n" + "!" * 60)
        print("ERRO: Email não está configurado!")
        print("!" * 60)
        print("\nPara configurar, adicione ao arquivo config/.env:")
        print("  EMAIL_ADDRESS=seu_email@gmail.com")
        print("  EMAIL_APP_PASSWORD=sua_senha_de_app_16_chars")
        print("\nOu defina as variáveis de ambiente antes de executar.")
        return False

    print("\n" + "-" * 60)
    print("Enviando email de teste...")
    print("-" * 60)

    # Enviar alerta de teste
    success = send_alert_email(
        severidade="warning",
        titulo="Teste de Alerta - Ache Sucatas",
        mensagem="Este é um email de teste do sistema de alertas do pipeline Ache Sucatas. "
                 "Se você está recebendo este email, a configuração está funcionando corretamente!",
        dados={
            "teste": True,
            "ambiente": "desenvolvimento",
            "origem": "test_email_alert.py"
        },
        run_id="TEST_20260125T000000Z"
    )

    print()
    if success:
        print("=" * 60)
        print("SUCESSO! Email enviado com sucesso!")
        print("=" * 60)
        print(f"\nVerifique sua caixa de entrada: {notifier.email_to}")
        print("(Pode levar alguns segundos para chegar)")
    else:
        print("!" * 60)
        print("FALHA! Não foi possível enviar o email.")
        print("!" * 60)
        print("\nVerifique:")
        print("  1. Se EMAIL_ADDRESS está correto")
        print("  2. Se EMAIL_APP_PASSWORD é uma senha de App válida")
        print("  3. Se a verificação em duas etapas está ativa na conta Google")
        print("  4. Confira os logs acima para mais detalhes")

    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
