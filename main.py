import json
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from aiogram.dispatcher.filters import CommandStart
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup

BOT_TOKEN = "AAHWb2H1civWxgqJ6Ut7R0hmtGqqCxA_EOw"

# 🔹 Logging
logging.basicConfig(level=logging.INFO)

# 🔹 Bot & Dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

# 🔹 Load books data
with open("books.json", "r", encoding="utf-8") as f:
    books_data = json.load(f)

# 🔹 State management
class BookStates(StatesGroup):
    waiting_for_direction = State()
    waiting_for_book = State()

# 🔹 Start command
@dp.message_handler(CommandStart())
async def start_command(message: types.Message, state: FSMContext):
    await state.finish()
    keyboard = InlineKeyboardMarkup()
    for direction in books_data:
        keyboard.add(InlineKeyboardButton(text=direction, callback_data=f"dir:{direction}"))
    await message.answer("📚 Yo‘nalishni tanlang:", reply_markup=keyboard)
    await BookStates.waiting_for_direction.set()

# 🔹 Direction tanlangani
@dp.callback_query_handler(lambda c: c.data.startswith("dir:"), state=BookStates.waiting_for_direction)
async def direction_chosen(callback_query: types.CallbackQuery, state: FSMContext):
    direction = callback_query.data.split(":")[1]
    await state.update_data(direction=direction)

    keyboard = InlineKeyboardMarkup()
    for book in books_data[direction]:
        keyboard.add(InlineKeyboardButton(text=book['title'], callback_data=f"book:{book['file']}"))

    await bot.send_message(callback_query.from_user.id, f"📖 Tanlangan yo‘nalish: {direction}\nKitobni tanlang:", reply_markup=keyboard)
    await BookStates.waiting_for_book.set()

# 🔹 Kitob tanlangani
@dp.callback_query_handler(lambda c: c.data.startswith("book:"), state=BookStates.waiting_for_book)
async def book_chosen(callback_query: types.CallbackQuery, state: FSMContext):
    file_name = callback_query.data.split(":")[1]
    file_path = os.path.join("books", file_name)

    if os.path.exists(file_path):
        await bot.send_document(callback_query.from_user.id, types.InputFile(file_path))
    else:
        await bot.send_message(callback_query.from_user.id, "❌ Fayl topilmadi.")

    await state.finish()

# 🔹 Run bot
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
