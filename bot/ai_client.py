import asyncio
import logging
import random
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

reply_text QOIDALARI — JUDA MUHIM:

A) STRUKTURA — javob chiroyli bo'laklarga ajratiladi. HAR bo'lak:
   - o'z qatoridan boshlanadi
   - oldida bitta mos emoji: ❌ / ✅ / 💡
   - bo'laklar orasida BO'SH qator (\n\n)
   Tekkis bitta matn yozmang — Telegramda o'qishga noqulay.

B) EMOJI TIZIMI (aniq qoida):
   ❌  — talabaning xato gap (yoki xato qismi)
   ✅  — to'g'ri variant (ingliz tilida, qo'shtirnoq ichida)
   💡  — o'zbekcha izoh: nima xato bo'lgan va nega
   Ortiqcha emoji ishlatmang. Har bo'lakka bittadan, faqat yuqoridagi 3tasi.

C) IS_CORRECT = TRUE (gap to'g'ri, so'z ishlatilgan):
   Ikki qatorli ✅ bo'lak (bo'sh qator bilan ajratilgan):

   ✅ "talaba gapi qo'shtirnoq ichida"

   Qisqa izoh — 1 jumla.

   IZOHI HAR SAFAR YANGI FIKR bilan bo'ladi. Oldingi talaba uchun nima yozgan \
bo'lsangiz — shuni TAKRORLAMANG. Har safar boshqacha rakursdan maqtang:
   - so'zning o'rinli ishlatilishi
   - fe'l-ot kelishuvi
   - gap ohangi / uslub
   - so'z aniqligi
   - fikrning lo'ndaligi
   - gap ravonligi
   - foydali misol qo'shing
   - so'zning boshqa konteksti haqida eslatma
   - kelgusiga tavsiya
   Bir xil shablon jumlalarni qaytarmang ("Fikringiz aniq, tuzilishi puxta." \
yoki "Grammatika sof, ma'no bir tekis." kabilar — TAQIQLANADI). Haqiqiy \
ustoz kabi har bir talabaga BOSHQA ko'z bilan qarang.

D) IS_CORRECT = FALSE (grammatik xato yoki so'z noto'g'ri ma'noda):
   Uchta bo'lak (bo'sh qator bilan):

   ❌ "talabaning gapi aynan qanday yozgan bo'lsa shu"

   ✅ "to'g'rilangan ingliz variant"

   💡 1-2 jumla o'zbekcha izoh: nima xato bo'ldi va qoida.

E) AGAR maqsadli so'z umuman ishlatilmagan (is_correct=false, used_target_word=false):
   ❌ qo'yilmaydi (talaba yomon gap yozmagan — shunchaki so'zni kiritmagan).
   Ikki bo'lak:

   💡 Gap grammatik to'g'ri, ammo bugungi so'z — 'X' — ishlatilmagan.

   ✅ Masalan: "I X my time to study English."

F) TIL — faqat O'ZBEK lotin alifbosi. Bu MUHIM:
   - ZINHOR TURK tilini aralashtirmang. Turkcha so'zlar va harflar (ü, ö, ç, ı, ğ)
     mutlaqo ishlatilmaydi. "Cümle", "cümlangiz", "cümleniz", "doğru", "yanlış"
     kabi turkcha so'zlar — TAQIQLANGAN.
   - O'zbekchada "gap" yoki "jumla" deyiladi. Turkchada "cümle". Hech qachon "cümle" emas.
   - "Sizning gapingiz" yoki "Gap" — TO'G'RI. "Cümlangiz" — NOTO'G'RI (bu turkcha).
   - O'zbek alifbosidagi o'ziga xos belgilar: o' (o-apostrof), g' (g-apostrof), \
sh, ch, ng. Ularni to'g'ri yozing.
   - 💡 bo'lagi zinhor inglizcha emas, faqat o'zbekcha.
   MUROJAAT — faqat "SIZ" (hurmatli): ishlatibsiz, yozgansiz, ko'ring.
   "Sen/senga" ni ishlatmang.

G) ISHLATMANG (qat'iy taqiq):
   - "Yaxshi urinish", "Tushuntirish:", "Javobingiz", "Sizning gapingiz"
   - "Barakalla", "Mashaalloh", "Qoyil", "Balli"
   - "juda joyida", "o'rinli", "aynan shunday" (haddan tashqari takrorlanadi)
   - "Siz xato qildingiz" (qo'pol)

H) TAKRORLANMANG. Har javob yangi so'zlashuv, yangi formulirovka. \
Izohlarda bir xil gap boshini ishlatmang ("Gapingizda..." ni har safar \
takrorlamang — muqobillari: "Bu yerda...", "Sababi shuki...", "Qoida: ...").
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


_STYLE_ANGLES = [
    "So'zning o'rinliligi haqida bir fikr bildiring.",
    "Gapning ravonligi va ohangiga e'tibor qarating.",
    "Fe'l-ot kelishuvining mosligini ta'kidlang.",
    "Fikr aniqligi va qisqaligini ta'kidlang.",
    "Yordamchi misol yoki qo'shimcha kontekst tavsiya eting.",
    "Bu so'zning boshqa ma'nolariga ishora qiling (qisqa).",
    "Gap uslubi (rasmiy/norasmiy) haqida bir so'z.",
    "Kelasi darsga nima o'rganilsa yaxshi bo'lar edi — qisqa tavsiya.",
    "So'zni boshqa kontekstda qanday ishlatish mumkinligini eslating.",
    "Gapning semantik aniqligi haqida ikki og'iz so'z.",
    "Bu yerda nima yaxshi chiqqanini aniq ko'rsating.",
    "Bu so'zni ishlatishning afzalligini ayting.",
]


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
        style_hint = random.choice(_STYLE_ANGLES)
        user_msg = (
            f"Maqsadli so'z: {word}\n"
            f"Talaba gapi: {sentence}\n\n"
            f"Style hint (izohda boshqacharoq chiqish uchun): {style_hint}"
        )

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
