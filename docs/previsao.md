# Previsão antes da medição (TP3)

## Páginas esperadas de `t` (100.000 tuplas) e tuplas por página

Para 100.000 tuplas, espera-se que a tabela `t` ocupe algumas centenas de páginas do PostgreSQL. Considerando o tamanho de página de 8 KB e o tamanho das tuplas, espera-se aproximadamente entre 200 e 250 tuplas por página.

Assim, espera-se uma quantidade de páginas na ordem de aproximadamente 400 a 500 páginas.

O valor exato poderá variar devido ao tamanho do cabeçalho das tuplas e ao espaço utilizado internamente nas páginas.

## Altura esperada do índice sobre `v` com 100.000 e com 1.000.000 de tuplas

Espera-se que o índice B-tree sobre `v` tenha baixa altura nos dois casos, devido à grande quantidade de entradas que podem ser armazenadas em cada página da árvore.

Para 100.000 tuplas, espera-se uma altura de aproximadamente 2 a 3 níveis.

Para 1.000.000 de tuplas, espera-se que a altura possa aumentar, provavelmente para aproximadamente 3 níveis.

Portanto, a previsão é que o aumento de 100.000 para 1.000.000 de tuplas possa aumentar a altura da árvore, embora esse aumento não seja necessariamente grande devido à alta capacidade de ramificação da B-tree.

## Efeito esperado do `fillfactor` (tamanho, altura, tempo)

Espera-se que valores menores de `fillfactor` deixem mais espaço livre nas páginas do índice, fazendo com que o índice ocupe mais páginas e, consequentemente, mais espaço em disco.

Assim, espera-se que o tamanho do índice aumente à medida que o `fillfactor` diminui:

`60 > 80 > 85 > 90`

em termos de espaço ocupado.

Espera-se que a altura do índice permaneça igual para a maior parte ou para todos os valores de `fillfactor`, pois a diferença de ocupação das páginas provavelmente não será suficiente para alterar o número de níveis da árvore.

Quanto ao tempo de criação, espera-se que índices com menor `fillfactor` possam apresentar maior tempo de criação devido à necessidade de utilizar mais páginas.

Para o tempo de consulta, espera-se uma diferença pequena entre os diferentes valores de `fillfactor`, pois a consulta de igualdade sobre `v` depende também do acesso às páginas da tabela. Como `v` possui apenas 10 valores distintos, cada valor deverá aparecer em aproximadamente 10% das tuplas.

## Tipo de acesso esperado em cada consulta de T12 (seletiva e não seletiva) e de T15

### T12

Para a consulta seletiva sobre `votes`, que deve retornar menos de 10 tuplas, espera-se que o PostgreSQL utilize o índice sobre `votes`, pois poucas linhas precisam ser recuperadas.

Para a consulta não seletiva, que deve retornar mais de 80% das tuplas, espera-se que o PostgreSQL utilize uma varredura sequencial (`Seq Scan`) em vez do índice. Nesse caso, utilizar o índice exigiria localizar uma quantidade muito grande de registros e acessar muitas páginas da tabela, tornando a varredura sequencial potencialmente mais barata.

Para `votes < X`, espera-se que o PostgreSQL utilize o índice para valores pequenos de `X` e deixe de utilizá-lo quando a quantidade estimada de linhas retornadas for suficientemente grande. O valor exato de `X` será determinado experimentalmente.

### T15

Para:

`title LIKE 'T%'`

espera-se que a consulta possa utilizar um índice B-tree adequado para buscas por padrão. Após a criação do índice com `text_pattern_ops`, espera-se maior possibilidade de utilização do índice.

Para:

`substr(title, 1, 1) = 'T'`

espera-se que o índice normal sobre `title` não seja utilizado diretamente, pois a consulta aplica uma função sobre a coluna. Após a criação de um índice sobre a expressão, espera-se que a consulta possa utilizar esse índice.

Para:

`title LIKE '%A'`

espera-se que uma varredura sequencial seja utilizada, pois o caractere `%` no início impede que um índice B-tree convencional aproveite a ordenação dos títulos para localizar diretamente os valores terminados em `A`.

Para:

`reverse(title) LIKE 'A%'`

espera-se que a consulta possa utilizar um índice sobre a expressão `reverse(title)`, pois a transformação do texto permite tratar a busca pelo sufixo como uma busca por prefixo.

## Estimativa de seletividade esperada em T16 (padrão e com `SET STATISTICS 1000`)

Para `votes < 1000`, espera-se que a quantidade estimada de linhas seja relativamente pequena em comparação com o total da tabela.

Para `votes > 35000`, espera-se uma quantidade significativamente maior de linhas.

Com as estatísticas padrão, espera-se que as estimativas sejam razoavelmente próximas dos valores reais, mas possam apresentar diferenças caso a distribuição dos votos não seja uniforme.

Com `SET STATISTICS 1000`, espera-se que o PostgreSQL tenha informações mais detalhadas sobre a distribuição de `votes`. Portanto, a previsão é que as estimativas de cardinalidade sejam mais próximas dos valores reais, principalmente se a distribuição dos votos apresentar regiões de maior concentração que não sejam bem representadas pelas estatísticas padrão.

Entretanto, não se espera necessariamente uma melhoria igual nas duas consultas, pois o resultado depende da distribuição real dos valores de `votes`.

## Comportamento esperado do tempo total em T17 quando `k` cresce, por versão e nível de isolamento

Espera-se que, com `k = 1`, o tempo total seja relativamente alto devido à ausência de paralelismo, mas que praticamente não ocorram conflitos entre agentes.

Com o aumento de `k`, espera-se inicialmente uma redução do tempo total devido ao maior paralelismo.

Depois de determinado ponto, espera-se que o ganho de desempenho diminua ou desapareça devido ao aumento da concorrência e dos conflitos entre agentes.

### Versão A

Na versão A, os três passos da reserva ficam dentro de uma única transação. Como existe uma espera de 0,1 segundo durante a escolha do assento, espera-se que as transações permaneçam abertas por mais tempo.

Assim, espera-se maior contenção conforme `k` aumenta e, consequentemente, maior número de tentativas e possível aumento do tempo total nas maiores concorrências.

### Versão B

Na versão B, o passo de escolha ocorre fora da transação. Portanto, espera-se que as transações sejam mais curtas e que a contenção causada pelo período de espera de 0,1 segundo seja menor.

Consequentemente, espera-se que a versão B apresente melhor escalabilidade com o aumento de `k`.

Por outro lado, como a escolha do assento ocorre fora da transação que efetivamente realiza a reserva, espera-se que possam ocorrer conflitos quando dois agentes escolhem o mesmo assento.

### `READ COMMITTED`

Espera-se que `READ COMMITTED` apresente menor quantidade de falhas de serialização e, consequentemente, menor número de tentativas que `SERIALIZABLE`.

Com o aumento de `k`, ainda deverão ocorrer conflitos relacionados à disputa pelos assentos, mas espera-se que o impacto seja menor do que em `SERIALIZABLE`.

### `SERIALIZABLE`

Espera-se maior número de conflitos e novas tentativas conforme `k` aumenta, devido às garantias mais fortes de isolamento.

Consequentemente, espera-se que o tempo total aumente mais ou apresente menor ganho de desempenho com o aumento da quantidade de agentes.

De maneira geral, a previsão é que o aumento de `k` inicialmente reduza o tempo total devido ao paralelismo, mas que a partir de determinado ponto a contenção passe a dominar o comportamento.

A expectativa geral é que a combinação de maior concorrência, versão A e isolamento `SERIALIZABLE` apresente maior quantidade de conflitos e tentativas, enquanto a versão B com `READ COMMITTED` apresente menor contenção.

