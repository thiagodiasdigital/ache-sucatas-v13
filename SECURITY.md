# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| V13.x   | :white_check_mark: |
| V11.x   | :white_check_mark: |
| < V11   | :x:                |

## Reporting a Vulnerability

**NAO abra issues publicas para vulnerabilidades de seguranca.**

Para reportar vulnerabilidades de seguranca de forma responsavel:

1. **Email:** Envie detalhes para o mantenedor do repositorio
2. **Inclua:**
   - Descricao da vulnerabilidade
   - Passos para reproduzir
   - Impacto potencial
   - Sugestao de correcao (se houver)

### Tempo de Resposta Esperado

| Severidade | Tempo de Resposta | Tempo de Correcao |
|------------|-------------------|-------------------|
| Critical   | 24 horas          | 48 horas          |
| High       | 48 horas          | 1 semana          |
| Medium     | 1 semana          | 2 semanas         |
| Low        | 2 semanas         | Proximo release   |

## Security Measures

Este projeto implementa:

- Row Level Security (RLS) em todas as tabelas
- Secrets gerenciados via GitHub Secrets
- Pre-commit hooks para deteccao de secrets
- Dependabot para monitoramento de vulnerabilidades
- CodeQL para analise estatica de codigo

## Audit History

| Data       | Tipo             | Resultado |
|------------|------------------|-----------|
| 2026-01-19 | Full Security Audit | Em progresso |
| 2026-01-16 | Credential Rotation | Concluido |

---

*Ultima atualizacao: 2026-01-19*
