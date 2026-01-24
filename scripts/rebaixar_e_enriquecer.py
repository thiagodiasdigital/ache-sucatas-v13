"""
Re-baixar PDFs e Enriquecer Editais com IA
==========================================
Este script baixa os PDFs do PNCP para editais que nao tem PDF no storage
e aplica o enriquecimento com IA.

Uso:
    python scripts/rebaixar_e_enriquecer.py [opcoes]

Opcoes:
    --limite N          Processar no maximo N editais (default: 50)
    --dry-run           Simular sem salvar
    --debug             Logs detalhados
"""

import os
import sys
import json
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime

import httpx
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("RebaixarEnriquecer")


# ============================================================
# OPENAI ENRICHER
# ============================================================

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None


class OpenAIEnricher:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = None
        self.model = model

        if OPENAI_AVAILABLE and api_key:
            try:
                self.client = OpenAI(api_key=api_key)
                logger.info(f"OpenAI inicializado: {model}")
            except Exception as e:
                logger.error(f"Erro OpenAI: {e}")

    def enriquecer(self, texto_pdf: str, metadados: dict) -> dict:
        if not self.client or not texto_pdf or len(texto_pdf) < 100:
            return {}

        texto_input = (
            f"--- INICIO ---\n{texto_pdf[:4000]}\n"
            f"\n--- CORTE ---\n"
            f"\n--- FINAL ---\n{texto_pdf[-3000:]}"
        )

        system_prompt = """
        Voce e o motor de inteligencia do 'Ache Sucatas', um DaaS para compradores de leiloes.
        Extraia dados comerciais de editais publicos.

        REGRAS:
        1. TITULO_COMERCIAL: Titulo vendedor [Tipo Ativo] + [Cidade/Orgao] + [Tipo Venda]
        2. RESUMO: Max 280 chars. Resuma a oportunidade.
        3. LISTA_VEICULOS: Modelos principais (Gol, Uno, MB 1113). Agrupe por categoria.
        4. URL_LEILOEIRO: Site do leiloeiro. Corrija erros de OCR.

        Retorne JSON:
        {"titulo_comercial": "string", "resumo_oportunidade": "string", "lista_veiculos": "string", "url_leilao_oficial": "string ou null"}
        """

        user_prompt = f"""
        CONTEXTO:
        Titulo: {metadados.get('titulo', '')}
        Orgao: {metadados.get('orgao', '')}
        Cidade: {metadados.get('cidade', '')}

        TEXTO DO EDITAL:
        {texto_input}
        """

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=500
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"Erro IA: {e}")
            return {}


# ============================================================
# FUNCOES AUXILIARES
# ============================================================

def extrair_texto_pdf(pdf_bytes: bytes) -> str:
    if not pdf_bytes:
        return ""
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(pdf_bytes)
        textos = []
        for i in range(min(len(pdf), 10)):
            page = pdf[i]
            textos.append(page.get_textpage().get_text_range())
        pdf.close()
        return "\n".join(textos)
    except Exception as e:
        logger.debug(f"Erro extrair PDF: {e}")
        return ""


def conectar_supabase():
    try:
        from supabase import create_client
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
        if not url or not key:
            logger.error("SUPABASE_URL/KEY nao configurados!")
            return None
        client = create_client(url, key)
        logger.info("Supabase conectado")
        return client
    except Exception as e:
        logger.error(f"Erro Supabase: {e}")
        return None


def buscar_editais_sem_pdf(client, limite: int = 50):
    """Busca editais que nao tem produtos_destaque (nao foram enriquecidos)."""
    try:
        result = client.table("editais_leilao").select(
            "pncp_id, titulo, orgao, cidade, uf, storage_path, produtos_destaque"
        ).is_("produtos_destaque", "null").order(
            "created_at", desc=True
        ).limit(limite).execute()

        logger.info(f"Encontrados {len(result.data)} editais para processar")
        return result.data
    except Exception as e:
        logger.error(f"Erro buscar editais: {e}")
        return []


def baixar_pdf_pncp(pncp_id: str, http_client: httpx.Client) -> tuple:
    """
    Baixa PDF do PNCP usando o pncp_id.
    Retorna (pdf_bytes, filename) ou (None, None).
    """
    # Normalizar pncp_id: pode ser "CNPJ-ESFERA-SEQ/ANO" ou "CNPJ-ESFERA-SEQ-ANO"
    pncp_id_norm = pncp_id.replace("/", "-")
    parts = pncp_id_norm.split("-")

    if len(parts) < 4:
        logger.debug(f"pncp_id invalido: {pncp_id}")
        return None, None

    cnpj = parts[0]
    seq = parts[2]
    ano = parts[3]

    # Buscar lista de arquivos
    url_arquivos = f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos"

    try:
        resp = http_client.get(url_arquivos)
        if resp.status_code != 200:
            return None, None

        arquivos = resp.json()
        if not isinstance(arquivos, list) or not arquivos:
            return None, None

        # Procurar primeiro PDF
        for arq in arquivos:
            url = arq.get("url")
            titulo = arq.get("titulo", "edital")
            tipo = arq.get("tipo", "")

            if not url:
                continue

            # Verificar se e PDF
            is_pdf = (
                "pdf" in tipo.lower() or
                "pdf" in url.lower() or
                "pdf" in titulo.lower()
            )

            if is_pdf or arquivos.index(arq) == 0:  # Pega o primeiro se nao achar PDF
                resp_pdf = http_client.get(url)
                if resp_pdf.status_code == 200:
                    content = resp_pdf.content
                    # Verificar magic bytes do PDF
                    if content[:4] == b'%PDF':
                        filename = f"{titulo}.pdf".replace(" ", "_")[:50]
                        return content, filename

        return None, None

    except Exception as e:
        logger.debug(f"Erro baixar PDF: {e}")
        return None, None


def upload_pdf_storage(client, pncp_id: str, pdf_bytes: bytes, filename: str) -> str:
    """Faz upload do PDF para o Supabase Storage."""
    try:
        bucket = "editais-pdfs"
        path = f"{pncp_id}/{filename}"

        client.storage.from_(bucket).upload(
            path,
            pdf_bytes,
            {"content-type": "application/pdf", "upsert": "true"}
        )

        return path
    except Exception as e:
        logger.debug(f"Erro upload: {e}")
        return None


def atualizar_edital(client, pncp_id: str, dados_ia: dict, storage_path: str, dry_run: bool = False):
    """Atualiza edital no banco."""
    if dry_run:
        logger.info(f"  [DRY-RUN] Atualizaria {pncp_id}")
        return True

    try:
        update_data = {"updated_at": datetime.now().isoformat()}

        if storage_path:
            update_data["storage_path"] = storage_path

        if dados_ia.get("titulo_comercial"):
            update_data["titulo"] = dados_ia["titulo_comercial"]

        if dados_ia.get("resumo_oportunidade"):
            update_data["descricao"] = dados_ia["resumo_oportunidade"]

        if dados_ia.get("lista_veiculos"):
            update_data["produtos_destaque"] = dados_ia["lista_veiculos"]

        if dados_ia.get("url_leilao_oficial"):
            url = dados_ia["url_leilao_oficial"]
            if url and "http" in url:
                update_data["link_leiloeiro"] = url

        result = client.table("editais_leilao").update(update_data).eq(
            "pncp_id", pncp_id
        ).execute()

        return len(result.data) > 0
    except Exception as e:
        logger.error(f"Erro atualizar: {e}")
        return False


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Re-baixar PDFs e enriquecer editais")
    parser.add_argument("--limite", type=int, default=50, help="Max editais (default: 50)")
    parser.add_argument("--dry-run", action="store_true", help="Simular sem salvar")
    parser.add_argument("--debug", action="store_true", help="Logs detalhados")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("=" * 60)
    logger.info("RE-BAIXAR PDFs E ENRIQUECER COM IA")
    logger.info("=" * 60)

    if args.dry_run:
        logger.info(">>> MODO DRY-RUN <<<")

    # Conectar
    client = conectar_supabase()
    if not client:
        return

    api_key = os.environ.get("OPENAI_API_KEY")
    enricher = OpenAIEnricher(api_key)
    if not enricher.client:
        logger.error("OpenAI nao disponivel!")
        return

    http = httpx.Client(
        timeout=60,
        headers={"User-Agent": "Mozilla/5.0"},
        follow_redirects=True
    )

    # Buscar editais
    editais = buscar_editais_sem_pdf(client, args.limite)
    if not editais:
        logger.info("Nenhum edital para processar")
        return

    stats = {
        "total": len(editais),
        "pdf_baixados": 0,
        "enriquecidos": 0,
        "sem_pdf": 0,
        "falhas": 0,
    }

    logger.info(f"Processando {len(editais)} editais...")
    logger.info("-" * 60)

    for i, edital in enumerate(editais, 1):
        pncp_id = edital.get("pncp_id")
        titulo = (edital.get("titulo") or "")[:40]

        logger.info(f"[{i}/{len(editais)}] {pncp_id}")
        logger.info(f"  Titulo: {titulo}...")

        # Rate limit
        time.sleep(1)

        # Baixar PDF do PNCP
        logger.info(f"  Baixando PDF do PNCP...")
        pdf_bytes, filename = baixar_pdf_pncp(pncp_id, http)

        if not pdf_bytes:
            logger.warning(f"  Sem PDF disponivel no PNCP")
            stats["sem_pdf"] += 1
            continue

        stats["pdf_baixados"] += 1
        logger.info(f"  PDF baixado: {len(pdf_bytes)} bytes")

        # Extrair texto
        texto_pdf = extrair_texto_pdf(pdf_bytes)
        if not texto_pdf or len(texto_pdf) < 100:
            logger.warning(f"  Texto PDF insuficiente")
            stats["sem_pdf"] += 1
            continue

        logger.info(f"  Texto extraido: {len(texto_pdf)} chars")

        # Upload para Storage
        storage_path = None
        if not args.dry_run:
            storage_path = upload_pdf_storage(client, pncp_id, pdf_bytes, filename)
            if storage_path:
                logger.info(f"  Upload Storage: {storage_path}")

        # Enriquecer com IA
        logger.info(f"  Enriquecendo com IA...")
        dados_ia = enricher.enriquecer(
            texto_pdf,
            {
                "titulo": edital.get("titulo", ""),
                "orgao": edital.get("orgao", ""),
                "cidade": edital.get("cidade", ""),
            }
        )

        if not dados_ia:
            logger.warning(f"  IA nao retornou dados")
            stats["falhas"] += 1
            continue

        # Mostrar resultado
        titulo_ia = str(dados_ia.get("titulo_comercial") or "")
        veiculos_ia = str(dados_ia.get("lista_veiculos") or "")

        if titulo_ia:
            logger.info(f"  -> Titulo: {titulo_ia[:50]}...")
        if veiculos_ia:
            logger.info(f"  -> Veiculos: {veiculos_ia[:50]}...")

        # Atualizar banco
        if atualizar_edital(client, pncp_id, dados_ia, storage_path, args.dry_run):
            stats["enriquecidos"] += 1
            logger.info(f"  ✓ Atualizado!")
        else:
            stats["falhas"] += 1
            logger.error(f"  ✗ Falha ao atualizar")

    http.close()

    # Resumo
    logger.info("=" * 60)
    logger.info("RESUMO")
    logger.info("=" * 60)
    logger.info(f"Total de editais: {stats['total']}")
    logger.info(f"PDFs baixados: {stats['pdf_baixados']}")
    logger.info(f"Enriquecidos com sucesso: {stats['enriquecidos']}")
    logger.info(f"Sem PDF no PNCP: {stats['sem_pdf']}")
    logger.info(f"Falhas: {stats['falhas']}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
