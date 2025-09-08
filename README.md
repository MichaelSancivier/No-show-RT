# Classificação No-show para RT's.

Aplicativo em **Streamlit** para padronizar a classificação de **no-show** pelas RT, em atendimentos técnicos.  
Permite selecionar motivos, preencher informações solicitadas e gerar automaticamente uma **máscara de texto** para registro na Ordem de Serviço (OS).  
Todos os dados podem ser exportados em **Excel** ou **CSV**.

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
- **Limpeza rápida**:
  - Botão *"🧹 Nova consulta (limpar tudo)"* limpa todos os campos, incluindo número da OS e máscara editada.

---

## 🖼️ Interface

1. **Número da OS (opcional)** – pode ser deixado em branco.  
2. **Motivos** – selecione o motivo do no-show.  
3. **Dados solicitados** – campos variáveis conforme o motivo.  
   - Exemplos: Nome, Data/Hora, Tipo de erro, Equipamento, etc.  
   - Campos de múltiplas datas/horas possuem rótulos explícitos (ex.: *Data do contato com o cliente*, *Hora do contato com a central*).  
4. **Máscara gerada (editável)** – texto pronto para copiar/colocar na OS.  
5. **Exportação** – adicione registros à tabela e baixe em Excel ou CSV.  

---

## 📦 Requisitos

- Python 3.9+  
- Dependências principais:
  - `streamlit`
  - `pandas`
  - `openpyxl` (opcional, para Excel)
  - `xlsxwriter` (opcional, para Excel)

Instale com:

```bash
pip install -r requirements.txt
