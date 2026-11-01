# Capturas do manual - recebimento e pendências

As capturas enviadas foram incorporadas ao `manual_usuario.html`. Os originais estão em `assets/manual/` e também estão embutidos no HTML, que pode ser aberto sem conexão. O PDF é gerado em `outputs/pdf/manual_usuario.pdf`.

Foram enviados 14 arquivos: 13 imagens distintas e uma repetição do diálogo de importação (imagens 3 e 5). O dashboard completo forneceu os detalhes dos indicadores, dos dois gráficos e dos resumos; não é necessário repetir essas capturas. A tela de alunos mostra filtros em Todos/Todas, e sua legenda deixa isso explícito.

## Originais utilizados

| Arquivo preservado | Identificador no HTML |
|---|---|
| 01_executavel.png | exe |
| 02_tela_inicial.png | inicio |
| 03_dialogo_importacao.png | importar |
| 04_planilha_importada.png | importada |
| 05_distribuicao_em_andamento.png | calculo |
| 06_dashboard_120_alunos.png | dashboard |
| 07_alunos_por_turma.png | alunos |
| 08_avisos_sem_edicao.png | avisos |
| 09_duplicidade_selecionada.png | duplicados |
| 10_recalculo_apos_revisao.png | recalculo |
| 11_dashboard_118_alunos.png | revisado |
| 12_destino_xlsx.png | xlsx |
| 13_destino_pdf.png | pdf |

## Quatro capturas para completar a ilustração dos estados

1. **Correções preenchidas:** use uma instância com Nome, Sexo ou Disponibilidade inválidos. Mostre linha/aluno, motivo, valores atuais e os campos corretos preenchidos. O botão **Salvar e gerar distribuição** deve estar habilitado, antes do clique. A imagem enviada com 0 inconsistências/4 avisos não contém esses campos.
2. **Duplicidade confirmada:** selecione uma linha e marque a caixa **Confirmo que é duplicidade real e desejo excluir esta linha.** O botão combinado deve estar habilitado. No print recebido, as caixas estão desmarcadas e o botão continua desabilitado.
3. **Exportação XLSX em andamento:** após confirmar Salvar, capture **Gerando arquivo Excel…**, a barra de carregamento e os botões desabilitados. O print recebido mostra o diálogo de destino, antes da gravação.
4. **Exportação PDF em andamento:** após confirmar Salvar, capture **Gerando relatório em PDF…**, a barra de carregamento e os botões desabilitados. O print recebido mostra o diálogo de destino.

As instruções desses quatro estados já estão no manual; não foram criadas imagens simuladas para representá-los. O documento pode ser consultado nesta edição, e as capturas complementares podem ser inseridas depois.

## Inconsistência de texto observada na interface

O print de duplicidade mostra o texto auxiliar **A decisão será aplicada ao clicar em “Salvar correções”.** O botão atual é **Salvar e gerar distribuição**. A legenda do manual explica a diferença; a captura e o código do aplicativo não foram alterados nesta tarefa.

## Critérios de captura

Envie PNG na resolução original, sem marcações, com a janela maximizada e a mesma escala. Para mensagens rápidas de exportação, use uma instância maior ou um quadro de gravação, sem simular a tela. Podem ser enviados também, como complementos, a confirmação de cancelamento e os arquivos XLSX/PDF abertos.
