# Desafio UniSoma 2026 — Gestão de capacidade

## Contexto

Este repositório servirá de base para desenvolver a solução do Desafio UniSoma 2026. O problema apresentado é de **otimização combinatória aplicada à gestão de capacidade**. O enunciado e o regulamento oficiais são as referências para o escopo; este README registra o entendimento atual e separa os fatos das hipóteses que ainda dependem dos dados.

- [Regulamento do Desafio UniSoma 2026](https://unisoma.com.br/desafio/regulamento-2026/)
- Organização parceira mencionada no regulamento: **ABC Aprendiz**.

## Problema apresentado

O desafio consiste em mapear **N demandas concorrentes** em **M recursos de capacidade finita**. A solução deve:

1. respeitar a capacidade disponível dos recursos;
2. eliminar conflitos operacionais, incluindo exclusividade temporal quando aplicável;
3. reduzir a ociosidade;
4. considerar critérios flexíveis de balanceamento e eficiência;
5. encontrar uma solução de boa qualidade em pouco tempo, pois a busca exaustiva não é viável para bases reais.

O enunciado distingue **restrições rígidas** (*hard constraints*), que uma solução válida precisa cumprir, de **restrições flexíveis** (*soft constraints*), cuja violação pode receber penalidade. A capacidade e a exclusividade temporal são exemplos de regras rígidas; balanceamento e métricas de eficiência são exemplos flexíveis.

## Entendimento atual e pontos em aberto

O problema está descrito em nível conceitual. Ainda não recebemos o enunciado detalhado, o dicionário dos dados nem a base de validação. Portanto, a formulação matemática abaixo é apenas um mapa inicial — não uma especificação definitiva.

Precisaremos identificar:

- o que representa uma demanda e se ela pode ser dividida;
- quais recursos existem, suas capacidades, tipos e unidades de medida;
- se as demandas têm horários fixos, janelas de tempo ou duração;
- quais pares de demandas conflitam e se o conflito depende de sobreposição temporal;
- se toda demanda deve ser atendida ou se algumas podem ficar sem alocação;
- como o desafio define e mede “ociosidade”;
- qual métrica concreta representa balanceamento e eficiência;
- se há preferências, prioridades, custos ou níveis mínimos de serviço;
- como o código deve receber os arquivos e qual formato/estrutura de Excel deve produzir.

Essas respostas determinam se a formulação mais apropriada é uma variante do **Problema de Atribuição Generalizada (GAP)**, de **escalonamento com recursos limitados (RCPSP)**, de programação de equipes ou uma combinação dessas famílias. O GAP é especialmente próximo quando cada demanda é atribuída a um recurso capacitado; escalonamento com recursos limitados se torna mais próximo quando as demandas ocupam recursos em intervalos de tempo. As referências ao final ajudam a distinguir esses casos.

## Abstração matemática inicial

Se cada demanda indivisível (i) for atribuída a um recurso (r), uma variável binária candidata é:

\[
x_{ir} =
\begin{cases}
1 & \text{se a demanda } i \text{ for atribuída ao recurso } r,\\
0 & \text{caso contrário.}
\end{cases}
\]

Uma formulação final poderá incluir, conforme os dados:

- **Cobertura:** atribuir cada demanda ao recurso exigido, se o atendimento integral for obrigatório.
- **Elegibilidade:** impedir atribuições a recursos que não possam executar a demanda.
- **Capacidade:** limitar a carga alocada a cada recurso; se houver tempo, verificar a carga em cada período relevante.
- **Conflitos:** impedir atribuições simultâneas incompatíveis ao mesmo recurso.
- **Objetivo:** reduzir a ociosidade e penalidades de balanceamento ou eficiência, respeitando todas as regras rígidas.

O significado e a unidade de “ociosidade” precisam ser confirmados antes de definir a função objetivo. Por exemplo, capacidade sem uso ao longo do horizonte e tempo ocioso entre atividades são medidas diferentes. Também pode ser necessário usar prioridades ou uma otimização em etapas, em vez de somar todos os critérios com pesos arbitrários.

## Estratégia de solução a avaliar

1. Ler e validar os dados de entrada, apontando campos ausentes, unidades incompatíveis e regras inconsistentes.
2. Formalizar conjuntos, parâmetros, variáveis, restrições rígidas e métricas flexíveis a partir do material oficial.
3. Implementar um modelo de programação inteira/mista ou de restrições, escolhido de acordo com a estrutura real do caso.
4. Medir a solução na base de validação: viabilidade, valor das métricas, tempo de execução e, quando disponível, limite/gap do solver.
5. Se a instância for grande ou o limite de tempo impedir boa solução, comparar uma heurística ou abordagem híbrida, sem deixar de verificar as restrições rígidas.
6. Gerar o arquivo de resultados e documentar como interpretar cada indicador.

O desempenho deve ser avaliado em mais de uma dimensão: uma solução inválida não é aceitável, e o tempo de execução deve ser analisado junto da qualidade obtida. A frase “melhor solução no menor tempo” não define sozinha uma função objetivo; será necessário esclarecer se primeiro se maximiza a qualidade dentro de um limite de tempo ou se há um compromisso explícito entre qualidade e tempo.

## Requisitos de entrega registrados no regulamento

Segundo o regulamento, a linguagem da solução deve ser **Python**, com execução considerada no **Microsoft Windows**. O script deve ler os dados de entrada, executar a modelagem e salvar resultados em um arquivo Excel. As entregas descritas incluem:

- rascunho do modelo matemático, com função objetivo e restrições;
- script Python;
- solução executável com Python, bibliotecas e script;
- manual com instalação, preenchimento do arquivo de entrada, validações, restrições e interpretação dos resultados;
- apresentação final em PDF com até três slides e aproximadamente três minutos.

A avaliação considera a apresentação e a execução do código sobre uma base de validação. O regulamento também prevê implantação pela equipe vencedora com apoio da UniSoma e determina que o código vencedor seja livre. Os dados da ABC Aprendiz são restritos a estudo e desenvolvimento relacionados ao desafio e devem ser tratados com cuidado nas divulgações.

## Referências para fundamentação

1. **Öncan, T. (2007).** “A Survey of the Generalized Assignment Problem and Its Applications.” *INFOR*, 45(3), 123–141. Revisão de modelos, aplicações e métodos para atribuir tarefas a recursos capacitados. [DOI: 10.3138/infor.45.3.123](https://doi.org/10.3138/infor.45.3.123)
2. **Brucker, P. et al. (1999).** “Resource-constrained project scheduling: Notation, classification, models, and methods.” *European Journal of Operational Research*, 112(1), 3–41. Referência para atividades que consomem recursos ao longo do tempo e para classificações de modelos e métodos. [DOI: 10.1016/S0377-2217(98)00204-5](https://doi.org/10.1016/S0377-2217(98)00204-5)
3. **Ernst, A. T., Jiang, H., Krishnamoorthy, M. & Sier, D. (2004).** “Staff scheduling and rostering: A review of applications, methods and models.” *European Journal of Operational Research*, 153(1), 3–27. Revisão útil se os recursos forem pessoas ou equipes e houver regras de escala. [DOI: 10.1016/S0377-2217(03)00095-X](https://doi.org/10.1016/S0377-2217(03)00095-X)
4. **Hartmann, S. & Briskorn, D. (2022).** “An updated survey of variants and extensions of the resource-constrained project scheduling problem.” *European Journal of Operational Research*, 297(1), 1–14. Revisão de extensões com restrições temporais, recursos e objetivos alternativos. [DOI: 10.1016/j.ejor.2021.05.004](https://doi.org/10.1016/j.ejor.2021.05.004)
5. **Stølevik, M. et al. (2011).** “A hybrid approach for solving real-world nurse rostering problems.” Estudo aplicado que combina programação por restrições e busca local em um problema com restrições rígidas e flexíveis. [DOI: 10.1007/978-3-642-23786-7_9](https://doi.org/10.1007/978-3-642-23786-7_9) · [Texto completo](https://hdl.handle.net/11250/2430595)

## Atualização deste README

Quando o enunciado completo e os arquivos forem disponibilizados, atualizar este documento com o dicionário dos dados, as regras confirmadas, as hipóteses rejeitadas, a formulação escolhida e os indicadores usados para avaliar a solução. Até lá, qualquer estrutura matemática descrita aqui deve ser tratada como preliminar.
