import logging
import os
import re
import sqlite3
from pathlib import Path

import requests
from dotenv import load_dotenv
from flask import Flask, request


# Отдельная шаблонная версия. Ищет .env рядом с файлом и не использует ИИ.
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
app = Flask(__name__)

META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "").strip()
META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "").strip()
IG_ACCOUNT_ID = os.getenv("IG_ACCOUNT_ID", "").strip()
GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v26.0").strip()
TELEGRAM_BOT_URL = os.getenv("TELEGRAM_BOT_URL", "").strip()
DB_FILE = BASE_DIR / "chat_history_suytsai.db"

missing = [
    key
    for key, value in {
        "META_ACCESS_TOKEN": META_ACCESS_TOKEN,
        "META_VERIFY_TOKEN": META_VERIFY_TOKEN,
        "IG_ACCOUNT_ID": IG_ACCOUNT_ID,
    }.items()
    if not value or value.startswith("ВСТАВЬТЕ_")
]
if missing:
    raise RuntimeError("Заполни значения в .env: " + ", ".join(missing))

META_SEND_URL = f"https://graph.instagram.com/{GRAPH_API_VERSION}/{IG_ACCOUNT_ID}/messages"
DISCLAIMER = (
    "Это ознакомительный разбор по материалам философии Сюцай. Число показывает "
    "только один аспект и не описывает человека целиком."
)

MAIN_MENU = [
    {"type": "postback", "title": "Расчёт по дате", "payload": "DATE_CALC"},
    {"type": "postback", "title": "Темы разбора", "payload": "TOPICS"},
    {"type": "postback", "title": "Матрица", "payload": "MATRIX_INFO"},
]

TOPIC_MENU = [
    {"type": "postback", "title": "Отношения", "payload": "TOPIC_RELATIONSHIPS"},
    {"type": "postback", "title": "Цели", "payload": "TOPIC_GOALS"},
    {"type": "postback", "title": "Бизнес", "payload": "TOPIC_BUSINESS"},
]

AFTER_READING_BUTTONS = [
    {"type": "postback", "title": "Сравнить пару", "payload": "PAIR_COMPARE"},
    {"type": "postback", "title": "Другие темы", "payload": "TOPICS"},
    {"type": "postback", "title": "Главное меню", "payload": "HOME"},
]

MATRIX_FOLLOWUP_BUTTONS = TOPIC_MENU

HOME_INPUTS = {
    "привет",
    "здравствуйте",
    "здравствуй",
    "добрый день",
    "доброе утро",
    "добрый вечер",
    "салам",
    "салем",
    "хай",
    "hello",
    "hi",
    "меню",
    "главное меню",
    "старт",
    "начать",
    "/start",
    "отмена",
    "назад",
}

# Тексты трактовок предоставлены пользователем. Упоминания планет исключены.
CONSCIOUSNESS_PROFILES = {
    1: {
        "days": "1, 10, 19, 28",
        "vector": "лидерство, управление и покровительство",
        "plus": "инициативность, масштабное мышление, великодушие, уверенность, ответственность и умение вести людей",
        "minus": "авторитарность, эгоцентричность, гордыня и стремление делить людей на сторонников и противников",
        "task": "учиться делегировать, слышать окружающих и поддерживать людей без подавления их воли",
    },
    2: {
        "days": "2, 11, 20, 29",
        "vector": "понимание людей, ситуаций и окружающего мира",
        "plus": "эмпатия, дипломатичность, исполнительность и умение выстраивать партнёрство",
        "minus": "сомнения, нерешительность и поиск опоры только во внешних обстоятельствах",
        "task": "укреплять уверенность в собственных решениях и выходить из состояния колебания",
    },
    3: {
        "days": "3, 12, 21, 30",
        "vector": "знания, системность, анализ и управление",
        "plus": "аналитическое мышление, глубокие знания, умение наводить порядок и справедливо руководить",
        "minus": "категоричность и убеждённость, что существует только один правильный взгляд",
        "task": "быть открытым к другим мнениям и переходить от теории к практике",
    },
    4: {
        "days": "4, 13, 22, 31",
        "vector": "поиск справедливости, креативность и отдача энергии",
        "plus": "нестандартное мышление, новаторство, щедрость и способность обновлять устаревшие подходы",
        "minus": "неудовлетворённость, апатия и склонность разрушать вместо созидания",
        "task": "замечать ценное в настоящем и направлять креативность на созидание",
    },
    5: {
        "days": "5, 14, 23",
        "vector": "логика, выгода, коммуникация и интеллект",
        "plus": "коммуникабельность, склонность к бизнесу и торговле, гибкость и логический анализ",
        "minus": "обидчивость, эмоциональная отстранённость и беспечность",
        "task": "не позволять обидам мешать логике и развивать чуткость к людям",
    },
    6: {
        "days": "6, 15, 24",
        "vector": "комфорт, любовь, гармония и удовольствие от жизни",
        "plus": "житейская мудрость, обаяние, такт и способность создавать уют и гармонию",
        "minus": "лень, мстительность и стремление ставить удовольствия выше обязательств",
        "task": "поддерживать дисциплину, быть активнее и проявлять бескорыстную заботу",
    },
    7: {
        "days": "7, 16, 25",
        "vector": "признание, трансформация и быстрое воплощение идей",
        "plus": "интуиция, быстрая реакция и способность действовать в кризисных ситуациях",
        "minus": "хаотичность, вспыльчивость и трудности с выбором направления",
        "task": "поддерживать дисциплину и направлять энергию на осознанные перемены",
    },
    8: {
        "days": "8, 17, 26",
        "vector": "результат, управление процессами и практическая реализация",
        "plus": "дисциплина, ответственность, системный труд, реализм и основательность",
        "minus": "чрезмерный контроль, недоверие и эмоциональная закрытость",
        "task": "ослаблять тотальный контроль, учиться доверять и добавлять гибкость в работу",
    },
    9: {
        "days": "9, 18, 27",
        "vector": "победа, служение идее и готовность помогать",
        "plus": "смелость, решительность и готовность прийти на помощь",
        "minus": "вспыльчивость и импульсивные действия под влиянием сильных эмоций",
        "task": "сначала планировать действия и не принимать решения в эмоциональном порыве",
    },
}


def init_db():
    with sqlite3.connect(DB_FILE, timeout=10) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_state (
                user_id TEXT PRIMARY KEY,
                flow TEXT NOT NULL DEFAULT ''
            )
            """
        )


def save_event(user_id: str, role: str, content: str, event_id: str | None = None):
    with sqlite3.connect(DB_FILE, timeout=10) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO events (event_id, user_id, role, content) VALUES (?, ?, ?, ?)",
            (event_id, user_id, role, content),
        )


def get_flow(user_id: str) -> str:
    with sqlite3.connect(DB_FILE, timeout=10) as conn:
        row = conn.execute("SELECT flow FROM user_state WHERE user_id = ?", (user_id,)).fetchone()
    return row[0] if row else ""


def set_flow(user_id: str, flow: str):
    with sqlite3.connect(DB_FILE, timeout=10) as conn:
        conn.execute(
            "INSERT INTO user_state (user_id, flow) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET flow=excluded.flow",
            (user_id, flow),
        )


def digital_root(value: int) -> int:
    while value > 9:
        value = sum(int(digit) for digit in str(value))
    return value


def parse_birth_date(text: str) -> tuple[int, int | None] | None:
    """Возвращает (день, миссия или None) для ДД.ММ[.ГГГГ] либо одного дня."""
    value = text.strip()
    if re.fullmatch(r"\d{1,2}", value):
        day = int(value)
        return (day, None) if 1 <= day <= 31 else None

    match = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})(?:[./-](\d{4}))?", value)
    if not match:
        return None
    day, month = int(match.group(1)), int(match.group(2))
    year_text = match.group(3)
    if not (1 <= day <= 31 and 1 <= month <= 12):
        return None
    if not year_text:
        return day, None
    year = int(year_text)
    if not 1 <= year <= 9999:
        return None

    # В философии Сюцай Число Сознания считают по цифрам дня,
    # а Число Миссии — по цифрам полной даты рождения.
    consciousness = digital_root(day)
    mission = digital_root(sum(int(ch) for ch in f"{day:02d}{month:02d}{year:04d}"))
    return consciousness, mission


def birthday_reply(text: str, topic: str = "") -> str:
    parsed = parse_birth_date(text)
    if not parsed:
        return "Не распознал дату. Отправь полную дату в формате ДД.ММ.ГГГГ, например 31.05.2001."

    consciousness, mission = parsed
    return profile_reply(consciousness, mission, topic)


def profile_reply(consciousness: int, mission: int | None = None, topic: str = "") -> str:
    profile = CONSCIOUSNESS_PROFILES[consciousness]
    answer = (
        f"Твоё Число Сознания — {consciousness} (дни рождения: {profile['days']}).\n\n"
        f"🔹 Вектор: {profile['vector']}.\n"
        f"✨ В сильном проявлении: {profile['plus']}.\n"
        f"⚠️ В сложном проявлении: {profile['minus']}.\n"
        f"🎯 Задача для развития: {profile['task']}."
    )
    if mission is not None:
        answer += (
            f"\nПо полной дате получается Число Миссии {mission}. В философии Сюцай "
            "его рассматривают как отдельный аспект поведения и взаимодействия с людьми."
        )
    else:
        answer += "\nДля расчёта Числа Миссии отправь полную дату рождения ДД.ММ.ГГГГ."

    topic_text = {
        "relationships": (
            f"\n\nДля размышления об отношениях: какие ожидания ты уже проговорил(а) прямо? "
            f"Попробуй применить задачу из разбора: {profile['task']}."
        ),
        "goals": (
            f"\n\nПрактика для целей: выбери один результат на ближайшую неделю, "
            f"разбей его на шаги и начни с первого. Учитывай задачу из разбора: {profile['task']}."
        ),
        "business": (
            f"\n\nПодумай, где твоя сильная сторона может пригодиться в работе. "
            f"Выбери один небольшой следующий шаг и помни о задаче из разбора: {profile['task']}."
        ),
        "self": (
            f"\n\nДля самореализации запиши, в каких делах твои сильные стороны проявляются лучше всего. "
            f"Начать можно с задачи из разбора: {profile['task']}."
        ),
    }
    answer += topic_text.get(topic, "\n\nВыбери, что разобрать дальше: отношения, цели, бизнес или самореализацию.")
    return answer + "\n\n" + DISCLAIMER


def pair_reply(text: str) -> str | None:
    days = [int(value) for value in re.findall(r"(?<!\d)(\d{1,2})(?!\d)", text)]
    if len(days) < 2 or any(day < 1 or day > 31 for day in days[:2]):
        return None
    results = []
    for index, day in enumerate(days[:2], start=1):
        cs = digital_root(day)
        profile = CONSCIOUSNESS_PROFILES[cs]
        results.append(
            f"Человек {index}: день {day}, ЧС {cs}. Сильные стороны: {profile['plus']}. "
            f"Задача: {profile['task']}."
        )
    return (
        "Сравнение по ЧС — это повод обсудить различия, а не готовый вывод о совместимости.\n\n"
        + "\n\n".join(results)
        + "\n\nОбсудите, какие ожидания и способы общения важны каждому.\n\n"
        + DISCLAIMER
    )


def matrix_info() -> str:
    return (
        "В философии Сюцай матрица описывается как схема девяти энергий и двенадцати "
        "линий, связанных с разными сферами жизни. Полного алгоритма для персонального "
        "расчёта в доступных материалах нет, поэтому бот не будет придумывать матрицу "
        "по одной дате. Выбери другую тему: отношения, цели или бизнес.\n\n"
        + DISCLAIMER
    )


def home_text() -> str:
    return (
        "Привет! Могу посчитать Число Сознания и предложить разбор по отношениям, целям, "
        "бизнесу или самореализации. Также можно сравнить ЧС двух людей. Выбери кнопку или напиши вопрос."
    )


def respond_text(user_id: str, text: str) -> tuple[str, list[dict] | None]:
    normalized = text.strip().lower().replace("ё", "е")

    # Эти команды должны работать даже тогда, когда бот ждёт дату или дни пары.
    if normalized in HOME_INPUTS:
        set_flow(user_id, "")
        return home_text(), MAIN_MENU

    flow = get_flow(user_id)
    if flow.startswith("awaiting_date"):
        topic = flow.split(":", 1)[1] if ":" in flow else ""
        parsed = parse_birth_date(text)
        if parsed:
            set_flow(user_id, "")
            return birthday_reply(text, topic), AFTER_READING_BUTTONS
        if any(key in normalized for key in ("отношен", "пара", "совместим")):
            set_flow(user_id, "awaiting_date:relationships")
            return "Понял, разбираем отношения. Пришли полную дату рождения в формате ДД.ММ.ГГГГ.", None
        if any(key in normalized for key in ("бизнес", "работ", "карьер", "деньг")):
            set_flow(user_id, "awaiting_date:business")
            return "Понял, разбираем работу и бизнес. Пришли день рождения или полную дату.", None
        if any(key in normalized for key in ("цель", "план")):
            set_flow(user_id, "awaiting_date:goals")
            return "Понял, разберём цели. Пришли день рождения или полную дату.", None
        if any(key in normalized for key in ("самореализац", "предназнач", "развит")):
            set_flow(user_id, "awaiting_date:self")
            return "Понял, разберём самореализацию. Пришли день рождения или полную дату.", None
        return "Не распознал дату. Отправь полную дату в формате ДД.ММ.ГГГГ, например 31.05.2001. Можно также написать тему: отношения, цели, бизнес или самореализация.", None

    if flow == "awaiting_pair":
        result = pair_reply(text)
        if result:
            set_flow(user_id, "")
            return result, AFTER_READING_BUTTONS
        return "Отправь два дня рождения через запятую или союз «и», например: 15 и 8.", None

    parsed = parse_birth_date(text)
    if parsed and re.fullmatch(r"\s*(?:\d{1,2}|\d{1,2}[./-]\d{1,2}[./-]\d{4})\s*", text):
        return birthday_reply(text), AFTER_READING_BUTTONS

    if any(key in normalized for key in ("что такое сюцай", "расскажи о сюцай", "что за сюцай")):
        return (
            "В философии Сюцай рассматривают сознание и подсознание, а также связь души, "
            "разума, ума, мыслей и эмоций. Здесь можно посчитать ЧС или выбрать тему разбора.",
            MAIN_MENU,
        )
    cs_match = re.search(r"(?:чс|число сознания)\s*[:№]?\s*([1-9])\b", normalized)
    if cs_match and any(key in normalized for key in ("что", "знач", "опиши", "расскажи", "характер", "чс")):
        return profile_reply(int(cs_match.group(1))), AFTER_READING_BUTTONS
    if any(key in normalized for key in ("число сознания", "дата рождения", "рассчитай", "расчет", "расчёт", "мисси")):
        set_flow(user_id, "awaiting_date")
        return "Отправь полную дату рождения в формате ДД.ММ.ГГГГ, например 31.05.2001.", None
    if any(key in normalized for key in ("матриц", "энерг")):
        return matrix_info(), MATRIX_FOLLOWUP_BUTTONS
    if any(key in normalized for key in ("совместим", "сравнить пару", "два дня", "пара")):
        set_flow(user_id, "awaiting_pair")
        return "Для сравнения отправь два дня рождения, например: 15 и 8. Я покажу ЧС и сильные стороны каждого, без автоматического вердикта о совместимости.", None
    topic = "relationships" if any(key in normalized for key in ("отношен", "парень", "девуш", "муж", "жена", "партнер", "партнёр", "руга", "ссор", "конфликт")) else "goals" if any(key in normalized for key in ("цель", "план", "решение")) else "business" if any(key in normalized for key in ("бизнес", "работ", "карьер", "деньг", "зарабат", "доход", "финанс", "богат", "професс")) else "self" if any(key in normalized for key in ("самореализац", "предназнач", "развит")) else ""
    if topic:
        set_flow(user_id, f"awaiting_date:{topic}")
        return "Могу сделать разбор по этой теме. Пришли полную дату рождения в формате ДД.ММ.ГГГГ, например 31.05.2001.", None
    if any(key in normalized for key in ("разбор", "интересно", "хочу узнать")):
        return "Выбери тему разбора: отношения, цели или бизнес. Для других направлений напиши «самореализация».", TOPIC_MENU
    return (
        "Могу посчитать ЧС, разобрать отношения, цели, бизнес или самореализацию, а также сравнить ЧС двух людей. Напиши тему или нажми кнопку.",
        MAIN_MENU,
    )


def respond_postback(user_id: str, payload: str) -> tuple[str, list[dict] | None]:
    if payload == "DATE_CALC":
        set_flow(user_id, "awaiting_date")
        return "Отправь полную дату рождения в формате ДД.ММ.ГГГГ, например 31.05.2001.", None
    if payload in {"TOPICS", "READING"}:
        return "Выбери тему разбора:", TOPIC_MENU
    topic_payloads = {
        "TOPIC_RELATIONSHIPS": "relationships",
        "TOPIC_GOALS": "goals",
        "TOPIC_BUSINESS": "business",
        "TOPIC_SELF": "self",
    }
    if payload in topic_payloads:
        topic = topic_payloads[payload]
        set_flow(user_id, f"awaiting_date:{topic}")
        topic_names = {"relationships": "отношения", "goals": "цели", "business": "работа и бизнес", "self": "самореализация"}
        return f"Разберём тему «{topic_names[topic]}». Пришли полную дату рождения в формате ДД.ММ.ГГГГ.", None
    if payload == "PAIR_COMPARE":
        set_flow(user_id, "awaiting_pair")
        return "Для сравнения отправь два дня рождения через «и» или запятую, например: 15 и 8.", None
    if payload == "MATRIX_INFO":
        return matrix_info(), MATRIX_FOLLOWUP_BUTTONS
    if payload == "HOME":
        set_flow(user_id, "")
        return home_text(), MAIN_MENU
    return "Выбери тему кнопкой или напиши вопрос своими словами.", MAIN_MENU


def send_button_template(
    recipient_id: str,
    text: str,
    buttons: list[dict],
    headers: dict[str, str],
    error_context: str,
) -> bool:
    message = {
        "attachment": {
            "type": "template",
            "payload": {
                "template_type": "button",
                "text": text,
                "buttons": buttons[:3],
            },
        }
    }
    try:
        response = requests.post(
            META_SEND_URL,
            json={"recipient": {"id": recipient_id}, "message": message},
            headers=headers,
            timeout=20,
        )
    except requests.RequestException:
        logging.exception("%s", error_context)
        return False
    if not response.ok:
        logging.error(
            "%s: HTTP %s — %s",
            error_context,
            response.status_code,
            response.text,
        )
    return response.ok


def send_instagram_message(
    recipient_id: str, text: str, buttons: list[dict] | None = None
) -> bool:
    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    message_buttons = list(buttons or [])
    telegram_button_added = False
    if TELEGRAM_BOT_URL:
        telegram_button = {
            "type": "web_url",
            "url": TELEGRAM_BOT_URL,
            "title": "Открыть Telegram",
        }
        if len(message_buttons) < 3:
            message_buttons.append(telegram_button)
            telegram_button_added = True

    if message_buttons and len(text) <= 640:
        message = {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "button",
                    "text": text,
                    "buttons": message_buttons[:3],
                },
            }
        }
    else:
        message = {"text": text}

    try:
        response = requests.post(
            META_SEND_URL,
            json={"recipient": {"id": recipient_id}, "message": message},
            headers=headers,
            timeout=20,
        )
    except requests.RequestException:
        logging.exception("Сетевая ошибка при отправке в Meta")
        return False

    if not response.ok:
        logging.error(
            "Meta отклонила отправку: HTTP %s — %s",
            response.status_code,
            response.text,
        )
        return False

    telegram_button_sent = telegram_button_added and len(text) <= 640

    if buttons and len(text) > 640:
        # Длинный ответ отправляем целиком, а кнопки — отдельным коротким сообщением.
        followup_buttons = list(buttons[:3])
        if TELEGRAM_BOT_URL and len(followup_buttons) < 3:
            followup_buttons.append(
                {
                    "type": "web_url",
                    "url": TELEGRAM_BOT_URL,
                    "title": "Открыть Telegram",
                }
            )
            telegram_button_sent = True
        send_button_template(
            recipient_id,
            "Что разберём дальше?",
            followup_buttons,
            headers,
            "Не удалось отправить кнопки после длинного ответа",
        )

    if TELEGRAM_BOT_URL and not telegram_button_sent:
        send_button_template(
            recipient_id,
            "Проверка подписки доступна в Telegram:",
            [
                {
                    "type": "web_url",
                    "url": TELEGRAM_BOT_URL,
                    "title": "Открыть Telegram",
                }
            ],
            headers,
            "Не удалось отправить ссылку на Telegram-бота",
        )

    logging.info("Ответ отправлен пользователю %s", recipient_id)
    return True

init_db()


@app.route("/webhook", methods=["GET"])
def verify_webhook():
    if (
        request.args.get("hub.mode") == "subscribe"
        and request.args.get("hub.verify_token") == META_VERIFY_TOKEN
        and request.args.get("hub.challenge")
    ):
        return request.args["hub.challenge"], 200
    return "Forbidden", 403


@app.route("/webhook", methods=["POST"])
def handle_webhook():
    data = request.get_json(silent=True) or {}
    if data.get("object") != "instagram":
        logging.warning("Webhook пришёл с неожиданным object=%s", data.get("object"))
        return "EVENT_RECEIVED", 200

    for entry in data.get("entry", []):
        for event in entry.get("messaging", []):
            message = event.get("message") or {}
            if message.get("is_echo"):
                continue
            sender_id = (event.get("sender") or {}).get("id")
            if not sender_id:
                continue
            postback = event.get("postback") or {}
            quick_reply = message.get("quick_reply") or {}
            payload = postback.get("payload") or quick_reply.get("payload")
            event_id = message.get("mid") or postback.get("mid")

            if payload:
                logging.info("Нажата кнопка Instagram: payload=%s", payload)
            elif message.get("text"):
                logging.info("Получен текст Instagram-сообщения")
            else:
                logging.warning(
                    "Получено событие без текста и payload; event_keys=%s, message_keys=%s",
                    list(event.keys()),
                    list(message.keys()),
                )

            if event_id:
                with sqlite3.connect(DB_FILE, timeout=10) as conn:
                    exists = conn.execute("SELECT 1 FROM events WHERE event_id = ?", (event_id,)).fetchone()
                if exists:
                    continue

            if payload:
                user_text = postback.get("title") or payload
                answer, buttons = respond_postback(sender_id, payload)
            elif message.get("text"):
                user_text = message["text"]
                answer, buttons = respond_text(sender_id, user_text)
            else:
                continue

            save_event(sender_id, "user", user_text, event_id)
            if send_instagram_message(sender_id, answer, buttons):
                save_event(sender_id, "assistant", answer)

    return "EVENT_RECEIVED", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))

