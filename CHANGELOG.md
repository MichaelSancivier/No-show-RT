# Changelog

## [v1.2.0] - 2025-09-06

### Novidades
- **Campo “Número da OS (opcional)”** adicionado **acima** do seletor de motivos.  
  - Pode ser deixado em branco.  
  - É incluído como a **primeira coluna** na tabela e no arquivo exportado.
- **Máscara editável**: o texto que o atendente **acrescentar/alterar na Caixa 3** (“Texto padrão (Máscara)”) agora é o conteúdo **efetivamente salvo** na tabela e exportado para Excel/CSV.

### Melhorias
- **Limpeza completa** ao usar “Nova consulta (limpar tudo)”:
  - Limpa também as chaves internas de máscara (`mask_*`) e o campo de OS (`os_consulta_*`), evitando resíduos entre consultas.

### Notas
- Mantida a compatibilidade com os rótulos explícitos e a lógica de substituição de tokens (`[DATA/HORA]`, `[DATA/HORA 2]`, `[DATA 2]`, etc.) introduzidos nas versões anteriores.

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
