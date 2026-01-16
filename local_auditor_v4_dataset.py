"""
ACHE SUCATAS - LOCAL AUDITOR V4 (DATASET GENERATOR)
---------------------------------------------------
Objetivo: Varrer PDFs locais e gerar um DATASET (CSV) estruturado
com campos específicos para filtragem (DaaS).
"""

import pdfplumber
import re
import unicodedata
import logging
import csv
import uuid
import json
import sys
import argparse
from pathlib import Path
from datetime import datetime

# ==============================================================================
# [CONFIG] CONFIGURACAO
# ==============================================================================
logging.basicConfig(level=logging.INFO, format='%(message)s')
log = logging.getLogger("AuditorV4")

OUTPUT_FILENAME = "ache_sucatas_relatorio_final.csv"

# ==============================================================================
# [ENGINE] ENGINE DE INTELIGENCIA E EXTRACAO
# ==============================================================================

class AuditorEngine:
    # Regex Patterns
    RE_DATA = r"\b\d{2}/\d{2}/\d{4}\b"
    RE_URL = r"(https?://[^\s]+|(?:www\.)?[a-zA-Z0-9-]+\.com(?:\.br)?)"
    RE_EDITAL = r"(?i)(?:edital|processo|pregão)\s*(?:n[ºo0]?\.?)?\s*(\d+[\./-]\d+)"
    
    VEICULOS_ALVO = [
        "veiculo", "carro", "moto", "caminhao", "onibus", "microonibus", "frota", 
        "viatura", "ambulancia", "van", "furgao", "pickup", "camionete", 
        "fiat", "volks", "ford", "chevrolet", "toyota", "honda", "renault",
        "scania", "volvo", "mercedes", "iveco", "gol", "palio", "uno", "strada",
        "hilux", "s10", "ranger", "toro", "saveiro", "cg 125", "cg 150", "cg 160",
        "sucata automotiva", "semirreboque", "chassi"
    ]

    @staticmethod
    def normalize_text(text: str) -> str:
        if not text: return ""
        text = unicodedata.normalize("NFD", text)
        text = "".join(c for c in text if unicodedata.category(c) != "Mn")
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def extract_dates(text: str) -> list:
        """Retorna todas as datas encontradas no texto."""
        return re.findall(AuditorEngine.RE_DATA, text)

    @staticmethod
    def extract_auction_date(text: str, dates_found: list) -> str:
        """Tenta adivinhar qual data é a do leilão baseada no contexto."""
        # Procura por termos próximos a datas
        lower_text = text.lower()
        match = re.search(r"(?:sessão|abertura|realização|data do leilão).*?(\d{2}/\d{2}/\d{4})", lower_text)
        if match:
            return match.group(1)
        # Fallback: retorna a primeira data futura encontrada (lógica simplificada) ou a primeira data do texto
        return dates_found[0] if dates_found else "A definir"

    @staticmethod
    def extract_links(text: str) -> str:
        """Extrai links que provavelmente são de leiloeiros."""
        matches = re.findall(AuditorEngine.RE_URL, text)
        # Filtra links que não sejam do PNCP ou gov.br (foca em leiloeiros privados)
        leiloeiro_links = [m for m in matches if "pncp.gov" not in m and "planalto.gov" not in m]
        return ", ".join(list(set(leiloeiro_links))[:2]) if leiloeiro_links else "Não identificado"

    @staticmethod
    def analyze_pdf_content(text: str) -> dict:
        clean_text_search = AuditorEngine.normalize_text(text).lower()
        original_text_lines = [line.strip() for line in text.split('\n') if line.strip()]

        # 1. Veículos (Tags)
        veiculos_found = []
        for veiculo in AuditorEngine.VEICULOS_ALVO:
            if re.search(rf"\b{veiculo}\b", clean_text_search):
                veiculos_found.append(veiculo.upper())
        tags = ", ".join(sorted(list(set(veiculos_found)))[:7])

        # 2. Nº Edital
        match_edital = re.search(AuditorEngine.RE_EDITAL, text)
        num_edital = match_edital.group(1) if match_edital else "N/D"

        # 3. Datas
        dates = AuditorEngine.extract_dates(text)
        data_leilao = AuditorEngine.extract_auction_date(text, dates)

        # 4. Título e Descrição (Heurística: Primeiras linhas não vazias)
        titulo = original_text_lines[0][:100] if len(original_text_lines) > 0 else "Sem Título"
        
        # Descrição: Pega as linhas 1, 2 e 3 concatenadas
        descricao = " ".join(original_text_lines[1:4])[:250] if len(original_text_lines) > 1 else "Sem Descrição"

        # 5. Link Leiloeiro
        link_leiloeiro = AuditorEngine.extract_links(text)

        # Score Simples (Reaproveitado da V3 para validar se é útil)
        is_sucata = "sucata" in clean_text_search or "leilao" in clean_text_search
        
        return {
            "tags": tags,
            "num_edital": num_edital,
            "data_leilao": data_leilao,
            "titulo": titulo,
            "descricao": descricao,
            "link_leiloeiro": link_leiloeiro,
            "is_valid": is_sucata or len(veiculos_found) > 0
        }

# ==============================================================================
# [METADATA] RECONSTRUTOR DE METADADOS
# ==============================================================================

def reconstruct_metadata(pdf_path: Path) -> dict:
    try:
        # Ex: "SC_JARAGUA_DO_SUL"
        folder_loc = pdf_path.parent.parent.name
        parts_loc = folder_loc.split('_', 1)
        uf = parts_loc[0]
        municipio = parts_loc[1].replace('_', ' ') if len(parts_loc) > 1 else "ND"

        # Ex: "2025-12-13_S60_84438381000185-1-000358-2025"
        folder_details = pdf_path.parent.name
        parts_det = folder_details.split('_')
        
        data_publicacao = parts_det[0] if len(parts_det) > 0 else "N/D"
        
        if len(parts_det) >= 3:
            pncp_id_raw = parts_det[-1]
            link_pncp = f"https://pncp.gov.br/app/editais/{pncp_id_raw.replace('-', '/', 2)}"
        else:
            link_pncp = "Link não reconstruído"
            pncp_id_raw = "N/A"

        return {
            "uf": uf,
            "municipio": municipio,
            "id_pncp": pncp_id_raw,
            "link_pncp": link_pncp,
            "data_publicacao": data_publicacao
        }
    except Exception:
        return {"uf": "??", "municipio": "Desconhecido", "id_pncp": "?", "link_pncp": "?", "data_publicacao": "?"}

# ==============================================================================
# [SCANNER] SCANNER & CSV BUILDER
# ==============================================================================

def scan_and_export(root_folder: str = "ACHE_SUCATAS_DB"):
    root = Path(root_folder)
    if not root.exists():
        log.error(f"Pasta '{root_folder}' nao encontrada.")
        return

    print("\n" + "="*80)
    log.info(f"[OK] INICIANDO MINERACAO PARA CSV EM: {root.absolute()}")
    print("="*80 + "\n")

    dataset = []

    for pdf_file in root.rglob("*.pdf"):
        if pdf_file.name.startswith('.'): continue

        try:
            full_text = ""
            with pdfplumber.open(pdf_file) as pdf:
                for page in pdf.pages[:4]: # Le primeiras 4 paginas para rapidez
                    extracted = page.extract_text()
                    if extracted: full_text += extracted + " "

            if len(full_text) < 50: continue # Pula OCR/Vazio

            # Analisa Conteudo e Metadados
            content_data = AuditorEngine.analyze_pdf_content(full_text)
            meta_data = reconstruct_metadata(pdf_file)

            if content_data["is_valid"]:
                # Mapeamento FINAL para Output Esperado
                row = {
                    "id_interno": str(uuid.uuid4())[:8],
                    "orgao": f"Prefeitura de {meta_data['municipio']}", # Inferencia padrao
                    "UF": meta_data['uf'],
                    "municipio": meta_data['municipio'],
                    "n_pncp": meta_data['id_pncp'],
                    "n_edital": content_data['num_edital'],
                    "data_publicacao": meta_data['data_publicacao'],
                    "data_atualizacao": datetime.now().strftime("%Y-%m-%d"),
                    "data_leilao": content_data['data_leilao'],
                    "titulo": content_data['titulo'],
                    "descricao": content_data['descricao'],
                    "tags": content_data['tags'],
                    "link_pncp": meta_data['link_pncp'],
                    "link_leiloeiro": content_data['link_leiloeiro']
                }

                dataset.append(row)
                print(f"[OK] Processado: {meta_data['municipio']} - {content_data['tags'][:30]}...")

        except Exception as e:
            print(f"[ERRO] PDF invalido: {pdf_file.name} - {e}")
            continue

    # ==========================================================================
    # [SAVE] SALVAR ARQUIVO FINAL (CSV)
    # ==========================================================================
    if dataset:
        keys = dataset[0].keys()
        with open(OUTPUT_FILENAME, 'w', newline='', encoding='utf-8-sig') as output_file:
            dict_writer = csv.DictWriter(output_file, fieldnames=keys, delimiter=';') # Ponto e virgula para Excel PT-BR
            dict_writer.writeheader()
            dict_writer.writerows(dataset)

        print("\n" + "="*80)
        print(f"[OK] SUCESSO! Relatorio gerado: {OUTPUT_FILENAME}")
        print(f"[INFO] Total de Editais Validos: {len(dataset)}")
        print("[OK] DICA: Abra este arquivo no Excel e use 'Dados -> Filtrar' para ordenar por Data, UF ou Veiculo.")
        print("="*80)
    else:
        print("[AVISO] Nenhum dado valido encontrado.")

# ==============================================================================
# [JSON MODE] MODO JSON PARA GOLDEN TESTS
# ==============================================================================

def process_single_pdf_json(pdf_path: Path) -> dict:
    """
    Processa UM UNICO PDF e retorna JSON estruturado para golden tests.
    """
    errors = []
    metrics = {}
    evidence = {}

    try:
        full_text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages[:4]:
                extracted = page.extract_text()
                if extracted:
                    full_text += extracted + " "

        if len(full_text) < 50:
            errors.append({
                "level": "HIGH",
                "message": "PDF vazio ou nao extrativel (OCR necessario)"
            })
            return {
                "ok": False,
                "data": {},
                "errors": errors,
                "evidence": evidence,
                "metrics": metrics
            }

        # Analisa conteudo
        content_data = AuditorEngine.analyze_pdf_content(full_text)
        meta_data = reconstruct_metadata(pdf_path)

        # VALIDACAO: data_leilao obrigatoria
        if content_data['data_leilao'] == "A definir" or not content_data['data_leilao']:
            errors.append({
                "level": "HIGH",
                "message": "Data do leilao nao encontrada no PDF"
            })

        # Converte data_leilao para formato ISO (YYYY-MM-DD)
        data_leilao_iso = content_data['data_leilao']
        if data_leilao_iso and data_leilao_iso != "A definir":
            try:
                # Converte DD/MM/YYYY para YYYY-MM-DD
                parts = data_leilao_iso.split('/')
                if len(parts) == 3:
                    data_leilao_iso = f"{parts[2]}-{parts[1]}-{parts[0]}"
            except:
                pass

        # Converte data_publicacao para formato ISO
        data_pub_iso = meta_data['data_publicacao']
        if data_pub_iso and data_pub_iso != "N/D":
            try:
                # Se ja estiver em formato YYYY-MM-DD, mantem
                if re.match(r"\d{4}-\d{2}-\d{2}", data_pub_iso):
                    pass
                # Se estiver em DD/MM/YYYY, converte
                elif '/' in data_pub_iso:
                    parts = data_pub_iso.split('/')
                    if len(parts) == 3:
                        data_pub_iso = f"{parts[2]}-{parts[1]}-{parts[0]}"
            except:
                pass

        # Monta resposta JSON
        data = {
            "id_interno": "FIXED_TEST_ID",  # Fixo para golden tests
            "orgao": f"Prefeitura de {meta_data['municipio']}",
            "UF": meta_data['uf'],
            "municipio": meta_data['municipio'],
            "n_pncp": meta_data['id_pncp'],
            "n_edital": content_data['num_edital'],
            "data_publicacao": data_pub_iso,
            "data_atualizacao": "1970-01-01",  # Fixo para golden tests
            "data_leilao": data_leilao_iso,
            "titulo": content_data['titulo'],
            "descricao": content_data['descricao'],
            "tags": content_data['tags']
        }

        return {
            "ok": True,
            "data": data,
            "errors": errors,
            "evidence": evidence,
            "metrics": metrics
        }

    except Exception as e:
        errors.append({
            "level": "CRITICAL",
            "message": f"Falha ao processar PDF: {str(e)}"
        })
        return {
            "ok": False,
            "data": {},
            "errors": errors,
            "evidence": evidence,
            "metrics": metrics
        }

# ==============================================================================
# [MAIN] ENTRY POINT
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="ACHE SUCATAS - Extrator de Leiloes")
    parser.add_argument("--pdf", type=str, help="Caminho para PDF unico (modo JSON)")
    parser.add_argument("--json", action="store_true", help="Saida em formato JSON")

    args = parser.parse_args()

    # MODO B: --pdf --json
    if args.pdf and args.json:
        # Configura stdout para UTF-8 no Windows
        if sys.platform == 'win32':
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

        pdf_path = Path(args.pdf)
        if not pdf_path.exists():
            result = {
                "ok": False,
                "data": {},
                "errors": [{"level": "CRITICAL", "message": f"Arquivo nao encontrado: {args.pdf}"}],
                "evidence": {},
                "metrics": {}
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))
            sys.exit(0)

        result = process_single_pdf_json(pdf_path)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0)

    # MODO A: Scan CSV (padrao)
    scan_and_export()

if __name__ == "__main__":
    main()