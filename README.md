# Desafio UniSoma 2026 — Ensalamento ABC Aprendiz

Aplicação em Python para distribuir os alunos matriculados nas turmas disponíveis no Excel do cenário. Esta versão foi construída a partir dos documentos em `Contexto/` e das quatro instâncias em `Dados/`.

## O que o programa faz

1. Abre uma janela para selecionar o Excel do cenário.
2. Lê as abas **Alunos** e **Turmas**.
3. Valida os registros e a capacidade disponível.
4. Resolve um modelo matemático de programação inteira binária usando PuLP e o solver CBC.
5. Grava as abas **Ensalamento** e **Inconsistências** no mesmo arquivo selecionado.

## Regras representadas

### Restrições rígidas

- Cada aluno válido é alocado em no máximo uma turma; se não receber turma, `u_i=1` registra essa situação.
- Disponibilidade de manhã só permite turma de manhã; disponibilidade à tarde só permite turma da tarde.
- Cada turma respeita o limite de vagas informado na aba **Turmas**.
- Um aluno pode ficar sem turma quando faltarem vagas; o modelo minimiza a quantidade de alunos sem alocação e os reporta na aba **Inconsistências**.
- A nomenclatura é contínua entre os períodos: as turmas da manhã recebem as primeiras letras e as da tarde continuam a sequência, no padrão `MANHÃ - A`, `MANHÃ - B`, `TARDE - C` etc.
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

- **Ensalamento**: colunas na ordem `Nome`, `Sexo`, `Disponibilidade`, `Turma`.
- **Inconsistências**: colunas `Linha`, `Nome`, `Motivo`; registra dados corrigidos automaticamente, registros que não puderam ser alocados e nomes duplicados.

As abas de entrada são mantidas. Se as abas de saída já existirem, elas são substituídas. Faça uma cópia do Excel antes de executar.

## Instalação e execução no Windows

O desafio exige Python **3.12.9**. No PowerShell, dentro desta pasta:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python ensalamento.py
```

Também é possível abrir `executar.bat`. A janela do programa permite selecionar o `.xlsx` sem passar o caminho pela linha de comando.

Execução opcional pelo terminal com caminho explícito:

```powershell
python ensalamento.py "C:\caminho\para\instancia.xlsx"
```

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
executar.bat
requirements.txt
README.md
```

## Pendências de entrega

- Validar os outputs com o programa oficial `Validador.exe`, especialmente os nomes exatos das abas/colunas e o formato do texto das inconsistências.
- Ajustar o layout para qualquer template final atualizado pela organização.
- Gerar e testar o `.exe` no Windows com PyInstaller, incluindo CBC e os arquivos de dependências.
- Criar o manual de usuário em PDF e o relatório resumo da distribuição, diferencial indicado nos documentos.
- Os cenários oficiais de desenvolvimento são quatro; a avaliação final executa 15 instâncias, das quais 11 não são fornecidas para desenvolvimento.

## Fontes do escopo

- `Contexto/Desafio_UniSoma.pdf`
- `Contexto/Modelo Conceitual Desafio 2026.pdf`
- As instâncias Excel em `Dados/`
- [Regulamento UniSoma 2026](https://unisoma.com.br/desafio/regulamento-2026/)
