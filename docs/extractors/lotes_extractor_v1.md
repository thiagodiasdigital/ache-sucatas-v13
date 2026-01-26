# Extrator de Lotes V1

**Versão:** 1.0.0
**Data:** 2026-01-25
**Autor:** Tech Lead (Claude Code)

---

## Visao Geral

O Extrator de Lotes V1 é um componente que extrai lotes individuais de veículos das tabelas dentro dos PDFs de editais de leilão e os armazena em uma estrutura 1:N (um-para-muitos) relacionada aos editais existentes.

## Arquitetura

```
PNCP API → Miner → Auditor → [LOTES EXTRACTOR V1] → Validator → Frontend
                                    ↓
                              ┌─────┴─────┐
                              │           │
                        lotes_leilao  lotes_quarentena
```

## Familias de PDF

O extrator classifica PDFs em 4 famílias estruturais:

| Familia | Cobertura | Descrição | Processável |
|---------|-----------|-----------|-------------|
| `PDF_TABELA_INICIO` | 43.1% | Tabelas nas primeiras 3 páginas | Sim |
| `PDF_NATIVO_SEM_TABELA` | 21.4% | Texto extraível, sem tabelas | Sim (regex) |
| `PDF_ESCANEADO` | 20.2% | Imagens sem texto | Não (quarentena) |
| `PDF_TABELA_MEIO_FIM` | 15.0% | Tabelas após página 3 | Sim |

## Tabelas do Banco de Dados

### lotes_leilao

Armazena lotes validados com relação 1:N para editais.

**Campos principais:**
- `id_interno` - Hash SHA256 para idempotência
- `edital_id` - FK para editais_leilao
- `numero_lote_raw` / `numero_lote` - Número do lote (bruto e processado)
- `descricao_raw` / `descricao_completa` - Descrição (bruta e processada)
- `avaliacao_valor` - Valor numérico parseado
- `placa`, `chassi`, `renavam`, `marca`, `modelo`, `ano_fabricacao` - Dados do veículo
- `fonte_tipo`, `fonte_arquivo`, `fonte_pagina` - Rastreabilidade
- `versao_extrator`, `familia_pdf` - Metadados de processamento

### lotes_quarentena

Dead Letter Queue para registros que falharam.

**Campos principais:**
- `payload_original` - JSONB com dados originais
- `estagio_falha` - Onde falhou (classificacao, extracao, validacao, etc.)
- `codigo_erro` - Código padronizado do erro
- `mensagem_erro` - Descrição do erro
- `status` - pendente, resolvido, descartado

### arquivos_processados_lotes

Rastreia arquivos processados para idempotência.

**Campos principais:**
- `hash_arquivo` - SHA256 do conteúdo binário (UNIQUE)
- `familia_pdf` - Família estrutural detectada
- `total_lotes_extraidos` - Contador de sucesso
- `total_lotes_quarentena` - Contador de falhas

## Códigos de Erro

### Classificação
- `PDF_ESCANEADO` - PDF é imagem sem texto
- `PDF_CORROMPIDO` - Não foi possível abrir o PDF
- `TIPO_NAO_SUPORTADO` - Formato não suportado

### Extração
- `TABELA_NAO_ENCONTRADA` - Nenhuma tabela de lotes detectada
- `TABELA_SEM_CABECALHO_VALIDO` - Tabela sem colunas reconhecíveis
- `ESTRUTURA_INESPERADA` - Erro não previsto na extração

### Validação
- `NUMERO_LOTE_AUSENTE` - Lote sem número identificável
- `DESCRICAO_INSUFICIENTE` - Descrição com menos de 10 caracteres
- `VALOR_NAO_PARSEAVEL` - Valor não conversível para número

### Persistência
- `ERRO_BANCO_DADOS` - Falha na conexão ou query
- `CONSTRAINT_VIOLADA` - Violação de constraint SQL

## Uso

### Linha de Comando

```bash
# Execução básica (requer SUPABASE_URL e SUPABASE_KEY)
python src/extractors/lotes_extractor_v1.py --limite 100 --diretorio ./pdfs

# Modo verbose
python src/extractors/lotes_extractor_v1.py --limite 50 --diretorio ./pdfs --verbose
```

### Uso Programático

```python
from src.extractors import LotesExtractorV1, ExtratorTabelas

# Opção 1: Executar pipeline completo
extrator = LotesExtractorV1()
metricas = extrator.executar(
    limite_editais=100,
    diretorio_pdfs="./pdfs"
)
print(metricas.to_dict())

# Opção 2: Extrair de um PDF específico
extrator_tabelas = ExtratorTabelas()
resultado = extrator_tabelas.extrair(
    caminho_pdf="./edital_123.pdf",
    edital_id=456
)

if resultado.sucesso:
    for lote in resultado.lotes:
        print(f"Lote {lote.numero_lote}: {lote.descricao_completa}")
else:
    for erro in resultado.erros:
        print(f"Erro: {erro['codigo']} - {erro['mensagem']}")
```

## Testes

```bash
# Executar todos os testes
pytest tests/extractors/test_lotes_extractor.py -v

# Executar teste específico
pytest tests/extractors/test_lotes_extractor.py::TestLoteExtraido -v
```

## Princípios de Design

1. **Idempotência** - Hash SHA256 garante que reprocessamento não duplica dados
2. **Proveniência** - Campos `*_raw` preservam dados originais
3. **Quarentena** - Falhas vão para tabela separada com código de erro
4. **Observabilidade** - Métricas por execução e família de PDF
5. **Versionamento** - `versao_extrator` permite rastrear qual versão processou

## Dependências

```
pdfplumber>=0.10.0
pandas>=2.0.0
supabase>=2.0.0
pydantic>=2.0.0
```

## Migração SQL

Executar no Supabase SQL Editor:

```bash
sql/migrations/001_create_lotes_tables.sql
```

## Roadmap

- [ ] Download automático do Supabase Storage
- [ ] Integração com OCR para PDFs escaneados
- [ ] Enriquecimento com taxonomia automotiva
- [ ] Dashboard de monitoramento de extração
