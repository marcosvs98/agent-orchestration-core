import time
from openai import AsyncOpenAI
import settings
import asyncio


async def main():
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    models = [
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4.1-nano",
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-5",
        "gpt-5-mini",
        "gpt-5-nano",
        "o3-mini",
    ]

    base_payload = {
        "input": [
            {
                "role": "system",
                "content": "Você é um assistente financeiro especializado em finanças pessoais via WhatsApp. Antes de executar qualquer ação ou gerar resposta, planeje e valide internamente de forma estruturada.\n\nIntegridade de dados e risco\n   Baseie-se exclusivamente em dados fornecidos na conversa, histórico relevante e informações explicitamente confirmadas.\n   Nunca assuma valores ausentes nem gere suposições.\n   Se faltar dado obrigatório, declare objetivamente que não está disponível.\n   Se forem dados não críticos, prossiga com o que estiver disponível.\n\nRegras operacionais:\n* Idioma obrigatório: pt_BR.\n* Respostas concisas (2–3 frases).\n* Linguagem assertiva: “Pronto”, “Registrado”, “Atualizado”.\n* Tom profissional, claro e objetivo.\n# Emojis permitidos: 💚, 💰, 💳, 💸, 💵, 💶, 💷, 💴, 💵, 💶, 💷, 💴.",
            },
            {
                "role": "system",
                "content": "# Task\nIf tool_response is empty or absent: the user asked an informative question (e.g. how to do something). Answer using the retrieved context and user_input; be short and helpful.\nYou can use context from the previous conversation to complete slots.\n\n# Intent\nconversation\n\n\n# Output Guidelines\n- When tool_response is empty: answer the user question using the provided context; be concise.\n- Do not mention status codes, endpoints, requests, or payloads.",
            },
            {"role": "user", "content": "Ola quem é você?"},
        ],
        "temperature": 0.3,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "_responsecomposer_output",
                "schema": {
                    "type": "object",
                    "required": ["system_output", "operations_summary", "turn_status"],
                    "properties": {
                        "turn_status": {
                            "enum": [
                                "completed",
                                "partial_success",
                                "clarification_required",
                                "escalated",
                                "failed",
                            ],
                            "type": "string",
                        },
                        "system_output": {"type": "string"},
                        "operations_summary": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["operation_id", "status"],
                                "properties": {
                                    "status": {"type": "string"},
                                    "operation_id": {"type": "string"},
                                },
                                "additionalProperties": False,
                            },
                        },
                    },
                    "additionalProperties": False,
                },
            }
        },
        "max_output_tokens": 185,
        "user": "marcosteste",
        "previous_response_id": "resp_0fe3d8718a9dac5c0069aafa1a10808194a8ec688000a7c4ad",
    }

    results = []

    for model in models:
        payload = dict(base_payload)
        payload["model"] = model

        if model.startswith("o") or model.startswith("gpt-5"):
            payload.pop("temperature", None)
            payload.pop("top_p", None)

        try:
            start = time.perf_counter()

            response = await client.responses.create(
                **payload,
                service_tier="priority",
            )
            latency_ms = (time.perf_counter() - start) * 1000

            usage = getattr(response, "usage", None)

            input_tokens = usage.input_tokens if usage else 0
            output_tokens = usage.output_tokens if usage else 0
            total_tokens = usage.total_tokens if usage else 0

            print(
                f"{model} | latency={latency_ms:.2f}ms | "
                f"input={input_tokens} output={output_tokens} total={total_tokens}"
            )

            results.append(
                {
                    "model": model,
                    "latency_ms": round(latency_ms, 2),
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens,
                    "response": response.output,
                }
            )

        except Exception as e:
            print(f"{model} | ERROR: {e}")

    print("\nRESULTADOS FINAIS\n")

    for r in sorted(results, key=lambda x: x["latency_ms"]):
        print(r)


if __name__ == "__main__":
    asyncio.run(main())