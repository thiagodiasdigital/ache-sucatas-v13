"""
Enriquecimento de Editais Existentes com IA
============================================
Este script aplica o enriquecimento da IA (OpenAI) nos editais
que ja estao no banco de dados.

Uso:
    python scripts/enriquecer_editais_existentes.py [opcoes]

Opcoes:
    --limite N          Processar no maximo N editais (default: todos)
    --apenas-sem-ia     Processar apenas editais sem produtos_destaque
    --dry-run           Simular sem salvar no banco
    --debug             Mostrar logs detalhados

Exemplos:
    # Enriquecer todos os editais que ainda nao tem produtos_destaque
    python scripts/enriquecer_editais_existentes.py --apenas-sem-ia

    # Testar com 5 editais sem salvar
    python scripts/enriquecer_editais_existentes.py --limite 5 --dry-run

    # Reenriquecer todos os editais
    python scripts/enriquecer_editais_existentes.py
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

# Adicionar path do projeto
sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("EnriquecerEditais")


# ============================================================
# OPENAI ENRICHER (copiado do miner v18)
# ============================================================

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None


class OpenAIEnricher:
    """
    Componente de Inteligencia Artificial.
    Transforma texto bruto em inteligencia de mercado.
    """

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = None
        self.model = model
        self.logger = logging.getLogger("AI_Enricher")

        if not OPENAI_AVAILABLE:
            self.logger.error("Biblioteca openai nao instalada!")
            self.logger.error("Execute: pip install openai")
            return

        if api_key:
            try:
                self.client = OpenAI(api_key=api_key)
                self.logger.info(f"OpenAI inicializado com modelo: {model}")
            except Exception as e:
                self.logger.error(f"Erro ao inicializar OpenAI: {e}")
        else:
            self.logger.error("OPENAI_API_KEY nao configurada!")

    def enriquecer_edital(self, texto_pdf: str, metadados: dict) -> dict:
        """
        Analisa o edital e retorna dados estruturados.
        """
        if not self.client:
            return {}

        if not texto_pdf or len(texto_pdf) < 100:
            return {}

        # Otimizacao: enviar apenas inicio e fim do edital
        texto_input = (
            f"--- INICIO DO EDITAL ---\n{texto_pdf[:4000]}\n"
            f"\n--- ... CORTE DE CONTEUDO ... ---\n"
            f"\n--- FINAL DO EDITAL ---\n{texto_pdf[-3000:]}"
        )

        system_prompt = """
        Voce e o motor de inteligencia do 'Ache Sucatas', um DaaS para compradores de leiloes.
        Sua missao e ler editais publicos (muitas vezes mal formatados) e extrair dados comerciais precisos.

        REGRAS DE EXTRACAO:
        1. TITULO_COMERCIAL: Ignore o juridiques. Crie um titulo vendedor: [Tipo Ativo] + [Cidade/Orgao] + [Tipo Venda]. Ex: "Leilao de Frota (Carros e Motos) - Prefeitura de Salto/SP".
        2. RESUMO: Max 280 chars. Resuma a oportunidade. Diga se tem documento ou sucata. Diga se e Online ou Presencial.
        3. LISTA_VEICULOS: Liste apenas os modelos principais (Ex: "Gol, Uno, Caminhao MB 1113"). Agrupe por categorias (Leves, Pesados, Motos). Ignore moveis/eletronicos.
        4. URL_LEILOEIRO: CRITICO. Encontre o site do leiloeiro ou portal de compras.
           - O texto pode ter erros de OCR (ex: "www. leiloes .com" ou "portal\ndecompras").
           - VOCE DEVE CORRIGIR E RECONSTRUIR A URL para um formato valido de navegador (https://...).
           - Se houver multiplas URLs, priorize a plataforma de lances.

        Retorne APENAS um JSON estrito com estas chaves:
        {
            "titulo_comercial": "string",
            "resumo_oportunidade": "string",
            "lista_veiculos": "string",
            "url_leilao_oficial": "string ou null"
        }
        """

        user_prompt = f"""
        CONTEXTO:
        Titulo Original: {metadados.get('titulo', '')}
        Orgao: {metadados.get('orgao', '')}
        Cidade: {metadados.get('cidade', '')}

        TEXTO DO EDITAL (PDF):
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

            content = response.choices[0].message.content
            return json.loads(content)

        except Exception as e:
            self.logger.error(f"Falha na IA: {e}")
            return {}


# ============================================================
# FUNCOES DE BANCO E STORAGE
# ============================================================

def conectar_supabase():
    """Conecta ao Supabase."""
    try:
        from supabase import create_client

        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")

        if not url or not key:
            logger.error("SUPABASE_URL ou SUPABASE_KEY nao configurados!")
            return None

        client = create_client(url, key)
        logger.info("Conectado ao Supabase")
        return client

    except ImportError:
        logger.error("Biblioteca supabase nao instalada!")
        logger.error("Execute: pip install supabase")
        return None
    except Exception as e:
        logger.error(f"Erro ao conectar Supabase: {e}")
        return None


def buscar_editais(client, apenas_sem_ia: bool = False, limite: int = None):
    """
    Busca editais do banco para enriquecer.

    Args:
        client: Cliente Supabase
        apenas_sem_ia: Se True, busca apenas editais sem produtos_destaque
        limite: Numero maximo de editais a buscar
    """
    try:
        query = client.table("editais_leilao").select(
            "pncp_id, titulo, descricao, orgao, cidade, uf, storage_path, produtos_destaque, link_leiloeiro"
        )

        if apenas_sem_ia:
            # Buscar editais que nao tem produtos_destaque preenchido
            query = query.is_("produtos_destaque", "null")

        # Ordenar pelos mais recentes
        query = query.order("created_at", desc=True)

        if limite:
            query = query.limit(limite)

        result = query.execute()

        logger.info(f"Encontrados {len(result.data)} editais para processar")
        return result.data

    except Exception as e:
        logger.error(f"Erro ao buscar editais: {e}")
        return []


def baixar_pdf_storage(client, storage_path: str) -> bytes:
    """
    Baixa o PDF do Supabase Storage.
    """
    if not storage_path:
        return None

    try:
        # Encontrar o arquivo PDF no storage
        bucket = "editais-pdfs"

        # Listar arquivos na pasta do edital
        pasta = storage_path.rsplit("/", 1)[0] if "/" in storage_path else storage_path

        files = client.storage.from_(bucket).list(pasta)

        # Procurar por PDF
        pdf_file = None
        for f in files:
            if f.get("name", "").lower().endswith(".pdf") or "pdf" in f.get("name", "").lower():
                pdf_file = f"{pasta}/{f['name']}"
                break

        if not pdf_file:
            return None

        # Baixar o arquivo
        response = client.storage.from_(bucket).download(pdf_file)
        return response

    except Exception as e:
        logger.debug(f"Erro ao baixar PDF do storage: {e}")
        return None


def extrair_texto_pdf(pdf_bytes: bytes) -> str:
    """Extrai texto de um PDF."""
    if not pdf_bytes:
        return ""

    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(pdf_bytes)
        texto_paginas = []

        max_paginas = min(len(pdf), 10)
        for i in range(max_paginas):
            page = pdf[i]
            textpage = page.get_textpage()
            texto_paginas.append(textpage.get_text_range())

        pdf.close()
        return "\n".join(texto_paginas)

    except ImportError:
        logger.error("pypdfium2 nao instalado! Execute: pip install pypdfium2")
        return ""
    except Exception as e:
        logger.debug(f"Erro ao extrair texto do PDF: {e}")
        return ""


def atualizar_edital(client, pncp_id: str, dados_ia: dict, dry_run: bool = False):
    """
    Atualiza o edital no banco com os dados da IA.
    """
    if dry_run:
        logger.info(f"  [DRY-RUN] Atualizaria {pncp_id} com:")
        logger.info(f"    - titulo: {dados_ia.get('titulo_comercial', '')[:50]}...")
        logger.info(f"    - descricao: {dados_ia.get('resumo_oportunidade', '')[:50]}...")
        logger.info(f"    - produtos_destaque: {dados_ia.get('lista_veiculos', '')[:50]}...")
        logger.info(f"    - link_leiloeiro: {dados_ia.get('url_leilao_oficial', '')}")
        return True

    try:
        update_data = {
            "updated_at": datetime.now().isoformat()
        }

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
        logger.error(f"Erro ao atualizar edital {pncp_id}: {e}")
        return False


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Enriquecer editais existentes com IA (OpenAI)"
    )
    parser.add_argument(
        "--limite",
        type=int,
        default=None,
        help="Processar no maximo N editais"
    )
    parser.add_argument(
        "--apenas-sem-ia",
        action="store_true",
        help="Processar apenas editais sem produtos_destaque"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simular sem salvar no banco"
    )
    parser.add_argument(
        "--modelo",
        type=str,
        default="gpt-4o-mini",
        help="Modelo OpenAI (default: gpt-4o-mini)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Mostrar logs detalhados"
    )

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("=" * 60)
    logger.info("ENRIQUECIMENTO DE EDITAIS EXISTENTES COM IA")
    logger.info("=" * 60)

    if args.dry_run:
        logger.info(">>> MODO DRY-RUN: Nenhuma alteracao sera salva <<<")

    # Conectar ao Supabase
    client = conectar_supabase()
    if not client:
        return

    # Inicializar IA
    api_key = os.environ.get("OPENAI_API_KEY")
    enricher = OpenAIEnricher(api_key, args.modelo)

    if not enricher.client:
        logger.error("Falha ao inicializar OpenAI. Abortando.")
        return

    # Buscar editais
    editais = buscar_editais(client, args.apenas_sem_ia, args.limite)

    if not editais:
        logger.info("Nenhum edital para processar.")
        return

    # Estatisticas
    stats = {
        "total": len(editais),
        "processados": 0,
        "enriquecidos": 0,
        "sem_pdf": 0,
        "falhas": 0,
    }

    logger.info(f"Processando {len(editais)} editais...")
    logger.info("-" * 60)

    for i, edital in enumerate(editais, 1):
        pncp_id = edital.get("pncp_id")
        titulo = edital.get("titulo", "")[:40]

        logger.info(f"[{i}/{len(editais)}] {pncp_id}")
        logger.info(f"  Titulo: {titulo}...")

        # Tentar baixar PDF do storage
        storage_path = edital.get("storage_path")
        pdf_bytes = None
        texto_pdf = ""

        if storage_path:
            logger.debug(f"  Baixando PDF de: {storage_path}")
            pdf_bytes = baixar_pdf_storage(client, storage_path)

            if pdf_bytes:
                texto_pdf = extrair_texto_pdf(pdf_bytes)
                logger.debug(f"  Texto extraido: {len(texto_pdf)} chars")

        if not texto_pdf or len(texto_pdf) < 100:
            logger.warning(f"  Sem texto PDF suficiente. Pulando.")
            stats["sem_pdf"] += 1
            continue

        stats["processados"] += 1

        # Enriquecer com IA
        logger.info(f"  Enriquecendo com IA...")

        dados_ia = enricher.enriquecer_edital(
            texto_pdf,
            {
                "titulo": edital.get("titulo", ""),
                "orgao": edital.get("orgao", ""),
                "cidade": edital.get("cidade", ""),
            }
        )

        if not dados_ia:
            logger.warning(f"  IA nao retornou dados.")
            stats["falhas"] += 1
            continue

        # Mostrar resultado
        if dados_ia.get("titulo_comercial"):
            logger.info(f"  -> Titulo IA: {dados_ia['titulo_comercial'][:50]}...")
        if dados_ia.get("lista_veiculos"):
            logger.info(f"  -> Veiculos: {dados_ia['lista_veiculos'][:50]}...")

        # Atualizar no banco
        if atualizar_edital(client, pncp_id, dados_ia, args.dry_run):
            stats["enriquecidos"] += 1
            logger.info(f"  ✓ Atualizado com sucesso!")
        else:
            stats["falhas"] += 1
            logger.error(f"  ✗ Falha ao atualizar")

    # Resumo final
    logger.info("=" * 60)
    logger.info("RESUMO")
    logger.info("=" * 60)
    logger.info(f"Total de editais: {stats['total']}")
    logger.info(f"Processados (com PDF): {stats['processados']}")
    logger.info(f"Enriquecidos com sucesso: {stats['enriquecidos']}")
    logger.info(f"Sem PDF disponivel: {stats['sem_pdf']}")
    logger.info(f"Falhas: {stats['falhas']}")
    logger.info("=" * 60)

    if args.dry_run:
        logger.info(">>> Modo DRY-RUN: Nenhuma alteracao foi salva <<<")


if __name__ == "__main__":
    main()
