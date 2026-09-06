import asyncio
import logging
import os
import sqlite3
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CHANNEL_ID = os.getenv("CHANNEL_ID", "").strip()
ADMIN_IDS = {
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}

DB_PATH = Path(os.getenv("DB_PATH", "zboriv_svitlo.db"))

SETTLEMENTS = [
    "Івачів", "Августівка", "Беримівці", "Бзовиця", "Велика Плавуча",
    "Вовчківці", "Волосівка", "Вільшанка", "Вірлів", "Гарбузів",
    "Годів", "Грабківці", "Гукалівці", "Жабиня", "Жуківці", "Заруддя",
    "Зборів", "Йосипівка", "Кабарівці", "Калинівка", "Кальне", "Корчунок",
    "Коршилів", "Красна", "Кудинівці", "Кудобинці", "Лавриківці",
    "Лопушани", "Манаїв", "Метенів", "Млинівці", "Монилівка", "Мшана",
    "Нище", "Озерянка", "Оліїв", "Перепельники", "Підгайчики", "Плісняни",
    "Погрібці", "Присівці", "Розгадів", "Славна", "Травотолоки",
    "Тустоголови", "Футори", "Хоробрів", "Хоростець", "Храбузна", "Цецівка",
    "Цицори", "Ярославичі", "Ярчівці",
]

PAGE_SIZE = 10
dp = Dispatcher()


def db():
    con = sqlite3.connect(DB_PATH)
    con.execute(
        """CREATE TABLE IF NOT EXISTS subscriptions (
            user_id INTEGER PRIMARY KEY,
            settlement TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    con.commit()
    return con


def set_subscription(user_id: int, settlement: str):
    con = db()
    con.execute(
        "INSERT INTO subscriptions(user_id, settlement) VALUES(?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET settlement=excluded.settlement",
        (user_id, settlement),
    )
    con.commit()
    con.close()


def remove_subscription(user_id: int):
    con = db()
    con.execute("DELETE FROM subscriptions WHERE user_id=?", (user_id,))
    con.commit()
    con.close()


def get_subscription(user_id: int):
    con = db()
    row = con.execute(
        "SELECT settlement FROM subscriptions WHERE user_id=?", (user_id,)
    ).fetchone()
    con.close()
    return row[0] if row else None


def subscribers(settlement: str):
    con = db()
    rows = con.execute(
        "SELECT user_id FROM subscriptions WHERE settlement=?", (settlement,)
    ).fetchall()
    con.close()
    return [r[0] for r in rows]


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def settlements_keyboard(page: int = 0):
    total_pages = (len(SETTLEMENTS) + PAGE_SIZE - 1) // PAGE_SIZE
    page = max(0, min(page, total_pages - 1))
    start = page * PAGE_SIZE
    items = SETTLEMENTS[start:start + PAGE_SIZE]

    builder = InlineKeyboardBuilder()
    for i, name in enumerate(items, start=start):
        builder.button(text=f"📍 {name}", callback_data=f"place:{i}")
    builder.adjust(2)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"page:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="Далі ➡️", callback_data=f"page:{page+1}"))
    builder.row(*nav)
    return builder.as_markup()


def place_keyboard(index: int):
    settlement = SETTLEMENTS[index]
    builder = InlineKeyboardBuilder()
    builder.button(text="🔔 Підписатися на сповіщення", callback_data=f"sub:{index}")
    builder.button(text="🔄 Змінити населений пункт", callback_data="menu:0")
    builder.button(text="❌ Відписатися", callback_data="unsubscribe")
    builder.adjust(1)
    return builder.as_markup()


@dp.message(CommandStart())
async def start(message: Message):
    current = get_subscription(message.from_user.id)
    text = (
        "⚡️ <b>Зборівська громада | Світло</b>\n\n"
        "Оберіть свій населений пункт.\n"
        "Після вибору можна підписатися на сповіщення про відключення."
    )
    if current:
        text += f"\n\n🔔 Зараз ви підписані на: <b>{current}</b>"
    await message.answer(text, parse_mode="HTML", reply_markup=settlements_keyboard(0))


@dp.message(Command("menu"))
async def menu(message: Message):
    await message.answer(
        "📍 <b>Оберіть населений пункт:</b>",
        parse_mode="HTML",
        reply_markup=settlements_keyboard(0),
    )


@dp.message(Command("myid"))
async def myid(message: Message):
    await message.answer(f"Ваш Telegram ID: <code>{message.from_user.id}</code>", parse_mode="HTML")


@dp.message(Command("help"))
async def help_cmd(message: Message):
    text = (
        "⚡️ <b>Зборівська громада | Світло</b>\n\n"
        "/start — вибрати населений пункт\n"
        "/menu — відкрити меню\n"
        "/myid — показати ваш Telegram ID\n"
        "/help — допомога"
    )
    if is_admin(message.from_user.id):
        text += (
            "\n\n<b>Команди адміністратора:</b>\n"
            "/post НаселенийПункт — текст — надіслати повідомлення "
            "підписникам і в канал\n"
            "/stats — статистика підписок"
        )
    await message.answer(text, parse_mode="HTML")


@dp.callback_query(F.data == "noop")
async def noop(call: CallbackQuery):
    await call.answer()


@dp.callback_query(F.data.startswith("page:"))
async def page(call: CallbackQuery):
    p = int(call.data.split(":")[1])
    await call.message.edit_reply_markup(reply_markup=settlements_keyboard(p))
    await call.answer()


@dp.callback_query(F.data.startswith("place:"))
async def place(call: CallbackQuery):
    index = int(call.data.split(":")[1])
    settlement = SETTLEMENTS[index]
    current = get_subscription(call.from_user.id)
    text = (
        f"📍 <b>{settlement}</b>\n\n"
        "Оберіть дію:"
    )
    if current == settlement:
        text += "\n\n🔔 Ви вже підписані на сповіщення цього населеного пункту."
    await call.message.edit_text(
        text, parse_mode="HTML", reply_markup=place_keyboard(index)
    )
    await call.answer()


@dp.callback_query(F.data.startswith("sub:"))
async def subscribe(call: CallbackQuery):
    index = int(call.data.split(":")[1])
    settlement = SETTLEMENTS[index]
    set_subscription(call.from_user.id, settlement)
    await call.answer("Підписку збережено ✅")
    await call.message.edit_text(
        f"📍 <b>{settlement}</b>\n\n"
        "🔔 <b>Ви підписані на сповіщення.</b>\n\n"
        "Коли адміністратор опублікує інформацію про відключення для "
        "цього населеного пункту, бот надішле вам повідомлення.",
        parse_mode="HTML",
        reply_markup=place_keyboard(index),
    )


@dp.callback_query(F.data == "unsubscribe")
async def unsubscribe(call: CallbackQuery):
    remove_subscription(call.from_user.id)
    await call.answer("Підписку скасовано")
    await call.message.edit_text(
        "🔕 <b>Підписку скасовано.</b>\n\n"
        "Ви можете знову вибрати населений пункт.",
        parse_mode="HTML",
        reply_markup=settlements_keyboard(0),
    )


@dp.callback_query(F.data == "menu:0")
async def back_menu(call: CallbackQuery):
    await call.message.edit_text(
        "📍 <b>Оберіть населений пункт:</b>",
        parse_mode="HTML",
        reply_markup=settlements_keyboard(0),
    )
    await call.answer()


@dp.message(Command("stats"))
async def stats(message: Message):
    if not is_admin(message.from_user.id):
        return
    con = db()
    total = con.execute("SELECT COUNT(*) FROM subscriptions").fetchone()[0]
    con.close()
    await message.answer(f"👥 Активних підписок: <b>{total}</b>", parse_mode="HTML")


@dp.message(Command("post"))
async def post(message: Message, bot: Bot):
    if not is_admin(message.from_user.id):
        return

    raw = message.text or ""
    payload = raw.partition(" ")[2].strip()
    if "\n" not in payload:
        await message.answer(
            "Формат:\n"
            "<code>/post Кальне\n⚠️ Кальне: відключення з 14:00 до 18:00.</code>",
            parse_mode="HTML",
        )
        return

    first_line, body = payload.split("\n", 1)
    settlement = first_line.strip()
    if settlement not in SETTLEMENTS:
        await message.answer("❌ Такого населеного пункту немає у списку.")
        return
    body = body.strip()
    if not body:
        await message.answer("❌ Текст повідомлення порожній.")
        return

    post_text = f"📍 <b>{settlement}</b>\n\n{body}\n\n#ЗборівськаГромада #Світло"
    sent_to = 0

    # Публікація у канал
    if CHANNEL_ID:
        try:
            await bot.send_message(CHANNEL_ID, post_text, parse_mode="HTML")
        except Exception as e:
            await message.answer(
                "⚠️ Не вдалося опублікувати в канал. "
                "Перевір CHANNEL_ID і права бота в каналі.\n\n"
                f"Помилка: {e}"
            )
            return

    # Розсилка підписникам
    for user_id in subscribers(settlement):
        try:
            await bot.send_message(user_id, post_text, parse_mode="HTML")
            sent_to += 1
        except Exception:
            # Користувач міг заблокувати бота — просто пропускаємо.
            pass

    await message.answer(
        f"✅ Опубліковано для <b>{settlement}</b>.\n"
        f"👥 Отримали повідомлення: {sent_to}",
        parse_mode="HTML",
    )


@dp.message()
async def unknown(message: Message):
    await message.answer(
        "Натисніть /start, щоб вибрати населений пункт. 📍"
    )


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("Не задано BOT_TOKEN")
    db()
    bot = Bot(BOT_TOKEN)
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
