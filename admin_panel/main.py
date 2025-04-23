import logging
import os
import sys
import django
import asyncio
from asgiref.sync import sync_to_async
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.dispatcher.filters import CommandStart
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(__file__)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

load_dotenv()
logging.basicConfig(level=logging.INFO)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
BOT_TOKEN = os.getenv("BOT_TOKEN")

from library.models import Category, Book

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())


class BookStates(StatesGroup):
    CHOOSING = State()


# 🔹 Start command
@dp.message_handler(CommandStart())
async def start_command(message: types.Message, state: FSMContext):
    await state.finish()
    top_cats = await sync_to_async(list)(
        Category.objects.filter(parent__isnull=True).order_by('name')
    )
    if not top_cats:
        return await message.reply("❗ No categories available.")

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)

    for category in top_cats:
        kb.add(category.name)

    await state.update_data(parent_id=None)
    await message.reply("📚 Select a category:", reply_markup=kb)
    await BookStates.CHOOSING.set()


@dp.message_handler(state=BookStates.CHOOSING, content_types=types.ContentTypes.TEXT)
async def pick_category(message: types.Message, state: FSMContext):
    data = await state.get_data()
    parent_id = data.get('parent_id')  # None for top level

    chosen_cat_text = message.text
    chosen_cat = await sync_to_async(Category.objects.filter(
        name=chosen_cat_text,
        parent_id=parent_id
    ).first)()

    if not chosen_cat:
        return await message.reply(
            "⚠️ I didn’t recognize that category. Please choose using the buttons."
        )

    children_cats = await sync_to_async(list)(
        chosen_cat.children.all()
    )

    if children_cats:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        for child in children_cats:
            kb.add(child.name)
        await state.update_data(parent_id=chosen_cat.id)
        return await message.reply(
            f"📂 Subcategories of *{chosen_cat.name}*:",
            reply_markup=kb, parse_mode="Markdown"
        )

    # leaf category reached → fetch books
    await state.finish()
    await message.reply(
        f"📖 Fetching books in *{chosen_cat.name}*…",
        reply_markup=types.ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )

    books = await sync_to_async(list)(
        chosen_cat.books.all().order_by('-created_date')
    )

    if not books:
        return await message.reply("🚫 No books found in this category.")

    # send each with 100  ms delay
    print(books)
    for book in books:
        try:
            await bot.send_document(chat_id=message.chat.id, document=book.file_id, caption=book.caption)
        except:
            logging.error(f'Sending file error with id: {book.id}')
        await asyncio.sleep(0.1)


# 🔹 Run bot
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
