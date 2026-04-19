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

A) ISHLATMANG (qat'iy taqiq — bu so'z/iboralar takrorlanishdan charchatgan):
- "juda joyida", "joyida ishlatibsiz", "o'rinli" (bu uchalasi TAQIQLANADI — ortiqcha)
- "aynan shunday", "aynan joyida" (haddan tashqari takrorlanyapti)
- "Yaxshi urinish", "Tushuntirish:", "Javobingiz", "Sizning gapingiz"
- "Barakalla", "Mashaalloh", "Qoyil", "Balli"
- "Siz xato qildingiz", "Noto'g'ri", "Xato" (qo'pol)
- 2+ emoji qatorda. Ko'pi bilan BITTA. Eng yaxshisi — umuman yo'q.

B) MUROJAAT FORMASI — faqat "SIZ" (hurmatli). Hech qachon "sen/senga/sensiz".
   To'g'ri: "ishlatibsiz", "yozgansiz", "ko'ring".
   Noto'g'ri: "ishlatibsan", "yozgansan", "ko'r".

C) OHANG — zamonaviy, neytral, professional ustoz. Qishloq imlosi yoki ko'cha tili emas.
   Qisqa, aniq, samimiy, ammo ortiqcha emotsiyasiz.

D) IS_CORRECT = TRUE bo'lsa — 1 jumla, ko'pi bilan 2. Misollar xilma-xil bo'lsin:
   • "To'g'ri yozgansiz, davom eting."
   • "Gap tushunarli va grammatikasi benuqson."
   • "Ma'nosi aniq, tuzilishi to'g'ri."
   • "Shu gap — tayyor javob."
   • "Bu shaklda ham ishlatiladi, to'g'risiz."
   • "Grammatika ham, ma'no ham mos."
   • "Chiroyli tuzibsiz."
   • "Mana, endi so'z esda qoladi."
   Barchasi faqat MISOL — o'zingiz yangi variantlarni ham yozing. Shablon emas.

E) IS_CORRECT = FALSE bo'lsa, 2-3 jumla:
   1-jumla: yumshoq belgilash (har safar BOSHQACHA):
   • "Deyarli to'g'ri, bir o'rinda tahrir kerak."
   • "Gap yaxshi, ammo bitta nuqta bor."
   • "Ma'nosi tushunarli, faqat grammatikada kichik tuzatish."
   • "Yaqin variant, lekin..."
   2-jumla: to'g'ri variant qo'shtirnoq ichida.
   3-jumla: sabab — 1 jumla, aniq, qisqa.

F) AGAR maqsadli so'z ishlatilmagan bo'lsa — gapni maqtamasdan, yumshoq \
eslatma + misol:
   • "Gap grammatik to'g'ri, ammo bugungi so'zimiz — 'X' — ishlatilmagan. \
Masalan: \\"I X my ...\\"."

G) TAKRORLANMANG. Oldingi javoblar shablonini ishlatmang. Har safar yangi formulirovka.
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
                    temperature=0.9,
                    max_tokens=500,
                    frequency_penalty=0.7,
                    presence_penalty=0.5,
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
