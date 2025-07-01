import logging
import random
import asyncio
import time
import os
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from flask import Flask

# Получаем токен из переменной окружения
TOKEN = os.getenv('TOKEN')

# Настройки логгера
logging.basicConfig(level=logging.INFO)

# Память пользователей (в ОЗУ, не сохраняется между перезапусками)
users = {}

# Фрукты для слотов
SLOT_SYMBOLS = ['🍒', '🍋', '🍊', '🍉', '🍇', '🍓']

BONUS_COOLDOWN = 7 * 24 * 60 * 60  # 1 неделя

def get_user_data(user_id):
    if user_id not in users:
        users[user_id] = {
            'balance': 1000,
            'earned': 0,
            'withdrawn': 0,
            'last_bonus': 0
        }
    return users[user_id]

# Flask-приложение для минимального HTTP-сервера
app = Flask(__name__)

@app.route('/')
def home():
    return "Казино-бот работает!"

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

# Главное меню
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[
        InlineKeyboardButton("💰 Баланс", callback_data='balance'),
        InlineKeyboardButton("🎮 Играть", callback_data='play')
    ], [
        InlineKeyboardButton("📊 Статистика", callback_data='stats'),
        InlineKeyboardButton("💵 Пополнить", callback_data='deposit'),
        InlineKeyboardButton("🏧 Вывод", callback_data='withdraw')
    ], [
        InlineKeyboardButton("👥 Реферал", callback_data='referral'),
        InlineKeyboardButton("🎁 Бонус", callback_data='bonus')
    ]]
    if update.message:
        await update.message.reply_text("Добро пожаловать в казино-бота!", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text("Добро пожаловать в казино-бота!", reply_markup=InlineKeyboardMarkup(keyboard))

# Обработка кнопок
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = get_user_data(user_id)

    if query.data == 'balance':
        await query.edit_message_text(f"Ваш баланс: {data['balance']} монет", reply_markup=return_menu())

    elif query.data == 'stats':
        await query.edit_message_text(f"Вы заработали: {data['earned']} монет\nВы вывели: {data['withdrawn']} монет", reply_markup=return_menu())

    elif query.data == 'play':
        keyboard = [[
            InlineKeyboardButton("🎰 Слоты", callback_data='slots'),
            InlineKeyboardButton("🎲 Кости", callback_data='dice')
        ], [
            InlineKeyboardButton("🪙 Монетка (в разработке)", callback_data='dev'),
            InlineKeyboardButton("✂ Камень-ножницы-бумага (в разработке)", callback_data='dev')
        ], [InlineKeyboardButton("⬅ Вернуться в меню", callback_data='menu')]]
        await query.edit_message_text("Выберите игру:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == 'slots':
        context.user_data['game'] = 'slots'
        await ask_bet(query, data)

    elif query.data == 'dice':
        context.user_data['game'] = 'dice'
        await ask_bet(query, data)

    elif query.data == 'menu':
        await start(update, context)

    elif query.data == 'bonus':
        now = time.time()
        if now - data['last_bonus'] >= BONUS_COOLDOWN:
            data['balance'] += 500
            data['last_bonus'] = now
            await query.edit_message_text("Вы получили бонус 500 монет!", reply_markup=return_menu())
        else:
            remain = int(BONUS_COOLDOWN - (now - data['last_bonus']))
            days = remain // 86400
            hours = (remain % 86400) // 3600
            minutes = (remain % 3600) // 60
            await query.edit_message_text(f"Бонус доступен через: {days} д. {hours} ч. {minutes} м.", reply_markup=return_menu())

    elif query.data == 'dev':
        await query.edit_message_text("Эта игра в разработке.", reply_markup=return_menu())

async def ask_bet(query, data):
    await query.edit_message_text(
        f"Ваш баланс: {data['balance']} монет\nВведите сумму ставки:")

# Ввод ставки вручную
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    data = get_user_data(user_id)
    text = update.message.text

    if 'game' in context.user_data:
        try:
            bet = int(text)
            if bet <= 0 or bet > data['balance']:
                await update.message.reply_text("Некорректная ставка. Введите сумму заново:")
                return
            game = context.user_data['game']
            if game == 'slots':
                await play_slots(update, context, bet)
            elif game == 'dice':
                await play_dice(update, context, bet)
        except ValueError:
            await update.message.reply_text("Введите корректное число.")

def return_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Вернуться в меню", callback_data='menu')]])

# Слоты
async def play_slots(update: Update, context: ContextTypes.DEFAULT_TYPE, bet: int):
    user_id = update.message.from_user.id
    data = get_user_data(user_id)
    data['balance'] -= bet

    msg = await update.message.reply_text("🎰 Крутим барабаны...")
    for _ in range(3):
        slots = [random.choice(SLOT_SYMBOLS) for _ in range(3)]
        await asyncio.sleep(1)
        await msg.edit_text("| {} | {} | {} |".format(*slots))

    slots = [random.choice(SLOT_SYMBOLS) for _ in range(3)]
    await asyncio.sleep(1)
    await msg.edit_text("🎰 Результат:\n| {} | {} | {} |".format(*slots))

    if slots[0] == slots[1] == slots[2]:
        win = bet * 5
        data['balance'] += win
        data['earned'] += win - bet
        await update.message.reply_text(f"Вы выиграли {win} монет!", reply_markup=return_menu())
    elif slots[0] == slots[1] or slots[1] == slots[2] or slots[0] == slots[2]:
        await update.message.reply_text("Выпало два одинаковых символа — проигрыш.", reply_markup=return_menu())
    else:
        await update.message.reply_text("Вы проиграли.", reply_markup=return_menu())

# Кости
async def play_dice(update: Update, context: ContextTypes.DEFAULT_TYPE, bet: int):
    user_id = update.message.from_user.id
    data = get_user_data(user_id)
    data['balance'] -= bet

    msg = await update.message.reply_text("🎲 Бросаем кости...")
    await asyncio.sleep(1)
    user_roll = random.randint(1, 6)
    bot_roll = random.randint(1, 6)
    await msg.edit_text(f"Вы: {user_roll} 🎲\nБот: {bot_roll} 🎲")

    if user_roll > bot_roll:
        win = bet * 2
        data['balance'] += win
        data['earned'] += win - bet
        await update.message.reply_text(f"Вы выиграли {win} монет!", reply_markup=return_menu())
    elif user_roll == bot_roll:
        data['balance'] += bet
        await update.message.reply_text("Ничья. Ставка возвращена.", reply_markup=return_menu())
    else:
        await update.message.reply_text("Вы проиграли.", reply_markup=return_menu())

# Точка входа
if __name__ == '__main__':
    if not TOKEN:
        print("Ошибка: переменная окружения TOKEN не установлена.")
    else:
        # Запускаем Flask в отдельном потоке
        flask_thread = threading.Thread(target=run_flask)
        flask_thread.start()

        # Запускаем Telegram-бота
        app_bot = ApplicationBuilder().token(TOKEN).build()
        app_bot.add_handler(CommandHandler('start', start))
        app_bot.add_handler(CallbackQueryHandler(button))
        app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app_bot.run_polling()
