import asyncio
import os
import random
import json
import logging
from pathlib import Path
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

# ==================== НАСТРОЙКА ЛОГИРОВАНИЯ ====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# ==================== ЗАГРУЗКА ТОКЕНА ====================
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден! Добавь его в .env")

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# ==================== ПУТИ К ФАЙЛАМ ====================
BACKS_DIR = Path("./images/backs")
OPEN_DIR = Path("./images/open")
PREDICTIONS_FILE = Path("predictions.json")

BACKS_DIR.mkdir(parents=True, exist_ok=True)
OPEN_DIR.mkdir(parents=True, exist_ok=True)

# ==================== СИСТЕМА ЯЗЫКОВ ====================
user_languages = {}  # {user_id: 'ru'/'en'}

TEXTS = {
    "ru": {
        "start": "Привет! Я бот Таро 🔮\n\nУзнай своё предсказание на сегодняшний день!\n\nИспользуй команду /tarot, чтобы получить предсказание!",
        "welcome": "👋 Добро пожаловать! Выберите язык: \n\n 👋 Welcome! Choose your language:",
        "language_set": "✅ Язык установлен: Русский",
        "choose_card": "🔮 Выбери карту судьбы (1-4):",
        "user_chooses": "🔮 {username} выбирает карту судьбы! Нажми кнопку (1-4):",
        "card_opening": "🔮 Карта открывается...",
        "your_card": "🎴 Твоя карта дня\n\n{prediction}\n\n✨ Используй /tarot для нового расклада!",
        "cards_unavailable": "❌ Карты временно недоступны.",
        "no_predictions": "❌ Бот не настроен. Файл с предсказаниями не найден.",
        "no_cards_files": "❌ Нет доступных карт с предсказаниями.",
        "error_loading": "❌ Ошибка загрузки карт",
        "help": "🔮 Бот Таро - Помощь:\n\n/start - Начать работу\n/tarot - Получить предсказание\n/language - Сменить язык\n/help - Эта справка\n/stats - Статистика бота\n/cards - Список карт\n\n💡 Бота можно добавлять в группы!",
        "stats": "📊 Статистика бота:\n\n🔙 Рубашек: {backs_count}\n🎴 Всего карт: {all_cards_count}\n✅ Карт с предсказаниями: {available_cards_count}\n📜 Предсказаний: {predictions_count}\n💬 Активных чатов: {active_chats}\n🕒 Кэшированных предсказаний: {total_cached_predictions}",
        "cards_list": "📋 Карты с предсказаниями:\n\n{cards_list}\n\n✅ - есть файл карты\n❌ - файл карты не найден",
        "history_cleared": "✅ История предсказаний очищена! Удалено {count} записей.",
        "history_empty": "ℹ️ История предсказаний уже пуста",
        "no_predictions_loaded": "❌ Нет загруженных предсказаний"
    },
    "en": {
        "start": "Hello! I'm a Tarot bot 🔮\n\nFind out your prediction for today!\n\n Use the /tarot command to get a prediction!",
        "welcome": "👋 Welcome! Choose your language: \n\n 👋 Добро пожаловать! Выберите язык:",
        "language_set": "✅ Language set: English",
        "choose_card": "🔮 Choose your fate card (1-4):",
        "user_chooses": "🔮 {username} is choosing a fate card! Press a button (1-4):",
        "card_opening": "🔮 The card is opening...",
        "your_card": "🎴 Your card of the day\n\n{prediction}\n\n✨ Use /tarot for a new reading!",
        "cards_unavailable": "❌ Cards are temporarily unavailable.",
        "no_predictions": "❌ Bot is not configured. Prediction file not found.",
        "no_cards_files": "❌ No available cards with predictions.",
        "error_loading": "❌ Error loading cards",
        "help": "🔮 Tarot Bot - Help:\n\n/start - Start\n/tarot - Get prediction\n/language - Change language\n/help - This help\n/stats - Bot statistics\n/cards - List of cards\n\n💡 You can add the bot to groups!",
        "stats": "📊 Bot statistics:\n\n🔙 Card backs: {backs_count}\n🎴 Total cards: {all_cards_count}\n✅ Cards with predictions: {available_cards_count}\n📜 Predictions: {predictions_count}\n💬 Active chats: {active_chats}\n🕒 Cached predictions: {total_cached_predictions}",
        "cards_list": "📋 Cards with predictions:\n\n{cards_list}\n\n✅ - card file exists\n❌ - card file not found",
        "history_cleared": "✅ Prediction history cleared! Deleted {count} records.",
        "history_empty": "ℹ️ Prediction history is already empty",
        "no_predictions_loaded": "❌ No predictions loaded"
    }
}

def get_user_language(user_id):
    """Получаем язык пользователя, по умолчанию русский"""
    return user_languages.get(user_id, "ru")

def get_text(text_key, user_id, **kwargs):
    """Получаем текст на языке пользователя"""
    lang = get_user_language(user_id)
    text = TEXTS[lang].get(text_key, text_key)
    return text.format(**kwargs) if kwargs else text

# ==================== СИСТЕМА КЭШИРОВАНИЯ ====================
prediction_history = {}
CACHE_DURATION = 3600

def cleanup_old_predictions():
    global prediction_history
    current_time = asyncio.get_event_loop().time()
    
    for chat_id in list(prediction_history.keys()):
        prediction_history[chat_id] = [
            pred for pred in prediction_history[chat_id]
            if current_time - pred['timestamp'] < CACHE_DURATION
        ]
        
        if not prediction_history[chat_id]:
            del prediction_history[chat_id]

# ==================== ЗАГРУЗКА ПРЕДСКАЗАНИЙ ====================
def load_predictions():
    if PREDICTIONS_FILE.exists():
        try:
            with open(PREDICTIONS_FILE, "r", encoding="utf-8") as f:
                predictions = json.load(f)
                
                if not predictions:
                    logger.error("Файл predictions.json пустой!")
                    return {}
                
                # Проверяем новую структуру
                first_card = list(predictions.values())[0]
                if isinstance(first_card, dict) and 'ru' in first_card:
                    logger.info("✅ Загружены мультиязычные предсказания")
                else:
                    logger.warning("❌ Старая структура предсказаний! Нужно обновить до мультиязычной")
                
                card_names = list(predictions.keys())
                logger.info(f"✅ Загружены предсказания для карт: {', '.join(card_names)}")
                
                return predictions
                
        except Exception as e:
            logger.error(f"Ошибка загрузки predictions: {e}")
            return {}
    
    logger.error("❌ Файл predictions.json не найден!")
    return {}

PREDICTIONS = load_predictions()

# ==================== РАБОТА С ФАЙЛАМИ ====================
def get_images_from_folder(folder_path):
    extensions = ['*.jpg', '*.jpeg', '*.png', '*.gif', '*.bmp']
    images = []
    for ext in extensions:
        images.extend(folder_path.glob(ext))
        images.extend(folder_path.glob(ext.upper()))
    return images

def get_available_cards():
    """Получаем карты, для которых ЕСТЬ предсказания"""
    all_cards = get_images_from_folder(OPEN_DIR)
    available_cards = []
    
    for card in all_cards:
        card_name = card.stem.lower()
        if card_name in PREDICTIONS:
            available_cards.append(card)
        else:
            logger.warning(f"❌ Для карты '{card_name}' нет предсказаний в файле")
    
    logger.info(f"🎴 Доступно карт с предсказаниями: {len(available_cards)}")
    return available_cards

def get_unique_prediction_for_card(card_filename, chat_id, user_id):
    global prediction_history
    cleanup_old_predictions()
    
    card_name = card_filename.stem.lower()
    user_lang = get_user_language(user_id)
    
    # Проверяем есть ли предсказания для этой карты
    if card_name not in PREDICTIONS:
        logger.error(f"❌ Нет предсказаний для карты: {card_name}")
        return get_text("no_predictions", user_id)
    
    card_data = PREDICTIONS[card_name]
    
    # Поддерживаем как старую, так и новую структуру
    if isinstance(card_data, dict):
        # Новая структура: {"ru": [...], "en": [...]}
        if user_lang not in card_data:
            # Если нет предсказаний на языке пользователя, используем русский
            user_lang = "ru"
        all_predictions = card_data.get(user_lang, [])
    else:
        # Старая структура: ["предсказание1", "предсказание2"]
        all_predictions = card_data
    
    if not all_predictions:
        logger.error(f"❌ Пустой список предсказаний для карты: {card_name}")
        return get_text("no_predictions", user_id)
    
    # Получаем уже использованные предсказания
    used_predictions = set()
    if chat_id in prediction_history:
        for pred_data in prediction_history[chat_id]:
            if pred_data['card'] == card_name and pred_data['language'] == user_lang:
                used_predictions.add(pred_data['text'])
    
    # Доступные предсказания
    available_predictions = [p for p in all_predictions if p not in used_predictions]
    
    # Если все предсказания использовались, сбрасываем историю для этой карты
    if not available_predictions:
        available_predictions = all_predictions
        if chat_id in prediction_history:
            prediction_history[chat_id] = [
                pred for pred in prediction_history[chat_id]
                if not (pred['card'] == card_name and pred['language'] == user_lang)
            ]
    
    selected_prediction = random.choice(available_predictions)
    
    # Сохраняем в историю
    if chat_id not in prediction_history:
        prediction_history[chat_id] = []
    
    prediction_history[chat_id].append({
        'card': card_name,
        'text': selected_prediction,
        'language': user_lang,
        'timestamp': asyncio.get_event_loop().time()
    })
    
    return selected_prediction

# ==================== ОТПРАВКА ФОТО ====================
async def send_photo_safe(chat_id, photo_path, caption="", reply_markup=None, reply_to_message_id=None):
    try:
        await bot.send_photo(
            chat_id=chat_id,
            photo=FSInputFile(photo_path),
            caption=caption,
            reply_markup=reply_markup,
            reply_to_message_id=reply_to_message_id
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки фото {photo_path}: {e}")
        return False

# ==================== КОМАНДЫ БОТА ====================

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    chat_type = message.chat.type
    
    logger.info(f"👋 Пользователь {user_id} запустил бота в {chat_type}.")
    
    # ВСЕГДА предлагаем выбрать язык при команде /start
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
            InlineKeyboardButton(text="🇺🇸 English", callback_data="lang_en")
        ]
    ])
    
    # Если язык уже установлен, показываем приветствие на текущем языке
    current_lang = get_user_language(user_id)
    welcome_text = TEXTS[current_lang]["welcome"]
    
    await message.answer(welcome_text, reply_markup=keyboard)

@dp.callback_query(lambda c: c.data.startswith("lang_"))
async def set_language_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    language = callback.data.split("_")[1]  # lang_ru -> ru
    
    user_languages[user_id] = language
    logger.info(f"🌍 Пользователь {user_id} установил язык: {language}")
    
    await callback.answer(get_text("language_set", user_id))
    await callback.message.delete()
    
    # Приветствуем на выбранном языке
    await callback.message.answer(get_text("start", user_id))

@dp.message(Command("language"))
async def language_cmd(message: types.Message):
    user_id = message.from_user.id
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
            InlineKeyboardButton(text="🇺🇸 English", callback_data="lang_en")
        ]
    ])
    
    await message.answer(get_text("welcome", user_id), reply_markup=keyboard)

@dp.message(Command("tarot"))
async def tarot_cmd(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    chat_type = message.chat.type
    
    logger.info(f"🔮 Пользователь {user_id} запросил расклад в {chat_type}.")
    
    # Проверяем есть ли предсказания
    if not PREDICTIONS:
        await message.answer(get_text("no_predictions", user_id))
        return
    
    # Получаем карты, для которых ЕСТЬ предсказания
    available_cards = get_available_cards()
    
    if not available_cards:
        await message.answer(get_text("no_cards_files", user_id))
        return
    
    backs = get_images_from_folder(BACKS_DIR)
    if not backs:
        await message.answer(get_text("cards_unavailable", user_id))
        return
    
    back_image = random.choice(backs)
    logger.info(f"📁 Используется рубашка: {back_image.name}")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1", callback_data="card_1"),
            InlineKeyboardButton(text="2", callback_data="card_2"),
        ],
        [
            InlineKeyboardButton(text="3", callback_data="card_3"),
            InlineKeyboardButton(text="4", callback_data="card_4"),
        ]
    ])
    
    if chat_type == "private":
        caption = get_text("choose_card", user_id)
    else:
        caption = get_text("user_chooses", user_id, username=username)
    
    success = await send_photo_safe(
        chat_id=message.chat.id,
        photo_path=back_image,
        caption=caption,
        reply_markup=keyboard
    )
    
    if not success:
        await message.answer(get_text("error_loading", user_id))

@dp.callback_query(lambda c: c.data.startswith("card_"))
async def process_card_selection(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    username = callback.from_user.username or callback.from_user.first_name
    card_number = callback.data
    chat_id = callback.message.chat.id
    chat_type = callback.message.chat.type
    
    logger.info(f"🃏 Пользователь {user_id} выбрал карту {card_number} в чате {chat_id}")
    
    # Удаляем сообщение с кнопками только в личных чатах
    if chat_type == "private":
        try:
            await callback.message.delete()
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение: {e}")
    else:
        # В группах просто убираем кнопки чтобы избежать путаницы
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception as e:
            logger.warning(f"Не удалось убрать кнопки: {e}")
    
    await callback.answer(get_text("card_opening", user_id))
    await asyncio.sleep(1)
    
    # Используем ТОЛЬКО карты с предсказаниями
    available_cards = get_available_cards()
    
    if not available_cards:
        error_msg = get_text("cards_unavailable", user_id)
        if chat_type == "private":
            await callback.message.answer(error_msg)
        else:
            await callback.message.reply(error_msg)
        return
    
    # Выбираем случайную карту ИЗ ДОСТУПНЫХ (с предсказаниями)
    selected_card = random.choice(available_cards)
    
    # Получаем предсказание для карты
    prediction = get_unique_prediction_for_card(selected_card, chat_id, user_id)
    
    logger.info(f"📁 Открыта карта: {selected_card.name} в чате {chat_id}")
    
    # Формируем текст ответа
    response_text = get_text("your_card", user_id, prediction=prediction)
    
    # Отправляем ответ в зависимости от типа чата
    try:
        if chat_type == "private":
            # В личных чатах - просто отправляем сообщение
            success = await send_photo_safe(
                chat_id=chat_id,
                photo_path=selected_card,
                caption=response_text
            )
        else:
            # В группах - отправляем ответ на сообщение пользователя
            success = await send_photo_safe(
                chat_id=chat_id,
                photo_path=selected_card,
                caption=response_text,
                reply_to_message_id=callback.message.message_id
            )
        
        if success:
            logger.info(f"📜 Пользователь {user_id} получил предсказание для карты {selected_card.stem}")
        else:
            error_msg = get_text("error_loading", user_id)
            if chat_type == "private":
                await callback.message.answer(error_msg)
            else:
                await callback.message.reply(error_msg)
                
    except Exception as e:
        logger.error(f"Ошибка отправки предсказания: {e}")
        # Если не удалось отправить фото, отправляем текстовое сообщение
        try:
            if chat_type == "private":
                await callback.message.answer(response_text)
            else:
                await callback.message.reply(response_text)
        except Exception as e2:
            logger.error(f"Не удалось отправить даже текст: {e2}")

@dp.message(Command("help"))
async def help_cmd(message: types.Message):
    user_id = message.from_user.id
    await message.answer(get_text("help", user_id))

@dp.message(Command("stats"))
async def stats_cmd(message: types.Message):
    user_id = message.from_user.id
    
    backs_count = len(get_images_from_folder(BACKS_DIR))
    all_cards_count = len(get_images_from_folder(OPEN_DIR))
    available_cards_count = len(get_available_cards())
    
    predictions_count = sum(len(preds) for preds in PREDICTIONS.values()) if PREDICTIONS else 0
    
    active_chats = len(prediction_history)
    total_cached_predictions = sum(len(chats) for chats in prediction_history.values())
    
    stats_text = get_text("stats", user_id,
                         backs_count=backs_count,
                         all_cards_count=all_cards_count,
                         available_cards_count=available_cards_count,
                         predictions_count=predictions_count,
                         active_chats=active_chats,
                         total_cached_predictions=total_cached_predictions)
    
    await message.answer(stats_text)

@dp.message(Command("cards"))
async def cards_cmd(message: types.Message):
    user_id = message.from_user.id
    
    if not PREDICTIONS:
        await message.answer(get_text("no_predictions_loaded", user_id))
        return
    
    # Получаем доступные карты (файлы которые есть в папке)
    available_cards = get_available_cards()
    available_card_names = [card.stem.lower() for card in available_cards]
    
    cards_list = []
    for card_name, predictions in PREDICTIONS.items():
        status = "✅" if card_name in available_card_names else "❌"

@dp.message(Command("stats"))
async def stats_cmd(message: types.Message):
    user_id = message.from_user.id
    
    backs_count = len(get_images_from_folder(BACKS_DIR))
    all_cards_count = len(get_images_from_folder(OPEN_DIR))
    available_cards_count = len(get_available_cards())
    
    predictions_count = sum(len(preds) for preds in PREDICTIONS.values()) if PREDICTIONS else 0
    
    active_chats = len(prediction_history)
    total_cached_predictions = sum(len(chats) for chats in prediction_history.values())
    
    stats_text = get_text("stats", user_id,
                         backs_count=backs_count,
                         all_cards_count=all_cards_count,
                         available_cards_count=available_cards_count,
                         predictions_count=predictions_count,
                         active_chats=active_chats,
                         total_cached_predictions=total_cached_predictions)
    
    await message.answer(stats_text)

@dp.message(Command("cards"))
async def cards_cmd(message: types.Message):
    user_id = message.from_user.id
    
    if not PREDICTIONS:
        await message.answer(get_text("no_predictions_loaded", user_id))
        return
    
    # Получаем доступные карты (файлы которые есть в папке)
    available_cards = get_available_cards()
    available_card_names = [card.stem.lower() for card in available_cards]
    
    cards_list = []
    for card_name, predictions in PREDICTIONS.items():
        status = "✅" if card_name in available_card_names else "❌"
        
        # Подсчитываем количество предсказаний для карты
        if isinstance(predictions, dict):
            # Новая структура
            pred_count = sum(len(lang_preds) for lang_preds in predictions.values())
        else:
            # Старая структура
            pred_count = len(predictions)
            
        cards_list.append(f"{status} {card_name} ({pred_count} предсказаний)")
    
    cards_text = "\n".join(cards_list)
    await message.answer(get_text("cards_list", user_id, cards_list=cards_text))

# ==================== ЗАПУСК БОТА ====================
async def main():
    logger.info("🤖 Запуск бота Таро...")
    
    # Проверяем наличие необходимых файлов
    if not PREDICTIONS:
        logger.error("❌ КРИТИЧЕСКАЯ ОШИБКА: Нет загруженных предсказаний!")
    else:
        logger.info(f"✅ Загружено предсказаний для {len(PREDICTIONS)} карт")
    
    backs = get_images_from_folder(BACKS_DIR)
    if not backs:
        logger.warning("⚠️ В папке images/backs нет изображений рубашек!")
    else:
        logger.info(f"✅ Найдено рубашек: {len(backs)}")
    
    available_cards = get_available_cards()
    if not available_cards:
        logger.warning("⚠️ Нет доступных карт с предсказаниями!")
    else:
        logger.info(f"✅ Доступно карт с предсказаниями: {len(available_cards)}")
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Ошибка запуска бота: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⏹️ Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Непредвиденная ошибка: {e}")