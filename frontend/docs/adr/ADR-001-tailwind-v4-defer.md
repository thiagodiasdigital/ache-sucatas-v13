# ADR-001: Tailwind CSS v4 - Migração Adiada

**Status:** Aceito
**Data:** 2026-01-31
**Decisor:** Tech Lead

---

## Contexto

O Dependabot abriu PR #5 sugerindo upgrade automático de Tailwind CSS v3.4.19 para v4.1.18. Esta é uma **mudança de MAJOR version** com breaking changes significativos.

## Decisão

**Tailwind v4 está BLOQUEADO** até que as condições de desbloqueio sejam atendidas.

Implementamos guardrails:
- Versão pinada sem caret: `"tailwindcss": "3.4.19"`
- npm overrides bloqueando v4
- Script de verificação: `npm run check:tailwind`

## Motivos Objetivos

### 1. Requisitos de Browser Mais Restritivos

| Feature | Tailwind v3 | Tailwind v4 |
|---------|-------------|-------------|
| CSS Variables | Suportado | Obrigatório |
| @layer | Suportado | Obrigatório |
| oklch() | Não usa | Usa por padrão |
| light-dark() | Não usa | Usa nativamente |

**Impacto:** Browsers antigos (Safari <15.4, Chrome <111) perdem suporte.

### 2. Arquitetura CSS-First (Breaking Change)

Tailwind v4 abandona `tailwind.config.js` em favor de configuração via CSS:

```css
/* v4: Nova sintaxe obrigatória */
@import "tailwindcss";
@theme {
  --color-primary: oklch(0.7 0.15 200);
}
```

**Impacto:** Nosso `tailwind.config.js` (84 linhas) precisaria reescrita completa.

### 3. Plugins Incompatíveis

| Plugin | Status v4 |
|--------|-----------|
| `tailwindcss-animate` | INCOMPATÍVEL - requer migração para `tw-animate-css` |
| `@tailwindcss/forms` | Requer nova versão |
| `@tailwindcss/typography` | Requer nova versão |

**Impacto:** Plugin de animação usado por shadcn/ui não funciona em v4.

### 4. shadcn/ui - Componentes Afetados

O projeto usa shadcn/ui extensivamente:
- 37 arquivos TSX com 613 usos de className
- Padrões como `ring-offset-*` e `border-*` foram alterados
- CSS Variables precisam nova sintaxe

### 5. Ausência de Testes de Regressão Visual

Não temos:
- Suite de testes visuais (Chromatic, Percy, etc.)
- Snapshots de componentes
- Cobertura de testes E2E para UI

**Risco:** Regressões visuais passariam despercebidas.

---

## Condições de Desbloqueio

Para reavaliar migração v4, precisamos:

1. **Telemetria de Browsers**
   - Confirmar que <1% dos usuários usam browsers incompatíveis
   - Implementar tracking de user-agent

2. **Suite de Testes Visuais**
   - Chromatic ou Percy configurado
   - Baseline de todos os componentes shadcn/ui

3. **Branch Dedicada**
   - Migração isolada em feature branch
   - Não via PR automático do Dependabot

4. **Checklist de Migração**
   - [ ] tailwindcss-animate → tw-animate-css
   - [ ] tailwind.config.js → CSS @theme
   - [ ] postcss.config.js atualizado
   - [ ] Todas as classes deprecated substituídas

5. **Janela de Release**
   - Período de baixo tráfego
   - Rollback preparado
   - Monitoramento ativo pós-deploy

---

## Consequências

### Positivas
- Estabilidade garantida do build
- Zero risco de regressão visual
- Manutenção do suporte a browsers existentes

### Negativas
- Não temos acesso a features v4 (performance, simplificação)
- Dependabot continuará abrindo PRs (fechar manualmente)

---

## Referências

- [Tailwind v4 Upgrade Guide](https://tailwindcss.com/docs/upgrade-guide)
- [Browser Compatibility v4](https://tailwindcss.com/docs/browser-support)
- [tailwindcss-animate migration](https://github.com/jamiebuilds/tailwindcss-animate/issues/99)
- PR #5: `dependabot/npm_and_yarn/frontend/tailwindcss-4.1.18`
