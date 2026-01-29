# Mobile UX Baseline - Ache Sucatas

## Informações da Análise

- **Data:** 2026-01-29
- **URL Testada:** https://ache-sucatas-frontend.pages.dev/dashboard
- **Dispositivo:** Mobile (emulado)
- **Ferramenta:** Lighthouse Mobile

## Comando para Rodar Lighthouse

```bash
npx lighthouse https://ache-sucatas-frontend.pages.dev/dashboard --preset=mobile --output=html --output-path=./lighthouse-baseline.html
```

## Métricas Baseline

> **NOTA:** Execute o comando acima para preencher as métricas abaixo.
> O dashboard requer autenticação, então as métricas serão da página de login/redirecionamento.

| Métrica | Valor | Status |
|---------|-------|--------|
| LCP (Largest Contentful Paint) | _pendente_ | - |
| CLS (Cumulative Layout Shift) | _pendente_ | - |
| INP (Interaction to Next Paint) | _pendente_ | - |
| TTFB (Time to First Byte) | _pendente_ | - |
| Performance Score | _pendente_ | - |

## Problemas Identificados (Análise de Código)

### 1. Overflow Horizontal no Header (CRÍTICO)
- **Arquivo:** `frontend/src/components/Header/Header.tsx:336-465`
- **Problema:** Barra de filtros com ~10 elementos em `flex gap-2` horizontal
- **Causa:** Inputs de data com `w-[115px]` fixo + sem breakpoints responsivos

### 2. Imagens sem Lazy Loading
- **Arquivo:** `frontend/src/components/AuctionCardGrid.tsx:88-92`
- **Problema:** `<img src={categoryImage}>` sem `loading="lazy"`
- **Impacto:** 20 cards = 20 imagens carregando simultaneamente, afetando LCP

### 3. N+1 Queries
- **Arquivo:** `frontend/src/components/AuctionCardGrid.tsx:77-78`
- **Problema:** `useLotes(auction.id_interno)` chamado por cada card
- **Impacto:** 20 cards/página = 20 queries adicionais + re-renders

### 4. Drawer Lateral no Mobile
- **Arquivo:** `frontend/src/components/LotesModal.tsx:131`
- **Problema:** `<DrawerContent side="right">` em todas as telas
- **Impacto:** UX ruim no mobile - dificulta navegação com polegar

### 5. Touch Targets Pequenos
- **Arquivos:** `AuctionCardGrid.tsx`, `Header.tsx`
- **Problema:** Botões com `py-1.5` (~24px altura)
- **Impacto:** Dificuldade de interação no mobile (mínimo recomendado: 44px)

## Screenshots Baseline

> Adicionar screenshots do comportamento atual no mobile antes das correções.
