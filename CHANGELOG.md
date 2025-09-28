# Changelog

## [v1.3.0] - 2025-09-28

### Novidades
- **Auto-fix de tokens nas máscaras**: varredura e correção automática de tokens fora do padrão  
  (ex.: `[CLIENTE]` → `[NOME]`, `[DESCREVA SITUAÇÃO]` → `[ITEM]`).  
  Exibe resumo dos ajustes aplicados na interface.
- **Remoção segura de tokens sem valor** na renderização da máscara (evita colchetes vazios).
- **Exemplos restaurados** para todos os 23 motivos.
- **Botões separados**:
  - **🧹 Limpar campos** – reinicia motivo/inputs/máscara sem apagar a tabela.
  - **🗑️ Limpar tabela** – apaga apenas os registros já adicionados.
- **Estabilidade**: correções de aliases e normalização para `[DATA/HORA n]`.

### Motivo
Evitar o problema observado na v1.2.0, quando variações de tokens nas máscaras impediam o preenchimento automático a partir dos campos.

### Impacto / Compatibilidade
- 100% compatível com os catálogos existentes.  
- Máscaras com tokens “antigos” ou variantes continuam funcionando graças à normalização automática.

### Observações técnicas
- Nova função: `aplicar_auto_fix_catalogo()` executada na carga para reescrever templates.  
- `normalize_token()` expandido com aliases e pares de data/hora.  
- `build_mask()` agora remove tokens sem valor e sanitiza espaços.

---

## [v1.2.0] - 2025-09-06

### Melhorias
- Inclusão de campo **“Número da OS (opcional)”** antes do seletor de motivos.
- A máscara exibida no passo 3 agora é **editável**: o texto digitado pelo atendente é o que será salvo/exportado.
- O botão **“Nova consulta (limpar tudo)”** limpa também o número da OS e o conteúdo editado da máscara.

### Motivos já contemplados
- Mantida a lógica de múltiplos campos de data/hora com rótulos explícitos.  
- Continuidade da padronização nos tokens (`[DATA/HORA]`, `[DATA/HORA 2]`, `[DATA/HORA 3]`, etc).

---

## [v1.1.0] - 2025-09-05

### Melhorias
- Motivos que utilizam múltiplas datas/horas agora exibem rótulos explícitos para cada campo, mantendo a lógica das máscaras.
- As chaves internas (`data`, `hora`, `data_2`, `hora_2`, `data_3`, `hora_3`, etc.) continuam funcionando normalmente com os rótulos `[DATA/HORA]`, `[DATA/HORA 2]`, `[DATA 2]`, `[DATA/HORA 3]`.

### Motivos atualizados com rótulos explícitos:
- **Erro de roteirização do agendamento – Atendimento móvel**  
  (Data/Hora do contato com o cliente e depois com o especialista)

- **Instabilidade de Equipamento/Sistema**  
  (Data/Hora do fim do atendimento; Data do teste/reinstalação; Data/Hora do contato com a central)

---

## [v1.0.0] - 2025-09-01

### Inicial
- Versão inicial do app com classificação de no-show para 23 regras mapeadas, permitindo padronizar a classificação com as RT's.
