Contrato Canônico do Dataset (Ache Sucatas DaaS)

POR: THIAGO DIAS
DATA: 22 de Janeiro de 2026.

Regra mental: contrato é “o que entra, o que sai, e o que é proibido”.

# Contrato Canônico do Dataset — Ache Sucatas

Uma linha deste dataset representa UM EVENTO DE LEILÃO DE VEÍCULOS do governo brasileiro.

## Campos do Registro

| campo             | o que é                              | obrigatório? | exemplo                                                    | de onde vem |
| -------------     | ------------------------------------ | ------------ | ---------------------------------------------------------- | ----------- |
| id_interno        | um código único para esse leilão     | SIM          | Ref: ID_FFC584EA30FA                                       | calculado   |
| municipio         | cidade onde ocorre o leilão          | SIM          | Cascavel                                                   | PNCP        |
| uf                | estado                               | SIM          | PR                                                         | PNCP        |
| data_leilao       | dia do leilão                        | SIM          | 18-01-2026                                                 | PNCP        |
| pncp_url          | link do PNCP                         | SIM          | [https://pncp.gov.br/](https://pncp.gov.br/)...            | PNCP        |
| leiloeiro_url     | site do leiloeiro                    | NÃO          | [https://lopesleiloes.net.br](https://lopesleiloes.net.br) | PDF         |
| data_atualizacao  | última atualização do edital no PNCP | SIM          | 21-01-2026                                                 | PNCP        |
| titulo            | texto com uma linha descritiva       | SIM          | Alienação de bens inservíveis.                             | PDF         |
| descricao         | texto com três linhas descritivas    | SIM          | O Serviço Autônomo de Água e Esgoto de Guanhães, torna...  | PDF         |
| orgao             | entidade do governo                  | SIM          | Prefeituras, Estados, Detrans, Policías, Tribunais e etc...| PNCP        |
| n_edital          | identificação do documento           | NÃO          | Edital nº 0800100/0001/2026, Edital nº 1/2026, Edital, 01  | PDF         |
| objeto_resumido   | cita alguns nomes dos objetos        | SIM          | FIAT UNO MILLE, MOTONIVELADORA, MARCOPOLO VOLARE, AGRALE   | PDF         |
| tags              | classificação do edital / leilão     | SIM          | SUCATA, DOCUMENTADO, SEM CLASSIFICAÇÃO->(NESSE SE = RETIRE)| PDF         |
| valor_estimado    | valor estimado dos lotes no edital   | SIM          | VALOR TOTAL ESTIMADO DO LEILÃO R$ 73.494,80                | PDF         |         
| tipo_leilao       | classificação modalidade do leilão   | SIM          | Leilão Presencial(1), Leilão Online (2) ou = (1+2) Híbrido | PDF|PNCP    |
| 

## Regra de Vendabilidade

Um registro só pode ser vendido se:

- data_leilao existir
- pncp_url existir
- municipio e uf existirem
- id_interno existir
- titulo existir
- descricao existir
- orgao existir
- descricao_dos_lotes
- tags existir
- valor_estimado existir
- data_publicacao existir

## Datas devem ser salvas no formato:
DD-MM-YYYY

Exemplo válido:
18-03-2025

Formato proibido:
18/03/2025

## Toda URL deve começar com https:// OU http:// - whitelist deve ser consultada

Se o PDF trouxer:
www.lopesleiloes.net.br
<http://www25.receita.fazenda.gov.br/sle-sociedade/portal/edital/200100/3/2025>

O sistema deve salvar como:
https://www.lopesleiloes.net.br
http://www25.receita.fazenda.gov.br/sle-sociedade/portal/edital/200100/3/2025

Domínios como .net.br são válidos

Palavras como "COMEMORA" NÃO são URL

## id_interno é um código que identifica unicamente um leilão.

Ele NÃO pode mudar se o sistema rodar de novo.

Ele deve ser criado usando:
municipio + processo + data_leilao

## Estados de um registro

draft = extraído mas incompleto  
valid = pronto para uso  
not_sellable = sem data ou regra crítica  
rejected = lixo

O dashboard só usa registros "valid"






