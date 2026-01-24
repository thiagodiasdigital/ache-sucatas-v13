-- ============================================================
-- MIGRATION: Taxonomia Automotiva para Ache Sucatas
-- ============================================================
-- Data: 2026-01-24
-- Descricao: Cria tabela para armazenar taxonomia de veiculos
--            que sera usada pelo Miner para classificar editais.
--            APENAS termos automotivos - sem imoveis/mobiliario/eletronicos
-- ============================================================

-- 1. Criar tabela de taxonomia automotiva
CREATE TABLE IF NOT EXISTS taxonomia_automotiva (
    id SERIAL PRIMARY KEY,
    categoria VARCHAR(50) NOT NULL,      -- TIPO, MARCA, MODELO_LEVE, MODELO_MOTO, MODELO_PESADO, IMPLEMENTO, MAQUINA
    termo VARCHAR(100) NOT NULL,         -- termo principal normalizado (minusculo, sem acento)
    sinonimos TEXT[] DEFAULT '{}',       -- variacoes/sinonimos do termo
    tag_gerada VARCHAR(50),              -- tag que sera gerada no edital (ex: VEICULO, CAMINHAO)
    ativo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Garante que nao haja duplicatas
    UNIQUE(categoria, termo)
);

-- 2. Criar indice para busca rapida
CREATE INDEX IF NOT EXISTS idx_taxonomia_categoria ON taxonomia_automotiva(categoria) WHERE ativo = TRUE;
CREATE INDEX IF NOT EXISTS idx_taxonomia_termo ON taxonomia_automotiva(termo) WHERE ativo = TRUE;
CREATE INDEX IF NOT EXISTS idx_taxonomia_tag ON taxonomia_automotiva(tag_gerada) WHERE ativo = TRUE;

-- 3. Trigger para atualizar updated_at
CREATE OR REPLACE FUNCTION update_taxonomia_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_taxonomia_updated_at ON taxonomia_automotiva;
CREATE TRIGGER trigger_taxonomia_updated_at
    BEFORE UPDATE ON taxonomia_automotiva
    FOR EACH ROW
    EXECUTE FUNCTION update_taxonomia_updated_at();

-- 4. Comentarios na tabela
COMMENT ON TABLE taxonomia_automotiva IS 'Taxonomia automotiva para classificacao de editais do Ache Sucatas';
COMMENT ON COLUMN taxonomia_automotiva.categoria IS 'Categoria do termo: TIPO, MARCA, MODELO_LEVE, MODELO_MOTO, MODELO_PESADO, IMPLEMENTO, MAQUINA';
COMMENT ON COLUMN taxonomia_automotiva.termo IS 'Termo principal normalizado (minusculo, sem acento)';
COMMENT ON COLUMN taxonomia_automotiva.sinonimos IS 'Array de sinonimos/variacoes do termo';
COMMENT ON COLUMN taxonomia_automotiva.tag_gerada IS 'Tag que sera atribuida ao edital quando este termo for encontrado';

-- ============================================================
-- POPULACAO INICIAL DA TAXONOMIA
-- ============================================================

-- Limpar dados existentes (se houver)
TRUNCATE TABLE taxonomia_automotiva RESTART IDENTITY;

-- ============================================================
-- CATEGORIA: TIPO (tipos gerais de veiculos/bens)
-- Estas keywords geram as TAGS principais nos cards
-- ============================================================
INSERT INTO taxonomia_automotiva (categoria, termo, sinonimos, tag_gerada) VALUES
-- Veiculos gerais
('TIPO', 'veiculo', ARRAY['veiculos', 'automovel', 'automoveis', 'carro', 'carros', 'automotor', 'automotores', 'automotivo'], 'VEICULO'),
('TIPO', 'sucata', ARRAY['sucatas', 'inservivel', 'inserviveis', 'ferroso', 'ferrosos', 'sucateado', 'sucateados'], 'SUCATA'),
('TIPO', 'moto', ARRAY['motos', 'motocicleta', 'motocicletas', 'ciclomotor', 'ciclomotores', 'motociclo'], 'MOTO'),
('TIPO', 'caminhao', ARRAY['caminhoes', 'caminhonete', 'camionete', 'truck', 'trucks', 'cavalo mecanico'], 'CAMINHAO'),
('TIPO', 'onibus', ARRAY['microonibus', 'micro-onibus', 'micro onibus', 'onibus urbano', 'onibus rodoviario'], 'ONIBUS'),
('TIPO', 'carreta', ARRAY['carretas', 'semi-reboque', 'semirreboque', 'reboque', 'reboques', 'implemento rodoviario'], 'CARRETA'),
('TIPO', 'trator', ARRAY['tratores', 'trator agricola', 'trator de esteira'], 'MAQUINARIO'),
('TIPO', 'maquina', ARRAY['maquinas', 'maquinario', 'equipamento pesado', 'maquina pesada'], 'MAQUINARIO'),
('TIPO', 'retroescavadeira', ARRAY['retroescavadeiras', 'retro escavadeira', 'retro-escavadeira'], 'MAQUINARIO'),
('TIPO', 'escavadeira', ARRAY['escavadeiras', 'escavadeira hidraulica'], 'MAQUINARIO'),
('TIPO', 'pa carregadeira', ARRAY['pa-carregadeira', 'carregadeira', 'carregadeiras'], 'MAQUINARIO'),
('TIPO', 'motoniveladora', ARRAY['motoniveladoras', 'patrol'], 'MAQUINARIO'),
('TIPO', 'documentado', ARRAY['documentados', 'com documento', 'documento ok', 'documentacao ok'], 'DOCUMENTADO'),
('TIPO', 'apreendido', ARRAY['apreendidos', 'apreensao', 'patio', 'removido', 'removidos', 'custodia'], 'APREENDIDO');

-- ============================================================
-- CATEGORIA: MARCA (fabricantes de veiculos)
-- ============================================================
INSERT INTO taxonomia_automotiva (categoria, termo, sinonimos, tag_gerada) VALUES
-- Montadoras de Leves
('MARCA', 'volkswagen', ARRAY['vw', 'volks', 'volksvagem', 'voks', 'wolksvagen'], 'VEICULO'),
('MARCA', 'chevrolet', ARRAY['gm', 'chevy', 'chev', 'general motors'], 'VEICULO'),
('MARCA', 'fiat', ARRAY['f.i.a.t'], 'VEICULO'),
('MARCA', 'ford', ARRAY[], 'VEICULO'),
('MARCA', 'toyota', ARRAY[], 'VEICULO'),
('MARCA', 'honda', ARRAY[], 'VEICULO'),
('MARCA', 'hyundai', ARRAY[], 'VEICULO'),
('MARCA', 'renault', ARRAY[], 'VEICULO'),
('MARCA', 'peugeot', ARRAY[], 'VEICULO'),
('MARCA', 'citroen', ARRAY[], 'VEICULO'),
('MARCA', 'nissan', ARRAY[], 'VEICULO'),
('MARCA', 'mitsubishi', ARRAY['mit'], 'VEICULO'),
('MARCA', 'jeep', ARRAY[], 'VEICULO'),
('MARCA', 'bmw', ARRAY['b.m.w.'], 'VEICULO'),
('MARCA', 'audi', ARRAY[], 'VEICULO'),
('MARCA', 'land rover', ARRAY['landrover'], 'VEICULO'),
-- Montadoras de Pesados
('MARCA', 'mercedes-benz', ARRAY['mb', 'mercedes', 'm.benz', 'm benz', 'merc'], 'CAMINHAO'),
('MARCA', 'scania', ARRAY[], 'CAMINHAO'),
('MARCA', 'volvo', ARRAY[], 'CAMINHAO'),
('MARCA', 'iveco', ARRAY[], 'CAMINHAO'),
('MARCA', 'daf', ARRAY[], 'CAMINHAO'),
('MARCA', 'man', ARRAY[], 'CAMINHAO'),
('MARCA', 'agrale', ARRAY[], 'CAMINHAO'),
-- Motos
('MARCA', 'yamaha', ARRAY[], 'MOTO'),
('MARCA', 'suzuki', ARRAY[], 'MOTO'),
('MARCA', 'kawasaki', ARRAY[], 'MOTO'),
('MARCA', 'triumph', ARRAY[], 'MOTO'),
('MARCA', 'dafra', ARRAY[], 'MOTO'),
('MARCA', 'shineray', ARRAY[], 'MOTO'),
-- Maquinas/Agricola
('MARCA', 'caterpillar', ARRAY['cat'], 'MAQUINARIO'),
('MARCA', 'john deere', ARRAY['jd'], 'MAQUINARIO'),
('MARCA', 'massey ferguson', ARRAY['massey', 'mf'], 'MAQUINARIO'),
('MARCA', 'valtra', ARRAY[], 'MAQUINARIO'),
('MARCA', 'new holland', ARRAY['nh'], 'MAQUINARIO'),
('MARCA', 'case', ARRAY['case ih'], 'MAQUINARIO'),
('MARCA', 'jcb', ARRAY[], 'MAQUINARIO'),
-- Implementos/Carretas
('MARCA', 'randon', ARRAY[], 'CARRETA'),
('MARCA', 'facchini', ARRAY[], 'CARRETA'),
('MARCA', 'guerra', ARRAY[], 'CARRETA'),
('MARCA', 'librelato', ARRAY[], 'CARRETA'),
('MARCA', 'noma', ARRAY[], 'CARRETA'),
-- Onibus
('MARCA', 'marcopolo', ARRAY[], 'ONIBUS'),
('MARCA', 'caio', ARRAY['caio induscar'], 'ONIBUS'),
('MARCA', 'busscar', ARRAY[], 'ONIBUS'),
('MARCA', 'neobus', ARRAY[], 'ONIBUS');

-- ============================================================
-- CATEGORIA: MODELO_LEVE (carros de passeio e utilitarios)
-- ============================================================
INSERT INTO taxonomia_automotiva (categoria, termo, sinonimos, tag_gerada) VALUES
-- Volkswagen
('MODELO_LEVE', 'gol', ARRAY['gol g3', 'gol g4', 'gol g5', 'gol g6', 'gol trend'], 'VEICULO'),
('MODELO_LEVE', 'polo', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'virtus', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'jetta', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 't-cross', ARRAY['tcross'], 'VEICULO'),
('MODELO_LEVE', 'nivus', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'taos', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'tiguan', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'amarok', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'saveiro', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'voyage', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'fox', ARRAY['spacefox', 'crossfox'], 'VEICULO'),
('MODELO_LEVE', 'up', ARRAY['up!'], 'VEICULO'),
('MODELO_LEVE', 'kombi', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'fusca', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'parati', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'santana', ARRAY[], 'VEICULO'),
-- Chevrolet
('MODELO_LEVE', 'onix', ARRAY['onix plus', 'onix joy'], 'VEICULO'),
('MODELO_LEVE', 'cruze', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'tracker', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'equinox', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'trailblazer', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 's10', ARRAY['s-10'], 'VEICULO'),
('MODELO_LEVE', 'montana', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'spin', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'celta', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'corsa', ARRAY['corsa sedan', 'corsa hatch'], 'VEICULO'),
('MODELO_LEVE', 'prisma', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'cobalt', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'astra', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'vectra', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'omega', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'kadett', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'monza', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'chevette', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'meriva', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'zafira', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'agile', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'captiva', ARRAY[], 'VEICULO'),
-- Fiat
('MODELO_LEVE', 'strada', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'toro', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'argo', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'cronos', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'mobi', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'pulse', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'fastback', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'fiorino', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'ducato', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'uno', ARRAY['uno mille', 'uno way'], 'VEICULO'),
('MODELO_LEVE', 'palio', ARRAY['palio weekend', 'palio fire'], 'VEICULO'),
('MODELO_LEVE', 'siena', ARRAY['grand siena'], 'VEICULO'),
('MODELO_LEVE', 'punto', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'bravo', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'stilo', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'idea', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'doblo', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'linea', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'marea', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'tempra', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'tipo', ARRAY[], 'VEICULO'),
('MODELO_LEVE', '147', ARRAY['fiat 147'], 'VEICULO'),
-- Ford
('MODELO_LEVE', 'ranger', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'maverick', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'territory', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'bronco', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'mustang', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'transit', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'ka', ARRAY['ka+', 'ka sedan'], 'VEICULO'),
('MODELO_LEVE', 'fiesta', ARRAY['fiesta sedan', 'new fiesta'], 'VEICULO'),
('MODELO_LEVE', 'focus', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'ecosport', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'fusion', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'edge', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'escort', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'corcel', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'del rey', ARRAY['delrey'], 'VEICULO'),
('MODELO_LEVE', 'belina', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'pampa', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'f1000', ARRAY['f-1000'], 'VEICULO'),
('MODELO_LEVE', 'f250', ARRAY['f-250'], 'VEICULO'),
('MODELO_LEVE', 'courier', ARRAY[], 'VEICULO'),
-- Toyota
('MODELO_LEVE', 'hilux', ARRAY['hilux sw4'], 'VEICULO'),
('MODELO_LEVE', 'corolla', ARRAY['corolla cross'], 'VEICULO'),
('MODELO_LEVE', 'yaris', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'rav4', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'sw4', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'camry', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'etios', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'fielder', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'bandeirante', ARRAY[], 'VEICULO'),
-- Honda (carros)
('MODELO_LEVE', 'civic', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'city', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'hr-v', ARRAY['hrv'], 'VEICULO'),
('MODELO_LEVE', 'fit', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'wr-v', ARRAY['wrv'], 'VEICULO'),
('MODELO_LEVE', 'cr-v', ARRAY['crv'], 'VEICULO'),
('MODELO_LEVE', 'accord', ARRAY[], 'VEICULO'),
-- Hyundai
('MODELO_LEVE', 'hb20', ARRAY['hb20s', 'hb20x'], 'VEICULO'),
('MODELO_LEVE', 'creta', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'tucson', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'ix35', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'santa fe', ARRAY['santafe'], 'VEICULO'),
('MODELO_LEVE', 'azera', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'i30', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'hr', ARRAY['hyundai hr'], 'VEICULO'),
-- Renault
('MODELO_LEVE', 'kwid', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'sandero', ARRAY['sandero stepway'], 'VEICULO'),
('MODELO_LEVE', 'logan', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'duster', ARRAY['duster oroch'], 'VEICULO'),
('MODELO_LEVE', 'oroch', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'captur', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'master', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'clio', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'megane', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'scenic', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'symbol', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'kangoo', ARRAY[], 'VEICULO'),
-- Jeep
('MODELO_LEVE', 'renegade', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'compass', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'commander', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'wrangler', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'gladiator', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'cherokee', ARRAY['grand cherokee'], 'VEICULO'),
-- Nissan
('MODELO_LEVE', 'kicks', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'versa', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'sentra', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'frontier', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'march', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'livina', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'tiida', ARRAY[], 'VEICULO'),
-- Mitsubishi
('MODELO_LEVE', 'l200', ARRAY['l200 triton'], 'VEICULO'),
('MODELO_LEVE', 'triton', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'pajero', ARRAY['pajero sport', 'pajero full'], 'VEICULO'),
('MODELO_LEVE', 'outlander', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'asx', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'eclipse cross', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'lancer', ARRAY[], 'VEICULO'),
-- Citroen
('MODELO_LEVE', 'c3', ARRAY['c3 aircross'], 'VEICULO'),
('MODELO_LEVE', 'c4', ARRAY['c4 cactus', 'c4 lounge'], 'VEICULO'),
('MODELO_LEVE', 'aircross', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'jumpy', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'berlingo', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'xsara', ARRAY['xsara picasso'], 'VEICULO'),
-- Peugeot
('MODELO_LEVE', '208', ARRAY['peugeot 208'], 'VEICULO'),
('MODELO_LEVE', '2008', ARRAY['peugeot 2008'], 'VEICULO'),
('MODELO_LEVE', '3008', ARRAY['peugeot 3008'], 'VEICULO'),
('MODELO_LEVE', 'partner', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'boxer', ARRAY[], 'VEICULO'),
('MODELO_LEVE', 'expert', ARRAY[], 'VEICULO'),
('MODELO_LEVE', '206', ARRAY[], 'VEICULO'),
('MODELO_LEVE', '207', ARRAY[], 'VEICULO'),
('MODELO_LEVE', '307', ARRAY[], 'VEICULO'),
('MODELO_LEVE', '308', ARRAY[], 'VEICULO'),
('MODELO_LEVE', '408', ARRAY[], 'VEICULO');

-- ============================================================
-- CATEGORIA: MODELO_MOTO (motocicletas)
-- ============================================================
INSERT INTO taxonomia_automotiva (categoria, termo, sinonimos, tag_gerada) VALUES
-- Honda Motos
('MODELO_MOTO', 'cg', ARRAY['cg 125', 'cg 150', 'cg 160', 'cg titan', 'cg fan', 'cg start'], 'MOTO'),
('MODELO_MOTO', 'titan', ARRAY['titan 125', 'titan 150', 'titan 160'], 'MOTO'),
('MODELO_MOTO', 'fan', ARRAY['fan 125', 'fan 150', 'fan 160'], 'MOTO'),
('MODELO_MOTO', 'start', ARRAY['cg start'], 'MOTO'),
('MODELO_MOTO', 'cargo', ARRAY['cg cargo'], 'MOTO'),
('MODELO_MOTO', 'biz', ARRAY['biz 100', 'biz 110', 'biz 125'], 'MOTO'),
('MODELO_MOTO', 'nxr', ARRAY['nxr bros', 'nxr 125', 'nxr 150', 'nxr 160'], 'MOTO'),
('MODELO_MOTO', 'bros', ARRAY['bros 125', 'bros 150', 'bros 160'], 'MOTO'),
('MODELO_MOTO', 'xre', ARRAY['xre 190', 'xre 300'], 'MOTO'),
('MODELO_MOTO', 'cb', ARRAY['cb 250', 'cb 300', 'cb 500', 'cb 650', 'cb twister'], 'MOTO'),
('MODELO_MOTO', 'twister', ARRAY['cb twister', 'cbx twister'], 'MOTO'),
('MODELO_MOTO', 'hornet', ARRAY['cb hornet', 'cb 600 hornet'], 'MOTO'),
('MODELO_MOTO', 'pcx', ARRAY['pcx 150'], 'MOTO'),
('MODELO_MOTO', 'elite', ARRAY['elite 125'], 'MOTO'),
('MODELO_MOTO', 'pop', ARRAY['pop 100', 'pop 110'], 'MOTO'),
('MODELO_MOTO', 'lead', ARRAY['lead 110'], 'MOTO'),
('MODELO_MOTO', 'nc', ARRAY['nc 750'], 'MOTO'),
('MODELO_MOTO', 'africa twin', ARRAY['crf 1000', 'crf 1100'], 'MOTO'),
('MODELO_MOTO', 'cbr', ARRAY['cbr 250', 'cbr 500', 'cbr 600', 'cbr 1000'], 'MOTO'),
-- Yamaha
('MODELO_MOTO', 'ybr', ARRAY['ybr 125', 'ybr 150'], 'MOTO'),
('MODELO_MOTO', 'factor', ARRAY['factor 125', 'factor 150'], 'MOTO'),
('MODELO_MOTO', 'fazer', ARRAY['fazer 150', 'fazer 250', 'fz25'], 'MOTO'),
('MODELO_MOTO', 'lander', ARRAY['lander 250', 'xtz lander'], 'MOTO'),
('MODELO_MOTO', 'tenere', ARRAY['tenere 250', 'tenere 660', 'tenere 700'], 'MOTO'),
('MODELO_MOTO', 'crosser', ARRAY['crosser 150', 'xtz crosser'], 'MOTO'),
('MODELO_MOTO', 'nmax', ARRAY['nmax 160'], 'MOTO'),
('MODELO_MOTO', 'xmax', ARRAY['xmax 250'], 'MOTO'),
('MODELO_MOTO', 'neo', ARRAY['neo 125'], 'MOTO'),
('MODELO_MOTO', 'crypton', ARRAY['crypton 115'], 'MOTO'),
('MODELO_MOTO', 'mt', ARRAY['mt-03', 'mt-07', 'mt-09', 'mt 03', 'mt 07', 'mt 09'], 'MOTO'),
('MODELO_MOTO', 'r3', ARRAY['yzf r3'], 'MOTO'),
('MODELO_MOTO', 'r1', ARRAY['yzf r1'], 'MOTO'),
('MODELO_MOTO', 'xt', ARRAY['xt 660'], 'MOTO'),
('MODELO_MOTO', 'xtz', ARRAY['xtz 125', 'xtz 150', 'xtz 250'], 'MOTO'),
-- Suzuki
('MODELO_MOTO', 'intruder', ARRAY['intruder 125'], 'MOTO'),
('MODELO_MOTO', 'yes', ARRAY['yes 125'], 'MOTO'),
('MODELO_MOTO', 'gsx', ARRAY['gsx 750', 'gsx-s', 'gsxr', 'gsx-r'], 'MOTO'),
('MODELO_MOTO', 'v-strom', ARRAY['vstrom', 'v strom', 'dl 650', 'dl 1000'], 'MOTO'),
('MODELO_MOTO', 'burgman', ARRAY['burgman 125', 'burgman 400'], 'MOTO'),
('MODELO_MOTO', 'boulevard', ARRAY[], 'MOTO'),
-- BMW Motos
('MODELO_MOTO', 'g310', ARRAY['g 310 r', 'g 310 gs'], 'MOTO'),
('MODELO_MOTO', 'f850', ARRAY['f 850 gs'], 'MOTO'),
('MODELO_MOTO', 'r1250', ARRAY['r 1250 gs', 'r 1250 rt'], 'MOTO'),
('MODELO_MOTO', 's1000', ARRAY['s 1000 rr', 's 1000 xr'], 'MOTO'),
-- Kawasaki
('MODELO_MOTO', 'ninja', ARRAY['ninja 250', 'ninja 300', 'ninja 400', 'ninja 650', 'ninja zx'], 'MOTO'),
('MODELO_MOTO', 'z', ARRAY['z 400', 'z 650', 'z 900', 'z 1000'], 'MOTO'),
('MODELO_MOTO', 'versys', ARRAY['versys 650', 'versys 1000'], 'MOTO'),
('MODELO_MOTO', 'vulcan', ARRAY['vulcan 900'], 'MOTO'),
-- Triumph
('MODELO_MOTO', 'tiger', ARRAY['tiger 800', 'tiger 900', 'tiger 1200'], 'MOTO'),
('MODELO_MOTO', 'street triple', ARRAY[], 'MOTO'),
('MODELO_MOTO', 'bonneville', ARRAY[], 'MOTO'),
-- Dafra
('MODELO_MOTO', 'citycom', ARRAY['citycom 300'], 'MOTO'),
('MODELO_MOTO', 'next', ARRAY['next 250'], 'MOTO'),
('MODELO_MOTO', 'apache', ARRAY['apache 150'], 'MOTO'),
('MODELO_MOTO', 'kansas', ARRAY['kansas 150'], 'MOTO'),
('MODELO_MOTO', 'zig', ARRAY['zig 50'], 'MOTO'),
-- Shineray
('MODELO_MOTO', 'jet', ARRAY['jet 50'], 'MOTO'),
('MODELO_MOTO', 'phoenix', ARRAY['phoenix 50'], 'MOTO'),
('MODELO_MOTO', 'xy', ARRAY['xy 50', 'xy 150'], 'MOTO');

-- ============================================================
-- CATEGORIA: MODELO_PESADO (caminhoes e onibus)
-- ============================================================
INSERT INTO taxonomia_automotiva (categoria, termo, sinonimos, tag_gerada) VALUES
-- Mercedes-Benz Caminhoes
('MODELO_PESADO', 'atego', ARRAY['atego 1419', 'atego 1719', 'atego 2426'], 'CAMINHAO'),
('MODELO_PESADO', 'actros', ARRAY['actros 2546', 'actros 2651'], 'CAMINHAO'),
('MODELO_PESADO', 'axor', ARRAY['axor 2035', 'axor 2041', 'axor 2544'], 'CAMINHAO'),
('MODELO_PESADO', 'accelo', ARRAY['accelo 815', 'accelo 1016'], 'CAMINHAO'),
('MODELO_PESADO', '1620', ARRAY['mb 1620', 'mercedes 1620'], 'CAMINHAO'),
('MODELO_PESADO', '1113', ARRAY['mb 1113', 'mercedes 1113'], 'CAMINHAO'),
('MODELO_PESADO', '1313', ARRAY['mb 1313', 'mercedes 1313'], 'CAMINHAO'),
('MODELO_PESADO', '1513', ARRAY['mb 1513', 'mercedes 1513'], 'CAMINHAO'),
('MODELO_PESADO', '1935', ARRAY['mb 1935', 'mercedes 1935'], 'CAMINHAO'),
('MODELO_PESADO', 'of', ARRAY['of 1721', 'of 1519', 'mb of'], 'ONIBUS'),
('MODELO_PESADO', 'oh', ARRAY['oh 1621', 'oh 1628', 'mb oh'], 'ONIBUS'),
('MODELO_PESADO', 'o500', ARRAY['o 500', 'o500 m', 'o500 rs', 'mb o500'], 'ONIBUS'),
-- Scania
('MODELO_PESADO', 'r440', ARRAY['scania r440'], 'CAMINHAO'),
('MODELO_PESADO', 'r450', ARRAY['scania r450'], 'CAMINHAO'),
('MODELO_PESADO', 'g420', ARRAY['scania g420'], 'CAMINHAO'),
('MODELO_PESADO', 'p310', ARRAY['scania p310'], 'CAMINHAO'),
('MODELO_PESADO', '113', ARRAY['scania 113', 'scania r113'], 'CAMINHAO'),
('MODELO_PESADO', '112', ARRAY['scania 112', 'scania r112'], 'CAMINHAO'),
('MODELO_PESADO', '124', ARRAY['scania 124', 'scania r124'], 'CAMINHAO'),
('MODELO_PESADO', 'r500', ARRAY['scania r500'], 'CAMINHAO'),
('MODELO_PESADO', 's500', ARRAY['scania s500'], 'CAMINHAO'),
('MODELO_PESADO', 's540', ARRAY['scania s540'], 'CAMINHAO'),
-- Volvo
('MODELO_PESADO', 'fh', ARRAY['volvo fh', 'fh 12', 'fh 380', 'fh 420'], 'CAMINHAO'),
('MODELO_PESADO', 'fh460', ARRAY['volvo fh460', 'fh 460'], 'CAMINHAO'),
('MODELO_PESADO', 'fh540', ARRAY['volvo fh540', 'fh 540'], 'CAMINHAO'),
('MODELO_PESADO', 'fm', ARRAY['volvo fm', 'fm 370', 'fm 380'], 'CAMINHAO'),
('MODELO_PESADO', 'vm', ARRAY['volvo vm', 'vm 220', 'vm 270', 'vm 330'], 'CAMINHAO'),
('MODELO_PESADO', 'nh', ARRAY['volvo nh', 'nh 12'], 'CAMINHAO'),
('MODELO_PESADO', 'b270f', ARRAY['volvo b270f'], 'ONIBUS'),
('MODELO_PESADO', 'b340m', ARRAY['volvo b340m'], 'ONIBUS'),
-- VW Caminhoes
('MODELO_PESADO', 'constellation', ARRAY['vw constellation', 'constelation'], 'CAMINHAO'),
('MODELO_PESADO', 'delivery', ARRAY['vw delivery'], 'CAMINHAO'),
('MODELO_PESADO', 'meteor', ARRAY['vw meteor'], 'CAMINHAO'),
('MODELO_PESADO', 'worker', ARRAY['vw worker'], 'CAMINHAO'),
('MODELO_PESADO', 'titan', ARRAY['vw titan'], 'CAMINHAO'),
('MODELO_PESADO', '24.250', ARRAY['vw 24.250', '24250'], 'CAMINHAO'),
('MODELO_PESADO', '8.150', ARRAY['vw 8.150', '8150'], 'CAMINHAO'),
-- Iveco
('MODELO_PESADO', 'daily', ARRAY['iveco daily'], 'CAMINHAO'),
('MODELO_PESADO', 'tector', ARRAY['iveco tector'], 'CAMINHAO'),
('MODELO_PESADO', 'stralis', ARRAY['iveco stralis'], 'CAMINHAO'),
('MODELO_PESADO', 'hi-way', ARRAY['iveco hiway', 'hi way'], 'CAMINHAO'),
('MODELO_PESADO', 's-way', ARRAY['iveco sway', 's way'], 'CAMINHAO'),
('MODELO_PESADO', 'eurocargo', ARRAY['iveco eurocargo'], 'CAMINHAO'),
-- DAF
('MODELO_PESADO', 'xf', ARRAY['daf xf'], 'CAMINHAO'),
('MODELO_PESADO', 'cf', ARRAY['daf cf'], 'CAMINHAO'),
('MODELO_PESADO', 'xf105', ARRAY['daf xf105', 'xf 105'], 'CAMINHAO'),
-- Ford Caminhoes
('MODELO_PESADO', 'cargo', ARRAY['ford cargo'], 'CAMINHAO'),
('MODELO_PESADO', 'f4000', ARRAY['ford f4000', 'f-4000'], 'CAMINHAO'),
('MODELO_PESADO', 'f350', ARRAY['ford f350', 'f-350'], 'CAMINHAO'),
('MODELO_PESADO', 'f12000', ARRAY['ford f12000', 'f-12000'], 'CAMINHAO'),
('MODELO_PESADO', 'f14000', ARRAY['ford f14000', 'f-14000'], 'CAMINHAO'),
-- Agrale
('MODELO_PESADO', '8700', ARRAY['agrale 8700'], 'CAMINHAO'),
('MODELO_PESADO', '10000', ARRAY['agrale 10000'], 'CAMINHAO'),
('MODELO_PESADO', 'marrua', ARRAY['agrale marrua'], 'VEICULO'),
('MODELO_PESADO', 'volare', ARRAY['agrale volare'], 'ONIBUS');

-- ============================================================
-- CATEGORIA: IMPLEMENTO (carretas e reboques)
-- ============================================================
INSERT INTO taxonomia_automotiva (categoria, termo, sinonimos, tag_gerada) VALUES
('IMPLEMENTO', 'graneleiro', ARRAY['graneleira', 'carreta graneleira'], 'CARRETA'),
('IMPLEMENTO', 'sider', ARRAY['bau sider', 'carreta sider'], 'CARRETA'),
('IMPLEMENTO', 'bau', ARRAY['carreta bau', 'bau refrigerado', 'bau seco'], 'CARRETA'),
('IMPLEMENTO', 'tanque', ARRAY['carreta tanque', 'tanque combustivel'], 'CARRETA'),
('IMPLEMENTO', 'prancha', ARRAY['carreta prancha', 'prancha rebaixada'], 'CARRETA'),
('IMPLEMENTO', 'cegonha', ARRAY['carreta cegonha', 'cegonheira'], 'CARRETA'),
('IMPLEMENTO', 'bitrem', ARRAY['bi-trem', 'bitren'], 'CARRETA'),
('IMPLEMENTO', 'rodotrem', ARRAY['rodo-trem', 'rodo trem'], 'CARRETA'),
('IMPLEMENTO', 'cacamba', ARRAY['carreta cacamba', 'basculante'], 'CARRETA'),
('IMPLEMENTO', 'dolly', ARRAY['carreta dolly'], 'CARRETA'),
('IMPLEMENTO', 'container', ARRAY['carreta container', 'porta-container'], 'CARRETA');

-- ============================================================
-- CATEGORIA: MAQUINA (tratores e equipamentos)
-- ============================================================
INSERT INTO taxonomia_automotiva (categoria, termo, sinonimos, tag_gerada) VALUES
-- Caterpillar
('MAQUINA', '416', ARRAY['cat 416', 'caterpillar 416'], 'MAQUINARIO'),
('MAQUINA', '320', ARRAY['cat 320', 'caterpillar 320'], 'MAQUINARIO'),
('MAQUINA', '924', ARRAY['cat 924', 'caterpillar 924'], 'MAQUINARIO'),
('MAQUINA', '120k', ARRAY['cat 120k', 'caterpillar 120k'], 'MAQUINARIO'),
('MAQUINA', 'd6', ARRAY['cat d6', 'caterpillar d6'], 'MAQUINARIO'),
-- John Deere
('MAQUINA', '5078', ARRAY['jd 5078', 'john deere 5078'], 'MAQUINARIO'),
('MAQUINA', '6110', ARRAY['jd 6110', 'john deere 6110'], 'MAQUINARIO'),
('MAQUINA', '7200', ARRAY['jd 7200', 'john deere 7200'], 'MAQUINARIO'),
('MAQUINA', 's430', ARRAY['jd s430', 'john deere s430'], 'MAQUINARIO'),
('MAQUINA', 'colheitadeira', ARRAY['colheitadeiras', 'colhedeira'], 'MAQUINARIO'),
('MAQUINA', 'pulverizador', ARRAY['pulverizadores', 'pulverizador autopropelido'], 'MAQUINARIO'),
-- Massey Ferguson
('MAQUINA', 'mf275', ARRAY['massey 275', 'mf 275'], 'MAQUINARIO'),
('MAQUINA', 'mf290', ARRAY['massey 290', 'mf 290'], 'MAQUINARIO'),
('MAQUINA', 'mf4275', ARRAY['massey 4275', 'mf 4275'], 'MAQUINARIO'),
('MAQUINA', 'mf7180', ARRAY['massey 7180', 'mf 7180'], 'MAQUINARIO'),
-- Valtra
('MAQUINA', 'bh190', ARRAY['valtra bh190', 'bh 190'], 'MAQUINARIO'),
('MAQUINA', 'a750', ARRAY['valtra a750', 'a 750'], 'MAQUINARIO'),
('MAQUINA', 'bm100', ARRAY['valtra bm100', 'bm 100'], 'MAQUINARIO'),
('MAQUINA', 'bm125', ARRAY['valtra bm125', 'bm 125'], 'MAQUINARIO'),
-- New Holland
('MAQUINA', 'tl75', ARRAY['nh tl75', 'new holland tl75'], 'MAQUINARIO'),
('MAQUINA', 'ts6020', ARRAY['nh ts6020', 'new holland ts6020'], 'MAQUINARIO'),
('MAQUINA', 'tc57', ARRAY['nh tc57', 'new holland tc57'], 'MAQUINARIO'),
('MAQUINA', 'tc59', ARRAY['nh tc59', 'new holland tc59'], 'MAQUINARIO'),
-- Case
('MAQUINA', '580n', ARRAY['case 580n', '580 n'], 'MAQUINARIO'),
('MAQUINA', 'puma', ARRAY['case puma'], 'MAQUINARIO'),
('MAQUINA', 'magnum', ARRAY['case magnum'], 'MAQUINARIO'),
-- JCB
('MAQUINA', '3cx', ARRAY['jcb 3cx'], 'MAQUINARIO'),
('MAQUINA', '4cx', ARRAY['jcb 4cx'], 'MAQUINARIO');

-- ============================================================
-- VERIFICACAO FINAL
-- ============================================================
SELECT
    categoria,
    COUNT(*) as total_termos
FROM taxonomia_automotiva
WHERE ativo = TRUE
GROUP BY categoria
ORDER BY total_termos DESC;
