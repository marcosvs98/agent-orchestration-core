-- ════════════════════════════════════════════════════════════════════════════
-- Script de Inicialização do Banco de Dados
-- ════════════════════════════════════════════════════════════════════════════
-- Este script é executado automaticamente pelo PostgreSQL na primeira inicialização
-- ════════════════════════════════════════════════════════════════════════════

-- Criar extensões necessárias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Configurar timezone padrão
SET timezone = 'America/Sao_Paulo';

-- Criar schema se necessário (opcional)
-- CREATE SCHEMA IF NOT EXISTS router;

-- Mensagem de sucesso
DO $$
BEGIN
    RAISE NOTICE 'Banco de dados inicializado com sucesso!';
    RAISE NOTICE 'Extensões instaladas: uuid-ossp, pg_trgm';
    RAISE NOTICE 'Timezone configurado: America/Sao_Paulo';
END $$;
