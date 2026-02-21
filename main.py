import os
import re
import csv
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters

CSV_PATH = "units.csv"


def parse_query(text: str):
    t = text.lower()

    rooms = None
    if re.search(r"\b1\s*к\b|\b1\s*комн|\bодн", t):
        rooms = 1
    elif re.search(r"\b2\s*к\b|\b2\s*комн|\bдвух", t):
        rooms = 2
    elif re.search(r"\b3\s*к\b|\b3\s*комн|\bтрех", t):
        rooms = 3

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

    min_area = None
    ma = re.search(r"от\s*(\d{2,4})\s*(м|м2|м²)", t)
    if ma:
        min_area = int(ma.group(1))
    else:
        ma2 = re.search(r"\b(\d{2,4})\s*(м|м2|м²)\b", t)
        if ma2:
            min_area = int(ma2.group(1))

    return rooms, max_price, min_area


def load_units():
    units = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            for k in ["rooms", "area", "price"]:
                if k in row and row[k]:
                    try:
                        row[k] = float(row[k])
                    except:
                        row[k] = None
            units.append(row)
    return units


def search_units(units, rooms=None, max_price=None, min_area=None):
    filtered = []
    for u in units:
        r = u.get("rooms")
        a = u.get("area")
        p = u.get("price")

        if rooms is not None and r is not None and int(r) != rooms:
            continue
        if max_price is not None and p is not None and p > max_price:
            continue
        if min_area is not None and a is not None and a < min_area:
            continue

        filtered.append(u)

    filtered.sort(key=lambda x: x.get("price") if x.get("price") is not None else 10**18)
    return filtered[0] if filtered else None


def build_text(row):
    rooms = int(row.get("rooms") or 0)
    area = row.get("area", "")
    price = int(row.get("price") or 0)

    text = (
        f"{rooms}-комнатная квартира в ЖК {row.get('complex','')}\n"
        f"Площадь: {area} м²\n"
        f"Цена: ${price}\n"
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


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    hard_triggers = ["кадастр", "суд", "арест", "жалоб", "юрист", "документ", "проблем"]
    if any(word in text.lower() for word in hard_triggers):
        await update.message.reply_text("Этот вопрос требует уточнения у менеджера. Передаю специалисту.")
        return

    rooms, max_price, min_area = parse_query(text)

    units = load_units()
    row = search_units(units, rooms, max_price, min_area)

    if not row:
        await update.message.reply_text(
            "Не нашёл точного совпадения. Напишите: комнаты (1/2/3), бюджет 'до ...' и площадь (если важно)."
        )
        return

    await update.message.reply_text(build_text(row))

    plan_url = str(row.get("plan_url", "")).strip()
    if plan_url and plan_url.lower() != "nan":
        await update.message.reply_photo(plan_url)

    render_urls = str(row.get("render_urls", "")).strip()
    if render_urls and render_urls.lower() != "nan":
        urls = [u.strip() for u in render_urls.split(";") if u.strip()]
        for url in urls[:5]:
            await update.message.reply_photo(url)


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
