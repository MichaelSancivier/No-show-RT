# Changelog

## [v1.2.0] - 2025-09-06

### Melhorias
- Inclusão de campo **“Número da OS (opcional)”** antes do seletor de motivos.
- A máscara exibida no passo 3 agora é **editável**: o texto digitado pelo atendente é o que será salvo/exportado.
- O botão **“Nova consulta (limpar tudo)”** limpa também o número da OS e o conteúdo editado da máscara.

### Motivos já contemplados
- Mantida a lógica de múltiplos campos de data/hora com rótulos explícitos.  
- Continuidade da padronização nos tokens (`[DATA/HORA]`, `[DATA/HORA 2]`, `[DATA/HORA 3]`, etc).

## [v1.1.0] - 2025-09-05
### Melhorias
- Motivos que utilizam múltiplas datas/horas agora exibem rótulos explícitos para cada campo, mantendo a lógica das máscaras.
- As chaves internas (`data`, `hora`, `data_2`, `hora_2`, `data_3`, `hora_3`, etc.) continuam funcionando normalmente com os rótulos `[DATA/HORA]`, `[DATA/HORA 2]`, `[DATA 2]`, `[DATA/HORA 3]`.

### Motivos atualizados com rótulos explícitos:
- **Erro de roteirização do agendamento – Atendimento móvel**  
  (Data/Hora do contato com o cliente e depois com o especialista)

- **Instabilidade de Equipamento/Sistema**  
  (Data/Hora do fim do atendimento; Data do teste/reinstalação; Data/Hora do contato com a central)

## [v1.0.0] - 2025-09-01
### Inicial
- Versão inicial do app com classificação de no-show para 23 regras mapeadas, permitindo padronisar a classificação com as RT's.
