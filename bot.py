#& C:\Users\2105f\AppData\Local\Python\pythoncore-3.14-64\python.exe c:/Users/2105f/bot.py

from threading import Thread
from flask import Flask
import asyncio
import sys
import random
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import os
import zipfile
import io
import requests
from aiogram.filters import Filter
import json
from aiogram.filters import CommandObject
from dataclasses import dataclass, field
from typing import Dict, Set, Optional
from aiogram import Router
from aiogram.types import Message
from aiogram.enums import ChatType
from asyncio import Task
import logging
from aiogram.exceptions import TelegramServerError

# 1. Настройка Flask для Render (чтобы хостинг не отключал бота)
app = Flask('')

@app.route('/')
def home():
    return "Бот запущен и работает!"

def run_flask():
    # Render автоматически передает нужный порт в переменную окружения PORT
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)





class CitiesGameActive(Filter):
    async def __call__(self, message: types.Message) -> bool:
        chat_id = message.chat.id
        game = cities_games.get(chat_id)
        return bool(game and game.get("active"))


class MafiaGame(StatesGroup):
    registration = State()
    night = State()
    day = State()
    voting = State()

TOKEN = "9260953052:AAGcC7gotpoNBznl_4RwPXmgWiWNQkkPCAY"
GROUP_ID = -1003005008797  
kazik = 0
pidoras = 0
anec = 0

games = {}  # chat_id: данные игры
cities_games = {}
# ===== КРИПТА =====
crypto_balances = {}  # user_id: количество монет
# Твой Telegram ID (узнать можно через @userinfobot)
ADMIN_ID = 1876083446   # <-- ЗАМЕНИ НА СВОЙ ID
FACTS_FILE = "estimation_facts_100_ru.json"   # путь к твоему json
QUESTIONS_PER_GAME = 11
ANSWER_TIMEOUT = 45          # секунд на ответ



# ====================== РОЛИ ======================
def assign_roles(player_ids: list) -> dict:
    """Простая раздача ролей. Можно потом улучшить."""
    roles = []
    n = len(player_ids)
    
    # Пример баланса
    mafia_count = max(1, n // 4)
    
    roles += ["Мафия"] * mafia_count
    roles += ["Комиссар"]
    roles += ["Доктор"]
    roles += ["Мирный"] * (n - len(roles))
    
    random.shuffle(roles)
    return dict(zip(player_ids, roles))

bot = Bot(token=TOKEN)
dp = Dispatcher()
CITIES_DB = set()
Jokes = set()
router = Router()
dp.include_router(router)



# ---------- Данные ----------
@dataclass
class Game:
    chat_id: int
    starter_id: int
    players: Set[int] = field(default_factory=set)
    scores: Dict[int, int] = field(default_factory=dict)
    questions: list = field(default_factory=list)
    current_q: int = 0
    answers: Dict[int, float] = field(default_factory=dict)  # user_id -> ответ
    is_registration: bool = True
    is_active: bool = False
    names: Dict[int, str] = field(default_factory=dict)      # чтобы красиво писать имена
    timer_task: Optional[Task] = None


fact_games: Dict[int, Game] = {}          # chat_id -> Game (игра в факты)
user_to_chat: Dict[int, int] = {}         # user_id -> chat_id


class GameStates(StatesGroup):
    waiting_answer = State()


def load_facts() -> list:
    # Берём папку, в которой лежит сам bot.py
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, "estimation_facts_100_ru.json")
    
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)




# ---------- Хелперы ----------
def get_player_name(user_id: int, game_obj: Game) -> str:
    return game_obj.names.get(user_id, f"Игрок {user_id}")


async def ask_next_question(chat_id: int):
    g = fact_games.get(chat_id)
    if not g or not g.is_active:
        return

    if g.current_q >= len(g.questions):
        await finish_game(chat_id)
        return

    q = g.questions[g.current_q]
    g.answers.clear()

    # Отменяем старый таймер, если он ещё жив
    if g.timer_task and not g.timer_task.done():
        g.timer_task.cancel()

    text = (
        f"❓ <b>Вопрос {g.current_q + 1}/{QUESTIONS_PER_GAME}</b>\n\n"
        f"{q['question']}\n\n"
        f"Отвечайте <b>только числом</b> в личные сообщения боту.\n"
        f"У вас {ANSWER_TIMEOUT} секунд."
    )
    await bot.send_message(chat_id, text, parse_mode="HTML")

    # Запускаем новый таймер
    g.timer_task = asyncio.create_task(timer_for_question(chat_id))


async def timer_for_question(chat_id: int):
    try:
        await asyncio.sleep(ANSWER_TIMEOUT)
        await process_answers(chat_id)
    except asyncio.CancelledError:
        # Таймер отменили — всё нормально
        pass


async def process_answers(chat_id: int):
    g = fact_games.get(chat_id)
    if not g or not g.is_active:
        return

    # Отменяем таймер, чтобы он больше не сработал
    if g.timer_task and not g.timer_task.done():
        g.timer_task.cancel()

    q = g.questions[g.current_q]
    correct = float(q["answer"])

    if not g.answers:
        await bot.send_message(chat_id, "Никто не ответил 😢 Переходим дальше...")
    else:
        closest_uid = None
        min_diff = float("inf")

        for uid, ans in g.answers.items():
            diff = abs(ans - correct)
            if diff < min_diff:
                min_diff = diff
                closest_uid = uid

        if closest_uid is not None:
            g.scores[closest_uid] = g.scores.get(closest_uid, 0) + 1
            name = get_player_name(closest_uid, g)
            await bot.send_message(
                chat_id,
                f"✅ Ближе всех был <b>{name}</b>! (+1 очко)\n"
                f"Сейчас у него: {g.scores[closest_uid]}",
                parse_mode="HTML"
            )

    g.current_q += 1
    await asyncio.sleep(2)
    await ask_next_question(chat_id)

async def finish_game(chat_id: int):
    g = fact_games.get(chat_id)
    if not g:
        return

    # Сортируем результаты
    sorted_scores = sorted(g.scores.items(), key=lambda x: x[1], reverse=True)

    text = "🏁 <b>Игра окончена!</b>\n\nРезультаты:\n"
    for i, (uid, score) in enumerate(sorted_scores, 1):
        name = get_player_name(uid, g)
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "•"
        text += f"{medal} {name}: {score} очк.\n"

    if sorted_scores:
        winner_id = sorted_scores[0][0]
        text += f"\nПобедитель — <b>{get_player_name(winner_id, g)}</b> 🎉"

    await bot.send_message(chat_id, text, parse_mode="HTML")

    # Чистим
    for uid in g.players:
        user_to_chat.pop(uid, None)
    fact_games.pop(chat_id, None)


# ---------- Команды ----------
@router.message(Command("game"), F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def cmd_game(message: Message):
    chat_id = message.chat.id

    if chat_id in fact_games and fact_games[chat_id].is_active:
        await message.reply("Игра уже идёт!")
        return

    # Новая игра
    g = Game(
        chat_id=chat_id,
        starter_id=message.from_user.id,
        is_registration=True,
        is_active=False
    )
    g.players.add(message.from_user.id)
    g.scores[message.from_user.id] = 0
    g.names[message.from_user.id] = message.from_user.full_name or message.from_user.first_name

    fact_games[chat_id] = g
    user_to_chat[message.from_user.id] = chat_id

    await message.reply(
        "🎮 Регистрация открыта!\n\n"
        "Напишите /join_fact чтобы присоединиться.\n"
        "Когда все будут готовы — создатель игры пишет /stop_fact"
    )


@router.message(Command("join_fact"), F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def cmd_join_fact(message: Message):
    chat_id = message.chat.id
    user = message.from_user

    g = fact_games.get(chat_id)
    if not g or not g.is_registration:
        await message.reply("Сейчас нет открытой регистрации.")
        return

    if user.id in g.players:
        await message.reply("Ты уже в игре.")
        return

    g.players.add(user.id)
    g.scores[user.id] = 0
    g.names[user.id] = user.full_name or user.first_name
    user_to_chat[user.id] = chat_id

    await message.reply(f"✅ {g.names[user.id]} присоединился! Сейчас игроков: {len(g.players)}")


@router.message(Command("stop_fact"), F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def cmd_stop_fact(message: Message):
    chat_id = message.chat.id
    g = fact_games.get(chat_id)
    if not g or not g.is_registration:
        await message.reply("Регистрация не идёт.")
        return

    if message.from_user.id != g.starter_id:
        await message.reply("Остановить регистрацию может только тот, кто её начал.")
        return

    if len(g.players) < 2:
        await message.reply("Нужно минимум 2 игрока.")
        return

    # Готовим вопросы
    selected = random.sample(FACTS, min(QUESTIONS_PER_GAME, len(FACTS)))
    g.questions = selected
    g.current_q = 0
    g.is_registration = False
    g.is_active = True

    await message.reply(
        f"🚀 Игра начинается! Игроков: {len(g.players)}\n"
        f"Вопросов: {QUESTIONS_PER_GAME}\n\n"
        f"Отвечайте только в личные сообщения боту!"
    )

    await asyncio.sleep(2)
    await ask_next_question(chat_id)









def load_jokes():
    """Загружает анекдоты, разделённые пустыми строками"""
    global Jokes

    script_dir = os.path.dirname(os.path.abspath(__file__))
    cache_file = os.path.join(script_dir, "full_jokes.txt")

    print(f"Ищу файл шуток: {cache_file}")

    if not os.path.exists(cache_file):
        print(f"❌ Файл не найден: {cache_file}")
        Jokes = set()
        return

    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Разбиваем по пустым строкам (одна или несколько)
        raw_jokes = content.split("\n\n")

        Jokes = set()
        for joke in raw_jokes:
            cleaned = joke.strip()          # убираем лишние пробелы и переносы по краям
            if cleaned:                     # пропускаем совсем пустые
                Jokes.add(cleaned)

        print(f"✅ Загружено {len(Jokes)} анекдотов")

    except Exception as e:
        print(f"❌ Ошибка чтения файла: {e}")
        Jokes = set()

# ---------- Загрузка фактов ----------
def load_facts() -> list:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, "estimation_facts_100_ru.json")
    
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


FACTS = load_facts()          # ← эта строка обязательно должна быть

def load_cities_db():
    """Скачивает и загружает базу городов мира (GeoNames)"""
    global CITIES_DB
    
    cache_file = "cities_cache.txt"
    
    # Если уже есть кэш — читаем его
    if os.path.exists(cache_file):
        print("Загружаю города из кэша...")
        with open(cache_file, "r", encoding="utf-8") as f:
            CITIES_DB = {line.strip().lower() for line in f if line.strip()}
        print(f"Загружено {len(CITIES_DB)} городов")
        return

    print("Скачиваю базу городов мира...")
    
    # Можно поставить cities5000.zip (больше городов) или cities15000.zip
    url = "https://download.geonames.org/export/dump/cities5000.zip"
    
    try:
        response = requests.get(url, timeout=90)
        response.raise_for_status()
        
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            # Ищем любой .txt файл внутри архива
            txt_files = [name for name in z.namelist() if name.lower().endswith(".txt")]
            
            if not txt_files:
                raise Exception(f"В архиве нет .txt файлов. Содержимое: {z.namelist()}")
            
            filename = txt_files[0]
            print(f"Найден файл: {filename}")
            
            with z.open(filename) as f:
                cities = set()
                for line in f:
                    try:
                        parts = line.decode("utf-8").split("\t")
                        if len(parts) > 1:
                            name = parts[1].strip()
                            if name:
                                cities.add(name.lower())
                            
                            # Альтернативные названия
                            if len(parts) > 3 and parts[3]:
                                for alt in parts[3].split(","):
                                    alt = alt.strip()
                                    if alt:
                                        cities.add(alt.lower())
                    except:
                        continue
                
                CITIES_DB = cities
        
        # Сохраняем кэш
        with open(cache_file, "w", encoding="utf-8") as f:
            for city in sorted(CITIES_DB):
                f.write(city + "\n")
        
        print(f"Успешно загружено {len(CITIES_DB)} городов")
        
    except Exception as e:
        print(f"Ошибка загрузки базы городов: {e}")
        CITIES_DB = set()

# 1. Обработка команды /start
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(f"Привет, {message.from_user.first_name}! Бот запущен. Напиши /help, чтобы увидеть список команд.")

# 2. Обработка команды /help
@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = (
        "❓ <b>Доступные команды:</b>\n\n"
        "/start — Перезапустить бота\n"
        "/help — Справка по командам\n"
        "/info — Узнать больше о боте\n"
        "/goroda — города\n"
        "/kazino — казино\n"
        "/pidor — кто пидор дня\n"
        "/anecdote — случайный анекдот\n"
        "/mafia — начать игру в мафию\n"
        "/join — присоединиться к игре\n"
        "/start_game — начать раздачу ролей (только хост)\n"
        "/game - игра в факты\n"

    )
    await message.answer(help_text, parse_mode="HTML")

# 3. Обработка команды /info
@dp.message(Command("info"))
async def cmd_info(message: types.Message):
    await message.answer("иди в сраку!")

@router.message(Command("na_kol"))
async def cmd_jaloba(message: types.Message, command: CommandObject):
    # command.args содержит всё, что написано ПОСЛЕ самой команды
    if not command.args:
        await message.answer("Ошибка! Введите данные по шаблону: `/na_kol @username`")
        return

    target_username = command.args.strip()

    if target_username.lower == "moi_user_temmie":
        await message.answer("такого человека нельзя на кол")
        return

    # 2. Проверяем, начинается ли текст с @ и нет ли в нем пробелов
    if target_username.lower == "взломщики":
        target_username = "Взломщики"
    elif not target_username.startswith("@") or " " in target_username:
        await message.answer("Это не похоже на юзернейм! Напишите его в формате @username")
        return

    # Если все проверки пройдены:
    await message.answer(f"на кол был посажен {target_username}")

@dp.message(Command("goroda"))
async def cmd_goroda(message: types.Message):
    chat_id = message.chat.id

    if chat_id in cities_games and cities_games[chat_id].get("active"):
        await message.answer("Игра в города уже идёт! Назовите город.")
        return

    cities_games[chat_id] = {
        "active": True,
        "used_cities": set(),
        "last_letter": None,
        "last_player": None
    }

    await message.answer(
        "🏙 Игра «Города» началась!\n\n"
        "Называйте города по очереди.\n"
        "Следующий город должен начинаться на последнюю букву предыдущего.\n"
        "Чтобы закончить игру — напишите /stop_goroda"
    )

@dp.message(Command("stop_goroda"))
async def cmd_stop_goroda(message: types.Message):
    chat_id = message.chat.id
    if chat_id in cities_games:
        cities_games[chat_id]["active"] = False
        await message.answer("Игра в города остановлена.")
    else:
        await message.answer("Игра и так не запущена.")

@dp.message(CitiesGameActive(), F.text)
async def cities_handler(message: types.Message):
    chat_id = message.chat.id
    user = message.from_user
    text = message.text.strip()

    if text.startswith("/"):
        return

    game = cities_games[chat_id]

    # Нельзя ходить два раза подряд
    if game.get("last_player") == user.id:
        await message.reply("❌ Ты уже ходил! Дождись хода другого игрока.")
        return

    city = text.strip().capitalize()
    city_lower = city.lower()

    if city_lower not in CITIES_DB:
        await message.reply("❌ Такого города нет в базе мира.")
        return

    if city_lower in (c.lower() for c in game["used_cities"]):
        await message.reply("❌ Этот город уже называли!")
        return

    if game["last_letter"]:
        expected = game["last_letter"].upper()
        if not city.upper().startswith(expected):
            await message.reply(f"❌ Город должен начинаться на букву «{expected}»!")
            return

    # Город принят
    game["used_cities"].add(city)

    last_char = city[-1].lower()
    if last_char in "ьъы" and len(city) > 1:
        last_char = city[-2].lower()

    game["last_letter"] = last_char
    game["last_player"] = user.id

    await message.reply(
        f"✅ Принято: <b>{city}</b>\n"
        f"Следующий город на букву «{last_char.upper()}»",
        parse_mode="HTML"
    )

# 5. Обработка команды /kazino 
# Не забудьте проверить, что в самом верху файла у вас написано: import random

@dp.message(Command("kazino"))
async def cmd_kazino(message: types.Message):  # Переименовали функцию в cmd_kazino для порядка
    kazik = random.randint(0, 999)
    
    if kazik == 0:
        # Отступы соблюдены, бот отвечает пользователю в чат
        await message.answer("0, лох ебанный")
    elif kazik == 777:
        await message.answer("777, ДЖЕКПОТ! ПОБЕДА! 🎉")
    elif kazik == 42:
        await message.answer("42 братуха")
    elif kazik == 52:
        await message.answer("52😀😀😀")
    elif kazik == 67:
        await message.answer("67, SIX SEVEN")
    elif kazik == 69:
        await message.answer("69, крутая поза")
    elif kazik == 670:
        await message.answer("670, сикс севен десять раз")
    elif kazik == 699:
        await message.answer("699! 69")
    elif kazik == 696:
        await message.answer("696! Красивое число")
    elif kazik == 148:
        await message.answer("148! Почти посхалка")
    elif kazik == 333:
        await message.answer("333! ТРИСТА ТРИДЦАТЬ ТРИ")
    elif kazik == 314:
        await message.answer("314... Почти как Пи")
    elif kazik == 993:
        await message.answer("993! 1000-7")
    elif kazik == 666:
        await message.answer("666 😈 ух, горячо!")
    elif kazik == 456:
        await message.answer("456! Сквид гейм")
    elif kazik == 911:
        await message.answer("911, emergency services! Срочный вызов 🚨")
    elif kazik == 228:
        await message.answer("228... Опачки 🤫")
    elif kazik == 420:
        await message.answer("420 🌿 время расслабиться")
    elif kazik == 200:
        await message.answer("200! Груз принят 🛥️")
    elif kazik == 690:
        await message.answer("690, 69 десять раз")
    elif kazik == 23:
        await message.answer("23, пісюнковий злодій")
    elif kazik == 66:
        await message.answer("66, 66")
    elif kazik == 230:
        await message.answer("230, пісюнковий злодій 2")
    elif kazik == 300:
            await message.answer("300, отсоси у тракториста")
    else:
        # Бот присылает выпавшее число и слово "азарт"
        await message.answer(f"Выпало число: {kazik}\nАзарт!")

@dp.message(Command("pidor"))
async def cmd_pidor(message: types.Message):  # Переименовали функцию в cmd_kazino для порядка
    pidor = random.randint(1, 5)
    
    if pidor == 1:
        # Отступы соблюдены, бот отвечает пользователю в чат
        await message.answer("пидор дня Денис")
    elif pidor == 2:
        await message.answer("пидор дня Максим")
    elif pidor == 3:
        await message.answer("пидор дня Аня")
    elif pidor == 4:
        await message.answer("пидор дня Алина")
    else:
        await message.answer("лень отвечать")

@dp.message(Command("anecdote"))
async def cmd_anecdot(message: types.Message): 
    if not Jokes:
        await message.answer("База шуток пуста 😔")
        return

    joke = random.choice(list(Jokes))
    await message.answer(joke)

@dp.message(Command("mafia"))
async def cmd_mafia(message: types.Message):
    if message.chat.type == "private":
        await message.answer("Эту команду нужно писать в группе.")
        return

    chat_id = message.chat.id
    games[chat_id] = {
        "players": {},
        "phase": "registration",
        "host": message.from_user.id,
        "night_actions": {},   # user_id: действие
        "votes": {}
    }

    await message.answer(
        "🩸 Игра «Мафия» создана!\n\n"
        "Пишите /join чтобы присоединиться.\n"
        "Когда все готовы — хост пишет /start_game"
    )

@dp.message(Command("join"))
async def cmd_join(message: types.Message):
    chat_id = message.chat.id
    user = message.from_user

    if chat_id not in games or games[chat_id]["phase"] != "registration":
        await message.answer("Сейчас нельзя присоединиться.")
        return

    # Проверяем, может ли бот писать в ЛС
    try:
        await bot.send_message(user.id, "✅ Ты записался в игру «Мафия»!\nЖди начала.")
    except Exception:
        await message.answer(
            f"{user.first_name}, сначала напиши боту в личку команду /start, "
            f"иначе я не смогу отправить тебе роль!"
        )
        return

    games[chat_id]["players"][user.id] = {
        "name": user.first_name,
        "role": None,
        "alive": True
    }
    await message.answer(f"✅ {user.first_name} в игре!")

@dp.message(Command("start_game"))
async def cmd_start_game(message: types.Message):
    chat_id = message.chat.id
    game = games.get(chat_id)

    if not game:
        return
    if message.from_user.id != game["host"]:
        await message.answer("Только хост может начать игру.")
        return

    players = list(game["players"].keys())
    if len(players) < 1:
        await message.answer("Нужно минимум 4 игрока.")
        return

    # Раздаём роли
    roles = assign_roles(players)

    for user_id, role in roles.items():
        game["players"][user_id]["role"] = role
        try:
            await bot.send_message(
                user_id,
                f"🎭 <b>Твоя роль: {role}</b>\n\n"
                f"Никому не говори свою роль!",
                parse_mode="HTML"
            )
        except Exception:
            await message.answer(f"Не удалось отправить роль игроку {user_id}")

    game["phase"] = "night"
    game["night_actions"] = {}

    await message.answer(
        "🌑 Ночь наступила...\n"
        "Все действия только в личных сообщениях с ботом."
    )
    await send_night_actions(chat_id)

async def send_night_actions(chat_id: int):
    """Отправляет каждому живому игроку, что он может сделать ночью"""
    game = games[chat_id]
    alive = {uid: p for uid, p in game["players"].items() if p["alive"]}

    for user_id, player in alive.items():
        role = player["role"]
        text = f"Ночь. Твоя роль: {role}\n\n"

        if role == "Мафия":
            text += "Напиши номер или имя игрока, которого хочешь убить:"
        elif role == "Комиссар":
            text += "Напиши номер или имя игрока, которого хочешь проверить:"
        elif role == "Доктор":
            text += "Напиши номер или имя игрока, которого хочешь вылечить:"
        else:
            text += "Ты мирный житель. Просто жди утра."

        # Можно добавить список живых игроков
        text += "\n\nЖивые игроки:\n"
        for i, (uid, p) in enumerate(alive.items(), 1):
            text += f"{i}. {p['name']}\n"

        try:
            await bot.send_message(user_id, text)
        except:
            pass

@dp.message(F.chat.type == "private")
async def private_handler(message: types.Message):
    user_id = message.from_user.id
    text = message.text.strip() if message.text else ""

    # ========== Сначала проверяем игру в ФАКТЫ ==========
    chat_id = user_to_chat.get(user_id)
    if chat_id and chat_id in fact_games:
        g = fact_games[chat_id]
        if g.is_active and user_id in g.players:
            # Уже отвечал?
            if user_id in g.answers:
                await message.reply("Ты уже ответил на этот вопрос.")
                return

            # Парсим число
            try:
                answer = float(text.replace(",", "."))
            except ValueError:
                await message.reply("Нужно отправить только число (например: 42 или 3.14)")
                return

            g.answers[user_id] = answer
            await message.reply("✅ Ответ принят!")

            if len(g.answers) == len(g.players):
                await process_answers(chat_id)
            return

    # ========== Если не факты — проверяем МАФИЮ ==========
    for chat_id, game in games.items():
        if user_id not in game["players"]:
            continue
        if not game["players"][user_id]["alive"]:
            continue

        if game["phase"] == "night":
            await process_night_action(chat_id, user_id, text)
            return

async def process_night_action(chat_id: int, user_id: int, text: str):
    game = games[chat_id]
    player = game["players"][user_id]
    role = player["role"]

    if role == "Мирный":
        await bot.send_message(user_id, "Ты мирный житель. Действий у тебя нет. Жди утра.")
        return

    # Уже сделал ход?
    if user_id in game["night_actions"]:
        await bot.send_message(user_id, "Ты уже сделал свой ход этой ночью.")
        return

    alive = {uid: p for uid, p in game["players"].items() if p["alive"]}
    alive_list = list(alive.items())  # [(uid, player), ...]

    target_id = None
    text = text.strip()

    # Пробуем как номер
    if text.isdigit():
        num = int(text)
        if 1 <= num <= len(alive_list):
            target_id = alive_list[num - 1][0]

    # Если не номер — ищем по имени
    if not target_id:
        for uid, p in alive.items():
            if p["name"].lower() == text.lower():
                target_id = uid
                break

    if not target_id:
        await bot.send_message(user_id, "Игрок не найден.\nНапиши номер из списка или имя точно.")
        return


    game["night_actions"][user_id] = {
        "role": role,
        "target": target_id
    }

    target_name = game["players"][target_id]["name"]
    await bot.send_message(user_id, f"✅ Принято. Ты выбрал: {target_name}")

    await check_night_finished(chat_id)

async def check_night_finished(chat_id: int):
    game = games[chat_id]
    alive = {uid: p for uid, p in game["players"].items() if p["alive"]}

    needed = []
    for uid, p in alive.items():
        if p["role"] in ("Мафия", "Комиссар", "Доктор"):
            needed.append(uid)

    if all(uid in game["night_actions"] for uid in needed):
        await resolve_night(chat_id)

@dp.message(Command("vote"))
async def cmd_vote(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    game = games.get(chat_id)

    if not game:
        await message.answer("Игра не найдена.")
        return

    if game["phase"] != "day":
        await message.answer("Сейчас не время для голосования.")
        return

    if user_id not in game["players"] or not game["players"][user_id]["alive"]:
        await message.answer("Ты не участвуешь в игре или уже мёртв.")
        return

    # Уже голосовал?
    if user_id in game.get("votes", {}):
        await message.answer("Ты уже проголосовал.")
        return

    # Получаем цель
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        # Показываем список живых
        alive = {uid: p for uid, p in game["players"].items() if p["alive"]}
        text = "Напиши: /vote имя или /vote номер\n\nЖивые игроки:\n"
        for i, (uid, p) in enumerate(alive.items(), 1):
            text += f"{i}. {p['name']}\n"
        await message.answer(text)
        return

    target_text = args[1].strip()
    alive = {uid: p for uid, p in game["players"].items() if p["alive"]}
    alive_list = list(alive.items())

    target_id = None

    # По номеру
    if target_text.isdigit():
        num = int(target_text)
        if 1 <= num <= len(alive_list):
            target_id = alive_list[num - 1][0]

    # По имени
    if not target_id:
        for uid, p in alive.items():
            if p["name"].lower() == target_text.lower():
                target_id = uid
                break

    if not target_id:
        await message.answer("Игрок не найден. Напиши имя точно или номер из списка.")
        return

    # Сохраняем голос
    if "votes" not in game:
        game["votes"] = {}

    game["votes"][user_id] = target_id
    target_name = game["players"][target_id]["name"]
    voter_name = game["players"][user_id]["name"]

    await message.answer(f"✅ {voter_name} проголосовал против {target_name}")

    # Проверяем, все ли проголосовали
    await check_voting_finished(chat_id)

@dp.message(Command("end_vote"))
async def cmd_end_vote(message: types.Message):
    """Хост может принудительно завершить голосование"""
    chat_id = message.chat.id
    game = games.get(chat_id)

    if not game:
        return

    if message.from_user.id != game["host"]:
        await message.answer("Только хост может завершить голосование.")
        return

    if game["phase"] != "day":
        await message.answer("Сейчас не идёт голосование.")
        return

    await resolve_voting(chat_id)

async def check_voting_finished(chat_id: int):
    game = games[chat_id]
    alive_players = [uid for uid, p in game["players"].items() if p["alive"]]
    votes = game.get("votes", {})

    # Если все живые проголосовали
    if all(uid in votes for uid in alive_players):
        await resolve_voting(chat_id)

async def resolve_voting(chat_id: int):
    game = games[chat_id]
    votes = game.get("votes", {})

    if not votes:
        await bot.send_message(chat_id, "Никто не проголосовал. Голосование отменено.")
        game["votes"] = {}
        return

    # Подсчёт голосов
    vote_count = {}
    for target_id in votes.values():
        vote_count[target_id] = vote_count.get(target_id, 0) + 1

    # Кто набрал больше всего
    max_votes = max(vote_count.values())
    candidates = [uid for uid, count in vote_count.items() if count == max_votes]

    result = ["🗳️ Результаты голосования:\n"]

    for uid, count in sorted(vote_count.items(), key=lambda x: -x[1]):
        name = game["players"][uid]["name"]
        result.append(f"• {name} — {count} голос(ов)")

    if len(candidates) > 1:
        result.append("\n🤝 Ничья! Никто не изгнан.")
        await bot.send_message(chat_id, "\n".join(result))
        game["votes"] = {}
        # Можно сразу начать новую ночь или дать ещё обсудить
        await start_new_night(chat_id)
        return

    # Изгоняем
    killed_id = candidates[0]
    game["players"][killed_id]["alive"] = False
    killed_name = game["players"][killed_id]["name"]
    killed_role = game["players"][killed_id]["role"]

    result.append(f"\n💀 Изгнан: {killed_name}")
    result.append(f"Его роль была: {killed_role}")

    await bot.send_message(chat_id, "\n".join(result))

    game["votes"] = {}

    # Проверяем победу
    if await check_win(chat_id):
        return

    # Новая ночь
    await start_new_night(chat_id)

async def start_new_night(chat_id: int):
    game = games[chat_id]
    game["phase"] = "night"
    game["night_actions"] = {}

    await bot.send_message(chat_id, "🌑 Наступает ночь...\nВсе действия — только в личных сообщениях.")
    await send_night_actions(chat_id)

async def resolve_night(chat_id: int):
    game = games[chat_id]
    actions = game["night_actions"]

    # Собираем голоса мафии
    mafia_votes = {}
    healed = None
    checked = None
    commissioner_id = None

    for uid, act in actions.items():
        role = act["role"]
        target = act["target"]

        if role == "Мафия":
            mafia_votes[target] = mafia_votes.get(target, 0) + 1
        elif role == "Доктор":
            healed = target
        elif role == "Комиссар":
            checked = target
            commissioner_id = uid

    # Определяем, кого убила мафия (кто набрал больше голосов)
    killed = None
    if mafia_votes:
        # Берём цель с максимальным количеством голосов
        killed = max(mafia_votes, key=mafia_votes.get)

    result = ["☀️ Утро наступило!\n"]

    if killed and killed != healed:
        game["players"][killed]["alive"] = False
        name = game["players"][killed]["name"]
        result.append(f"💀 Этой ночью был убит: {name}")
    else:
        result.append("Этой ночью никто не умер.")

    # Результат проверки комиссару в ЛС
    if checked and commissioner_id:
        role = game["players"][checked]["role"]
        try:
            await bot.send_message(
                commissioner_id,
                f"🔍 Результат проверки: {game['players'][checked]['name']} — {role}"
            )
        except:
            pass

    await bot.send_message(chat_id, "\n".join(result))

    # Проверяем условия победы
    if await check_win(chat_id):
        return

    # Переходим в день
    game["phase"] = "day"
    game["night_actions"] = {}
    await bot.send_message(
    chat_id,
    "🗣️ День. Обсуждайте!\n\n"
    "Чтобы проголосовать: /vote имя  или  /vote номер\n"
    "Хост может завершить голосование досрочно: /end_vote"
)

async def check_win(chat_id: int) -> bool:
    game = games[chat_id]
    alive = [p for p in game["players"].values() if p["alive"]]

    mafia_alive = sum(1 for p in alive if p["role"] == "Мафия")
    peaceful_alive = len(alive) - mafia_alive

    if mafia_alive == 0:
        await bot.send_message(chat_id, "🎉 Победа мирных жителей! Все мафии мертвы.")
        game["phase"] = "ended"
        return True

    if mafia_alive >= peaceful_alive:
        await bot.send_message(chat_id, "🩸 Победа мафии! Мафии осталось не меньше, чем мирных.")
        game["phase"] = "ended"
        return True

    return False

@router.message(Command("sent"))
async def admin_send(message: Message, command: CommandObject):
    """Отправить сообщение в группу. Использование: /send текст"""
    if message.from_user.id != ADMIN_ID:
        return
    
    if not command.args:
        await message.reply("Использование: /send текст сообщения")
        return
    
    try:
        await bot.send_message(GROUP_ID, command.args)
        await message.reply("✅ Отправлено в группу")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")
        
@router.message(Command("sentid"))
async def admin_send_id(message: Message, command: CommandObject):
    """Отправить сообщение пользователю. Использование: /sendid 123456789 Привет"""
    if message.from_user.id != ADMIN_ID:
        return
    
    if not command.args:
        await message.reply("Использование: /sendid ID текст")
        return
    
    parts = command.args.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("Нужно: /sendid ID текст")
        return
    
    try:
        target_id = int(parts[0])
        text = parts[1]
        await bot.send_message(target_id, text)
        await message.reply(f"✅ Отправлено пользователю {target_id}")
    except ValueError:
        await message.reply("ID должен быть числом")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")





async def main():
    while True:
        try:
            await dp.start_polling(bot, skip_updates=True)
        except TelegramServerError as e:
            logging.error(f"Ошибка сервера Telegram: {e}. Перезапуск через 5 секунд...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    # Запускаем веб-сервер Flask в отдельном потоке для Render
    t = Thread(target=run_flask)
    t.daemon = True  # поток закроется автоматически при остановке бота
    t.start()
    
    # Запускаем асинхронного бота aiogram
    asyncio.run(main())
