# Changelog - Contrato de Dados Ache Sucatas

Todas as alteracoes no schema de dados sao documentadas aqui.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).

---

## [2.0.0] - 2026-01-19

### Adicionado
- Campo `latitude` (numeric) - Coordenada geografica
- Campo `longitude` (numeric) - Coordenada geografica
- Campo `quantidade_itens` (integer) - Quantidade de lotes/itens
- Campo `nome_leiloeiro` (text) - Nome do leiloeiro oficial
- View `pub.v_auction_discovery` para consumo publico
- Documentacao de convencoes de naming
- Politica de versionamento (SemVer)

### Alterado
- Schema atualizado para v2
- Documentacao de contrato expandida

### Corrigido
- N/A

### Removido
- N/A

---

## [1.0.0] - 2025-12-XX

### Adicionado
- Schema inicial com campos basicos
- Tabela `editais` com campos do PNCP
- Tabela `execucoes_miner` para rastreamento
- RLS policies para seguranca
- Indices para performance

### Notas
- Versao inicial do contrato
- Baseado na API PNCP v1

---

## Tipos de Mudancas

- `Adicionado` - Novos recursos
- `Alterado` - Mudancas em recursos existentes
- `Descontinuado` - Recursos que serao removidos em breve
- `Removido` - Recursos removidos
- `Corrigido` - Correcoes de bugs
- `Seguranca` - Correcoes de vulnerabilidades

---

## Politica de Versoes

- **MAJOR** (X.0.0): Breaking changes - campos removidos, tipos alterados
- **MINOR** (0.X.0): Adicoes backward-compatible - novos campos opcionais
- **PATCH** (0.0.X): Correcoes sem mudanca de schema

---

*Mantido pela equipe Ache Sucatas*
