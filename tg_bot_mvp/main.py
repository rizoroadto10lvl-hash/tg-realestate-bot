import os
import re
import pandas as pd
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters

CSV_PATH = "units.csv"


# -------- Парсинг запроса --------
def parse_query(text: str):
    t = text.lower()

    # комнаты
    rooms = None
    if re.search(r"\b1\s*к\b|\b1\s*комн|\bодн", t):
        rooms = 1
    elif re.search(r"\b2\s*к\b|\b2\s*комн|\bдвух", t):
        rooms = 2
    elif re.search(r"\b3\s*к\b|\b3\s*комн|\bтрех", t):
        rooms = 3

    # бюджет (до 110000 / $110000 / 110k)
    max_price = None
    m = re.search(r"до\s*\$?\s*(\d{2,6})\s*(k)?", t)
    if m:
        value = int(m.group(1))
        if m.group(2):
            value *= 1000
        max_price = value
    else:
        m2 = re.search(r"\$\s*(\d{2,6})", t)
        if m2:
            max_price = int(m2.group(1))

    # площадь (от 60м / 60 м2)
    min_area = None
    ma = re.search(r"от\s*(\d{2,4})\s*(м|м2|м²)", t)
    if ma:
        min_area = int(ma.group(1))
    else:
        ma2 = re.search(r"\b(\d{2,4})\s*(м|м2|м²)\b", t)
        if ma2:
            min_area = int(ma2.group(1))

    return rooms, max_price, min_area


# -------- Загрузка базы --------
def load_units():
    df = pd.read_csv(CSV_PATH)

    for col in ["rooms", "area", "price"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


# -------- Поиск --------
def search_units(df, rooms=None, max_price=None, min_area=None):
    result = df.copy()

    if rooms is not None:
        result = result[result["rooms"] == rooms]

    if max_price is not None:
        result = result[result["price"] <= max_price]

    if min_area is not None:
        result = result[result["area"] >= min_area]

    result = result.sort_values(by=["price"], ascending=True)

    return result.head(1)


# -------- Формирование ответа --------
def build_text(row):
    text = (
        f"{int(row['rooms'])}-комнатная квартира в ЖК {row.get('complex','')}\n"
        f"Площадь: {row.get('area','')} м²\n"
        f"Цена: ${int(row.get('price',0))}\n"
        f"Срок сдачи: {row.get('deadline','')}\n\n"
        f"{row.get('description','')}\n\n"
    )

    installment = str(row.get("installment", "")).strip()
    if installment and installment.lower() != "nan":
        text += f"Рассрочка: {installment}\n"

    mortgage = str(row.get("mortgage", "")).strip()
    if mortgage and mortgage.lower() != "nan":
        text += f"Ипотека: {mortgage}\n"

    text += "\nНапишите бюджет и удобное время — подберу лучший вариант и запишу на просмотр."

    return text


# -------- Обработка сообщений --------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # слова, при которых бот передаёт менеджеру
    hard_triggers = ["кадастр", "суд", "арест", "жалоб", "юрист", "документ", "проблем"]

    if any(word in text.lower() for word in hard_triggers):
        await update.message.reply_text(
            "Этот вопрос требует уточнения у менеджера. Передаю специалисту."
        )
        return

    rooms, max_price, min_area = parse_query(text)

    df = load_units()
    found = search_units(df, rooms, max_price, min_area)

    if found.empty:
        await update.message.reply_text(
            "Не нашёл точного совпадения. Напишите: комнаты (1/2/3), бюджет 'до ...' и площадь."
        )
        return

    row = found.iloc[0].to_dict()

    # отправка текста
    await update.message.reply_text(build_text(row))

    # отправка планировки
    plan_url = str(row.get("plan_url", "")).strip()
    if plan_url and plan_url.lower() != "nan":
        await update.message.reply_photo(plan_url)

    # отправка рендеров
    render_urls = str(row.get("render_urls", "")).strip()
    if render_urls and render_urls.lower() != "nan":
        urls = [u.strip() for u in render_urls.split(";") if u.strip()]
        for url in urls[:5]:
            await update.message.reply_photo(url)


# -------- Запуск --------
def main():
    token = os.getenv("BOT_TOKEN")

    if not token:
        raise RuntimeError("BOT_TOKEN не установлен")

    app = Application.builder().token(token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()                      