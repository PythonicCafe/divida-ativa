DROP TABLE IF EXISTS divida_ativa;
CREATE TABLE divida_ativa AS
  WITH fgts AS (
    SELECT
      'FGTS' AS tipo_divida,
      numero_inscricao,
      CASE
        WHEN tipo_pessoa = 'Pessoa jurídica' THEN RIGHT('00000000000000' || REGEXP_REPLACE(cpf_cnpj, '[^0-9*]+', '', 'g'), 14)
        WHEN tipo_pessoa = 'Pessoa física' THEN RIGHT('00000000000' || REGEXP_REPLACE(cpf_cnpj, '[^0-9*]+', '', 'g'), 11)
        ELSE NULL
      END AS devedor_cpf_cnpj,
      nome_devedor AS devedor,
      uf_devedor AS devedor_uf,
      CASE
        WHEN tipo_devedor = 'PRINCIPAL' THEN 'Principal'
        WHEN tipo_devedor = 'CORRESPONSAVEL' THEN 'Corresponsável'
        WHEN tipo_devedor = 'SOLIDARIO' THEN 'Solidário'
        ELSE tipo_devedor
      END AS devedor_tipo,
      unidade_responsavel,
      entidade_responsavel,
      unidade_inscricao,
      tipo_situacao_inscricao,
      situacao_inscricao,
      receita_principal,
      NULL AS tipo_credito,
      TO_DATE(data_inscricao, 'DD/MM/YYY') AS data_inscricao,
      CASE
        WHEN lower(indicador_ajuizado) = 'sim' THEN TRUE
        WHEN lower(indicador_ajuizado) IN ('nao', 'não') THEN FALSE
        ELSE NULL
      END AS ajuizado,
      valor_consolidado::decimal(16, 2)
    FROM divida_ativa_fgts_orig
  ),
  nao_prev AS (
    SELECT
      'Não previdenciária' AS tipo_divida,
      numero_inscricao,
      CASE
        WHEN tipo_pessoa = 'Pessoa jurídica' THEN RIGHT('00000000000000' || REGEXP_REPLACE(cpf_cnpj, '[^0-9*]+', '', 'g'), 14)
        WHEN tipo_pessoa = 'Pessoa física' THEN RIGHT('00000000000' || REGEXP_REPLACE(cpf_cnpj, '[^0-9*]+', '', 'g'), 11)
        ELSE NULL
      END AS devedor_cpf_cnpj,
      nome_devedor AS devedor,
      uf_devedor AS devedor_uf,
      CASE
        WHEN tipo_devedor = 'PRINCIPAL' THEN 'Principal'
        WHEN tipo_devedor = 'CORRESPONSAVEL' THEN 'Corresponsável'
        WHEN tipo_devedor = 'SOLIDARIO' THEN 'Solidário'
        ELSE tipo_devedor
      END AS devedor_tipo,
      unidade_responsavel,
      NULL AS entidade_responsavel,
      NULL AS unidade_inscricao,
      tipo_situacao_inscricao,
      situacao_inscricao,
      receita_principal,
      NULL AS tipo_credito,
      TO_DATE(data_inscricao, 'DD/MM/YYY') AS data_inscricao,
      CASE
        WHEN lower(indicador_ajuizado) = 'sim' THEN TRUE
        WHEN lower(indicador_ajuizado) IN ('nao', 'não') THEN FALSE
        ELSE NULL
      END AS ajuizado,
      valor_consolidado::decimal(16, 2)
    FROM divida_ativa_nao_previdenciario_orig
  ),
  prev AS (
    SELECT
      'Previdenciária' AS tipo_divida,
      numero_inscricao,
      CASE
        WHEN tipo_pessoa = 'Pessoa jurídica' THEN RIGHT('00000000000000' || REGEXP_REPLACE(cpf_cnpj, '[^0-9*]+', '', 'g'), 14)
        WHEN tipo_pessoa = 'Pessoa física' THEN RIGHT('00000000000' || REGEXP_REPLACE(cpf_cnpj, '[^0-9*]+', '', 'g'), 11)
        ELSE NULL
      END AS devedor_cpf_cnpj,
      nome_devedor AS devedor,
      uf_devedor AS devedor_uf,
      CASE
        WHEN tipo_devedor = 'PRINCIPAL' THEN 'Principal'
        WHEN tipo_devedor = 'CORRESPONSAVEL' THEN 'Corresponsável'
        WHEN tipo_devedor = 'SOLIDARIO' THEN 'Solidário'
        ELSE tipo_devedor
      END AS devedor_tipo,
      unidade_responsavel,
      NULL AS entidade_responsavel,
      NULL AS unidade_inscricao,
      tipo_situacao_inscricao,
      situacao_inscricao,
      NULL AS receita_principal,
      tipo_credito,
      TO_DATE(data_inscricao, 'DD/MM/YYY') AS data_inscricao,
      CASE
        WHEN lower(indicador_ajuizado) = 'sim' THEN TRUE
        WHEN lower(indicador_ajuizado) IN ('nao', 'não') THEN FALSE
        ELSE NULL
      END AS ajuizado,
      valor_consolidado::decimal(16, 2)
    FROM divida_ativa_previdenciario_orig
  )
  SELECT
    CASE
      WHEN LENGTH(devedor_cpf_cnpj) = 14 THEN company_uuid(devedor_cpf_cnpj)
      WHEN LENGTH(devedor_cpf_cnpj) = 11 THEN person_uuid(devedor_cpf_cnpj, devedor)
      ELSE NULL
    END AS devedor_uuid,
    tipo_divida,
    numero_inscricao,
    devedor_cpf_cnpj,
    devedor,
    devedor_uf,
    devedor_tipo,
    unidade_responsavel,
    entidade_responsavel,
    unidade_inscricao,
    situacao_inscricao,
    tipo_situacao_inscricao,
    receita_principal,
    tipo_credito,
    data_inscricao,
    ajuizado,
    valor_consolidado
  FROM (
    SELECT * FROM fgts
    UNION ALL
    SELECT * FROM prev
    UNION ALL
    SELECT * FROM nao_prev
  ) AS t;
