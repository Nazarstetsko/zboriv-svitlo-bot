import asyncio
import logging
import os
import sqlite3
from pathlib import Path
from urllib.parse import quote

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CHANNEL_ID = os.getenv("CHANNEL_ID", "").strip()
ADMIN_IDS = {
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}
DB_PATH = Path(os.getenv("DB_PATH", "zboriv_svitlo.db"))

# 53 населені пункти громади — збережено існуючий список бота.
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

# Офіційні та перевірені інформаційні джерела.
OFFICIAL = {
    "community": "https://zborivska-gromada.gov.ua",
    "oblast_communities": "https://oda.te.gov.ua/oda-i-organi-vladi/teritorialni-gromadi",
    "decentralization": "https://decentralization.gov.ua/newrayons/1394/communities",
    "electricity": "https://www.toe.com.ua/",
    "power_check": "https://poweron.toe.com.ua/",
    "hospital": "https://zborivlik.med.ukraina.org.ua/",
    "hospital_contacts": "https://zborivlik.med.ukraina.org.ua/kontakty",
    "police": "https://tp.npu.gov.ua/kontakty",
    "dsns": "https://tr.dsns.gov.ua/",
    "migration": "https://dmsu.gov.ua/ternopil",
    "gas": "https://gas.ua/uk/home/contacts",
    "gas_indicators": "https://gas.ua/uk/indicators",
    "invest": "https://invest.zborivska-gromada.gov.ua/",
    "bus_ternopil_zboriv": "https://railukraine.com/uk/rozklad-avtobusiv/ternopil/zboriv",
    "bus_zboriv_ternopil": "https://rubikon.com.ua/direction/zboriv/ternopil",
    "bus_station": "https://bus-info.in.ua/ternopilska-oblast/zboriv/",
}

# Статичні контакти, перевірені перед створенням цієї версії.
CONTACTS = {
    "police": {
        "title": "👮 Поліція",
        "text": (
            "👮 <b>ВІДДІЛЕННЯ ПОЛІЦІЇ №2 (м. Зборів)</b>\n\n"
            "📍 Адреса: вул. Б. Хмельницького, 44, м. Зборів, 47201\n"
            "☎️ Телефон: <b>(03540) 2-12-45</b>\n"
            "🚨 Екстрений номер: <b>102</b>\n\n"
            "Дані підрозділу опубліковані на офіційному сайті ГУНП "
            "у Тернопільській області."
        ),
        "url": OFFICIAL["police"],
        "map": "https://www.google.com/maps/search/?api=1&query=" + quote(
            "Відділення поліції №2 Зборів, вул. Б. Хмельницького 44, Зборів"
        ),
    },
    "hospital": {
        "title": "🏥 Зборівська лікарня",
        "text": (
            "🏥 <b>КНП «ЗБОРІВСЬКА ЛІКАРНЯ»</b>\n\n"
            "📍 47201, м. Зборів, вул. Б. Хмельницького, 17\n"
            "☎️ Приймальня/загальний: <b>+380 3540 21054</b>\n"
            "🚑 Швидка допомога: <b>103</b>\n\n"
            "Поліклініка: Пн–Пт 09:00–17:00, Сб 09:00–13:00.\n"
            "Лабораторія: Пн–Пт 08:30–15:30.\n"
            "Стоматологія: Пн–Пт 09:00–16:42, Сб 09:00–14:00.\n\n"
            "Точні графіки окремих підрозділів дивіться на офіційному сайті."
        ),
        "url": OFFICIAL["hospital_contacts"],
        "map": "https://www.google.com/maps/search/?api=1&query=" + quote(
            "КНП Зборівська лікарня, вул. Б. Хмельницького 17, Зборів"
        ),
    },
    "city": {
        "title": "🏛️ Зборівська міська рада",
        "text": (
            "🏛️ <b>ЗБОРІВСЬКА МІСЬКА РАДА</b>\n\n"
            "📍 Адреса: вул. Б. Хмельницького, 24, м. Зборів, 47201\n"
            "☎️ Телефони: <b>(03540) 2-17-43; 2-11-86; 2-10-50</b>\n"
            "✉️ rada@zborivska-gromada.gov.ua\n"
            "👤 Голова громади: Максимів Руслан Сергійович\n\n"
            "Графік роботи: Пн–Чт 08:00–17:15, Пт 08:00–16:00."
        ),
        "url": OFFICIAL["community"],
        "map": "https://www.google.com/maps/search/?api=1&query=" + quote(
            "Зборівська міська рада, вул. Б. Хмельницького 24, Зборів"
        ),
    },
    "migration": {
        "title": "🛂 Міграційна служба",
        "text": (
            "🛂 <b>Зборівський сектор ДМС</b>\n\n"
            "📍 вул. Б. Хмельницького, 44, м. Зборів\n"
            "☎️ <b>+380 3540 22420</b>\n\n"
            "Актуальний графік і перелік послуг краще перевіряти на сайті ДМС."
        ),
        "url": OFFICIAL["migration"],
        "map": "https://www.google.com/maps/search/?api=1&query=" + quote(
            "Зборівський сектор ДМС, вул. Б. Хмельницького 44, Зборів"
        ),
    },
    "water": {
        "title": "💧 Зборівський водоканал",
        "text": (
            "💧 <b>КП «ЗБОРІВСЬКИЙ ВОДОКАНАЛ»</b>\n\n"
            "📍 вул. Козацька, 3, м. Зборів, 47201\n"
            "☎️ <b>+380 67 260 08 23</b>\n"
            "☎️ <b>+380 3540 21209</b>\n"
            "✉️ zborivvodokanal@ukr.net\n\n"
            "Для аварій або відсутності води рекомендується спочатку "
            "уточнити актуальний номер у підприємства."
        ),
        "url": "https://ukrvodokanal.in.ua/participants/kp-zborivskyj-vodokanal/",
        "map": "https://www.google.com/maps/search/?api=1&query=" + quote(
            "Зборівський водоканал, вул. Козацька 3, Зборів"
        ),
    },
}

def db():
    con = sqlite3.connect(DB_PATH)
    con.execute(
        """CREATE TABLE IF NOT EXISTS subscriptions (
            user_id INTEGER PRIMARY KEY,
            settlement TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    con.execute(
        """CREATE TABLE IF NOT EXISTS user_places (
            user_id INTEGER PRIMARY KEY,
            settlement TEXT NOT NULL
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
    con.execute(
        "INSERT INTO user_places(user_id, settlement) VALUES(?, ?) "
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

def set_place(user_id: int, settlement: str):
    con = db()
    con.execute(
        "INSERT INTO user_places(user_id, settlement) VALUES(?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET settlement=excluded.settlement",
        (user_id, settlement),
    )
    con.commit()
    con.close()

def get_place(user_id: int):
    con = db()
    row = con.execute(
        "SELECT settlement FROM user_places WHERE user_id=?", (user_id,)
    ).fetchone()
    con.close()
    return row[0] if row else get_subscription(user_id)

def subscribers(settlement: str):
    con = db()
    rows = con.execute(
        "SELECT user_id FROM subscriptions WHERE settlement=?", (settlement,)
    ).fetchall()
    con.close()
    return [r[0] for r in rows]

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# Громадський транспорт — дані, перевірені у відкритих онлайн-джерелах у вересні 2026.
TRANSPORT_2026 = {
    "Тернопіль → Зборів": [
        "06:15 → 07:02 — рейс Тернопіль → Жабиня",
        "07:00 → 07:55 — рейс Тернопіль → Манаїв",
        "09:40 → 10:30 — рейс Тернопіль → Жабиня",
        "12:20 → 13:15 — рейс Тернопіль → Жабиня",
        "12:50 → 13:50 — рейс Тернопіль → Манаїв",
        "14:15 → 15:05 — рейс Тернопіль → Жабиня",
        "15:50 → 16:45 — рейс Тернопіль → Жабиня",
        "16:00 → 16:47 — рейс Тернопіль → Золочів",
        "16:15 → 17:10 — рейс Тернопіль → Манаїв",
        "17:00 → 17:58 — рейс Тернопіль → Жабиня",
    ],
    "Зборів → Тернопіль": [
        "07:55 — актуальний рейс Зборів → Тернопіль, підтверджений онлайн на 11.09.2026",
    ],
}

def transport_menu():
    b = InlineKeyboardBuilder()
    b.button(text="🏙️ Тернопіль → Зборів", callback_data="transport:to_zboriv")
    b.button(text="🏡 Зборів → Тернопіль", callback_data="transport:to_ternopil")
    b.button(text="🏘️ Місцеві маршрути", callback_data="transport:local")
    b.button(text="🔎 Онлайн-розклад", callback_data="transport:online")
    b.button(text="ℹ️ Важливо про розклад", callback_data="transport:info")
    b.button(text="🏠 Головне меню", callback_data="main")
    b.adjust(2, 2, 1, 1)
    return b.as_markup()

def transport_text(direction: str):
    rows = TRANSPORT_2026[direction]
    return (
        f"🚌 <b>{direction}</b>\n\n"
        + "\n".join(f"• {row}" for row in rows)
        + "\n\n⚠️ <i>Розклад може змінюватися перевізником. Перед поїздкою перевіряйте актуальний рейс за посиланням нижче.</i>"
    )

def main_menu():
    b = InlineKeyboardBuilder()
    b.button(text="⚡ Електроенергія", callback_data="main:electricity")
    b.button(text="📰 Новини", callback_data="main:news")
    b.button(text="📢 Оголошення", callback_data="main:announcements")
    b.button(text="🏛️ Про громаду", callback_data="main:community")
    b.button(text="🗺️ Мій населений пункт", callback_data="main:my_place")
    b.button(text="📞 Корисні контакти", callback_data="main:contacts")
    b.button(text="🆘 Важлива інформація", callback_data="main:important")
    b.button(text="🚌 Автобуси та розклад", callback_data="main:transport")
    b.button(text="🤖 Автодопомога 24/7 Чат", callback_data="main:help_chat")
    b.button(text="⚙️ Налаштування", callback_data="main:settings")
    b.adjust(2, 2, 2, 2, 1, 1, 1)
    return b.as_markup()

def back_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Головне меню", callback_data="main")]
    ])

def electricity_menu():
    b = InlineKeyboardBuilder()
    b.button(text="📅 Графік відключень", callback_data="elec:schedule")
    b.button(text="📍 Обрати населений пункт", callback_data="elec:places")
    b.button(text="🔔 Моя підписка", callback_data="elec:subscription")
    b.button(text="🚨 Аварійні/поточні відключення", callback_data="elec:current")
    b.button(text="☎️ Контакти Тернопільобленерго", callback_data="elec:contacts")
    b.button(text="ℹ️ Як перевірити адресу", callback_data="elec:info")
    b.button(text="🏠 Головне меню", callback_data="main")
    b.adjust(2, 2, 2, 1)
    return b.as_markup()

def contacts_menu():
    b = InlineKeyboardBuilder()
    for key in ["police", "hospital", "city", "migration", "water"]:
        b.button(text=CONTACTS[key]["title"], callback_data=f"contact:{key}")
    b.button(text="🚒 ДСНС / Пожежа", callback_data="contact:dsns")
    b.button(text="🚑 Екстрені номери", callback_data="contact:emergency")
    b.button(text="🔥 Газова служба", callback_data="contact:gas")
    b.button(text="⚡ Електромережі", callback_data="contact:power")
    b.button(text="🏠 Головне меню", callback_data="main")
    b.adjust(2, 2, 2, 2, 1)
    return b.as_markup()

def important_menu():
    b = InlineKeyboardBuilder()
    b.button(text="🚨 Екстрені номери", callback_data="contact:emergency")
    b.button(text="🔥 Запах газу — що робити", callback_data="important:gas")
    b.button(text="⚡ Аварія електромережі", callback_data="important:power")
    b.button(text="💧 Аварія водопостачання", callback_data="important:water")
    b.button(text="📢 Офіційні повідомлення громади", callback_data="main:announcements")
    b.button(text="🏠 Головне меню", callback_data="main")
    b.adjust(2, 2, 1)
    return b.as_markup()

def settings_menu():
    b = InlineKeyboardBuilder()
    b.button(text="🗺️ Змінити населений пункт", callback_data="elec:places")
    b.button(text="🔔 Моя підписка", callback_data="elec:subscription")
    b.button(text="🔕 Відписатися", callback_data="unsubscribe")
    b.button(text="ℹ️ Про бота", callback_data="settings:about")
    b.button(text="🏠 Головне меню", callback_data="main")
    b.adjust(2, 2, 1)
    return b.as_markup()

def places_keyboard(page: int = 0):
    total_pages = (len(SETTLEMENTS) + PAGE_SIZE - 1) // PAGE_SIZE
    page = max(0, min(page, total_pages - 1))
    start = page * PAGE_SIZE
    items = SETTLEMENTS[start:start + PAGE_SIZE]
    b = InlineKeyboardBuilder()
    for i, name in enumerate(items, start=start):
        b.button(text=f"📍 {name}", callback_data=f"place:{i}")
    b.adjust(2)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"places:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="Далі ➡️", callback_data=f"places:{page+1}"))
    b.row(*nav)
    b.row(InlineKeyboardButton(text="🏠 Головне меню", callback_data="main"))
    return b.as_markup()

def place_keyboard(index: int):
    settlement = SETTLEMENTS[index]
    b = InlineKeyboardBuilder()
    b.button(text="🔔 Підписатися на сповіщення", callback_data=f"sub:{index}")
    b.button(text="🗺️ Зробити моїм населеним пунктом", callback_data=f"setplace:{index}")
    b.button(text="🔄 Змінити населений пункт", callback_data="elec:places")
    b.button(text="❌ Відписатися", callback_data="unsubscribe")
    b.button(text="🏠 Головне меню", callback_data="main")
    b.adjust(1)
    return b.as_markup()

def url_keyboard(url: str, map_url: str | None = None):
    rows = [[InlineKeyboardButton(text="🌐 Офіційний сайт", url=url)]]
    if map_url:
        rows.append([InlineKeyboardButton(text="📍 Відкрити на карті", url=map_url)])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="main:contacts")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def show_main(target: Message | CallbackQuery):
    text = (
        "🏛️ <b>ЗБОРІВСЬКА ГРОМАДА</b>\n\n"
        "Вітаємо! 👋\n"
        "Оберіть потрібний розділ нижче."
    )
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, parse_mode="HTML", reply_markup=main_menu())
        await target.answer()
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=main_menu())

@dp.message(CommandStart())
async def start(message: Message):
    db()
    await show_main(message)

@dp.message(Command("menu"))
async def menu(message: Message):
    await show_main(message)

@dp.message(Command("myid"))
async def myid(message: Message):
    await message.answer(f"Ваш Telegram ID: <code>{message.from_user.id}</code>", parse_mode="HTML")

@dp.message(Command("help"))
async def help_cmd(message: Message):
    text = (
        "🤖 <b>Зборівська громада</b>\n\n"
        "/start — головне меню\n"
        "/menu — головне меню\n"
        "/myid — ваш Telegram ID\n"
        "/help — допомога\n\n"
        "Для запитань скористайтеся «🤖 Автодопомога 24/7 Чат»."
    )
    if is_admin(message.from_user.id):
        text += (
            "\n\n<b>Команди адміністратора:</b>\n"
            "/post НаселенийПункт — текст — розсилка підписникам і в канал\n"
            "/stats — статистика підписок"
        )
    await message.answer(text, parse_mode="HTML")

@dp.callback_query(F.data == "noop")
async def noop(call: CallbackQuery):
    await call.answer()

@dp.callback_query(F.data == "main")
async def main_callback(call: CallbackQuery):
    await show_main(call)

@dp.callback_query(F.data == "main:electricity")
async def main_electricity(call: CallbackQuery):
    await call.message.edit_text(
        "⚡ <b>ЕЛЕКТРОЕНЕРГІЯ</b>\n\n"
        "Тут зібрано інформацію про відключення та підписку.\n"
        "Графік може змінюватися оператором мережі протягом доби.",
        parse_mode="HTML", reply_markup=electricity_menu()
    )
    await call.answer()

@dp.callback_query(F.data == "main:news")
async def main_news(call: CallbackQuery):
    b = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Новини громади", url=OFFICIAL["community"])],
        [InlineKeyboardButton(text="💼 Новини та розвиток", url=OFFICIAL["invest"])],
        [InlineKeyboardButton(text="🏠 Головне меню", callback_data="main")],
    ])
    await call.message.edit_text(
        "📰 <b>НОВИНИ</b>\n\n"
        "Актуальні новини та офіційні повідомлення краще читати "
        "безпосередньо з офіційних ресурсів громади.",
        parse_mode="HTML", reply_markup=b
    )
    await call.answer()

@dp.callback_query(F.data == "main:announcements")
async def main_announcements(call: CallbackQuery):
    b = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏛️ Офіційний сайт громади", url=OFFICIAL["community"])],
        [InlineKeyboardButton(text="⚡ Офіційні повідомлення про електроенергію", url=OFFICIAL["electricity"])],
        [InlineKeyboardButton(text="🏠 Головне меню", callback_data="main")],
    ])
    await call.message.edit_text(
        "📢 <b>ОГОЛОШЕННЯ</b>\n\n"
        "Тут будуть важливі оголошення громади. "
        "Поки що найнадійніше джерело — офіційний сайт громади.",
        parse_mode="HTML", reply_markup=b
    )
    await call.answer()

@dp.callback_query(F.data == "main:community")
async def main_community(call: CallbackQuery):
    await call.message.edit_text(
        "🏛️ <b>ПРО ЗБОРІВСЬКУ ГРОМАДУ</b>\n\n"
        "🏙️ Тип: міська територіальна громада\n"
        "📍 Район: Тернопільський\n"
        "📐 Площа: <b>466,9 км²</b>\n"
        "👥 Населення: <b>18 158</b>\n"
        "🏘️ Населених пунктів: <b>53</b>\n"
        "📅 Утворена: 2020 року\n"
        "🏛️ Адміністративний центр: м. Зборів\n\n"
        "👤 Голова громади: Максимів Руслан Сергійович\n"
        "📍 Міська рада: вул. Б. Хмельницького, 24\n"
        "☎️ (03540) 2-17-43; 2-11-86; 2-10-50\n"
        "✉️ rada@zborivska-gromada.gov.ua",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌐 Сайт громади", url=OFFICIAL["community"])],
            [InlineKeyboardButton(text="📊 Дані про громаду", url=OFFICIAL["decentralization"])],
            [InlineKeyboardButton(text="💼 Інвестиційний портал", url=OFFICIAL["invest"])],
            [InlineKeyboardButton(text="🏠 Головне меню", callback_data="main")],
        ])
    )
    await call.answer()

@dp.callback_query(F.data == "main:my_place")
async def main_my_place(call: CallbackQuery):
    place = get_place(call.from_user.id)
    if not place:
        await call.message.edit_text(
            "🗺️ <b>МІЙ НАСЕЛЕНИЙ ПУНКТ</b>\n\n"
            "Ви ще не вибрали населений пункт.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📍 Обрати населений пункт", callback_data="elec:places")],
                [InlineKeyboardButton(text="🏠 Головне меню", callback_data="main")],
            ])
        )
    else:
        await call.message.edit_text(
            f"🗺️ <b>МІЙ НАСЕЛЕНИЙ ПУНКТ</b>\n\n"
            f"📍 <b>{place}</b>\n\n"
            "⚡ Відключення — у розділі «Електроенергія».\n"
            "📢 Місцеві оголошення та новини — через офіційні ресурси громади.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⚡ Електроенергія", callback_data="main:electricity")],
                [InlineKeyboardButton(text="🔄 Змінити населений пункт", callback_data="elec:places")],
                [InlineKeyboardButton(text="🏠 Головне меню", callback_data="main")],
            ])
        )
    await call.answer()

@dp.callback_query(F.data == "main:contacts")
async def main_contacts(call: CallbackQuery):
    await call.message.edit_text(
        "📞 <b>КОРИСНІ КОНТАКТИ</b>\n\n"
        "Виберіть службу:",
        parse_mode="HTML", reply_markup=contacts_menu()
    )
    await call.answer()

@dp.callback_query(F.data == "main:important")
async def main_important(call: CallbackQuery):
    await call.message.edit_text(
        "🆘 <b>ВАЖЛИВА ІНФОРМАЦІЯ</b>\n\n"
        "Тут зібрані екстрені контакти та короткі інструкції "
        "для аварійних ситуацій.",
        parse_mode="HTML", reply_markup=important_menu()
    )
    await call.answer()

@dp.callback_query(F.data == "main:transport")
async def main_transport(call: CallbackQuery):
    await call.message.edit_text(
        "🚌 <b>АВТОБУСИ ТА РОЗКЛАД</b>\n\n"
        "Розділ містить доступні дані про автобусні сполучення Зборова та напрямки громади. "
        "Дані актуалізуються за відкритими онлайн-джерелами.",
        parse_mode="HTML", reply_markup=transport_menu()
    )
    await call.answer()

@dp.callback_query(F.data == "transport:to_zboriv")
async def transport_to_zboriv(call: CallbackQuery):
    await call.message.edit_text(transport_text("Тернопіль → Зборів"), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔎 Актуальний онлайн-розклад", url=OFFICIAL["bus_ternopil_zboriv"])],
        [InlineKeyboardButton(text="⬅️ Автобуси та розклад", callback_data="main:transport")],
    ]))
    await call.answer()

@dp.callback_query(F.data == "transport:to_ternopil")
async def transport_to_ternopil(call: CallbackQuery):
    await call.message.edit_text(transport_text("Зборів → Тернопіль"), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔎 Перевірити рейс на дату", url=OFFICIAL["bus_zboriv_ternopil"])],
        [InlineKeyboardButton(text="⬅️ Автобуси та розклад", callback_data="main:transport")],
    ]))
    await call.answer()

@dp.callback_query(F.data == "transport:local")
async def transport_local(call: CallbackQuery):
    await call.message.edit_text(
        "🏘️ <b>МІСЦЕВІ МАРШРУТИ</b>\n\n"
        "У відкритих джерелах є маршрути через населені пункти громади, зокрема Манаїв, Жабиню, Кальне, Нище, Храбузну, Бзовицю, Годів та інші.\n\n"
        "⚠️ Частина опублікованих таблиць має старі дати, тому я не видаю їх за гарантовано актуальний розклад 2026 року.",
        parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔎 Розклад автостанції Зборів", url=OFFICIAL["bus_station"])],
            [InlineKeyboardButton(text="⬅️ Автобуси та розклад", callback_data="main:transport")],
        ])
    )
    await call.answer()

@dp.callback_query(F.data == "transport:online")
async def transport_online(call: CallbackQuery):
    await call.message.edit_text(
        "🔎 <b>ОНЛАЙН-РОЗКЛАД</b>\n\nДля точного часу на конкретну дату використовуйте актуальні сторінки розкладу.",
        parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚌 Тернопіль → Зборів", url=OFFICIAL["bus_ternopil_zboriv"])],
            [InlineKeyboardButton(text="🚌 Зборів → Тернопіль", url=OFFICIAL["bus_zboriv_ternopil"])],
            [InlineKeyboardButton(text="⬅️ Автобуси та розклад", callback_data="main:transport")],
        ])
    )
    await call.answer()

@dp.callback_query(F.data == "transport:info")
async def transport_info(call: CallbackQuery):
    await call.message.edit_text(
        "ℹ️ <b>ПРО РОЗКЛАД</b>\n\nДані в боті не замінюють підтвердження рейсу. Перевізник може змінити час або скасувати рейс. Перед поїздкою перевіряйте конкретну дату.",
        parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔎 Онлайн-розклад", callback_data="transport:online")],
            [InlineKeyboardButton(text="⬅️ Автобуси та розклад", callback_data="main:transport")],
        ])
    )
    await call.answer()

@dp.callback_query(F.data == "main:help_chat")
async def main_help_chat(call: CallbackQuery):
    await call.message.edit_text(
        "🤖 <b>АВТОДОПОМОГА 24/7 ЧАТ</b>\n\n"
        "Напишіть своє питання наступним повідомленням.\n\n"
        "Я можу підказати за базовими темами:\n"
        "👮 поліція • 🏥 медицина • 🏛️ міська рада • 📄 ЦНАП\n"
        "⚡ електроенергія • 🔥 газ • 💧 вода • 🚨 екстрені служби.\n\n"
        "При складному або нестандартному питанні я запропоную "
        "офіційне джерело.",
        parse_mode="HTML",
        reply_markup=back_main()
    )
    await call.answer()

@dp.callback_query(F.data == "main:settings")
async def main_settings(call: CallbackQuery):
    await call.message.edit_text(
        "⚙️ <b>НАЛАШТУВАННЯ</b>\n\n"
        "Тут можна змінити населений пункт та керувати підпискою.",
        parse_mode="HTML", reply_markup=settings_menu()
    )
    await call.answer()

@dp.callback_query(F.data == "elec:places")
async def elec_places(call: CallbackQuery):
    await call.message.edit_text(
        "📍 <b>ОБЕРІТЬ НАСЕЛЕНИЙ ПУНКТ</b>",
        parse_mode="HTML", reply_markup=places_keyboard(0)
    )
    await call.answer()

@dp.callback_query(F.data.startswith("places:"))
async def places_page(call: CallbackQuery):
    p = int(call.data.split(":")[1])
    await call.message.edit_reply_markup(reply_markup=places_keyboard(p))
    await call.answer()

@dp.callback_query(F.data.startswith("place:"))
async def place(call: CallbackQuery):
    index = int(call.data.split(":")[1])
    settlement = SETTLEMENTS[index]
    current = get_subscription(call.from_user.id)
    text = f"📍 <b>{settlement}</b>\n\nОберіть дію:"
    if current == settlement:
        text += "\n\n🔔 Ви вже підписані на сповіщення цього населеного пункту."
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=place_keyboard(index))
    await call.answer()

@dp.callback_query(F.data.startswith("setplace:"))
async def setplace(call: CallbackQuery):
    index = int(call.data.split(":")[1])
    settlement = SETTLEMENTS[index]
    set_place(call.from_user.id, settlement)
    await call.message.edit_text(
        f"🗺️ <b>Ваш населений пункт: {settlement}</b>\n\n"
        "Тепер він збережений у вашому профілі.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚡ Електроенергія", callback_data="main:electricity")],
            [InlineKeyboardButton(text="🏠 Головне меню", callback_data="main")],
        ])
    )
    await call.answer("Збережено ✅")

@dp.callback_query(F.data.startswith("sub:"))
async def subscribe(call: CallbackQuery):
    index = int(call.data.split(":")[1])
    settlement = SETTLEMENTS[index]
    set_subscription(call.from_user.id, settlement)
    await call.answer("Підписку збережено ✅")
    await call.message.edit_text(
        f"📍 <b>{settlement}</b>\n\n"
        "🔔 <b>Ви підписані на сповіщення.</b>\n\n"
        "Адміністратор може надсилати вам повідомлення про відключення "
        "для цього населеного пункту.",
        parse_mode="HTML", reply_markup=place_keyboard(index)
    )

@dp.callback_query(F.data == "unsubscribe")
async def unsubscribe(call: CallbackQuery):
    remove_subscription(call.from_user.id)
    await call.answer("Підписку скасовано")
    await call.message.edit_text(
        "🔕 <b>Підписку скасовано.</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📍 Обрати населений пункт", callback_data="elec:places")],
            [InlineKeyboardButton(text="🏠 Головне меню", callback_data="main")],
        ])
    )

@dp.callback_query(F.data == "elec:schedule")
async def elec_schedule(call: CallbackQuery):
    await call.message.edit_text(
        "📅 <b>ГРАФІК ВІДКЛЮЧЕНЬ</b>\n\n"
        "Для найточнішої перевірки введіть населений пункт, "
        "вулицю та номер будинку на сервісі АТ «Тернопільобленерго».\n\n"
        "Графік може змінюватися протягом доби.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔎 Перевірити мою адресу", url=OFFICIAL["power_check"])],
            [InlineKeyboardButton(text="📍 Обрати населений пункт", callback_data="elec:places")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="main:electricity")],
        ])
    )
    await call.answer()

@dp.callback_query(F.data == "elec:current")
async def elec_current(call: CallbackQuery):
    await call.message.edit_text(
        "🚨 <b>ПОТОЧНІ / АВАРІЙНІ ВІДКЛЮЧЕННЯ</b>\n\n"
        "Оперативну інформацію перевіряйте на офіційному сервісі "
        "АТ «Тернопільобленерго».",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚡ Перевірити стан електропостачання", url=OFFICIAL["power_check"])],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="main:electricity")],
        ])
    )
    await call.answer()

@dp.callback_query(F.data == "elec:contacts")
async def elec_contacts(call: CallbackQuery):
    await call.message.edit_text(
        "⚡ <b>АТ «ТЕРНОПІЛЬОБЛЕНЕРГО»</b>\n\n"
        "☎️ Кол-центр: <b>0-800-40-90-40</b> — цілодобово, безкоштовно в Україні\n"
        "📞 Додатково: 097-993-42-22; 063-993-42-22; 050-993-42-22\n"
        "📍 вул. Енергетична, 2, м. Тернопіль\n\n"
        "Офіційний сайт містить графіки погодинних, аварійних "
        "та планових відключень.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌐 Офіційний сайт", url=OFFICIAL["electricity"])],
            [InlineKeyboardButton(text="🔎 Перевірити адресу", url=OFFICIAL["power_check"])],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="main:electricity")],
        ])
    )
    await call.answer()

@dp.callback_query(F.data == "elec:info")
async def elec_info(call: CallbackQuery):
    await call.message.edit_text(
        "ℹ️ <b>ЯК ПЕРЕВІРИТИ ВІДКЛЮЧЕННЯ</b>\n\n"
        "1️⃣ Відкрийте сервіс «Чому немає світла?».\n"
        "2️⃣ Введіть населений пункт.\n"
        "3️⃣ Введіть вулицю.\n"
        "4️⃣ Введіть номер будинку.\n"
        "5️⃣ Сервіс покаже підчергу та години відключення/відновлення, "
        "якщо дані доступні.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔎 Відкрити сервіс", url=OFFICIAL["power_check"])],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="main:electricity")],
        ])
    )
    await call.answer()

@dp.callback_query(F.data == "elec:subscription")
async def elec_subscription(call: CallbackQuery):
    place = get_subscription(call.from_user.id)
    text = "🔔 <b>МОЯ ПІДПИСКА</b>\n\n"
    if place:
        text += f"📍 Ви підписані на: <b>{place}</b>\n\n"
        text += "Бот може надсилати вам повідомлення, які адміністратор опублікує для цього населеного пункту."
    else:
        text += "Ви ще не маєте активної підписки."
    await call.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📍 Обрати населений пункт", callback_data="elec:places")],
            [InlineKeyboardButton(text="🔕 Відписатися", callback_data="unsubscribe")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="main:electricity")],
        ])
    )
    await call.answer()

@dp.callback_query(F.data.startswith("contact:"))
async def contact(call: CallbackQuery):
    key = call.data.split(":")[1]
    if key in CONTACTS:
        item = CONTACTS[key]
        await call.message.edit_text(
            item["text"], parse_mode="HTML",
            reply_markup=url_keyboard(item["url"], item.get("map"))
        )
    elif key == "dsns":
        await call.message.edit_text(
            "🚒 <b>ДСНС</b>\n\n"
            "🚨 Пожежа / рятувальна служба: <b>101</b>\n"
            "📞 Головне управління ДСНС у Тернопільській області:\n"
            "+380 352 43-43-30\n\n"
            "Для негайної небезпеки телефонуйте 101.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🌐 ДСНС Тернопільщини", url=OFFICIAL["dsns"])],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="main:contacts")],
            ])
        )
    elif key == "emergency":
        await call.message.edit_text(
            "🚨 <b>ЕКСТРЕНІ НОМЕРИ</b>\n\n"
            "🚒 Пожежа / рятувальники — <b>101</b>\n"
            "👮 Поліція — <b>102</b>\n"
            "🚑 Швидка допомога — <b>103</b>\n"
            "🔥 Аварійна газова служба — <b>104</b>\n\n"
            "У разі безпосередньої загрози життю телефонуйте відповідній службі.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="main:contacts")],
            ])
        )
    elif key == "gas":
        await call.message.edit_text(
            "🔥 <b>ГАЗ</b>\n\n"
            "🚨 Аварійна газова служба: <b>104</b>\n"
            "📞 Контакти ГК «Нафтогаз України»:\n"
            "066-300-2-888\n098-300-2-888\n093-300-2-888\n\n"
            "Показання лічильника можна передавати онлайн.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🌐 Контакти Нафтогазу", url=OFFICIAL["gas"])],
                [InlineKeyboardButton(text="🧾 Передати показання", url=OFFICIAL["gas_indicators"])],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="main:contacts")],
            ])
        )
    elif key == "power":
        await call.message.edit_text(
            "⚡ <b>ЕЛЕКТРОМЕРЕЖІ</b>\n\n"
            "АТ «Тернопільобленерго»\n"
            "☎️ 0-800-40-90-40 — цілодобово\n"
            "📞 097-993-42-22\n"
            "📞 063-993-42-22\n"
            "📞 050-993-42-22",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🌐 Офіційний сайт", url=OFFICIAL["electricity"])],
                [InlineKeyboardButton(text="🔎 Перевірити адресу", url=OFFICIAL["power_check"])],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="main:contacts")],
            ])
        )
    await call.answer()

@dp.callback_query(F.data == "important:gas")
async def important_gas(call: CallbackQuery):
    await call.message.edit_text(
        "🔥 <b>ЯКЩО ВИ ВІДЧУЛИ ЗАПАХ ГАЗУ</b>\n\n"
        "1. Перекрийте газові крани, якщо це безпечно.\n"
        "2. Відкрийте вікна та двері.\n"
        "3. Не вмикайте і не вимикайте електроприлади.\n"
        "4. Вийдіть із приміщення.\n"
        "5. Зателефонуйте <b>104</b>.",
        parse_mode="HTML",
        reply_markup=important_menu()
    )
    await call.answer()

@dp.callback_query(F.data == "important:power")
async def important_power(call: CallbackQuery):
    await call.message.edit_text(
        "⚡ <b>АВАРІЯ ЕЛЕКТРОМЕРЕЖІ</b>\n\n"
        "Перевірте стан електропостачання за адресою на офіційному сервісі "
        "АТ «Тернопільобленерго» або телефонуйте 0-800-40-90-40.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔎 Перевірити адресу", url=OFFICIAL["power_check"])],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="main:important")],
        ])
    )
    await call.answer()

@dp.callback_query(F.data == "important:water")
async def important_water(call: CallbackQuery):
    await call.message.edit_text(
        "💧 <b>АВАРІЯ ВОДОПОСТАЧАННЯ</b>\n\n"
        "КП «Зборівський водоканал»\n"
        "☎️ +380 67 260 08 23\n"
        "☎️ +380 3540 21209\n"
        "📍 вул. Козацька, 3, м. Зборів",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="main:important")],
        ])
    )
    await call.answer()

@dp.callback_query(F.data == "settings:about")
async def settings_about(call: CallbackQuery):
    await call.message.edit_text(
        "ℹ️ <b>ПРО БОТА</b>\n\n"
        "«Зборівська громада | Світ» — інформаційний Telegram-бот "
        "для жителів Зборівської громади.\n\n"
        "Основні функції:\n"
        "⚡ відключення та підписки;\n"
        "📞 корисні контакти;\n"
        "🏛️ інформація про громаду;\n"
        "🤖 автоматична довідка;\n"
        "🔗 посилання на офіційні джерела.",
        parse_mode="HTML",
        reply_markup=back_main()
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

    post_text = f"📍 <b>{settlement}</b>\n\n{body}\n\n#ЗборівськаГромада"
    sent_to = 0
    if CHANNEL_ID:
        try:
            await bot.send_message(CHANNEL_ID, post_text, parse_mode="HTML")
        except Exception as e:
            await message.answer(
                "⚠️ Не вдалося опублікувати в канал. Перевір CHANNEL_ID і права бота.\n\n"
                f"Помилка: {e}"
            )
            return
    for user_id in subscribers(settlement):
        try:
            await bot.send_message(user_id, post_text, parse_mode="HTML")
            sent_to += 1
        except Exception:
            pass
    await message.answer(
        f"✅ Опубліковано для <b>{settlement}</b>.\n"
        f"👥 Отримали повідомлення: {sent_to}",
        parse_mode="HTML",
    )

@dp.message()
async def assistant_chat(message: Message):
    text = (message.text or "").lower().strip()
    if not text:
        return

    # Простий 24/7 довідник без зовнішнього AI API.
    if any(x in text for x in ["поліці", "поліція", "102"]):
        item = CONTACTS["police"]
        await message.answer(item["text"], parse_mode="HTML", reply_markup=url_keyboard(item["url"], item["map"]))
    elif any(x in text for x in ["лікар", "лікарн", "медицин", "103", "швидк"]):
        item = CONTACTS["hospital"]
        await message.answer(item["text"], parse_mode="HTML", reply_markup=url_keyboard(item["url"], item["map"]))
    elif any(x in text for x in ["міська рада", "мерія", "рада", "мер"]):
        item = CONTACTS["city"]
        await message.answer(item["text"], parse_mode="HTML", reply_markup=url_keyboard(item["url"], item["map"]))
    elif any(x in text for x in ["вод", "водоканал"]):
        item = CONTACTS["water"]
        await message.answer(item["text"], parse_mode="HTML", reply_markup=url_keyboard(item["url"], item["map"]))
    elif any(x in text for x in ["газ", "104"]):
        await message.answer(
            "🔥 Аварійна газова служба: <b>104</b>\n\n"
            "Якщо відчули запах газу — вийдіть із приміщення та телефонуйте 104.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🌐 Нафтогаз", url=OFFICIAL["gas"])],
                [InlineKeyboardButton(text="🏠 Головне меню", callback_data="main")],
            ])
        )
    elif any(x in text for x in ["світл", "електр", "відключ", "обленерго"]):
        await message.answer(
            "⚡ Для перевірки відключення введіть адресу на офіційному сервісі "
            "АТ «Тернопільобленерго».",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔎 Перевірити адресу", url=OFFICIAL["power_check"])],
                [InlineKeyboardButton(text="⚡ Меню електроенергії", callback_data="main:electricity")],
            ])
        )
    elif any(x in text for x in ["цнап", "адмін", "документ", "паспорт"]):
        await message.answer(
            "📄 <b>ЦНАП / адміністративні послуги</b>\n\n"
            "Для актуальних адрес, графіка та переліку послуг відкрийте офіційний "
            "сайт Зборівської громади.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🌐 Сайт громади", url=OFFICIAL["community"])],
                [InlineKeyboardButton(text="🏠 Головне меню", callback_data="main")],
            ])
        )
    else:
        await message.answer(
            "🤖 Я поки не знайшов точної відповіді на це питання.\n\n"
            "Спробуйте написати простіше, наприклад:\n"
            "• «Де поліція?»\n"
            "• «Телефон лікарні»\n"
            "• «Коли світло?»\n"
            "• «Де ЦНАП?»\n"
            "• «Телефон водоканалу»\n\n"
            "Або відкрийте головне меню.",
            reply_markup=back_main()
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

