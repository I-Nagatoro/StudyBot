import random
import psycopg2
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from concurrent.futures import ThreadPoolExecutor

# Данные для подключения к PostgreSQL
DB_HOST = "45.67.56.214"
DB_PORT = 5454
DB_NAME = "user2"
DB_USER = "user2"
DB_PASSWORD = "hGcLvi0i"
DB_SCHEMA = "questions"  # Указываем схему

# Глобальные переменные для хранения состояния теста
user_data = {}
executor = ThreadPoolExecutor()

def get_db_connection():
    """Создаёт и возвращает соединение с базой данных."""
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    return conn

def fetch_random_questions(limit=10):
    """Получает случайные вопросы из базы данных."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT q.id, q.question_text, ca.correct_answer, array_agg(ia.incorrect_answer) AS incorrect_answers
        FROM {DB_SCHEMA}.questions q
        JOIN {DB_SCHEMA}.correct_answers ca ON q.id = ca.question_id
        JOIN {DB_SCHEMA}.incorrect_answers ia ON q.id = ia.question_id
        GROUP BY q.id, ca.correct_answer
        ORDER BY random()
        LIMIT %s;
    """, (limit,))
    questions = cursor.fetchall()
    cursor.close()
    conn.close()
    return questions

async def start(update: Update, context: CallbackContext) -> None:
    """Обработка команды /start."""
    user = update.message.from_user
    await update.message.reply_text(f"Привет, {user.first_name}! Хочешь пройти тест? Нажми /quiz чтобы начать.")

async def quiz(update: Update, context: CallbackContext) -> None:
    """Начало теста."""
    user_id = update.message.from_user.id
    user_data[user_id] = {"score": 0, "questions_asked": 0, "current_question": None}

    # Получаем 10 случайных вопросов из базы данных в отдельном потоке
    loop = asyncio.get_event_loop()
    questions = await loop.run_in_executor(executor, fetch_random_questions, 10)
    user_data[user_id]["questions"] = questions
    await ask_question(update, context)

async def ask_question(update: Update, context: CallbackContext) -> None:
    """Задаёт вопрос пользователю."""
    user_id = update.message.from_user.id
    user_state = user_data[user_id]

    if user_state["questions_asked"] >= 10:
        await end_quiz(update, context)
        return

    question = user_state["questions"][user_state["questions_asked"]]
    user_state["current_question"] = {
        "id": question[0],
        "text": question[1],
        "correct": question[2],
        "incorrect": question[3]
    }

    options = user_state["current_question"]["incorrect"] + [user_state["current_question"]["correct"]]
    random.shuffle(options)

    reply_markup = ReplyKeyboardMarkup([options[i:i + 2] for i in range(0, len(options), 2)], one_time_keyboard=True)
    await update.message.reply_text(f"Вопрос {user_state['questions_asked'] + 1}: {user_state['current_question']['text']}", reply_markup=reply_markup)

async def handle_answer(update: Update, context: CallbackContext) -> None:
    """Обрабатывает ответ пользователя."""
    user_id = update.message.from_user.id
    user_state = user_data[user_id]
    user_answer = update.message.text

    if user_answer == user_state["current_question"]["correct"]:
        user_state["score"] += 1
        await update.message.reply_text("Правильно! ✅")
    else:
        await update.message.reply_text(f"Неправильно! ❌ Правильный ответ: {user_state['current_question']['correct']}")

    user_state["questions_asked"] += 1
    await ask_question(update, context)

async def end_quiz(update: Update, context: CallbackContext) -> None:
    """Завершает тест и показывает результаты."""
    user_id = update.message.from_user.id
    user_state = user_data[user_id]

    await update.message.reply_text(
        f"Тест завершён! 🎉\n"
        f"Правильных ответов: {user_state['score']}\n"
        f"Неправильных ответов: {10 - user_state['score']}",
        reply_markup=ReplyKeyboardRemove()
    )


    del user_data[user_id]

def main() -> None:
    """Запуск бота."""
    application = Application.builder().token("7651648984:AAHTZylaIhLBYKNBiSTDDqon1SBeCMI7MGQ").build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("quiz", quiz))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_answer))

    application.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())