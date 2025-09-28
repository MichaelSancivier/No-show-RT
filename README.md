# Classificação No-show para RT's

Aplicativo em **Streamlit** para padronizar a classificação de **no-show** pelas RT, em atendimentos técnicos.  
Permite selecionar motivos, preencher informações solicitadas e gerar automaticamente uma **máscara de texto** para registro na Ordem de Serviço (OS).  
Todos os dados podem ser exportados em **Excel** ou **CSV**.

👉 **Acesse o app aqui:** [https://no-show-rt-09.streamlit.app/](https://no-show-rt-09.streamlit.app/)

---

## ✨ Funcionalidades

- **Seleção de motivo** entre 23 regras pré-cadastradas, cada uma com:
  - O que fazer
  - Quando usar
  - Exemplos
  - Máscara de texto (com campos dinâmicos)
- **Campos dinâmicos** exibidos conforme o motivo selecionado.
- **Máscara automática editável**:
  - É possível ajustar o texto final antes de salvar/exportar.
  - O que for digitado vai junto para a tabela/Excel.
- **Número da OS (opcional)**:
  - Campo livre, antes da seleção de motivos.
  - Incluído na tabela e exportações.
- **Exportação**:
  - Excel (usando `openpyxl` ou `xlsxwriter`, se disponíveis).
  - CSV (fallback automático).
- **Limpeza**:
  - **🧹 Limpar campos** – reinicia motivo/inputs/máscara sem apagar a tabela.
  - **🗑️ Limpar tabela** – apaga apenas os registros já adicionados.
- **Exemplos restaurados**: todos os 23 motivos têm exemplos visíveis na interface.

---

## 🔒 Blindagem de Máscaras (auto-fix de tokens)

Desde a versão **v1.3.0**, o app valida e **corrige automaticamente** tokens usados nas máscaras do catálogo.  
Isso evita que campos preenchidos (azuis) deixem de aparecer no texto final por causa de variações como `[CLIENTE]`, `[NOME CLIENTE]`, `[DESCREVA SITUAÇÃO]`, etc.

### Como funciona
- Na inicialização, o app varre todas as máscaras do `CATALOGO` e:
  - **Reescreve tokens** não padronizados para um **conjunto canônico** (ex.: `[CLIENTE]` → `[NOME]`, `[DESCREVA SITUAÇÃO]` → `[ITEM]`).
  - Mantém compatibilidade com pares de data/hora (ex.: `[DATA/HORA 2]`, `[HORA 3]`).
  - Exibe um **resumo dos ajustes** aplicados na interface.
- Em tempo de geração, o `build_mask()`:
  - Preenche tokens com os valores dos inputs.
  - Remove tokens sem valor (não ficam colchetes vazios no texto).

### Tokens canônicos aceitos
- Pessoas/entidades: `[NOME]`, `[NOME TÉCNICO]`, `[ESPECIALISTA]`, `[CANAL]`
- Dados do agendamento: `[DATA]`, `[HORA]`, `[DATA/HORA]`, `[DATA 2]`, `[HORA 2]`, `[DATA/HORA 3]`, …
- Outras chaves: `[TIPO]`, `[EXPLIQUE A SITUAÇÃO]`, `[EQUIPAMENTO/SISTEMA]`, `[ITEM]`, `[MOTIVO]`, `[NÚMERO ORDEM DE SERVIÇO]`, `[NÚMERO]`
- Sinônimos comuns (ex.: `[CLIENTE]`, `[NOME CLIENTE]`) são **normalizados automaticamente**.

### Como desativar o auto-fix (opcional)
No arquivo `app_classificador_no_show.py`, comente a linha:
```python
CATALOGO = aplicar_auto_fix_catalogo(CATALOGO)
