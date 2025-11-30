"""
Seed script for fiscal_regulations table - LISR Article 34 (Depreciation Rates)

This script:
1. Loads LISR Article 34 provisions (depreciation rates for fixed assets)
2. Generates embeddings using sentence-transformers
3. Inserts into fiscal_regulations table with structured data

Run with:
    python scripts/seed_fiscal_regulations.py

Author: System
Date: 2025-11-28
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import psycopg2
from psycopg2.extras import execute_values
from sentence_transformers import SentenceTransformer
import json
from datetime import date
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# LISR Article 34 - Depreciation Rates
# Source: https://www.diputados.gob.mx/LeyesBiblio/pdf/LISR.pdf
# Last reform: DOF 12-11-2023

ARTICLE_34_PROVISIONS = [
    {
        "law_code": "LISR",
        "article_number": "34",
        "section": "Fracción II",
        "title": "Depreciación de bombas de suministro de combustible",
        "content": "Tratándose de bombas de suministro de combustible a depósitos de distribución en gasolineras y carburación, así como de tanques de depósito y demás equipos utilizados en la actividad de autotransporte, 6%.",
        "regulation_type": "depreciation",
        "asset_categories": ["equipo_especial", "tanques", "gasolineras"],
        "keywords": ["bombas", "combustible", "gasolineras", "autotransporte", "6%", "6 por ciento", "tanques"],
        "structured_data": {
            "depreciation_rate_annual": 6.0,
            "depreciation_years": 16.67,
            "depreciation_months": 200,
            "asset_type": "bombas_combustible",
            "applies_to": ["Bombas de gasolinera", "Tanques de combustible", "Equipo de autotransporte"],
            "common_sat_codes": []
        },
        "effective_date": "2014-01-01",
        "dof_publication_date": "2013-12-11"
    },
    {
        "law_code": "LISR",
        "article_number": "34",
        "section": "Fracción III",
        "title": "Depreciación de equipo de comunicación telefónica",
        "content": "Tratándose de comunicaciones telefónicas, 8%.",
        "regulation_type": "depreciation",
        "asset_categories": ["equipo_comunicacion", "telecomunicaciones"],
        "keywords": ["comunicaciones", "telefónicas", "telefonía", "8%", "8 por ciento", "teléfono"],
        "structured_data": {
            "depreciation_rate_annual": 8.0,
            "depreciation_years": 12.5,
            "depreciation_months": 150,
            "asset_type": "equipo_telefonia",
            "applies_to": ["Central telefónica", "Sistema VoIP", "Infraestructura telecomunicaciones"],
            "common_sat_codes": ["43222600"]
        },
        "effective_date": "2014-01-01",
        "dof_publication_date": "2013-12-11"
    },
    {
        "law_code": "LISR",
        "article_number": "34",
        "section": "Fracción IV",
        "title": "Depreciación de equipo de comunicación satelital",
        "content": "Tratándose de comunicaciones satelitales, 9%.",
        "regulation_type": "depreciation",
        "asset_categories": ["equipo_comunicacion", "satelites"],
        "keywords": ["satélite", "satelital", "comunicaciones", "9%", "9 por ciento", "antenas"],
        "structured_data": {
            "depreciation_rate_annual": 9.0,
            "depreciation_years": 11.11,
            "depreciation_months": 133,
            "asset_type": "equipo_satelital",
            "applies_to": ["Antenas satelitales", "Equipo de transmisión satelital"],
            "common_sat_codes": []
        },
        "effective_date": "2014-01-01",
        "dof_publication_date": "2013-12-11"
    },
    {
        "law_code": "LISR",
        "article_number": "34",
        "section": "Fracción V",
        "title": "Depreciación de equipo de cómputo electrónico",
        "content": "Tratándose de equipo de cómputo electrónico de procesamiento de datos y manufactura, 30%.",
        "regulation_type": "depreciation",
        "asset_categories": ["equipo_computo", "tecnologia", "computadoras"],
        "keywords": ["cómputo", "computadora", "laptop", "servidor", "procesamiento", "datos", "30%", "30 por ciento", "pc", "notebook"],
        "structured_data": {
            "depreciation_rate_annual": 30.0,
            "depreciation_years": 3.33,
            "depreciation_months": 40,
            "asset_type": "equipo_computo",
            "applies_to": [
                "Computadoras de escritorio",
                "Laptops y notebooks",
                "Servidores",
                "Equipo de procesamiento de datos",
                "Equipo de manufactura electrónico",
                "Tablets corporativas"
            ],
            "common_sat_codes": ["43211500", "43211507", "43211509", "43211511"]
        },
        "effective_date": "2014-01-01",
        "dof_publication_date": "2013-12-11"
    },
    {
        "law_code": "LISR",
        "article_number": "34",
        "section": "Fracción VI",
        "title": "Depreciación de mobiliario y equipo de oficina",
        "content": "Tratándose de mobiliario y equipo de oficina, 10%.",
        "regulation_type": "depreciation",
        "asset_categories": ["mobiliario", "equipo_oficina"],
        "keywords": ["mobiliario", "muebles", "escritorio", "silla", "oficina", "10%", "10 por ciento", "archivero", "mesa"],
        "structured_data": {
            "depreciation_rate_annual": 10.0,
            "depreciation_years": 10.0,
            "depreciation_months": 120,
            "asset_type": "mobiliario",
            "applies_to": [
                "Escritorios",
                "Sillas ejecutivas y ergonómicas",
                "Archiveros y gabinetes",
                "Libreros",
                "Mesas de juntas",
                "Estantes",
                "Recepción"
            ],
            "common_sat_codes": ["56101500", "56101600", "56101700"]
        },
        "effective_date": "2014-01-01",
        "dof_publication_date": "2013-12-11"
    },
    {
        "law_code": "LISR",
        "article_number": "34",
        "section": "Fracción VII",
        "title": "Depreciación de dados, troqueles, moldes y matrices",
        "content": "Tratándose de dados, troqueles, moldes, matrices y herramental, 35%.",
        "regulation_type": "depreciation",
        "asset_categories": ["herramental", "moldes", "manufactura"],
        "keywords": ["dados", "troqueles", "moldes", "matrices", "herramental", "35%", "35 por ciento"],
        "structured_data": {
            "depreciation_rate_annual": 35.0,
            "depreciation_years": 2.86,
            "depreciation_months": 34,
            "asset_type": "herramental",
            "applies_to": ["Dados industriales", "Troqueles", "Moldes de inyección", "Matrices", "Herramental industrial"],
            "common_sat_codes": []
        },
        "effective_date": "2014-01-01",
        "dof_publication_date": "2013-12-11"
    },
    {
        "law_code": "LISR",
        "article_number": "34",
        "section": "Fracción VIII",
        "title": "Depreciación de vehículos de transporte",
        "content": "Tratándose de automóviles, autobuses, camiones de carga, tractocamiones, montacargas y remolques, 25%.",
        "regulation_type": "depreciation",
        "asset_categories": ["vehiculos", "autotransporte"],
        "keywords": ["automóvil", "auto", "camioneta", "camión", "vehículo", "autobús", "tractocamión", "montacargas", "25%", "25 por ciento", "transporte"],
        "structured_data": {
            "depreciation_rate_annual": 25.0,
            "depreciation_years": 4.0,
            "depreciation_months": 48,
            "asset_type": "vehiculos",
            "applies_to": [
                "Automóviles",
                "Camionetas pickup",
                "Autobuses",
                "Camiones de carga",
                "Tractocamiones",
                "Montacargas",
                "Remolques"
            ],
            "common_sat_codes": ["25101500", "25101600", "25101700", "25101800"],
            "special_rules": "Límite de deducción de $175,000 para automóviles según Art. 36 LISR"
        },
        "effective_date": "2014-01-01",
        "dof_publication_date": "2013-12-11"
    },
    {
        "law_code": "LISR",
        "article_number": "34",
        "section": "Fracción IX",
        "title": "Depreciación de aviones agrícolas",
        "content": "Tratándose de aviones dedicados a la aerofumigación agrícola, 25%.",
        "regulation_type": "depreciation",
        "asset_categories": ["aviones", "agricola"],
        "keywords": ["avión", "aviones", "aerofumigación", "agrícola", "25%", "25 por ciento"],
        "structured_data": {
            "depreciation_rate_annual": 25.0,
            "depreciation_years": 4.0,
            "depreciation_months": 48,
            "asset_type": "aviones_agricolas",
            "applies_to": ["Aviones de aerofumigación agrícola"],
            "common_sat_codes": []
        },
        "effective_date": "2014-01-01",
        "dof_publication_date": "2013-12-11"
    },
    {
        "law_code": "LISR",
        "article_number": "34",
        "section": "Fracción X",
        "title": "Depreciación de aviones en general",
        "content": "Tratándose de aviones distintos de los señalados en la fracción anterior, 10%.",
        "regulation_type": "depreciation",
        "asset_categories": ["aviones", "transporte_aereo"],
        "keywords": ["avión", "aviones", "aeronave", "10%", "10 por ciento", "helicóptero"],
        "structured_data": {
            "depreciation_rate_annual": 10.0,
            "depreciation_years": 10.0,
            "depreciation_months": 120,
            "asset_type": "aviones_generales",
            "applies_to": ["Aviones comerciales", "Aviones ejecutivos", "Helicópteros"],
            "common_sat_codes": []
        },
        "effective_date": "2014-01-01",
        "dof_publication_date": "2013-12-11"
    },
    {
        "law_code": "LISR",
        "article_number": "34",
        "section": "Fracción XI",
        "title": "Depreciación de equipo ferroviario",
        "content": "Tratándose de equipo de ferrocarril, 5%.",
        "regulation_type": "depreciation",
        "asset_categories": ["ferrocarril", "transporte"],
        "keywords": ["ferrocarril", "locomotora", "vagón", "5%", "5 por ciento", "tren"],
        "structured_data": {
            "depreciation_rate_annual": 5.0,
            "depreciation_years": 20.0,
            "depreciation_months": 240,
            "asset_type": "equipo_ferroviario",
            "applies_to": ["Locomotoras", "Vagones de ferrocarril", "Rieles"],
            "common_sat_codes": []
        },
        "effective_date": "2014-01-01",
        "dof_publication_date": "2013-12-11"
    },
    {
        "law_code": "LISR",
        "article_number": "34",
        "section": "Fracción XII",
        "title": "Depreciación de embarcaciones",
        "content": "Tratándose de embarcaciones, 6%.",
        "regulation_type": "depreciation",
        "asset_categories": ["embarcaciones", "maritimo"],
        "keywords": ["embarcación", "barco", "lancha", "navío", "marítimo", "6%", "6 por ciento"],
        "structured_data": {
            "depreciation_rate_annual": 6.0,
            "depreciation_years": 16.67,
            "depreciation_months": 200,
            "asset_type": "embarcaciones",
            "applies_to": ["Barcos", "Lanchas", "Embarcaciones comerciales"],
            "common_sat_codes": []
        },
        "effective_date": "2014-01-01",
        "dof_publication_date": "2013-12-11"
    },
    {
        "law_code": "LISR",
        "article_number": "34",
        "section": "Fracción XIII",
        "title": "Depreciación de maquinaria y equipo en general",
        "content": "Tratándose de maquinaria y equipo distintos de los señalados en las fracciones anteriores, 10%.",
        "regulation_type": "depreciation",
        "asset_categories": ["maquinaria", "equipo_general"],
        "keywords": ["maquinaria", "equipo", "industrial", "10%", "10 por ciento", "general"],
        "structured_data": {
            "depreciation_rate_annual": 10.0,
            "depreciation_years": 10.0,
            "depreciation_months": 120,
            "asset_type": "maquinaria_general",
            "applies_to": [
                "Maquinaria industrial",
                "Equipo de producción",
                "Equipo de manufactura",
                "Cualquier maquinaria no especificada en fracciones anteriores"
            ],
            "common_sat_codes": [],
            "is_default": True
        },
        "effective_date": "2014-01-01",
        "dof_publication_date": "2013-12-11"
    }
]


def normalize_text(text: str) -> str:
    """Normalize text: lowercase, remove accents"""
    import unicodedata
    # Remove accents
    text = ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )
    return text.lower()


def seed_fiscal_regulations():
    """Seed fiscal_regulations table with LISR Article 34 provisions"""

    logger.info("🚀 Starting fiscal regulations seed process...")

    # 1. Initialize embeddings model
    logger.info("Loading sentence-transformers model...")
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    logger.info("✅ Model loaded")

    # 2. Connect to PostgreSQL
    from core.shared.db_config import POSTGRES_CONFIG

    logger.info(f"Connecting to PostgreSQL at {POSTGRES_CONFIG['host']}...")
    conn = psycopg2.connect(**POSTGRES_CONFIG)
    cursor = conn.cursor()
    logger.info("✅ Connected to database")

    # 3. Clear existing depreciation regulations (for re-seeding)
    logger.info("Clearing existing depreciation regulations...")
    cursor.execute("""
        DELETE FROM fiscal_regulations
        WHERE regulation_type = 'depreciation'
          AND law_code = 'LISR'
          AND article_number = '34'
    """)
    deleted_count = cursor.rowcount
    logger.info(f"✅ Deleted {deleted_count} existing regulations")

    # 4. Prepare data for insertion
    logger.info(f"Processing {len(ARTICLE_34_PROVISIONS)} Article 34 provisions...")

    rows_to_insert = []

    for i, provision in enumerate(ARTICLE_34_PROVISIONS, 1):
        logger.info(f"  [{i}/{len(ARTICLE_34_PROVISIONS)}] Processing {provision['section']}...")

        # Generate embedding
        content_text = provision['content']
        embedding = model.encode(content_text)

        # Normalize content
        content_normalized = normalize_text(content_text)

        # Prepare row
        row = (
            provision['law_code'],
            provision['article_number'],
            provision['section'],
            provision['title'],
            provision['content'],
            content_normalized,
            embedding.tolist(),  # Convert numpy array to list
            provision['regulation_type'],
            provision['asset_categories'],
            provision['keywords'],
            json.dumps(provision['structured_data']),
            provision['effective_date'],
            None,  # superseded_date
            'active',
            'https://www.diputados.gob.mx/LeyesBiblio/pdf/LISR.pdf',
            provision.get('dof_publication_date')
        )

        rows_to_insert.append(row)

    # 5. Bulk insert
    logger.info(f"Inserting {len(rows_to_insert)} regulations into database...")

    insert_query = """
        INSERT INTO fiscal_regulations (
            law_code, article_number, section, title,
            content, content_normalized, content_embedding,
            regulation_type, asset_categories, keywords,
            structured_data, effective_date, superseded_date, status,
            source_url, dof_publication_date
        ) VALUES %s
    """

    execute_values(cursor, insert_query, rows_to_insert)
    conn.commit()

    logger.info(f"✅ Successfully inserted {len(rows_to_insert)} fiscal regulations")

    # 6. Verify insertion
    cursor.execute("""
        SELECT COUNT(*) FROM fiscal_regulations
        WHERE regulation_type = 'depreciation'
          AND law_code = 'LISR'
          AND article_number = '34'
    """)
    count = cursor.fetchone()[0]
    logger.info(f"✅ Verification: {count} regulations in database")

    # 7. Test semantic search
    logger.info("\n🧪 Testing semantic search...")
    test_queries = [
        "laptop dell computadora",
        "escritorio silla muebles oficina",
        "camioneta nissan vehículo"
    ]

    for query in test_queries:
        query_embedding = model.encode(query)
        cursor.execute("""
            SELECT
                article_number,
                section,
                title,
                structured_data->>'depreciation_rate_annual' as rate,
                1 - (content_embedding <=> %s::vector) as similarity
            FROM fiscal_regulations
            WHERE regulation_type = 'depreciation'
            ORDER BY content_embedding <=> %s::vector
            LIMIT 1
        """, (query_embedding.tolist(), query_embedding.tolist()))

        result = cursor.fetchone()
        if result:
            article, section, title, rate, similarity = result
            logger.info(
                f"  Query: '{query}'\n"
                f"  → Match: Art. {article} {section} - {rate}% (similarity: {similarity:.2%})"
            )

    # Cleanup
    cursor.close()
    conn.close()

    logger.info("\n✅ Fiscal regulations seed completed successfully!")


if __name__ == "__main__":
    seed_fiscal_regulations()
