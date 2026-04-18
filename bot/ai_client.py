import asyncio
import logging
from pydantic import BaseModel, Field
from google import genai
from google.genai import types


log = logging.getLogger(__name__)

MODEL = "gemini-flash-lite-latest"

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
"""


class CheckResult(BaseModel):
    is_correct: bool = Field(description="True if the sentence has no grammar or word-usage errors")
    used_target_word: bool = Field(description="True if the target word appears in the sentence and is used in the correct meaning")
    corrected: str = Field(description="The corrected English sentence. If no errors, return the original.")
    explanation_uz: str = Field(description="Explanation of the error in Uzbek (2-3 sentences). Empty string if no errors.")


class GeminiClient:
    def __init__(self, api_key: str):
        self._client = genai.Client(api_key=api_key)

    async def check_sentence(self, word: str, sentence: str) -> tuple[CheckResult, float]:
        user_msg = f"Maqsadli so'z: {word}\nTalaba gapi: {sentence}"

        last_err: Exception | None = None
        for attempt in range(3):
            try:
                resp = await self._client.aio.models.generate_content(
                    model=MODEL,
                    contents=user_msg,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        temperature=0.2,
                        max_output_tokens=400,
                        response_mime_type="application/json",
                        response_schema=CheckResult,
                    ),
                )
                cost = self._calc_cost(resp.usage_metadata)
                parsed = resp.parsed
                if parsed is None:
                    raise RuntimeError("Gemini returned no parsed result")
                return parsed, cost
            except Exception as e:
                last_err = e
                log.warning("Gemini attempt %d failed: %s", attempt + 1, e)
                if attempt < 2:
                    await asyncio.sleep(2 ** (attempt + 1))

        raise RuntimeError(f"Gemini failed after 3 attempts: {last_err}")

    @staticmethod
    def _calc_cost(usage) -> float:
        inp = (usage.prompt_token_count / 1_000_000) * PRICE_INPUT_PER_1M
        out = (usage.candidates_token_count / 1_000_000) * PRICE_OUTPUT_PER_1M
        return round(inp + out, 6)
