# Dívida Ativa da União

Software que baixa e transforma/limpa a base de dados de devedores da [Dívida
Ativa da União](https://www.listadevedores.pgfn.gov.br/), disponibilizados pela
[Procuradoria-Geral da Fazenda Nacional](https://www.gov.br/pgfn/pt-br).


## Licença

A licença do código é [LGPL3](https://www.gnu.org/licenses/lgpl-3.0.en.html) e
dos dados convertidos [Creative Commons Attribution
ShareAlike](https://creativecommons.org/licenses/by-sa/4.0/). Caso utilize os
dados, **cite a fonte original e quem tratou os dados**, como: **Fonte:
Procuradoria-Geral da Fazenda Nacional, dados tratados por Álvaro
Justen/[Brasil.IO](https://brasil.io/)**. Caso compartilhe os dados, **utilize
a mesma licença**.

Se esses dados forem úteis você pode considerar [doar para o
Brasil.IO](https://brasil.io/doe/).

## Rodando

```shell
docker compose up -d
docker compose exec main ./run.sh
```
