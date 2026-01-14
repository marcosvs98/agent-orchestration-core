import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from adapters.observability.logging import get_logger
from infra.database import create_db, get_db
from resources.scripts.seeds.seed_tenant import seed_tenant_data
from resources.scripts.seeds.seed_plan_type import seed_plan_types
from resources.scripts.seeds.seed_account import seed_account
from resources.scripts.seeds.seed_specialist_config import seed_specialist_configs
from resources.scripts.seeds.seed_specialist_intent_examples import (
    seed_specialist_intent_examples,
)
from resources.scripts.seeds.seed_specialist_multi_intent_groups import (
    seed_specialist_multi_intent_groups,
)
from resources.scripts.seeds.seed_specialist_edge_cases import (
    seed_specialist_edge_cases,
)
from resources.scripts.seeds.seed_persona_specialist import (
    seed_persona_specialists_data,
)
from resources.scripts.seeds.seed_specialist_intents import (
    seed_specialist_intents_complete,
)
from resources.scripts.seeds.seed_rag_embedding_version import seed_rag_embedding_version
from resources.scripts.seeds.seed_rag_documents import seed_rag_documents
from resources.scripts.seeds.seed_rag_faqs import seed_rag_faqs
from resources.scripts.seeds.seed_specialist_tools import seed_specialist_tools_complete
from resources.scripts.seeds.seed_intent_slots import seed_intent_slots
from resources.scripts.seeds.seed_onboarding_steps import seed_onboarding_steps
from resources.scripts.seeds.seed_specialist_intent_prompt import seed_intent_prompt
from resources.scripts.seeds.seed_slot_filling_templates import seed_slot_filling_templates
from resources.scripts.seeds.seed_persona_system_prompts import seed_persona_system_prompts
from resources.scripts.seeds.seed_data import (
    seed_policy_data,
    seed_persona_data,
)

logger = get_logger()


async def apply_fk_constraints():
    import sqlalchemy as sa

    async with get_db() as db:
        try:
            logger.info("Linking Plans to PlanTypes")
            result = await db.execute(
                sa.text("""
                UPDATE plans p
                SET plan_type_id = (
                    SELECT pt.id
                    FROM plan_types pt
                    WHERE pt.plan_key = LOWER(p.plan_type::text)
                    LIMIT 1
                )
                WHERE p.plan_type_id IS NULL
            """)
            )
            logger.info("Plans linked", plans_count=result.rowcount)

            logger.info("Updating Plans persona_id from PlanType")
            result = await db.execute(
                sa.text("""
                UPDATE plans p
                SET persona_id = (
                    SELECT pt.default_persona_id
                    FROM plan_types pt
                    WHERE pt.id = p.plan_type_id
                )
                WHERE p.persona_id IS NULL OR p.persona_id = ''
            """)
            )
            logger.info("Plans persona_id updated", plans_count=result.rowcount)

            await db.commit()
            logger.info("FK constraints applied")

        except Exception as e:
            await db.rollback()
            logger.warning("Warning applying FK constraints", error=str(e))


async def verify_database_structure():
    import sqlalchemy as sa
    from sqlalchemy import func, and_
    from infra.database.models.specialist import SpecialistIntent

    async with get_db() as db:
        try:
            result = await db.execute(
                sa.text("""
                SELECT COUNT(*)
                FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_plans_plan_type_id'
            """)
            )
            fk_exists = result.scalar() > 0

            result = await db.execute(
                sa.text("""
                SELECT COUNT(*)
                FROM plans
                WHERE plan_type_id IS NOT NULL
            """)
            )
            plans_linked = result.scalar()

            result = await db.execute(
                sa.text("""
                SELECT tenant_id, intent_name, intent_version, COUNT(*) as count
                FROM specialist_intents
                GROUP BY tenant_id, intent_name, intent_version
                HAVING COUNT(*) > 1
            """)
            )
            duplicates = result.fetchall()

            result = await db.execute(
                sa.select(func.count(SpecialistIntent.id)).where(
                    and_(
                        SpecialistIntent.tenant_id == "default",
                        SpecialistIntent.intent_name == "update_contact_name",
                    )
                )
            )
            has_update_contact = result.scalar() > 0

            result = await db.execute(
                sa.select(func.count(SpecialistIntent.id)).where(
                    SpecialistIntent.tenant_id == "default"
                )
            )
            total_intents = result.scalar()

            logger.info("Database integrity verification")
            logger.info("FK constraint check", fk_exists=fk_exists, plans_linked=plans_linked, total_intents=total_intents)
            logger.info("Intent update_contact_name check", found=has_update_contact)
            logger.info("Duplicate intents check", duplicates_count=len(duplicates), has_duplicates=bool(duplicates))

            if duplicates:
                logger.error("Duplicate intents found")
                for dup in duplicates:
                    logger.error(
                        "Duplicate intent details",
                        tenant_id=dup.tenant_id,
                        intent_name=dup.intent_name,
                        intent_version=dup.intent_version,
                        count=dup.count,
                    )
                raise RuntimeError(
                    f"Seeds created {len(duplicates)} duplicate intents"
                )

        except RuntimeError:
            raise
        except Exception as e:
            logger.warning("Error during verification", error=str(e))


async def main(rag_enabled: bool = False): # Todo: lembrar de desativar se for executar o seed
    try:
        logger.info("Database initialization started", version="2.0", features="Multi-Tenancy, PlanTypes, Strong FKs")

        logger.info("Creating database tables")
        await create_db()
        logger.info("Database tables created successfully")

        logger.info("Seeding initial data")

        logger.info("Seeding tenants")
        await seed_tenant_data()

        logger.info("Seeding plan types")
        await seed_plan_types()

        logger.info("Seeding account")
        await seed_account()

        logger.info("Seeding policy rules")
        await seed_policy_data()

        logger.info("Seeding specialist configs")
        await seed_specialist_configs()

        logger.info("Seeding specialist intents", total_intents=31)
        await seed_specialist_intents_complete()

        logger.info("Seeding intent prompts")
        await seed_intent_prompt()

        logger.info("Seeding slot filling templates")
        await seed_slot_filling_templates()

        logger.info("Seeding intent examples")
        await seed_specialist_intent_examples()

        if rag_enabled == True:
            logger.info("Seeding RAG embedding version")
            await seed_rag_embedding_version()
    
            logger.info("Seeding RAG documents from intent examples")
            await seed_rag_documents()
    
            logger.info("Seeding RAG edge cases")
            from resources.scripts.seeds.seed_rag_edge_cases import seed_rag_edge_cases
            await seed_rag_edge_cases()
    
            logger.info("Seeding RAG multi-intent groups")
            from resources.scripts.seeds.seed_rag_multi_intents import seed_rag_multi_intents
            await seed_rag_multi_intents()
    
            logger.info("Seeding RAG FAQs")
            await seed_rag_faqs()
    
            logger.info("Seeding RAG slot examples")
            from resources.scripts.seeds.seed_rag_slot_examples import seed_rag_slot_examples
            await seed_rag_slot_examples()
    
            logger.info("Seeding RAG category patterns")
            from resources.scripts.seeds.seed_rag_category_patterns import seed_rag_category_patterns
            await seed_rag_category_patterns()
    
            logger.info("Seeding RAG negative examples")
            from resources.scripts.seeds.seed_rag_negative_examples import seed_rag_negative_examples
            await seed_rag_negative_examples()

        logger.info("Seeding multi-intent groups")
        await seed_specialist_multi_intent_groups()

        logger.info("Seeding edge cases")
        await seed_specialist_edge_cases()

        logger.info("Seeding specialist tools", total_tools=20)
        await seed_specialist_tools_complete()

        logger.info("Seeding intent slots")
        async with get_db() as db:
            await seed_intent_slots(db)

        logger.info("Seeding onboarding steps")
        await seed_onboarding_steps()

        logger.info("Seeding persona configs")
        await seed_persona_data()

        logger.info("Seeding persona system prompts")
        await seed_persona_system_prompts()

        logger.info("Seeding persona specialist mapping")
        await seed_persona_specialists_data()

        logger.info("Applying FK constraints and links")
        await apply_fk_constraints()

        logger.info("Verifying database structure")
        await verify_database_structure()

        logger.info("Database initialization completed successfully")
        logger.info("Implemented structure", tenant_name="Assistente de Bolso", plan_types=4, specialist_intents=31, specialist_tools=20)
        logger.info("Available intents", total=31, includes_update_contact_name=True)

    except Exception as e:
        logger.error("Error during initialization", error=str(e))
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
