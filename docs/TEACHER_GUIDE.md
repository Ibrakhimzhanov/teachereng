# Teacher Guide / Ustoz uchun qo'llanma

Quick reference for the English teacher who uses the `@uztozationaiteachertestbot` — the AI assistant that checks student sentences in the channel's comment thread.

Qisqa ma'lumot: `@uztozationaiteachertestbot` — kanal ostidagi sharhlarda o'quvchilarning ingliz tilidagi gaplarini tekshiradigan AI yordamchi.

---

## 🇬🇧 English

### What the bot does

For each student comment, the bot replies in the comment thread with:
- **Praise** if the sentence is grammatically correct and uses the target word in the right meaning.
- **Correction + Uzbek explanation** if anything is off (grammar, wrong word meaning, or target word missing).

### How to publish a word-of-the-day post

The bot needs to know which word is being taught. Add **exactly one** of these to your post:

#### Option 1 — Explicit marker (recommended for reliability)

```
#word_leverage

Today we learn "leverage"...
```

Works for multi-word phrases too — replace spaces with underscores:

```
#word_look_up          →  target: look up
#word_give_up_on       →  target: give up on
#word_run_out_of       →  target: run out of
```

#### Option 2 — Single simple hashtag

If your post has **one** hashtag and it's the target word, the bot picks it up automatically:

```
#Leverage

Ushbu so'zga gap tuzing...
```

```
#give_up

Write sentences using this phrasal verb.
```

### What to avoid

- **Multiple unrelated hashtags** — the bot can't tell which one is the target:
  ```
  ❌ #english #vocabulary #leverage
  ```
  Use `#word_leverage` format instead.

- **No hashtag at all** — the bot ignores the post.

- **Non-English target words** — the bot checks English only.

### What the bot does with comments

| Situation | Bot reaction |
|---|---|
| Correct sentence, target word used | Short warm praise (varied wording each time) |
| Grammar error | Correction in English + brief Uzbek explanation |
| Target word used in wrong meaning | Flags it, shows correct usage |
| Target word missing | Reminds the student, gives an example |
| Comment written in Uzbek or Russian | Silently ignored |
| Toxic / off-topic comment | Silently ignored |

### Prerequisites (one-time setup)

The bot must be an **admin** in:
1. The channel — to read your posts.
2. The linked discussion group — to read comments and reply.

In `@BotFather`, the bot's privacy mode must be **Disabled** (`/setprivacy` → select bot → Disable).

### Weekly report

Every Sunday at 20:00 (Tashkent time), the bot sends you a private summary:
- Total sentences checked
- Percent correct / incorrect
- Top 3 words of the week

---

## 🇺🇿 O'zbekcha

### Bot nima qiladi

Har bir o'quvchi sharhiga bot sharh oqimida javob beradi:
- **Maqtov** — gap grammatik to'g'ri va maqsadli so'z to'g'ri ma'noda ishlatilgan bo'lsa.
- **Tuzatish + o'zbekcha tushuntirish** — biror narsa noto'g'ri bo'lsa (grammatika, so'z ma'nosi, yoki maqsadli so'z ishlatilmagan).

### "Kun so'zi" postini qanday chiqarish

Bot qaysi so'z o'rgatilayotganini bilishi kerak. Postga **aniq bitta** belgi qo'ying:

#### 1-variant — To'g'ridan-to'g'ri marker (eng ishonchli)

```
#word_leverage

Bugun "leverage" so'zini o'rganamiz...
```

Ko'p so'zli iboralar uchun ham ishlaydi — bo'sh joy o'rniga pastki chiziq:

```
#word_look_up          →  maqsad: look up
#word_give_up_on       →  maqsad: give up on
#word_run_out_of       →  maqsad: run out of
```

#### 2-variant — Oddiy bitta hashtag

Agar postda **bitta** hashtag bo'lsa va u maqsadli so'z bo'lsa, bot uni avtomatik tanlaydi:

```
#Leverage

Ushbu so'zga gap tuzing...
```

```
#give_up

Ushbu fe'l bilan gap tuzing.
```

### Nimani ishlatmaslik kerak

- **Bir nechta mavzusiz hashtag** — bot qaysi biri maqsadli ekanini topa olmaydi:
  ```
  ❌ #english #vocabulary #leverage
  ```
  O'rniga `#word_leverage` ishlating.

- **Umuman hashtagsiz** — bot postni inobatga olmaydi.

- **Ingliz tilidagi emas so'zlar** — bot faqat inglizcha tekshiradi.

### Sharhlar bilan bot nima qiladi

| Vaziyat | Bot reaksiyasi |
|---|---|
| Gap to'g'ri, so'z ishlatilgan | Qisqa iliq maqtov (har safar boshqacha so'zlar bilan) |
| Grammatik xato | Ingliz tilida to'g'ri variant + o'zbekcha qisqa izoh |
| So'z noto'g'ri ma'noda | Belgilab, to'g'ri ma'noni ko'rsatadi |
| So'z ishlatilmagan | Eslatadi va misol keltiradi |
| Sharh o'zbek yoki rus tilida | Javob bermaydi |
| Qo'pol yoki mavzudan chetga chiqqan sharh | Javob bermaydi |

### Talablar (bir marta sozlash)

Bot quyidagi joylarda **admin** bo'lishi shart:
1. Kanalda — postlaringizni o'qish uchun.
2. Bog'langan sharh-guruhda — sharhlarni o'qish va javob berish uchun.

`@BotFather` da botning privacy rejimi **Disabled** bo'lishi kerak (`/setprivacy` → botni tanlang → Disable).

### Haftalik hisobot

Har yakshanba soat 20:00 (Toshkent vaqti) da bot sizga shaxsiy xabarda hisobot yuboradi:
- Jami tekshirilgan gaplar soni
- Necha foiz to'g'ri / xato
- Hafta davomidagi eng ko'p 3 ta so'z

---

## Quick test checklist / Tezkor test ro'yxati

To verify the bot works end-to-end / Botning ishlashini tekshirish uchun:

1. Post in the channel with `#word_leverage` (or `#Leverage`).
2. Write a comment: `I leverage my skills to grow faster.`
3. Wait a few seconds — the bot should reply in the thread with praise.
4. Write another comment with an error: `I leveraging my English.`
5. The bot should reply with a corrected version + Uzbek explanation.
