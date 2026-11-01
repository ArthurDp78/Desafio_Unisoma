# Desafio UniSoma 2026 — Ensalamento ABC Aprendiz

Aplicação em Python para distribuir os alunos matriculados nas turmas disponíveis no Excel do cenário. Esta versão foi construída a partir dos documentos em `Contexto/` e das quatro instâncias em `Dados/`.

## O que o programa faz

1. Abre a aplicação desktop para importar o Excel do cenário.
2. Lê as abas **Alunos** e **Turmas**.
3. Valida os registros e a capacidade disponível.
4. Resolve um modelo matemático de programação inteira binária usando PuLP e o solver CBC.
5. Exibe os dashboards, os alunos da turma selecionada e as inconsistências agrupadas.
6. Exporta a planilha completa com as abas `Ensalamento` e `Inconsistências`, preservando as abas de entrada.

## Regras representadas

### Restrições rígidas

- Cada aluno válido é alocado em no máximo uma turma; se não receber turma, `u_i=1` registra essa situação.
- Disponibilidade de manhã só permite turma de manhã; disponibilidade à tarde só permite turma da tarde.
- Cada turma respeita o limite de vagas informado na aba **Turmas**.
- Um aluno pode ficar sem turma quando faltarem vagas; ele aparece na aba **Ensalamento** com `SEM TURMA` na coluna `Turma` e também é reportado na aba **Inconsistências**.
- A nomenclatura é contínua entre os períodos: as turmas da manhã recebem as primeiras letras e as da tarde continuam a sequência, no padrão `MANHÃ - A`, `MANHÃ - B`, `TARDE - C` etc. Após `Z`, a sequência continua com `AA`, `AB`, …, `AZ`, `BA`, …; após `ZZ`, segue com `AAA`. Por exemplo, com 26 turmas de manhã, a primeira turma da tarde se chama `TARDE - AA`.
- As linhas de alunos com nomes repetidos são preservadas como registros distintos e incluídas no ensalamento; o nome duplicado é reportado como aviso, pois pode ser homônimo ou erro cadastral.

### Função objetivo

O modelo segue a formulação do rascunho da equipe e minimiza:

- (k_j): desvio absoluto entre a quantidade de alunas na turma (j) e a média de alunas por turma naquele período;
- (w_j): desvio absoluto entre a quantidade de alunos na turma (j) e a média de alunos por turma naquele período;
- (u_i): indicador binário de que o aluno (i) ficou sem turma.

Em notação, a função objetivo é `min Σ k_j + Σ w_j + Σ u_i`. Os desvios e alunos sem turma têm peso unitário, como no rascunho. As restrições garantem capacidade, disponibilidade e no máximo uma turma por aluno. O solver CBC resolve o modelo; não há algoritmo heurístico de distribuição.

## Formato esperado do Excel

### Aba `Alunos`

Cabeçalhos exigidos: `Nome`, `Sexo`, `Disponibilidade`. Valores regulares de sexo são `M` e `F`; os períodos são `Manhã` e `Tarde`.

O código trata diferenças simples de caixa, espaços e acentuação. Por exemplo, `manha`, ` F ` e `feminino` são normalizados e incluídos no ensalamento, com aviso na aba **Inconsistências**. Valores desconhecidos como `X`, `?`, `Noite`, `Integral`, campos vazios ou nome ausente são reportados; o registro sem dados suficientes não entra na otimização. Linhas inteiramente vazias são ignoradas.

### Aba `Turmas`

Cabeçalhos: `Recursos` e `Quantidade`. O programa lê estes quatro recursos:

| Recurso | Significado |
|---|---|
| `turmas_manha` | Quantidade de turmas no período da manhã |
| `turmas_tarde` | Quantidade de turmas no período da tarde |
| `vagas_manha` | Capacidade de cada turma da manhã |
| `vagas_tarde` | Capacidade de cada turma da tarde |

Os parâmetros são lidos do Excel em cada execução; não ficam fixos no código. Isso permite usar as variações das instâncias: por exemplo, a instância 1 tem duas turmas por período e a instância 3 tem cinco turmas de manhã e uma à tarde.

## Arquivos de saída

- **Ensalamento**: colunas na ordem `Nome`, `Sexo`, `Disponibilidade`, `Turma`. Inclui todos os alunos válidos: os alocados recebem o nome da turma e os sem vaga recebem `SEM TURMA`.
- **Inconsistências**: colunas `Linha`, `Nome`, `Motivo`; registra valores normalizados, registros inválidos, nomes repetidos e alunos sem turma.

Na interface, o cálculo usa uma cópia temporária e mantém a planilha original intacta. **Exportar XLSX** grava a cópia completa no destino escolhido, com `Ensalamento` e `Inconsistências` atualizadas após o status `Optimal`. As abas `Alunos`, `Turmas` e eventuais abas adicionais são preservadas, assim como a formatação suportada pela rotina original do projeto. A exportação não executa o solver novamente.

A execução pelo terminal com caminho explícito preserva a planilha de entrada e grava uma cópia em `outputs/xlsx/<nome>_ensalamento.xlsx`. A interface continua abrindo o seletor de destino para exportar XLSX. Em ambos os casos, a gravação do resultado é feita primeiro em um temporário e substituída ao terminar.

## Interface desktop

- Importar XLSX, gerar a distribuição e exportar o workbook completo.
- **Manual do usuário** no canto superior direito abre o PDF pronto no visualizador padrão do computador. Em janelas menores que 900 px, mostra apenas o ícone de livro, mantendo a tooltip **Abrir Manual do Usuário** e uma área de clique de pelo menos 40 × 40 px.
- **Exportar relatório PDF** fica disponível ao lado de **Exportar XLSX** após gerar uma distribuição. O seletor sugere `outputs/pdf/<nome>_relatorio.pdf` e continua permitindo escolher outro destino. O relatório A4 inclui arquivo e identificação/data da execução, resumo geral, resumo por turno, indicadores de qualidade, gráficos completos e inconsistências/avisos separados. A seção final contém a lista completa de alunos por turma, com turno, alunos/capacidade, nome, sexo e disponibilidade, além dos alunos sem turma quando houver. Cabeçalhos de tabelas se repetem nas continuações e todas as páginas têm cabeçalho institucional e numeração. Os filtros da tela não restringem o PDF.
- Falhas são exibidas dentro da aplicação, sem modal, em um banner de atenção abaixo do card superior. A mensagem principal orienta a verificar o formato da planilha e o detalhe preserva o motivo retornado pelo processamento. O banner é limpo ao carregar outro arquivo, iniciar uma nova tentativa ou receber um resultado válido; a validação original permanece inalterada.
- Dashboard com quatro cards brancos: alunos alocados/total, alunos sem turma, ocupação e ociosidade. Os gráficos de alunos/capacidade e homens/mulheres têm maior altura, textos de alto contraste e eixos explícitos. A partir de 1200 px de largura, os gráficos e os painéis inferiores ficam lado a lado e os cards em uma linha. Abaixo disso, preserva-se o carrossel dos gráficos, os painéis inferiores ficam empilhados e os cards usam duas colunas. Clicar numa linha do gráfico seleciona a turma correspondente.
- O resumo por turno apresenta Manhã e Tarde nas linhas e as colunas Turno, Alocados, Sem turma, Capacidade, Ocupação e Vagas livres. Linhas finas separam cabeçalho e registros. O card de qualidade organiza a maior diferença de tamanho por turno e a maior variação H/M em dois quadros internos leves. A lista de turmas empatadas mostra até quatro nomes separados por vírgulas, com `...` quando há mais; a tooltip e a descrição acessível preservam a lista completa. Os quadros se empilham quando o card fica estreito; os dados e cálculos das métricas são preservados.
- Lista de uma turma por vez, com seletor de dropdown e chevron visível, setas adjacentes com tooltips de turma anterior/próxima e busca por nome que ignora caixa e acentos. Os filtros Sexo (Todos/Feminino/Masculino) e Disponibilidade (Todas/Manhã/Tarde) funcionam em conjunto com a busca dentro da turma selecionada, sem alterar a tabela de origem ou as métricas do dashboard. Os filtros são preservados ao navegar entre abas e turmas, e voltam a Todos/Todas ao importar outra planilha; a busca continua sendo limpa ao trocar a turma. Os controles ocupam uma linha em telas maiores e duas nas menores.
- Uma única aba **Inconsistências e avisos** contém duas seções com ícones, descrição, contadores próprios e relatórios agrupados por tipo, mantendo nome, linhas e motivo completo. As seções são alinhadas ao topo, crescem com o conteúdo e ficam separadas por 16 px; estados vazios são compactos e relatórios longos usam uma única rolagem da página. A altura do texto acompanha as quebras de linha ao redimensionar. Dados inválidos e alunos sem turma aparecem em Inconsistências; normalizações e nomes duplicados preservados aparecem em Avisos, conforme os motivos já emitidos pelo processamento. Um registro com dados inválidos continua em Inconsistências mesmo que seu motivo também contenha uma normalização. O relatório completo e a exportação continuam preservando todas as ocorrências originais.
- Três seções selecionáveis com SVGs e indicador azul da aba ativa: **Dashboard**, **Alunos por turma** e **Inconsistências e avisos**. O badge circular âmbar da última mostra a soma das duas categorias e fica oculto quando a soma é zero; os contadores internos continuam visíveis. A navegação usa o clique nas abas, sem atalhos Alt+número. Busca e turma selecionada são preservadas.
- Em janelas pequenas, a área externa permite rolagem sem comprimir a tabela até esconder suas linhas.

A interface usa Qt/PySide6 Essentials, sem navegador ou servidor. Os gráficos são widgets desenhados com `QPainter`; não há biblioteca gráfica adicional. Cada gráfico tem rolagem própria para as barras, com ticks, linha e título do eixo horizontal em um widget irmão fixo, fora do `QScrollArea` das barras. O dashboard tem sua própria rolagem para acessar os painéis inferiores. A tabela de alunos usa model/view, sem criar um widget por aluno. Botões exclusivos e `QStackedWidget` implementam a navegação; os mesmos widgets, dados, seleção e conexões são preservados ao redimensionar. A altura dos gráficos acompanha a altura da janela, com limites legíveis; no modo desktop, eles cedem até 32 px quando isso basta para eliminar uma pequena rolagem externa, preservando a altura mínima. Trocar de seção ou redimensionar não recalcula dados nem reinicia a tabela. A única animação decorativa move o marcador da navegação por 120 ms.

`ui/tema.py` centraliza cores da identidade ABC Aprendiz, fontes, dimensões e QSS. A tipografia usa a sequência anterior de fallback: Inter, Segoe UI, Noto Sans, Arial e alternativas locais, sem baixar fontes. Textos e ticks usam peso regular, valores e navegação ativa usam medium e títulos de painéis usam semibold. Durante o cálculo, a mensagem “Aguarde. A distribuição está sendo gerada.” e a linha verde indeterminada aparecem imediatamente abaixo do card de importação. Ambas desaparecem ao concluir ou falhar, sem reservar espaço; não há faixa de status persistente nem carregamento no rodapé. O botão de gerar permanece bloqueado enquanto a operação está em andamento. As abas têm altura comum, padding uniforme e larguras equivalentes quando há espaço; o badge tem uma reserva discreta para não deslocar o título ao aparecer. Cards são `QFrame`s com layouts nativos. Os SVGs ficam em `assets/icons/` e o logo em `assets/images/`; `ui/recursos.py` resolve caminhos no código e no pacote PyInstaller. `ABC_Aprendiz.spec` inclui toda a pasta `assets` e os módulos SVG do Qt.

Leitura, resolução e exportação rodam fora da thread da interface. Durante uma operação, importar, calcular e exportar ficam bloqueados para impedir resultados de instâncias diferentes na mesma tela; navegar pelas seções continua disponível. O fechamento aguarda a operação em andamento.

`ensalamento.py` mantém as funções de leitura, validação, modelo e gravação; apenas o ponto de entrada gráfico foi substituído. `apresentacao.py` adapta os resultados da rotina original para a tela e mantém o workbook processado para exportação. `ui/interface_desktop.py` contém a interface Qt. `relatorio_pdf.py` gera o relatório usando `QPdfWriter`, texto/tabelas nativos de `QTextDocument` e gráficos renderizados com `QPainter`, sem navegador ou dependências adicionais. A exportação roda em background sobre o resultado em memória, sem chamar o solver, recalcular métricas ou ler/gravar XLSX. O PDF é gravado em um temporário e substitui o destino apenas ao finalizar; falhas aparecem no banner da aplicação. O botão fica desabilitado sem resultado ou durante uma operação.

### Métricas do painel

`ResultadoInterface.metricas`, produzido por `metricas.calcular_metricas`, é a
fonte dos dados do dashboard e pode ser serializado em JSON. O módulo analisa a
solução existente, sem chamar o solver novamente. Retorna `resumo`, `por_turno`,
`turmas`, `balanceamento`, `nao_alocados` e `destaques`.

Ocupação e ociosidade são calculadas na camada de métricas, globalmente e por
turno. A soma das taxas é 100% quando existe capacidade; ambas são zero quando
não há capacidade. Os cálculos mantêm a precisão até o retorno, com duas casas
decimais; a tela formata percentuais com uma casa e vírgula decimal.

`balanceamento[turno]["alunos"]` contém apenas `minimo`, `maximo` e `amplitude`,
sempre dentro do próprio turno. Cada turma tem `diferenca_genero` (mulheres menos
homens). `destaques["variacao_genero"]` informa a maior diferença absoluta,
as turmas empatadas e os sentidos encontrados (`mulheres`, `homens` ou
`equilibrado`). Em empates com sentidos opostos, a tela mostra ambos, sem
classificar a distribuição como boa ou ruim.

Foram retirados os cálculos de dispersão, médias de referência do modelo,
percentuais de gênero e destaques sem uso no painel. Status e objetivo continuam
disponíveis em `ResultadoExecucao`; os parâmetros correspondentes de
`calcular_metricas` são mantidos por compatibilidade, mas não entram no retorno
de gestão. A lista de não alocados preserva nome, sexo e disponibilidade; esses
alunos não entram nos grupos nem nos gráficos de turmas.

## Instalação e execução no Windows

O desafio exige Python **3.12.9**. No PowerShell, dentro desta pasta:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python ensalamento.py
```

Também é possível abrir `executar.bat`. Ele prioriza o executável em `dist/ABC_Aprendiz.exe`; se ainda não tiver sido gerado, usa o ambiente local `.venv-ui` ou um Python com as dependências instaladas.

Na janela, use **Importar XLSX**, **Gerar distribuição** e **Exportar XLSX**. A distribuição não é despejada no terminal.

Execução opcional pelo terminal com caminho explícito:

```powershell
python ensalamento.py "C:\caminho\para\instancia.xlsx"
```

## Executável Windows

Para preparar o empacotamento com Python 3.12.9:

```powershell
python -m pip install -r requirements-dev.txt
python -m playwright install chromium --only-shell
python -m PyInstaller --noconfirm ABC_Aprendiz.spec
```

Ou execute `gerar_executavel.bat` após instalar as dependências de desenvolvimento. O script prepara o Chromium de build (reutiliza a instalação quando já disponível) e executa o PyInstaller, priorizando `.venv-ui`, depois `.venv` e, por fim, `py -3.12`. O resultado é:

```text
dist/
├── ABC_Aprendiz.exe
└── Manual_do_Usuario_ABC_Aprendiz.pdf
```

Distribua **os dois arquivos juntos, na mesma pasta**: o computador de destino não precisa de Python nem de ferramentas para gerar o manual. O executável único inclui suas bibliotecas e prepara os componentes em uma pasta temporária durante a abertura; não há pasta `_internal` para distribuir. O PDF permanece externo para ser encontrado facilmente e aberto pelo visualizador padrão.

O `.spec` inclui o solver CBC do PuLP e exclui os módulos de navegador e QML, que a interface não utiliza. A pasta `dist/` é um artefato local e não é versionada. O executável é uma build de desenvolvimento sem assinatura digital.

No Windows, o pacote também exclui cópias de ICU encontradas no `PATH` de outras ferramentas, deixando o Qt usar a API ICU do próprio Windows. Uma cópia incompatível dessa DLL impede a importação de `QtCore`, mesmo quando o processamento por terminal funciona.

### Preparação e abertura do Manual do Usuário

`manual_usuario.html` é o fonte editável. No início de cada build, antes de `Analysis`, o `.spec` executa `gerar_manual.py` com o mesmo Python do PyInstaller. O gerador usa [Playwright e a impressão em PDF do Chromium](https://playwright.dev/python/docs/api/class-page#page-pdf), aplica o CSS de impressão/A4 do HTML, preserva fundos e espera fontes e imagens carregarem. A conversão é local; apenas a instalação inicial das ferramentas exige download. Se a conversão falhar, o build para, impedindo uma entrega com manual ausente ou desatualizado.

O PDF gerado fica na raiz do projeto. Ao terminar `EXE`, o `.spec` copia esse PDF para `dist/`, ao lado do executável, respeitando também `--distpath`. Ele não entra em `datas`, pois isso o incorporaria ao executável e o extrairia na pasta temporária em vez de deixá-lo ao lado do `.exe`. O HTML, o gerador, o Playwright e o Chromium não são incluídos na aplicação. O PDF da raiz, `build/` e `dist/` são artefatos locais ignorados pelo Git.

Para preparar somente o manual em desenvolvimento, depois de instalar as ferramentas acima:

```powershell
python gerar_manual.py
python ensalamento.py
```

Faça essa preparação ao atualizar o HTML. O programa nunca gera o manual na inicialização ou no clique. Opcionalmente, o gerador aceita `--html caminho.html` e `--destino caminho.pdf`.

`ui/recursos.py:caminho_manual()` usa a raiz do projeto em desenvolvimento e `Path(sys.executable).resolve().parent` quando `sys.frozen` está ativo. A busca independe da pasta de trabalho e não usa `_MEIPASS` para o manual. No Windows, o botão chama `os.startfile` para abrir o próprio PDF no aplicativo associado; em outros sistemas, usa `QDesktopServices.openUrl`. Nenhuma cópia nem seletor de destino é criado.

Teste em desenvolvimento e depois no executável Windows:

1. Prepare o PDF, abra a interface e clique em **Manual do usuário**. Confirme a abertura do PDF no visualizador padrão. Abra também o programa a partir de outra pasta de trabalho.
2. Redimensione a janela para 680, 899, 900 e 1280 px de largura. Confirme o cabeçalho, o modo apenas ícone abaixo de 900 px, a tooltip e a abertura pelo mesmo botão.
3. Renomeie temporariamente o PDF e clique. Deve aparecer **Manual não encontrado** com “O Manual do Usuário não foi encontrado na pasta do sistema.” Restaure o nome em seguida.
4. Em um ambiente Windows de teste sem associação funcional para PDF, clique com o arquivo presente. Deve aparecer **Não foi possível abrir o manual** com “Verifique se existe um programa instalado no computador capaz de abrir arquivos PDF.” Os testes automatizados também simulam essa falha sem alterar associações do computador.
5. Execute `gerar_executavel.bat`, confira a estrutura acima e copie o `.exe` e o PDF juntos para outra localização ou um Windows sem Python. Abra o `.exe` e repita os passos anteriores. Confirme que cliques e reinicializações não alteram a data de modificação do manual.

O executável Windows deve ser gerado e validado no Windows; o teste em Linux não substitui essa verificação.

## Testes

```powershell
python -m unittest discover -s tests -v
```

Os testes verificam métricas, modos desktop e compacto, tabela transposta por turno, quatro cards, eixo horizontal fixo ao rolar as barras, SVGs no código e no caminho simulado do pacote, separação das ocorrências e contadores, preservação da entrada e das abas adicionais, exportação sem recálculo, falhas de escrita, seleção, busca, rolagem, conexões e processamento em background. Incluem tabela com 10.000 registros e navegação sem recriar o modelo. `python tests/preview_interface.py /tmp/abc_preview` executa a interface em modo offscreen e gera capturas em 1920 × 1080, 1366 × 768 e modo compacto, incluindo os gráficos rolados com 40 turmas de demonstração. Um segundo argumento opcional escolhe a planilha usada na prévia.

## Conteúdo desta pasta

```text
assets/
  icons/
  images/
Contexto/
  Desafio_UniSoma.pdf
  Modelo Conceitual Desafio 2026.pdf
Dados/
  instancia_1.xlsx
  instancia_2.xlsx
  instancia_3.xlsx
  instancia_4.xlsx
ensalamento.py
apresentacao.py
metricas.py
dados.py
relatorio_pdf.py
manual_usuario.html
gerar_manual.py
ui/
  interface_desktop.py
  tema.py
  recursos.py
outputs/
  xlsx/
  pdf/
ABC_Aprendiz.spec
executar.bat
gerar_executavel.bat
requirements.txt
requirements-dev.txt
tests/
  test_desktop.py
  test_metricas.py
  test_manual.py
README.md
```

## Pendências de entrega

- Validar os outputs com o programa oficial `Validador.exe`, especialmente os nomes exatos das abas/colunas e o formato do texto das inconsistências.
- Ajustar o layout para qualquer template final atualizado pela organização.
- Validar a distribuição do `.exe` em uma instalação Windows limpa e definir assinatura digital, se necessária para a entrega.
- Conferir o manual final com as capturas de tela e preparar o relatório resumo da distribuição, diferencial indicado nos documentos.
- Os cenários oficiais de desenvolvimento são quatro; a avaliação final executa 15 instâncias, das quais 11 não são fornecidas para desenvolvimento.

## Fontes do escopo

- `Contexto/Desafio_UniSoma.pdf`
- `Contexto/Modelo Conceitual Desafio 2026.pdf`
- As instâncias Excel em `Dados/`
- [Regulamento UniSoma 2026](https://unisoma.com.br/desafio/regulamento-2026/)
