import asyncio
import logging
from pydantic import BaseModel, Field
from openai import AsyncOpenAI


log = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "google/gemini-3.1-flash-lite"

# OpenRouter pricing for Gemini 3.1 Flash Lite, USD per 1M tokens.
# Update when OpenRouter pricing changes.
PRICE_INPUT_PER_1M = 0.25
PRICE_OUTPUT_PER_1M = 1.50


SYSTEM_PROMPT = """Siz ingliz tilini o'rgatuvchi AI yordamchisiz. Sizning vazifangiz — \
talabaning ingliz tilidagi gapini tekshirish va jo'natuvchiga mehribon, \
rag'batlantiruvchi fikr bildirish.

TEKSHIRUV MEZONLARI:
1. Grammatika (zamonlar, artikl, gap tuzilishi).
2. Maqsadli so'z TO'G'RI ma'noda ishlatilganmi.

QOIDALAR:
- Mehribon ohang. Hech qachon "siz xato qildingiz" demang.
- Tushuntirish 2-3 jumladan oshmasin.
- Maqsadli so'z gap ichida yo'q bo'lsa → is_correct=false, used_target_word=false, \
eslatib qo'ying: "Maqsadli so'zni gapga kiriting".
- Grammatik to'g'ri, lekin so'z noto'g'ri ma'noda → is_correct=false, \
to'g'ri ma'noni ko'rsating.
- explanation_uz FAQAT O'ZBEK tilida. Xato bo'lmasa — bo'sh string.
- corrected maydonida har doim to'g'ri ingliz gapni bering (xato bo'lmasa — originalni qaytaring).

JAVOB FAQAT JSON formatida bo'ladi (is_correct, used_target_word, corrected, explanation_uz).
"""


class CheckResult(BaseModel):
    is_correct: bool = Field(description="True if the sentence has no grammar or word-usage errors")
    used_target_word: bool = Field(description="True if the target word appears in the sentence and is used in the correct meaning")
    corrected: str = Field(description="The corrected English sentence. If no errors, return the original.")
    explanation_uz: str = Field(description="Explanation of the error in Uzbek (2-3 sentences). Empty string if no errors.")


_JSON_SCHEMA = {
    "name": "check_result",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "is_correct": {"type": "boolean"},
            "used_target_word": {"type": "boolean"},
            "corrected": {"type": "string"},
            "explanation_uz": {"type": "string"},
        },
        "required": ["is_correct", "used_target_word", "corrected", "explanation_uz"],
        "additionalProperties": False,
    },
}


class GeminiClient:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self._model = model
        self._client = AsyncOpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=api_key,
            default_headers={
                "HTTP-Referer": "https://github.com/Ibrakhimzhanov/teachereng",
                "X-Title": "teachereng",
            },
        )

    async def check_sentence(self, word: str, sentence: str) -> tuple[CheckResult, float]:
        user_msg = f"Maqsadli so'z: {word}\nTalaba gapi: {sentence}"

        last_err: Exception | None = None
        for attempt in range(3):
            try:
                resp = await self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_msg},
                    ],
                    response_format={
                        "type": "json_schema",
                        "json_schema": _JSON_SCHEMA,
                    },
                    temperature=0.2,
                    max_tokens=400,
                )
                content = resp.choices[0].message.content
                if not content:
                    raise RuntimeError("OpenRouter returned empty content")
                parsed = CheckResult.model_validate_json(content)
                cost = self._calc_cost(resp.usage)
                return parsed, cost
            except Exception as e:
                last_err = e
                log.warning("OpenRouter attempt %d failed: %s", attempt + 1, e)
                if attempt < 2:
                    await asyncio.sleep(2 ** (attempt + 1))

        raise RuntimeError(f"OpenRouter failed after 3 attempts: {last_err}")

    @staticmethod
    def _calc_cost(usage) -> float:
        if usage is None:
            return 0.0
        inp = (usage.prompt_tokens / 1_000_000) * PRICE_INPUT_PER_1M
        out = (usage.completion_tokens / 1_000_000) * PRICE_OUTPUT_PER_1M
        return round(inp + out, 6)
