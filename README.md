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

A execução pelo terminal com caminho explícito mantém o comportamento original: atualiza o próprio arquivo informado. Em ambos os casos, a gravação é feita primeiro em um temporário e substituída ao terminar. Feche a planilha no Excel antes de sobrescrever um arquivo existente.

## Interface desktop

- Importar XLSX, gerar a distribuição e exportar o workbook completo.
- Dashboard com rolagem vertical: seis cards de resumo, gráficos compactos de alunos/capacidade e homens/mulheres, qualidade da distribuição e resumo por turno. A partir de 1200 px de largura da janela, os gráficos e os painéis inferiores ficam lado a lado e os cards em uma linha. Abaixo disso, os gráficos usam um carrossel com setas e indicador de página, os painéis inferiores ficam empilhados e os cards usam três colunas a partir de 820 px ou duas abaixo dessa largura. Clicar numa linha do gráfico seleciona a turma correspondente.
- O resumo por turno é uma única tabela centralizada, com cabeçalhos Manhã/Tarde e cinco linhas: alocados/disponíveis, sem turma, capacidade, ocupação e vagas livres. A qualidade da distribuição tem duas áreas: diferença de tamanho por turno (por exemplo, `0 aluno` ou `2 alunos`) e maior variação H/M, com a turma em texto secundário. Essas áreas se empilham quando o próprio card fica estreito; os dados e cálculos das métricas são preservados.
- Lista de uma turma por vez, com seletor, setas e busca por nome que ignora caixa e acentos. As contagens dos dashboards não são alteradas pela busca.
- Relatório de inconsistências da instância, agrupado por tipo de ocorrência, com nome, aba de origem, linhas e motivo completo, incluindo os avisos de normalização.
- Três seções selecionáveis: **Dashboards**, **Alunos por turma** e **Inconsistências**. Só uma ocupa a área principal de cada vez. As teclas **Alt+1**, **Alt+2** e **Alt+3** também alternam entre elas. Busca e turma selecionada são preservadas ao trocar de seção.
- Em janelas pequenas, a área externa permite rolagem sem comprimir a tabela até esconder suas linhas.

A interface usa Qt/PySide6 Essentials, sem navegador ou servidor. A tabela usa model/view, sem criar um widget por aluno. Os três painéis e os dois gráficos permanecem montados; `QStackedWidget` alterna somente as seções principais. O modo desktop mostra os dois gráficos simultaneamente e esconde a paginação; o modo compacto mostra um por vez. Os mesmos widgets são reposicionados somente ao cruzar os breakpoints, mantendo os dados, a turma selecionada, a página do carrossel e a rolagem dos gráficos. Cada gráfico tem rolagem própria quando há muitas turmas. Trocar de seção ou redimensionar não recalcula dados nem reinicia o modelo da tabela. A única animação decorativa move o pequeno marcador da navegação por 120 ms; não aplica efeitos de opacidade, sombra ou movimento à tabela, ao relatório ou aos gráficos. Uma nova seleção interrompe e reaproveita a mesma animação. As cores azuis, verdes e amarelas e os contornos arredondados são estáticos.

Leitura, resolução e exportação rodam fora da thread da interface. Durante uma operação, importar, calcular e exportar ficam bloqueados para impedir resultados de instâncias diferentes na mesma tela; navegar pelas seções continua disponível. O fechamento aguarda a operação em andamento.

`ensalamento.py` mantém as funções de leitura, validação, modelo e gravação; apenas o ponto de entrada gráfico foi substituído. `apresentacao.py` adapta os resultados da rotina original para a tela e mantém o workbook processado para exportação. `interface_desktop.py` contém a interface Qt.

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

Também é possível abrir `executar.bat`. Ele prioriza o executável em `dist/ABC_Aprendiz/`; se ainda não tiver sido gerado, usa o ambiente local `.venv-ui` ou um Python com as dependências instaladas.

Na janela, use **Importar XLSX**, **Gerar distribuição** e **Exportar XLSX**. A distribuição não é despejada no terminal.

Execução opcional pelo terminal com caminho explícito:

```powershell
python ensalamento.py "C:\caminho\para\instancia.xlsx"
```

## Executável Windows

Para preparar o empacotamento com Python 3.12.9:

```powershell
python -m pip install -r requirements-dev.txt
python -m PyInstaller --noconfirm ABC_Aprendiz.spec
```

Ou execute `gerar_executavel.bat` após instalar as dependências de desenvolvimento. O resultado fica em **`dist/ABC_Aprendiz/ABC_Aprendiz.exe`**. Distribua a pasta **ABC_Aprendiz inteira**, incluindo `_internal`: o computador de destino não precisa de Python. O empacotamento em pasta evita extrair todas as bibliotecas a cada abertura; não mova apenas o `.exe`.

O `.spec` inclui o solver CBC do PuLP e exclui os módulos de navegador e QML, que a interface não utiliza. A pasta `dist/` é um artefato local e não é versionada. O executável é uma build de desenvolvimento sem assinatura digital.

No Windows, o pacote também exclui cópias de ICU encontradas no `PATH` de outras ferramentas, deixando o Qt usar a API ICU do próprio Windows. Uma cópia incompatível dessa DLL impede a importação de `QtCore`, mesmo quando o processamento por terminal funciona.

## Testes

```powershell
python -m unittest discover -s tests -v
```

Os testes verificam métricas e taxas de ocupação/ociosidade, amplitude por turno, variação H/M e empates, modos desktop e compacto do dashboard, gráficos simultâneos em Full HD e carrossel abaixo de 1200 px, tabela centralizada por turno, cards em seis/três/duas colunas, transições de largura preservando dados, seleção, rolagem e conexões, preservação da entrada e das abas adicionais, exportação sem recálculo, falhas de escrita, navegação entre turmas e seções, preservação da busca, área útil dos painéis, término da animação curta, tabela com 10.000 registros e processamento com eventos da interface ativos. As verificações não representam uma garantia de taxa de quadros em qualquer máquina.

## Conteúdo desta pasta

```text
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
interface_desktop.py
metricas.py
dados.py
ABC_Aprendiz.spec
executar.bat
gerar_executavel.bat
requirements.txt
requirements-dev.txt
tests/
  test_desktop.py
  test_metricas.py
README.md
```

## Pendências de entrega

- Validar os outputs com o programa oficial `Validador.exe`, especialmente os nomes exatos das abas/colunas e o formato do texto das inconsistências.
- Ajustar o layout para qualquer template final atualizado pela organização.
- Validar a distribuição do `.exe` em uma instalação Windows limpa e definir assinatura digital, se necessária para a entrega.
- Criar o manual de usuário em PDF e o relatório resumo da distribuição, diferencial indicado nos documentos.
- Os cenários oficiais de desenvolvimento são quatro; a avaliação final executa 15 instâncias, das quais 11 não são fornecidas para desenvolvimento.

## Fontes do escopo

- `Contexto/Desafio_UniSoma.pdf`
- `Contexto/Modelo Conceitual Desafio 2026.pdf`
- As instâncias Excel em `Dados/`
- [Regulamento UniSoma 2026](https://unisoma.com.br/desafio/regulamento-2026/)
