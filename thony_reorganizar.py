#!/usr/bin/env python3
"""
THONY - Technical Hygiene & Organized Network Yield
Script de Reorganizacao Estrutural do Projeto ACHE SUCATAS

Autor: THONY (IRE & DataOps Engineer)
Versao: 1.0

IMPORTANTE: Este script NAO DELETA arquivos. Apenas MOVE para pastas apropriadas.
A pasta _DESCARTE_AUDITORIA contem arquivos para revisao humana antes de exclusao.
"""

import os
import shutil
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

# ============================================================================
# CONFIGURACAO
# ============================================================================

ROOT_DIR = Path(__file__).parent.resolve()
DRY_RUN = False  # Altere para True para apenas simular sem mover

# Pastas de destino
ESTRUTURA_ALVO = {
    "_DESCARTE_AUDITORIA": "Arquivos obsoletos, duplicados e temporarios para revisao",
    "_DESCARTE_AUDITORIA/versoes_antigas": "Versoes antigas de scripts (nao deletadas)",
    "_DESCARTE_AUDITORIA/logs_antigos": "Logs historicos",
    "_DESCARTE_AUDITORIA/backups": "Diretorios de backup consolidados",
    "_DESCARTE_AUDITORIA/analises_antigas": "CSVs de analises anteriores",
    "_DESCARTE_AUDITORIA/artifacts": "Arquivos de sistema/temporarios",
    "src/core": "Codigo fonte principal de producao",
    "src/scripts": "Scripts utilitarios e auxiliares",
    "src/migrations": "Scripts de migracao de schema",
    "docs": "Documentacao do projeto",
    "docs/reports": "Relatorios historicos",
    "config": "Arquivos de configuracao",
    "data/sql": "Scripts SQL",
}

# ============================================================================
# CLASSIFICACAO DE ARQUIVOS
# ============================================================================

# Arquivos de PRODUCAO - manter em src/core
ARQUIVOS_PRODUCAO = {
    "ache_sucatas_miner_v11.py",
    "cloud_auditor_v14.py",
    "supabase_repository.py",
    "supabase_storage.py",
    "coleta_historica_30d.py",
    "streamlit_app.py",
}

# Arquivos de CONFIGURACAO - mover para config/
ARQUIVOS_CONFIG = {
    ".env.example",
    "pytest.ini",
    "ruff.toml",
    ".ache_sucatas_checkpoint.json",
}

# Versoes ANTIGAS de auditor - mover para DESCARTE
AUDITOR_ANTIGOS = {
    "local_auditor_v4_dataset.py",
    "local_auditor_v8.py",
    "local_auditor_v9.py",
    "local_auditor_v10.py",
    "local_auditor_v11.py",
    "local_auditor_v12.py",
    "local_auditor_v12_final.py",
    "local_auditor_v13.py",
}

# Versoes ANTIGAS de miner - mover para DESCARTE
MINER_ANTIGOS = {
    "ache_sucatas_miner_v8.py",
    "ache_sucatas_miner_v9_cron.py",
    "ache_sucatas_miner_v10.py",
}

# Scripts de V12 (obsoletos) - mover para DESCARTE
SCRIPTS_V12_OBSOLETOS = {
    "funcoes_v12.py",
    "corrigir_criticos_v12.py",
    "aplicar_correcoes_v12.py",
    "monitor_v12.py",
    "stats_v12.py",
    "monitor_criticos.py",
    "validar_csv_v12.py",
    "validar_v12.py",
    "testar_v13_5_editais.py",
}

# Scripts de MIGRACAO - mover para src/migrations
SCRIPTS_MIGRACAO = {
    "migrar_v13_robusto.py",
    "executar_schema_migracao.py",
    "executar_schema_completo.py",
    "executar_schema_producao.py",
    "acompanhar_migracao.py",
}

# Scripts UTILITARIOS ativos - mover para src/scripts
SCRIPTS_UTILITARIOS = {
    "instalar_hooks_seguranca.py",
    "rotacionar_credenciais.py",
    "desligar_supabase.py",
    "reativar_supabase.py",
    "gerar_excel_final.py",
    "regenerar_excel.py",
    "sincronizar_storage_banco.py",
    "check_completion.py",
    "buscar_data_api_pncp.py",
    "explorar_api_campos.py",
    "generate_municipios_sql.py",
}

# Scripts de TESTE/VALIDACAO - mover para DESCARTE (testes unitarios ficam em tests/)
SCRIPTS_TESTE_AVULSOS = {
    "testar_auditor_isolado.py",
    "testar_coleta_ids.py",
    "testar_conexao_supabase.py",
    "testar_extracao_datas.py",
    "testar_extracao_limpa.py",
    "testar_funcoes_v12.py",
    "testar_local_auditor.py",
    "testar_metadados_simples.py",
    "testar_miner_simples.py",
    "testar_uma_orgao.py",
    "testar_upload_direto.py",
    "validar_ambiente.py",
    "validar_instalacao.py",
    "verificar_config.py",
    "verificar_protecoes.py",
}

# Scripts de MONITORAMENTO - mover para src/scripts
SCRIPTS_MONITORAMENTO = {
    "monitorar_coleta.py",
    "monitorar_progresso.py",
    "monitorar_storage.py",
    "monitorar_pipeline.py",
}

# Scripts de ANALISE - mover para DESCARTE (dados historicos)
SCRIPTS_ANALISE = {
    "analisar_editais_completo.py",
    "analisar_problematicos.py",
    "analisar_valor_estimado.py",
    "listar_links.py",
    "listar_nd.py",
    "resumo_nd.py",
}

# Logs ANTIGOS - mover para DESCARTE
LOGS_ANTIGOS = {
    "auditor_reprocessamento.log",
    "auditor_v12_OLD.log",
    "auditor_v12_REPROCESSAMENTO.log",
    "reprocessamento_output.log",
    "migracao_robusta_output.txt",
    "migracao_v13_output.txt",
}

# Analises CSV antigas - mover para DESCARTE
ANALISES_ANTIGAS = {
    "analise_editais_v8.csv",
    "analise_editais_v9.csv",
    "analise_editais_v11.csv",
    "analise_editais_v12_OLD.csv",
}

# Analises CSV para MANTER na raiz (dados atuais)
ANALISES_MANTER = {
    "analise_editais_v12.csv",
    "analise_editais_v14.csv",
    "ache_sucatas_relatorio_final.csv",
    "editais_sem_link_leiloeiro.csv",
    "ache_sucatas_metrics.jsonl",
}

# Documentacao - mover para docs/
DOCUMENTACAO = {
    "CLAUDE.md",
    "CLAUDE_FULL_1.md",
    "CLAUDE_FULL_2.md",
    "CLAUDE_FULL_3.md",
    "CLAUDE_FULL_4.md",
    "CLAUDE_FULL_5.md",
    "CLAUDE_FULL_6.md",
    "README_V12.md",
    "GUIA_SEGURANCA_MAXIMA.md",
    "PROTECOES_IMPLEMENTADAS.md",
    "RESUMO_PROTECOES.txt",
    "INTEGRACAO_API_COMPLETA.md",
    "INSTRUCOES_SCHEMA_SUPABASE.md",
    "PROPOSTA_INTEGRACAO_SUPABASE_GITHUB.md",
}

# Relatorios historicos - mover para docs/reports
RELATORIOS = {
    "RELATORIO_FINAL_V12_SUCESSO_TOTAL.md",
    "RELATORIO_V12.md",
    "RESULTADO_V12_FINAL.md",
    "RESUMO_COMPLETO_V12.md",
    "CORRECOES_EMERGENCIAIS_V12.md",
    "FREIO_SEGURANCA_CUSTOS.md",
    "STATUS_V13_MIGRACAO.md",
}

# Arquivos SQL - mover para data/sql
ARQUIVOS_SQL = {
    "insert_municipios.sql",
    "migrar_schema_v11_storage.sql",
    "schemas_v13_supabase.sql",
}

# Arquivos de SISTEMA/ARTIFACTS - mover para DESCARTE
ARTIFACTS = {
    "executar_v13_direto.bat",
    "exemplo_api_completa.json",
}

# Arquivos ESPECIAIS do Windows que NAO podem ser movidos
ARQUIVOS_SISTEMA_WINDOWS = {
    "NUL", "CON", "PRN", "AUX",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}

# Diretorios de BACKUP - mover para DESCARTE/backups
DIRETORIOS_BACKUP = {
    "antes-dia-15-01-26",
    "backup_antes_reprocessamento",
    "backup_antes_reprocessamento_20260116_092646",
}

# Diretorios para IGNORAR (nao mover)
DIRETORIOS_IGNORAR = {
    ".git",
    ".github",
    ".githooks",
    ".pytest_cache",
    ".ruff_cache",
    ".streamlit",
    ".claude",
    "__pycache__",
    "node_modules",
    "frontend",  # Frontend ja esta bem organizado
    "tests",     # Testes unitarios ja estao organizados
    "logs",
    "ACHE_SUCATAS_DB",  # Database local - 1.3GB, nao mover
    "dist",
    ".venv",
    "venv",
}

# Arquivos para IGNORAR (manter na raiz)
ARQUIVOS_IGNORAR = {
    ".env",
    ".gitignore",
    "requirements.txt",
    "package.json",
    "thony_reorganizar.py",  # Este script
    "README_THONY.md",
    "RESULTADO_FINAL.xlsx",  # Manter o principal
}

# ============================================================================
# FUNCOES AUXILIARES
# ============================================================================

class ThonyLogger:
    """Logger para registrar todas as operacoes"""

    def __init__(self, log_file: Path):
        self.log_file = log_file
        self.operations: List[Dict] = []
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def log(self, action: str, source: str, dest: str, reason: str):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "source": source,
            "destination": dest,
            "reason": reason
        }
        self.operations.append(entry)
        status = "[DRY-RUN]" if DRY_RUN else "[EXEC]"
        print(f"{status} {action}: {source} -> {dest}")
        print(f"         Motivo: {reason}")

    def save(self):
        with open(self.log_file, "w", encoding="utf-8") as f:
            f.write(f"# THONY Reorganization Log\n")
            f.write(f"# Executado em: {self.timestamp}\n")
            f.write(f"# Modo: {'DRY-RUN (simulacao)' if DRY_RUN else 'EXECUCAO REAL'}\n")
            f.write(f"# Total de operacoes: {len(self.operations)}\n\n")
            for op in self.operations:
                f.write(f"[{op['timestamp']}] {op['action']}\n")
                f.write(f"  De: {op['source']}\n")
                f.write(f"  Para: {op['destination']}\n")
                f.write(f"  Motivo: {op['reason']}\n\n")


def criar_estrutura_pastas(logger: ThonyLogger):
    """Cria todas as pastas de destino"""
    print("\n" + "="*60)
    print("FASE 1: Criando estrutura de pastas")
    print("="*60 + "\n")

    for pasta, descricao in ESTRUTURA_ALVO.items():
        caminho = ROOT_DIR / pasta
        if not caminho.exists():
            if not DRY_RUN:
                caminho.mkdir(parents=True, exist_ok=True)
            logger.log("CRIAR_PASTA", str(pasta), str(caminho), descricao)


def mover_arquivo(origem: Path, destino: Path, logger: ThonyLogger, motivo: str):
    """Move arquivo com tratamento de conflitos e erros"""
    if not origem.exists():
        return False

    # Tratar conflito de nomes
    destino_final = destino
    contador = 1
    while destino_final.exists():
        nome_base = destino.stem
        extensao = destino.suffix
        destino_final = destino.parent / f"{nome_base}_CONFLITO_{contador}{extensao}"
        contador += 1

    if not DRY_RUN:
        try:
            destino_final.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(origem), str(destino_final))
        except (PermissionError, OSError) as e:
            print(f"[ERRO] Nao foi possivel mover {origem.name}: {e}")
            logger.log("ERRO_MOVER", str(origem.relative_to(ROOT_DIR)), "N/A", f"Erro: {e}")
            return False

    logger.log("MOVER", str(origem.relative_to(ROOT_DIR)), str(destino_final.relative_to(ROOT_DIR)), motivo)
    return True


def mover_diretorio(origem: Path, destino: Path, logger: ThonyLogger, motivo: str):
    """Move diretorio inteiro"""
    if not origem.exists() or not origem.is_dir():
        return False

    destino_final = destino / origem.name

    if not DRY_RUN:
        destino_final.parent.mkdir(parents=True, exist_ok=True)
        if destino_final.exists():
            # Merge ou renomear
            destino_final = destino / f"{origem.name}_MERGED_{datetime.now().strftime('%Y%m%d')}"
        shutil.move(str(origem), str(destino_final))

    logger.log("MOVER_DIR", str(origem.relative_to(ROOT_DIR)), str(destino_final.relative_to(ROOT_DIR)), motivo)
    return True


def processar_arquivos(logger: ThonyLogger):
    """Processa e move todos os arquivos conforme classificacao"""
    print("\n" + "="*60)
    print("FASE 2: Processando arquivos")
    print("="*60 + "\n")

    # Contadores
    movidos = 0
    ignorados = 0

    # Listar arquivos na raiz
    for item in ROOT_DIR.iterdir():
        nome = item.name

        # Ignorar diretorios especiais
        if item.is_dir():
            if nome in DIRETORIOS_IGNORAR:
                ignorados += 1
                continue
            # Mover diretorios de backup
            if nome in DIRETORIOS_BACKUP:
                if mover_diretorio(item, ROOT_DIR / "_DESCARTE_AUDITORIA/backups", logger,
                                   "Diretorio de backup historico"):
                    movidos += 1
                continue
            continue

        # Ignorar arquivos especiais
        if nome in ARQUIVOS_IGNORAR:
            ignorados += 1
            continue

        # Ignorar arquivos de sistema do Windows (NUL, CON, etc.)
        nome_upper = nome.upper().split('.')[0]  # Remove extensao para comparar
        if nome_upper in ARQUIVOS_SISTEMA_WINDOWS:
            print(f"[SKIP] Ignorando arquivo de sistema Windows: {nome}")
            ignorados += 1
            continue

        # Classificar e mover
        destino = None
        motivo = ""

        # Arquivos de producao -> src/core
        if nome in ARQUIVOS_PRODUCAO:
            destino = ROOT_DIR / "src/core" / nome
            motivo = "Arquivo de producao ativo"

        # Configuracao -> config/
        elif nome in ARQUIVOS_CONFIG:
            destino = ROOT_DIR / "config" / nome
            motivo = "Arquivo de configuracao"

        # Auditor antigos -> DESCARTE
        elif nome in AUDITOR_ANTIGOS:
            destino = ROOT_DIR / "_DESCARTE_AUDITORIA/versoes_antigas" / nome
            motivo = "Versao antiga de auditor (v14 eh atual)"

        # Miner antigos -> DESCARTE
        elif nome in MINER_ANTIGOS:
            destino = ROOT_DIR / "_DESCARTE_AUDITORIA/versoes_antigas" / nome
            motivo = "Versao antiga de miner (v11 eh atual)"

        # Scripts V12 obsoletos -> DESCARTE
        elif nome in SCRIPTS_V12_OBSOLETOS:
            destino = ROOT_DIR / "_DESCARTE_AUDITORIA/versoes_antigas" / nome
            motivo = "Script V12 obsoleto"

        # Scripts de migracao -> src/migrations
        elif nome in SCRIPTS_MIGRACAO:
            destino = ROOT_DIR / "src/migrations" / nome
            motivo = "Script de migracao de schema"

        # Scripts utilitarios -> src/scripts
        elif nome in SCRIPTS_UTILITARIOS:
            destino = ROOT_DIR / "src/scripts" / nome
            motivo = "Script utilitario ativo"

        # Scripts de teste avulsos -> DESCARTE
        elif nome in SCRIPTS_TESTE_AVULSOS:
            destino = ROOT_DIR / "_DESCARTE_AUDITORIA/versoes_antigas" / f"test_{nome}"
            motivo = "Script de teste avulso (testes oficiais estao em tests/)"

        # Scripts de monitoramento -> src/scripts
        elif nome in SCRIPTS_MONITORAMENTO:
            destino = ROOT_DIR / "src/scripts" / nome
            motivo = "Script de monitoramento"

        # Scripts de analise -> DESCARTE
        elif nome in SCRIPTS_ANALISE:
            destino = ROOT_DIR / "_DESCARTE_AUDITORIA/versoes_antigas" / nome
            motivo = "Script de analise ad-hoc (dados ja processados)"

        # Logs antigos -> DESCARTE
        elif nome in LOGS_ANTIGOS:
            destino = ROOT_DIR / "_DESCARTE_AUDITORIA/logs_antigos" / nome
            motivo = "Log historico"

        # Analises antigas -> DESCARTE
        elif nome in ANALISES_ANTIGAS:
            destino = ROOT_DIR / "_DESCARTE_AUDITORIA/analises_antigas" / nome
            motivo = "Analise CSV de versao anterior"

        # Analises atuais -> manter na raiz
        elif nome in ANALISES_MANTER:
            ignorados += 1
            continue

        # Documentacao -> docs/
        elif nome in DOCUMENTACAO:
            destino = ROOT_DIR / "docs" / nome
            motivo = "Documentacao do projeto"

        # Relatorios -> docs/reports
        elif nome in RELATORIOS:
            destino = ROOT_DIR / "docs/reports" / nome
            motivo = "Relatorio historico"

        # SQL -> data/sql
        elif nome in ARQUIVOS_SQL:
            destino = ROOT_DIR / "data/sql" / nome
            motivo = "Script SQL"

        # Artifacts -> DESCARTE
        elif nome in ARTIFACTS:
            destino = ROOT_DIR / "_DESCARTE_AUDITORIA/artifacts" / nome
            motivo = "Arquivo de sistema/temporario"

        # Arquivos nao classificados com _OLD, _bkp, _backup
        elif any(tag in nome.lower() for tag in ["_old", "_bkp", "_backup", "_copy"]):
            destino = ROOT_DIR / "_DESCARTE_AUDITORIA/versoes_antigas" / f"REVIEW_NEEDED_{nome}"
            motivo = "Arquivo marcado como antigo/backup (revisar)"

        # Arquivos .pyc ou __pycache__
        elif nome.endswith(".pyc") or nome == "__pycache__":
            destino = ROOT_DIR / "_DESCARTE_AUDITORIA/artifacts" / nome
            motivo = "Cache Python"

        # Arquivos Python nao classificados -> src/scripts com tag de revisao
        elif nome.endswith(".py") and nome not in ARQUIVOS_IGNORAR:
            destino = ROOT_DIR / "src/scripts" / f"REVIEW_NEEDED_{nome}"
            motivo = "Script Python nao classificado (revisar funcao)"

        # Outros arquivos nao classificados
        else:
            # Deixar na raiz se nao souber o que fazer
            ignorados += 1
            continue

        # Executar movimento
        if destino:
            if mover_arquivo(item, destino, logger, motivo):
                movidos += 1

    return movidos, ignorados


def gerar_readme(logger: ThonyLogger) -> str:
    """Gera README_THONY.md explicando a nova estrutura"""

    conteudo = f"""# README_THONY.md - Estrutura Reorganizada

> **Gerado por:** THONY (Technical Hygiene & Organized Network Yield)
> **Data:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
> **Modo:** {'DRY-RUN (simulacao)' if DRY_RUN else 'EXECUCAO REAL'}

---

## Nova Estrutura do Projeto

```
testes-12-01-17h/
|
|-- src/                          # Codigo fonte
|   |-- core/                     # Arquivos de producao
|   |   |-- ache_sucatas_miner_v11.py    # Miner principal
|   |   |-- cloud_auditor_v14.py         # Auditor principal
|   |   |-- supabase_repository.py       # CRUD PostgreSQL
|   |   |-- supabase_storage.py          # Storage operations
|   |   |-- coleta_historica_30d.py      # Coleta historica
|   |   +-- streamlit_app.py             # Dashboard Streamlit
|   |
|   |-- scripts/                  # Scripts utilitarios
|   |   |-- instalar_hooks_seguranca.py
|   |   |-- rotacionar_credenciais.py
|   |   |-- gerar_excel_final.py
|   |   |-- monitorar_*.py
|   |   +-- [outros scripts ativos]
|   |
|   +-- migrations/               # Scripts de migracao
|       |-- migrar_v13_robusto.py
|       +-- executar_schema_*.py
|
|-- docs/                         # Documentacao
|   |-- CLAUDE.md                 # Quick start
|   |-- CLAUDE_FULL_*.md          # Documentacao completa
|   |-- GUIA_SEGURANCA_MAXIMA.md
|   +-- reports/                  # Relatorios historicos
|       |-- RELATORIO_*.md
|       +-- RESULTADO_*.md
|
|-- config/                       # Configuracoes
|   |-- .env.example
|   |-- pytest.ini
|   |-- ruff.toml
|   +-- .ache_sucatas_checkpoint.json
|
|-- data/                         # Dados
|   +-- sql/                      # Scripts SQL
|       |-- insert_municipios.sql
|       |-- migrar_schema_v11_storage.sql
|       +-- schemas_v13_supabase.sql
|
|-- tests/                        # Testes unitarios (98 testes)
|   |-- conftest.py
|   |-- test_auditor_extraction.py
|   |-- test_miner_scoring.py
|   +-- test_repository_parsing.py
|
|-- frontend/                     # Dashboard React + Vite
|   |-- src/
|   |-- supabase/
|   +-- [estrutura padrao React]
|
|-- .github/workflows/            # CI/CD
|   |-- ache-sucatas.yml
|   +-- ci.yml
|
|-- _DESCARTE_AUDITORIA/          # LIXEIRA LOGICA (revisar antes de deletar)
|   |-- versoes_antigas/          # Scripts v8-v13
|   |-- logs_antigos/             # Logs historicos
|   |-- backups/                  # Diretorios de backup
|   |-- analises_antigas/         # CSVs de versoes anteriores
|   +-- artifacts/                # Arquivos de sistema
|
|-- ACHE_SUCATAS_DB/              # Database local (1.3 GB - nao movido)
|
+-- [arquivos de dados atuais]    # CSVs e XLSX atuais
    |-- analise_editais_v12.csv
    |-- analise_editais_v14.csv
    |-- ache_sucatas_relatorio_final.csv
    +-- RESULTADO_FINAL.xlsx
```

---

## Arquivos de Producao (ATIVOS)

| Arquivo | Local | Funcao |
|---------|-------|--------|
| `ache_sucatas_miner_v11.py` | src/core/ | Coleta editais PNCP |
| `cloud_auditor_v14.py` | src/core/ | Extrai dados dos PDFs |
| `supabase_repository.py` | src/core/ | CRUD PostgreSQL |
| `supabase_storage.py` | src/core/ | Upload/download Storage |
| `coleta_historica_30d.py` | src/core/ | Coleta historica |

---

## Pasta _DESCARTE_AUDITORIA

Esta pasta contem arquivos que foram identificados como:
- **Duplicados** ou versoes anteriores
- **Temporarios** ou logs antigos
- **Backups** consolidados
- **Scripts de teste** avulsos

### ACAO REQUERIDA
1. Revise os arquivos marcados com `REVIEW_NEEDED_`
2. Verifique se algum arquivo ainda eh necessario
3. Apos revisao, delete a pasta inteira: `rm -rf _DESCARTE_AUDITORIA`

---

## Comandos Atualizados

```bash
# Executar miner (novo caminho)
python src/core/ache_sucatas_miner_v11.py

# Executar auditor (novo caminho)
python src/core/cloud_auditor_v14.py

# Testes (sem alteracao)
pytest tests/ -v

# Frontend (sem alteracao)
cd frontend && npm run dev
```

---

## Estatisticas da Reorganizacao

- **Operacoes realizadas:** {len(logger.operations)}
- **Modo:** {'Simulacao (DRY-RUN)' if DRY_RUN else 'Execucao real'}
- **Log completo:** `thony_reorganizar.log`

---

## Proximos Passos

1. [ ] Revisar pasta `_DESCARTE_AUDITORIA`
2. [ ] Atualizar imports nos workflows (`.github/workflows/`)
3. [ ] Verificar se todos os testes passam: `pytest tests/ -v`
4. [ ] Deletar `_DESCARTE_AUDITORIA` apos revisao
5. [ ] Commitar nova estrutura

---

> *"Ordem eh o primeiro passo para a maestria."* - THONY
"""

    return conteudo


def main():
    """Funcao principal"""
    print("\n" + "="*60)
    print("  THONY - Technical Hygiene & Organized Network Yield")
    print("  Script de Reorganizacao Estrutural v1.0")
    print("="*60)
    print(f"\n  Diretorio: {ROOT_DIR}")
    print(f"  Modo: {'DRY-RUN (simulacao)' if DRY_RUN else 'EXECUCAO REAL'}")
    print(f"  Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n" + "="*60)

    # Inicializar logger
    log_file = ROOT_DIR / "thony_reorganizar.log"
    logger = ThonyLogger(log_file)

    # FASE 1: Criar estrutura
    criar_estrutura_pastas(logger)

    # FASE 2: Processar arquivos
    movidos, ignorados = processar_arquivos(logger)

    # FASE 3: Gerar README
    print("\n" + "="*60)
    print("FASE 3: Gerando documentacao")
    print("="*60 + "\n")

    readme_content = gerar_readme(logger)
    readme_path = ROOT_DIR / "README_THONY.md"

    if not DRY_RUN:
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(readme_content)

    logger.log("CRIAR", "README_THONY.md", str(readme_path), "Documentacao da nova estrutura")

    # Salvar log
    logger.save()

    # Resumo final
    print("\n" + "="*60)
    print("  RESUMO DA REORGANIZACAO")
    print("="*60)
    print(f"\n  Arquivos/Pastas movidos: {movidos}")
    print(f"  Arquivos ignorados: {ignorados}")
    print(f"  Total de operacoes: {len(logger.operations)}")
    print(f"\n  Log salvo em: {log_file}")
    print(f"  README gerado: {readme_path}")
    print("\n" + "="*60)

    if DRY_RUN:
        print("\n  *** MODO DRY-RUN ***")
        print("  Nenhum arquivo foi movido.")
        print("  Para executar de verdade, altere DRY_RUN = False no script.")
    else:
        print("\n  *** REORGANIZACAO CONCLUIDA ***")
        print("  Revise a pasta _DESCARTE_AUDITORIA antes de deletar.")

    print("\n")


if __name__ == "__main__":
    main()
