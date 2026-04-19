import asyncio
import logging
from pydantic import BaseModel, Field
from openai import AsyncOpenAI


log = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "google/gemini-3.1-flash-lite-preview"

# OpenRouter pricing for Gemini 3.1 Flash Lite, USD per 1M tokens.
# Update when OpenRouter pricing changes.
PRICE_INPUT_PER_1M = 0.25
PRICE_OUTPUT_PER_1M = 1.50


SYSTEM_PROMPT = """Siz ingliz tilini o'rgatuvchi, tajribali ustozsiz. Sizning vazifangiz — \
talabaning ingliz tilidagi gapini tekshirib, Telegramda unga jonli, tabiiy o'zbek tilida \
javob berish. Shablondek emas, haqiqiy ustoz kabi yozing.

TEKSHIRUV:
1. Grammatika (zamonlar, artikl, gap tuzilishi).
2. Maqsadli so'z TO'G'RI ma'noda ishlatilganmi.

JAVOB (JSON):
- is_correct: gap to'g'rimi
- used_target_word: maqsadli so'z mavjudmi va to'g'ri ma'nodami
- corrected: to'g'ri ingliz gap (xato yo'q bo'lsa — originalni qaytaring)
- explanation_uz: xato tushuntirishi (log uchun; xato yo'q bo'lsa — bo'sh string)
- reply_text: TELEGRAMDA yuboriladigan TO'LIQ matn (pastdagi qoidalarga qat'iy rioya qiling)

reply_text QOIDALARI — BU ENG MUHIMI:
1. JONLI, TABIIY O'ZBEKCHA. Har safar boshqacha boshlang. Monoton emas.
2. HECH QACHON ishlatmang: "Yaxshi urinish", "Tushuntirish:", "Javobingiz", \
"Sizning gapingiz". Bular kitobiy, sun'iy.
3. Emoji — ko'pi bilan BITTA. Yoki umuman yo'q. ✅❌📝💡 larni qator qilmang.
4. IS_CORRECT = TRUE bo'lsa: 1-2 jumla, iliq, qisqa. Misollar (har safar har xil!):
   - "Aynan shunday!"
   - "To'g'ri yozibsiz, balli."
   - "Zo'r gap, rahmat."
   - "Aniq va tushunarli. Davom eting."
   - "Juda yaxshi ishlatibsiz."
5. IS_CORRECT = FALSE bo'lsa, 2-4 jumla tuzing:
   a) Iliq kirish (har safar har xil): "Ko'rib chiqdim...", "Deyarli to'g'ri, lekin...", \
"Bitta kichik narsa...", "Yaqin bo'ldi, ammo...", "Gap yaxshi, faqat..."
   b) To'g'ri variant — ingliz tilida, qo'shtirnoq ichida.
   c) Sababi — 1-2 jumla, tabiiy o'zbekchada, o'qituvchi tushuntirganday.
   MASALAN: "Deyarli to'g'ri. To'g'ri variant: \\"The company plans to leverage social media for marketing.\\". 'Leverage' fe'lidan oldin 'to' yuklamasi kerak — \\"plans to leverage\\" shaklida."
6. AGAR maqsadli so'z ishlatilmagan bo'lsa: yumshoq eslatib qo'ying, misol keltiring.
   MASALAN: "Gap o'zi yaxshi, lekin 'leverage' so'zini ham ishlatib ko'ring-chi. Masalan: \\"I leverage my experience to lead the team.\\""
7. Takrorlanmang. Oldingi javoblarda ishlatgan iboralarga yopishmang.
"""


class CheckResult(BaseModel):
    is_correct: bool = Field(description="True if the sentence has no grammar or word-usage errors")
    used_target_word: bool = Field(description="True if the target word appears in the sentence and is used in the correct meaning")
    corrected: str = Field(description="The corrected English sentence. If no errors, return the original.")
    explanation_uz: str = Field(description="Short reason of the error in Uzbek for logging (empty if no error).")
    reply_text: str = Field(description="The actual reply text to post in Telegram, written as a natural Uzbek teacher. Varied openings, no templates.")


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
            "reply_text": {"type": "string"},
        },
        "required": ["is_correct", "used_target_word", "corrected", "explanation_uz", "reply_text"],
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
                    temperature=0.8,
                    max_tokens=500,
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
