asyncio
import logging
import os
import sqlite3
import json
import urllib.request
import urllib.error
from pathlib import Path
from urllib.parse import quote

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.filters.command import CommandObject
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
COMMUNITY_CHAT_URL = os.getenv("COMMUNITY_CHAT_URL", "").strip()
ALERTS_API_TOKEN = os.getenv("ALERTS_API_TOKEN", "").strip()
ALERTS_POLL_SECONDS = int(os.getenv("ALERTS_POLL_SECONDS", "10"))

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
    con.execute(
        """CREATE TABLE IF NOT EXISTS alarm_subscriptions (
            user_id INTEGER PRIMARY KEY,
            settlement TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    con.execute(
        """CREATE TABLE IF NOT EXISTS bot_feedback (
            user_id INTEGER PRIMARY KEY,
            rating TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
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

def set_alarm_subscription(user_id: int, settlement: str):
    con = db()
    con.execute(
        "INSERT INTO alarm_subscriptions(user_id, settlement) VALUES(?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET settlement=excluded.settlement",
        (user_id, settlement),
    )
    con.commit()
    con.close()

def remove_alarm_subscription(user_id: int):
    con = db()
    con.execute("DELETE FROM alarm_subscriptions WHERE user_id=?", (user_id,))
    con.commit()
    con.close()

def get_alarm_subscription(user_id: int):
    con = db()
    row = con.execute(
        "SELECT settlement FROM alarm_subscriptions WHERE user_id=?", (user_id,)
    ).fetchone()
    con.close()
    return row[0] if row else None

def alarm_subscribers():
    con = db()
    rows = con.execute("SELECT user_id, settlement FROM alarm_subscriptions").fetchall()
    con.close()
    return rows

def set_feedback(user_id: int, rating: str):
    con = db()
    con.execute(
        "INSERT INTO bot_feedback(user_id, rating) VALUES(?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET rating=excluded.rating, updated_at=CURRENT_TIMESTAMP",
        (user_id, rating),
    )
    con.commit()
    con.close()

def get_feedback_stats():
    con = db()
    useful = con.execute("SELECT COUNT(*) FROM bot_feedback WHERE rating='useful'").fetchone()[0]
    not_useful = con.execute("SELECT COUNT(*) FROM bot_feedback WHERE rating='not_useful'").fetchone()[0]
    total = useful + not_useful
    con.close()
    return useful, not_useful, total

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# Громадський транспорт — актуальні онлайн-дані, перевірені у вересні 2026.
# Для кожного з 53 населених пунктів показуємо лише ті рейси, які вдалося
# підтвердити у відкритих актуальних онлайн-розкладах. Якщо підтвердженого
# рейсу немає — бот прямо про це повідомляє, без вигадування часу.
TRANSPORT_2026_BY_PLACE = {
    "Івачів": [], "Августівка": [], "Беримівці": ["Тернопіль → Манаїв: зупинка Беримівці близько 07:00 рейсу з Тернополя; зворотний час не підтверджено"],
    "Бзовиця": ["Бзовиця → Тернопіль: 08:30", "Тернопіль → Бзовиця: 13:10"],
    "Велика Плавуча": [], "Вовчківці": [], "Волосівка": [], "Вільшанка": [], "Вірлів": [],
    "Гарбузів": [], "Годів": ["Годів → Тернопіль: 06:55, 11:05", "Тернопіль → Годів: 09:55, 15:55"],
    "Грабківці": [], "Гукалівці": [], "Жабиня": ["Жабиня → Тернопіль: 08:10, 14:10, 18:20", "Тернопіль → Жабиня: 07:10, 13:15, 17:10"],
    "Жуківці": [], "Заруддя": ["Заруддя — зупинка рейсу Тернопіль → Жабиня; точний час проходження близько 14:08 для рейсу 13:00 з Тернополя"],
    "Зборів": ["Зборів → Красна: 07:15", "Зборів → Залізці: 12:10"],
    "Йосипівка": [], "Кабарівці": [], "Калинівка": [], "Кальне": ["Кальне → Тернопіль: 08:30, 12:15, 20:40", "Тернопіль → Кальне: 07:25, 11:00, 15:05, 19:30"],
    "Корчунок": [], "Коршилів": [], "Красна": ["Красна → Тернопіль: 09:22, 12:55", "Зборів → Красна: 07:15"],
    "Кудинівці": [], "Кудобинці": ["Кудобинці — зупинка рейсів Тернопіль → Манаїв / Білокриниця; у рейсі 07:00 до Манаєва — близько 08:12"],
    "Лавриківці": [], "Лопушани": [], "Манаїв": ["Манаїв → Тернопіль: 08:45, 10:25, 19:25", "Тернопіль → Манаїв: 07:55, 13:55, 17:05"],
    "Метенів": [], "Млинівці": [], "Монилівка": [], "Мшана": [], "Нище": ["Нище → Тернопіль: 08:05, 11:50, 17:30", "Тернопіль → Нище: 06:55, 10:40, 16:20"],
    "Озерянка": [], "Оліїв": [], "Перепельники": ["Перепельники — зупинка рейсу Тернопіль → Манаїв; у рейсі 07:00 — близько 08:36"],
    "Підгайчики": [], "Плісняни": [], "Погрібці": [], "Присівці": [], "Розгадів": [], "Славна": [],
    "Травотолоки": [], "Тустоголови": [], "Футори": [], "Хоробрів": [], "Хоростець": [], "Хоростець": [],
    "Храбузна": ["Храбузна → Тернопіль: 07:45, 16:25", "Тернопіль → Храбузна: 14:30"],
    "Цецівка": [], "Цицори": [], "Ярославичі": ["Ярославичі — зупинка рейсу Тернопіль → Манаїв; у рейсі 07:00 — близько 08:26"], "Ярчівці": []
}
# Нормалізація списку, щоб усі 53 населені пункти були присутні.
for _place in SETTLEMENTS:
    TRANSPORT_2026_BY_PLACE.setdefault(_place, [])

TRANSPORT_SOURCES_TEXT = (
    "Джерела: актуальні онлайн-табло та маршрути, доступні у вересні 2026. "
    "Перед поїздкою перевіряйте конкретну дату, бо перевізник може змінити рейс."
)

def transport_menu():
    b = InlineKeyboardBuilder()
    b.button(text="🏙️ Тернопіль → Зборів", callback_data="transport:to_zboriv")
    b.button(text="🏡 Зборів → Тернопіль", callback_data="transport:to_ternopil")
    b.button(text="🏘️ Розклад по населених пунктах громади", callback_data="transport:places:0")
    b.button(text="🏠 Головне меню", callback_data="main")
    b.adjust(1, 1, 1, 1)
    return b.as_markup()

def transport_places_keyboard(page: int = 0):
    total_pages = (len(SETTLEMENTS) + PAGE_SIZE - 1) // PAGE_SIZE
    page = max(0, min(page, total_pages - 1))
    start = page * PAGE_SIZE
    items = SETTLEMENTS[start:start + PAGE_SIZE]
    b = InlineKeyboardBuilder()
    for i, name in enumerate(items, start=start):
        mark = "🚌" if TRANSPORT_2026_BY_PLACE.get(name) else "📍"
        b.button(text=f"{mark} {name}", callback_data=f"transport:place:{i}")
    b.adjust(2)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"transport:places:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"transport:places:{page+1}"))
    b.row(*nav)
    b.row(InlineKeyboardButton(text="⬅️ Автобуси та розклад", callback_data="main:transport"))
    return b.as_markup()

def transport_place_text(place: str):
    rows = TRANSPORT_2026_BY_PLACE.get(place, [])
    if rows:
        body = "\n".join(f"• {r}" for r in rows)
        return (f"🚌 <b>{place}</b>\n\n{body}\n\n"
                "⚠️ Час може змінюватися. Перевіряйте рейс перед поїздкою.\n\n"
                f"ℹ️ {TRANSPORT_SOURCES_TEXT}")
    return (f"📍 <b>{place}</b>\n\n"
            "На момент перевірки я не знайшов у відкритих актуальних онлайн-джерелах "
            "підтвердженого рейсу 2026 року саме для цього населеного пункту.\n\n"
            "Я не буду вигадувати час рейсу. Якщо з'явиться підтверджений розклад, його можна додати в бот.\n\n"
            f"ℹ️ {TRANSPORT_SOURCES_TEXT}")

def transport_text(direction: str):
    if direction == "Тернопіль → Зборів":
        rows = [
            "07:00 → 07:55 — Тернопіль → Манаїв (Зборів як проміжна зупинка)",
            "07:50 → 08:45 — Тернопіль → Білокриниця (Зборів як проміжна зупинка)",
            "12:50 → 13:50 — Тернопіль → Манаїв (Зборів як проміжна зупинка)",
            "13:00 → 13:55 — Тернопіль → Жабиня (Зборів як проміжна зупинка)",
        ]
    else:
        rows = ["Зборів → Тернопіль — доступні рейси залежать від конкретної дати; перевіряйте актуальну сторінку розкладу."]
    return f"🚌 <b>{direction}</b>\n\n" + "\n".join(f"• {r}" for r in rows) + "\n\n⚠️ Розклад може змінюватися перевізником."


# АКТУАЛЬНІ ДАНІ ТРАНСПОРТУ 2026
TRANSPORT_2026 = {
    "Тернопіль → Зборів": {
        "summary": "32 рейси на добу; перший 06:15, останній 18:40.",
        "source": "https://railukraine.com/uk/rozklad-avtobusiv/ternopil/zboriv",
        "examples": [
            "06:15 → 07:02 — через Зборів, далі Заруддя та Жабиня",
            "07:00 → 07:55 — рейс до Манаєва",
            "12:50 → 13:50 — рейс до Манаєва; далі Кудобинці, Ярославичі, Перепельники",
            "13:00 → 13:55 — рейс до Жабині",
            "13:15 → 14:09 — рейс до Жабині",
        ],
    },
    "Зборів → Тернопіль": {
        "summary": "Актуальні рейси потрібно перевіряти для конкретної дати.",
        "source": "https://ticket.bus.com.ua/",
        "examples": [],
    },
}
TRANSPORT_SETTLEMENTS_2026 = {
    "Кудобинці": "Рейс Тернопіль → Манаїв проходить через Кудобинці.",
    "Ярославичі": "Рейс Тернопіль → Манаїв проходить через Ярославичі.",
    "Перепельники": "Рейс Тернопіль → Манаїв проходить через Перепельники.",
    "Заруддя": "Рейси Тернопіль → Жабиня проходять через Заруддя.",
    "Жабиня": "Є рейси на напрямку Тернопіль → Жабиня.",
    "Манаїв": "Є рейси на напрямку Тернопіль → Манаїв.",
    "Розгадів": "Є рейси на напрямку Тернопіль → Розгадів.",
    "Годів": "Є рейси у Зборівському напрямку.",
    "Кальне": "Є рейси у Зборівському напрямку.",
    "Нище": "Є рейси у Зборівському напрямку.",
    "Лопушани": "Є рейси у Зборівському напрямку.",
}

def main_menu():
    b = InlineKeyboardBuilder()
    b.button(text="🏢 Комунальні послуги", callback_data="main:utilities")
    b.button(text="🚌 Автобуси та розклад", callback_data="main:transport")
    b.button(text="📞 Корисні контакти", callback_data="main:contacts")
    b.button(text="🚕 Таксі", callback_data="main:taxi")
    b.button(text="🚗 Водієві", callback_data="main:drivers")
    b.button(text="🏛️ Про громаду", callback_data="main:community")
    b.button(text="📰 Новини", callback_data="main:news")
    b.button(text="💬 Спілкування 24/7", callback_data="main:community_chat")
    b.button(text="🚨 Тривога", callback_data="main:alarm")
    b.adjust(2, 2, 2, 2, 1)
    b.row(
        InlineKeyboardButton(text="👍 Корисний", callback_data="feedback:useful"),
        InlineKeyboardButton(text="👎 Не корисний", callback_data="feedback:not_useful"),
    )
    return b.as_markup()

def drivers_menu():
    b = InlineKeyboardBuilder()
    b.button(text="🔧 Контакти СТО", callback_data="driver:sto")
    b.button(text="🛞 Магазини автозапчастин", callback_data="driver:parts")
    b.button(text="🏠 Головне меню", callback_data="main")
    b.adjust(1, 1, 1)
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
    b.button(text="🚑 Екстрені номери", callback_data="contact:emergency")
    b.button(text="🍽️ Ресторани", callback_data="contact:restaurants")
    b.button(text="🔧 СТО", callback_data="contact:sto")
    b.button(text="👮 Поліція", callback_data="contact:police")
    b.button(text="🏥 Лікарня", callback_data="contact:hospital")
    b.button(text="🏛️ Міська рада", callback_data="contact:city")
    b.button(text="💧 Водоканал", callback_data="contact:water")
    b.button(text="🔥 Газова служба", callback_data="contact:gas")
    b.button(text="⚡ Електромережі", callback_data="contact:power")
    b.button(text="🚕 Таксі", callback_data="contact:taxi")
    b.button(text="🏠 Головне меню", callback_data="main")
    b.adjust(2, 2, 2, 2, 2, 1)
    return b.as_markup()

def utilities_menu():
    b = InlineKeyboardBuilder()
    b.button(text="💧 Водоканал", callback_data="utility:water")
    b.button(text="⚡ Електроенергія", callback_data="main:electricity")
    b.button(text="🏢 Комунальні служби", callback_data="utility:other")
    b.button(text="🏠 Головне меню", callback_data="main")
    b.adjust(2, 1, 1)
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
        "🏡 <b>Вітаємо у «Зборів | Моя громада»!</b>\n\n"
        "📌 <b>Оберіть потрібний розділ нижче:</b>\n\n"
        "🛡️ <b>Ми дбаємо про безпеку та приватність.</b>\n"
        "Бот не має доступу до вашого акаунта в Telegram, ваших повідомлень чи особистих чатів.\n\n"
        "💻 <b>Бот розроблений місцевими розробниками — мешканцями Зборівської громади.</b> 🇺🇦\n\n"
        "🤝 Ми створили його, щоб зібрати в одному місці корисну, актуальну та важливу інформацію для жителів нашої громади.\n\n"
        "❤️ <b>Дякуємо, що користуєтеся «Зборів | Моя громада»!</b>"
    )
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, parse_mode="HTML", reply_markup=main_menu())
        await target.answer()
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=main_menu())

def bot_deep_link_menu():
    # Кнопки під інформаційними постами: швидкий перехід у потрібний розділ + оцінка поста.
    base = "https://t.me/zboriv_gromada_bot"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ Світло", url=f"{base}?start=electricity"),
         InlineKeyboardButton(text="🚨 Тривога", url=f"{base}?start=alarm")],
        [InlineKeyboardButton(text="🚌 Транспорт", url=f"{base}?start=transport"),
         InlineKeyboardButton(text="📞 Контакти", url=f"{base}?start=contacts")],
        [InlineKeyboardButton(text="🏢 Комунальні", url=f"{base}?start=utilities"),
         InlineKeyboardButton(text="🚗 Водієві", url=f"{base}?start=drivers")],
        [InlineKeyboardButton(text="🏛️ Про громаду", url=f"{base}?start=community"),
         InlineKeyboardButton(text="📰 Новини", url=f"{base}?start=news")],
        [InlineKeyboardButton(text="💬 Чат 24/7", url=f"{base}?start=community_chat"),
         InlineKeyboardButton(text="🤖 Відкрити бота", url=base)],
        [InlineKeyboardButton(text="👍 Корисний", callback_data="feedback:post_useful"),
         InlineKeyboardButton(text="👎 Не корисний", callback_data="feedback:post_not_useful")],
    ])


@dp.message(CommandStart())
async def start(message: Message, command: CommandObject):
    db()
    payload = (command.args or "").strip().lower()
    if payload == "electricity":
        await message.answer(
            "⚡ <b>ЕЛЕКТРОЕНЕРГІЯ</b>\n\n"
            "Оберіть свій населений пункт, щоб налаштувати підписку та отримувати повідомлення.",
            parse_mode="HTML", reply_markup=electricity_menu()
        )
        return
    if payload == "alarm":
        status = get_alarm_subscription(message.from_user.id)
        api_status = (
            "\n\n🟢 Автоматичні сповіщення підключені." if ALERTS_API_TOKEN
            else "\n\n🟡 Для автоматичних сповіщень адміністратору потрібно підключити API."
        )
        current = f"\n\n📍 Ваша локація: <b>{status}</b>" if status else ""
        await message.answer(
            "🚨 <b>ПОВІТРЯНА ТРИВОГА</b>\n\n"
            "Оберіть населений пункт для підписки на сповіщення про тривогу та відбій."
            + current + api_status,
            parse_mode="HTML", reply_markup=alarm_menu(message.from_user.id)
        )
        return
    deep_links = {
        "utilities": ("🏢 <b>КОМУНАЛЬНІ ПОСЛУГИ</b>", utilities_menu),
        "transport": ("🚌 <b>АВТОБУСИ ТА РОЗКЛАД</b>", transport_menu),
        "contacts": ("📞 <b>КОРИСНІ КОНТАКТИ</b>", contacts_menu),
        "drivers": ("🚗 <b>ВОДІЄВІ</b>", drivers_menu),
    }
    if payload in deep_links:
        title, menu_fn = deep_links[payload]
        await message.answer(title + "\n\nОберіть потрібний розділ:", parse_mode="HTML", reply_markup=menu_fn())
        return
    if payload == "community":
        await message.answer(
            "🏛️ <b>ПРО ЗБОРІВСЬКУ ГРОМАДУ</b>\n\nОберіть потрібну інформацію.",
            parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🌐 Офіційний сайт", url=OFFICIAL["community"])],
                [InlineKeyboardButton(text="🏠 Головне меню", callback_data="main")]
            ])
        )
        return
    if payload == "news":
        await message.answer(
            "📰 <b>НОВИНИ</b>\n\nАктуальні новини та важливі повідомлення громади.",
            parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🌐 Новини громади", url=OFFICIAL["community"])],
                [InlineKeyboardButton(text="🏠 Головне меню", callback_data="main")]
            ])
        )
        return
    if payload == "community_chat":
        if COMMUNITY_CHAT_URL:
            await message.answer(
                "💬 <b>СПІЛКУВАННЯ 24/7</b>\n\nПриєднуйтесь до чату мешканців громади.",
                parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💬 Відкрити чат", url=COMMUNITY_CHAT_URL)],
                    [InlineKeyboardButton(text="🏠 Головне меню", callback_data="main")]
                ])
            )
        else:
            await show_main(message)
        return
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

@dp.message(Command("feedback"))
async def feedback_command(message: Message):
    useful, not_useful, total = get_feedback_stats()
    await message.answer(
        "⭐ <b>ОЦІНІТЬ БОТА</b>\n\n"
        "Наскільки цей бот корисний для вас?\n"
        "Ваш голос допоможе нам зрозуміти, що потрібно покращити.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="👍 Корисний", callback_data="feedback:useful"),
                InlineKeyboardButton(text="👎 Не корисний", callback_data="feedback:not_useful"),
            ],
            [InlineKeyboardButton(text=f"📊 Вже проголосували: {total}", callback_data="feedback:stats")]
        ])
    )

@dp.callback_query(F.data.in_({"feedback:post_useful", "feedback:post_not_useful"}))
async def post_feedback_vote(call: CallbackQuery):
    rating = "useful" if call.data == "feedback:post_useful" else "not_useful"
    set_feedback(call.from_user.id, rating)
    if rating == "useful":
        await call.answer("👍 Дякуємо! Пост корисний.", show_alert=False)
    else:
        await call.answer("👎 Дякуємо за думку! Будемо покращувати.", show_alert=False)

@dp.callback_query(F.data.in_({"feedback:useful", "feedback:not_useful"}))
async def feedback_vote(call: CallbackQuery):
    rating = "useful" if call.data == "feedback:useful" else "not_useful"
    set_feedback(call.from_user.id, rating)
    useful, not_useful, total = get_feedback_stats()
    message = (
        "Дякуємо! ❤️ Раді, що бот корисний."
        if rating == "useful"
        else "Дякуємо за чесну думку! 🙏 Ми будемо його покращувати."
    )
    await call.answer(message, show_alert=True)
    await call.message.edit_reply_markup(
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="👍 Корисний", callback_data="feedback:useful"),
                InlineKeyboardButton(text="👎 Не корисний", callback_data="feedback:not_useful"),
            ],
            [InlineKeyboardButton(text=f"📊 Відгуків: {total}", callback_data="feedback:stats")]
        ])
    )

@dp.callback_query(F.data == "feedback:stats")
async def feedback_stats(call: CallbackQuery):
    useful, not_useful, total = get_feedback_stats()
    useful_pct = round(useful * 100 / total) if total else 0
    not_useful_pct = 100 - useful_pct if total else 0
    await call.answer(
        f"👍 Корисний: {useful} ({useful_pct}%)\n"
        f"👎 Не корисний: {not_useful} ({not_useful_pct}%)",
        show_alert=True
    )

@dp.callback_query(F.data == "noop")
async def noop(call: CallbackQuery):
    await call.answer()

@dp.callback_query(F.data == "main")
async def main_callback(call: CallbackQuery):
    await show_main(call)

@dp.callback_query(F.data == "main:utilities")
async def main_utilities(call: CallbackQuery):
    await call.message.edit_text(
        "🏢 <b>КОМУНАЛЬНІ ПОСЛУГИ</b>\n\n"
        "Оберіть потрібну комунальну службу:",
        parse_mode="HTML", reply_markup=utilities_menu()
    )
    await call.answer()

@dp.callback_query(F.data == "utility:water")
async def utility_water(call: CallbackQuery):
    item = CONTACTS["water"]
    await call.message.edit_text(
        item["text"], parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌐 Деталі та контакти", url=item["url"])],
            [InlineKeyboardButton(text="⬅️ Комунальні послуги", callback_data="main:utilities")],
        ])
    )
    await call.answer()

@dp.callback_query(F.data == "utility:other")
async def utility_other(call: CallbackQuery):
    await call.message.edit_text(
        "🏢 <b>КОМУНАЛЬНІ СЛУЖБИ</b>\n\n"
        "Тут збиратимемо контакти та інформацію про інші комунальні послуги громади: "
        "благоустрій, вивезення відходів, аварійні служби та інші послуги.\n\n"
        "⚠️ Дані додаватимемо лише після перевірки актуальних контактів.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Комунальні послуги", callback_data="main:utilities")],
        ])
    )
    await call.answer()

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

@dp.callback_query(F.data == "main:taxi")
async def main_taxi(call: CallbackQuery):
    await call.message.edit_text(
        "🚕 <b>ТАКСІ ЗБОРІВ</b>\n\n"
        "📞 Оберіть водія та натисніть кнопку, щоб одразу зателефонувати.\n\n"
        "👤 <b>Богдан</b>\n"
        "👤 <b>Богдан</b>\n"
        "👤 <b>Міша</b>\n"
        "👤 <b>Василь</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📞 Зателефонувати • 068 227 00 89", url="tel:+380682270089")],
            [InlineKeyboardButton(text="📞 Зателефонувати • 068 147 19 52", url="tel:+380681471952")],
            [InlineKeyboardButton(text="📞 Зателефонувати • 096 255 36 44", url="tel:+380962553644")],
            [InlineKeyboardButton(text="📞 Зателефонувати • 068 999 68 44", url="tel:+380689996844")],
            [InlineKeyboardButton(text="⬅️ Корисні контакти", callback_data="main:contacts"),
             InlineKeyboardButton(text="🏠 Головне меню", callback_data="main")],
        ])
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

@dp.callback_query(F.data == "transport:trains")
async def transport_trains(call: CallbackQuery):
    await call.message.edit_text(
        "🚆 <b>ЕЛЕКТРИЧКИ: ТЕРНОПІЛЬ ↔ ЗБОРІВ</b>\n\n"
        "Розклад потрібно перевіряти на конкретну дату, оскільки він може змінюватися.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚆 Тернопіль → Зборів", url="https://poizdato.net/rozklad-poizdiv/ternopil--zboriv/elektrychky/")],
            [InlineKeyboardButton(text="🚆 Зборів → Тернопіль", url="https://poizdato.net/rozklad-poizdiv/zboriv--ternopil/elektrychky/")],
            [InlineKeyboardButton(text="⬅️ Автобуси та розклад", callback_data="main:transport")]
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

@dp.callback_query(F.data.startswith("transport:places:"))
async def transport_places(call: CallbackQuery):
    page = int(call.data.split(":")[-1])
    await call.message.edit_text(
        "🏘️ <b>ОБЕРІТЬ НАСЕЛЕНИЙ ПУНКТ</b>\n\n"
        "🚌 — є підтверджені онлайн-дані про рейси.\n"
        "📍 — на момент перевірки підтвердженого розкладу 2026 не знайдено.",
        parse_mode="HTML", reply_markup=transport_places_keyboard(page)
    )
    await call.answer()

@dp.callback_query(F.data.startswith("transport:place:"))
async def transport_place(call: CallbackQuery):
    index = int(call.data.split(":")[-1])
    place = SETTLEMENTS[index]
    await call.message.edit_text(
        transport_place_text(place),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔎 Перевірити онлайн-розклад", url=OFFICIAL["bus_station"])],
            [InlineKeyboardButton(text="⬅️ До населених пунктів", callback_data="transport:places:0")],
            [InlineKeyboardButton(text="🏠 Автобуси та розклад", callback_data="main:transport")],
        ])
    )
    await call.answer()

@dp.callback_query(F.data == "main:drivers")
async def main_drivers(call: CallbackQuery):
    await call.message.edit_text(
        "🚗 <b>ВОДІЄВІ</b>\n\n"
        "<b>Все для автомобіліста</b> — корисні контакти та сервіси для водіїв у Зборові та громаді.",
        parse_mode="HTML", reply_markup=drivers_menu()
    )
    await call.answer()

@dp.callback_query(F.data == "driver:sto")
async def driver_sto(call: CallbackQuery):
    url = "https://www.google.com/maps/search/?api=1&query=" + quote("СТО Зборів Тернопільська область")
    await call.message.edit_text(
        "🔧 <b>КОНТАКТИ СТО</b>\n\n"
        "Знайти найближчі станції технічного обслуговування у Зборові можна на карті.\n\n"
        "⚠️ Перед візитом рекомендуємо уточнити графік роботи та наявність потрібної послуги.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📍 СТО у Зборові", url=url)],
            [InlineKeyboardButton(text="⬅️ Водієві", callback_data="main:drivers")],
        ])
    )
    await call.answer()

@dp.callback_query(F.data == "driver:parts")
async def driver_parts(call: CallbackQuery):
    url = "https://www.google.com/maps/search/?api=1&query=" + quote("магазин автозапчастин Зборів Тернопільська область")
    await call.message.edit_text(
        "🛞 <b>МАГАЗИНИ АВТОЗАПЧАСТИН</b>\n\n"
        "Знайти магазини автозапчастин у Зборові та поблизу можна на карті.\n\n"
        "⚠️ Наявність деталей та графік роботи краще уточнювати безпосередньо перед поїздкою.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📍 Автозапчастини у Зборові", url=url)],
            [InlineKeyboardButton(text="⬅️ Водієві", callback_data="main:drivers")],
        ])
    )
    await call.answer()

@dp.callback_query(F.data == "main:community_chat")
async def main_community_chat(call: CallbackQuery):
    if COMMUNITY_CHAT_URL:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 Відкрити чат громади 24/7", url=COMMUNITY_CHAT_URL)],
            [InlineKeyboardButton(text="🏠 Головне меню", callback_data="main")],
        ])
        text = (
            "💬 <b>СПІЛКУВАННЯ 24/7</b>\n\n"
            "Приєднуйтесь до чату мешканців Зборівської громади.\n"
            "Обговорення, допомога, оголошення та спілкування між жителями."
        )
    else:
        kb = back_main()
        text = (
            "💬 <b>СПІЛКУВАННЯ 24/7</b>\n\n"
            "Чат громади ще не підключено.\n\n"
            "Після створення Telegram-групи її посилання потрібно додати в Railway "
            "у змінну <code>COMMUNITY_CHAT_URL</code>."
        )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await call.answer()

def alarm_places_keyboard(page: int = 0):
    total_pages = (len(SETTLEMENTS) + PAGE_SIZE - 1) // PAGE_SIZE
    page = max(0, min(page, total_pages - 1))
    start = page * PAGE_SIZE
    items = SETTLEMENTS[start:start + PAGE_SIZE]
    b = InlineKeyboardBuilder()
    for i, name in enumerate(items, start=start):
        b.button(text=f"📍 {name}", callback_data=f"alarmplace:{i}")
    b.adjust(2)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"alarmplaces:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="Далі ➡️", callback_data=f"alarmplaces:{page+1}"))
    b.row(*nav)
    b.row(InlineKeyboardButton(text="🏠 Головне меню", callback_data="main"))
    return b.as_markup()

def alarm_menu(user_id: int):
    current = get_alarm_subscription(user_id)
    rows = [
        [InlineKeyboardButton(text="🚨 Відкрити карту тривог", url="https://map.ukrainealarm.com/")],
        [InlineKeyboardButton(text="🔔 Підписатися за моєю локацією", callback_data="alarm:location")],
    ]
    if current:
        rows.append([InlineKeyboardButton(text=f"📍 Моя локація: {current}", callback_data="alarm:status")])
        rows.append([InlineKeyboardButton(text="🔕 Відписатися від тривог", callback_data="alarm:unsubscribe")])
    rows.append([InlineKeyboardButton(text="🏠 Головне меню", callback_data="main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

@dp.callback_query(F.data == "main:alarm")
async def main_alarm(call: CallbackQuery):
    current = get_alarm_subscription(call.from_user.id)
    status = f"\n\n📍 Ваша локація: <b>{current}</b>" if current else "\n\n📍 Локацію для сповіщень ще не обрано."
    api_status = (
        "\n\n🟢 Автоматичні сповіщення підключені." if ALERTS_API_TOKEN
        else "\n\n🟡 Для автоматичних сповіщень потрібно додати <code>ALERTS_API_TOKEN</code> у Railway."
    )
    await call.message.edit_text(
        "🚨 <b>ПОВІТРЯНА ТРИВОГА</b>\n\n"
        "Оберіть населений пункт і бот автоматично надсилатиме повідомлення про початок тривоги та відбій. "
        "Також можна відкрити офіційну карту." + status + api_status,
        parse_mode="HTML", reply_markup=alarm_menu(call.from_user.id)
    )
    await call.answer()

@dp.callback_query(F.data == "alarm:location")
async def alarm_location(call: CallbackQuery):
    await call.message.edit_text(
        "📍 <b>ОБЕРІТЬ НАСЕЛЕНИЙ ПУНКТ</b>\n\n"
        "Саме для нього ви отримуватимете повідомлення про повітряну тривогу та відбій.",
        parse_mode="HTML", reply_markup=alarm_places_keyboard(0)
    )
    await call.answer()

@dp.callback_query(F.data.startswith("alarmplaces:"))
async def alarm_places_page(call: CallbackQuery):
    p = int(call.data.split(":")[1])
    await call.message.edit_reply_markup(reply_markup=alarm_places_keyboard(p))
    await call.answer()

@dp.callback_query(F.data.startswith("alarmplace:"))
async def alarm_place(call: CallbackQuery):
    index = int(call.data.split(":")[1])
    settlement = SETTLEMENTS[index]
    set_alarm_subscription(call.from_user.id, settlement)
    await call.message.edit_text(
        f"🔔 <b>Сповіщення увімкнено</b>\n\n"
        f"📍 Локація: <b>{settlement}</b>\n\n"
        "Тепер бот перевірятиме актуальний статус тривоги та надсилатиме повідомлення про початок і відбій.\n\n"
        "⚠️ Це інформаційний сервіс. У разі небезпеки орієнтуйтеся на офіційні сповіщення та негайно прямуйте в укриття.",
        parse_mode="HTML", reply_markup=alarm_menu(call.from_user.id)
    )
    await call.answer("Сповіщення увімкнено ✅")

@dp.callback_query(F.data == "alarm:status")
async def alarm_status(call: CallbackQuery):
    place = get_alarm_subscription(call.from_user.id)
    text = (
        f"🔔 <bПІДПИСКА НА ТРИВОГУ</b>\n\n📍 Ваша локація: <b>{place}</b>\n\n"
        "Автоматичні сповіщення активні." if place else
        "🔔 <b>ПІДПИСКА</b>\n\nЛокацію ще не обрано."
    )
    # Correct malformed tag defensively for old clients/code edits.
    text = text.replace("<bПІДПИСКА", "<b>ПІДПИСКА")
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=alarm_menu(call.from_user.id))
    await call.answer()

@dp.callback_query(F.data == "alarm:unsubscribe")
async def alarm_unsubscribe(call: CallbackQuery):
    remove_alarm_subscription(call.from_user.id)
    await call.message.edit_text(
        "🔕 <b>Сповіщення про повітряні тривоги вимкнено.</b>",
        parse_mode="HTML", reply_markup=alarm_menu(call.from_user.id)
    )
    await call.answer("Відписано ✅")

async def fetch_active_alerts():
    if not ALERTS_API_TOKEN:
        return None
    url = "https://api.alerts.in.ua/v1/alerts/active.json"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {ALERTS_API_TOKEN}"})
    def _get():
        with urllib.request.urlopen(req, timeout=8) as response:
            return json.loads(response.read().decode("utf-8"))
    try:
        return await asyncio.to_thread(_get)
    except Exception as exc:
        logging.warning("Alerts API error: %s", exc)
        return None

def alert_applies_to_settlement(alert: dict, settlement: str) -> bool:
    if alert.get("alert_type") != "air_raid":
        return False
    title = str(alert.get("location_title", "")).lower()
    raion = str(alert.get("location_raion", "")).lower()
    oblast = str(alert.get("location_oblast", "")).lower()
    settlement_l = settlement.lower()
    # Exact community-level alert for Zboriv hromada.
    if "зборів" in title and ("громад" in title or alert.get("location_type") == "hromada"):
        return True
    # If API reports a specific settlement, match it.
    if settlement_l in title:
        return True
    # District/oblast-wide alert covers the user's settlement.
    if "тернопільськ" in oblast and alert.get("location_type") == "oblast":
        return True
    if "тернопільськ" in raion and alert.get("location_type") == "raion":
        return True
    return False

async def alerts_monitor(bot: Bot):
    if not ALERTS_API_TOKEN:
        logging.warning("ALERTS_API_TOKEN is not set; automatic alarm notifications are disabled.")
        return
    previous_active = set()
    while True:
        try:
            data = await fetch_active_alerts()
            if data is not None:
                alerts = data.get("alerts", []) if isinstance(data, dict) else []
                subs = alarm_subscribers()
                current_keys = set()
                for alert in alerts:
                    aid = str(alert.get("id", ""))
                    if not aid:
                        continue
                    for user_id, settlement in subs:
                        if alert_applies_to_settlement(alert, settlement):
                            key = (user_id, aid)
                            current_keys.add(key)
                            if key not in previous_active:
                                title = alert.get("location_title", "Території")
                                await bot.send_message(
                                    user_id,
                                    "🚨 <b>ПОВІТРЯНА ТРИВОГА!</b>\n\n"
                                    f"📍 Локація: <b>{settlement}</b>\n"
                                    f"📡 Джерело: {title}\n\n"
                                    "⚠️ Негайно прямуйте до укриття!",
                                    parse_mode="HTML",
                                )
                ended = previous_active - current_keys
                for user_id, aid in ended:
                    # A missing alert means the previously active alert ended.
                    place = get_alarm_subscription(user_id)
                    if place:
                        await bot.send_message(
                            user_id,
                            "🟢 <b>ВІДБІЙ ПОВІТРЯНОЇ ТРИВОГИ</b>\n\n"
                            f"📍 Локація: <b>{place}</b>",
                            parse_mode="HTML",
                        )
                previous_active = current_keys
        except Exception:
            logging.exception("Alarm monitor iteration failed")
        await asyncio.sleep(max(10, ALERTS_POLL_SECONDS))


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

@dp.callback_query(F.data == "contact:restaurants")
async def contact_restaurants(call: CallbackQuery):
    url = "https://www.google.com/maps/search/?api=1&query=" + quote("ресторани Зборів Тернопільська область")
    await call.message.edit_text(
        "🍽️ <b>РЕСТОРАНИ ТА ЗАКЛАДИ ХАРЧУВАННЯ</b>\n\n"
        "Переглянути актуальні заклади, адреси, телефони та графік роботи можна на карті.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🍽️ Відкрити ресторани на карті", url=url)],
            [InlineKeyboardButton(text="⬅️ Корисні контакти", callback_data="main:contacts")],
        ])
    )
    await call.answer()

@dp.callback_query(F.data == "contact:sto")
async def contact_sto(call: CallbackQuery):
    url = "https://www.google.com/maps/search/?api=1&query=" + quote("СТО Зборів Тернопільська область")
    await call.message.edit_text(
        "🔧 <b>СТО</b>\n\n"
        "Переглянути актуальні СТО, адреси, телефони та графік роботи можна на карті.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔧 Відкрити СТО на карті", url=url)],
            [InlineKeyboardButton(text="⬅️ Корисні контакти", callback_data="main:contacts")],
        ])
    )
    await call.answer()

@dp.callback_query(F.data == "contact:taxi")
async def contact_taxi(call: CallbackQuery):
    await call.message.edit_text(
        "🚕 <b>ТАКСІ ЗБОРІВ</b>\n"
        "⚡ <b>Швидкий виклик • доступні ціни</b>\n\n"
        "📞 Оберіть водія нижче та натисніть номер — дзвінок розпочнеться одразу.\n\n"
        "🚕 <b>Богдан</b>\n"
        "📞 068 227 00 89\n\n"
        "🚕 <b>Богдан</b>\n"
        "📞 068 147 19 52\n\n"
        "🚕 <b>Міша</b>\n"
        "📞 096 255 36 44\n\n"
        "🚕 <b>Василь</b>\n"
        "📞 068 999 68 44",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📞 Зателефонувати • 068 227 00 89", url="tel:+380682270089")],
            [InlineKeyboardButton(text="📞 Зателефонувати • 068 147 19 52", url="tel:+380681471952")],
            [InlineKeyboardButton(text="📞 Зателефонувати • 096 255 36 44", url="tel:+380962553644")],
            [InlineKeyboardButton(text="📞 Зателефонувати • 068 999 68 44", url="tel:+380689996844")],
            [InlineKeyboardButton(text="🏠 Головне меню", callback_data="main")],
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

@dp.message(Command("feedback_stats"))
async def feedback_stats_command(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Недоступно.")
        return
    useful, not_useful, total = get_feedback_stats()
    useful_pct = round(useful * 100 / total) if total else 0
    not_useful_pct = 100 - useful_pct if total else 0
    await message.answer(
        "📊 <b>СТАТИСТИКА ОЦІНКИ БОТА</b>\n\n"
        f"👍 Корисний: <b>{useful}</b> ({useful_pct}%)\n"
        f"👎 Не корисний: <b>{not_useful}</b> ({not_useful_pct}%)\n"
        f"👥 Усього оцінок: <b>{total}</b>",
        parse_mode="HTML"
    )

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

    raw = message.text or message.caption or ""
    payload = raw.partition(" ")[2].strip()
    if "\n" not in payload:
        await message.answer(
            "Формат без фото:\n"
            "<code>/post Кальне\n⚠️ Кальне: відключення з 14:00 до 18:00.</code>\n\n"
            "Або надішліть фото з таким самим текстом у підписі — бот опублікує фото + текст + кнопки.",
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

    post_text = (
        f"📍 <b>{settlement}</b>\n\n{body}\n\n"
        "🤖 <b>Зборів | Моя громада</b> — корисна інформація для жителів громади.\n"
        "Підписуйтеся на сповіщення та користуйтеся ботом.\n\n"
        "#ЗборівськаГромада"
    )
    keyboard = bot_deep_link_menu()
    sent_to = 0

    if CHANNEL_ID:
        try:
            if message.photo:
                await bot.send_photo(
                    CHANNEL_ID, message.photo[-1].file_id,
                    caption=post_text, parse_mode="HTML", reply_markup=keyboard
                )
            else:
                await bot.send_message(
                    CHANNEL_ID, post_text, parse_mode="HTML", reply_markup=keyboard
                )
        except Exception as e:
            await message.answer(
                "⚠️ Не вдалося опублікувати в канал/групу. Перевір CHANNEL_ID і права бота.\n\n"
                f"Помилка: {e}"
            )
            return

    for user_id in subscribers(settlement):
        try:
            if message.photo:
                await bot.send_photo(
                    user_id, message.photo[-1].file_id,
                    caption=post_text, parse_mode="HTML", reply_markup=keyboard
                )
            else:
                await bot.send_message(
                    user_id, post_text, parse_mode="HTML", reply_markup=keyboard
                )
            sent_to += 1
        except Exception:
            pass

    await message.answer(
        f"✅ Опубліковано для <b>{settlement}</b>.\n"
        f"👥 Отримали повідомлення: {sent_to}\n"
        "🔘 Додано кнопки: «Світло», «Тривога», «Відкрити бота».",
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
    asyncio.create_task(alerts_monitor(bot))
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
