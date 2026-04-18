from bot.ai_client import CheckResult


CORRECT_TEMPLATE = "✅ Zo'r! To'g'ri gap tuzibsiz. 👏"

ERROR_TEMPLATE = (
    "📝 Yaxshi urinish!\n\n"
    "✅ To'g'ri varianti: \"{corrected}\"\n\n"
    "💡 Tushuntirish: {explanation_uz}"
)


def format_reply(result: CheckResult) -> str:
    if result.is_correct:
        return CORRECT_TEMPLATE
    return ERROR_TEMPLATE.format(
        corrected=result.corrected,
        explanation_uz=result.explanation_uz,
    )
