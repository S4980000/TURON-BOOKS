import logging
import os
import sys
import django
import asyncio

from asgiref.sync import sync_to_async
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.dispatcher.filters import CommandStart, Command
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
ADMIN_IDS = os.getenv("ADMIN_IDS", "757652114")
ADMIN_IDS = list(map(int, ADMIN_IDS.split(',')))

from library.models import Category, Book

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())


class BookStates(StatesGroup):
    CHOOSING = State()


class AddBookStates(StatesGroup):
    WAIT_FILE = State()
    WAIT_CAPTION = State()
    CHOOSING = State()

# default number of buttons per row in keyboards
ROW_SIZE = 3


def build_keyboard(options, include_back=False, row_size=ROW_SIZE):
    """
    Build a ReplyKeyboardMarkup with buttons for each option.
    If include_back=True, add an "Ortga" button in its own top row.
    Then arrange option buttons into rows of length `row_size`.
    """
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    # add back button as a separate row if requested
    if include_back:
        kb.row(types.KeyboardButton("Ortga"))
    # create buttons for options
    buttons = [types.KeyboardButton(opt) for opt in options]
    # chunk into rows
    for i in range(0, len(buttons), row_size):
        kb.row(*buttons[i:i+row_size])
    return kb


@dp.message_handler(CommandStart())
async def start_command(message: types.Message, state: FSMContext):
    await state.finish()
    top_cats = await sync_to_async(list)(
        Category.objects.filter(parent__isnull=True).order_by('name')
    )
    if not top_cats:
        return await message.reply("❗ Hech qanday bo‘lim mavjud emas.")

    names = [cat.name for cat in top_cats]
    kb = build_keyboard(names, include_back=False)

    await state.update_data(parent_id=None)
    await message.reply("📚 Bo‘limni tanlang:", reply_markup=kb)
    await BookStates.CHOOSING.set()


@dp.message_handler(Command('add_book'), state='*')
async def cmd_add_book(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return await message.reply("❌ Sizga kitob qo‘shish huquqi berilmagan.")
    await state.finish()
    await message.reply(
        "📥 Iltimos, kitob faylini (hujjat sifatida) yuboring.",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await AddBookStates.WAIT_FILE.set()


@dp.message_handler(state=AddBookStates.WAIT_FILE, content_types=types.ContentType.DOCUMENT)
async def add_book_file(message: types.Message, state: FSMContext):
    file_id = message.document.file_id
    file_caption = message.caption or ''
    await state.update_data(file_id=file_id, file_caption=file_caption)

    # Prompt for caption with skip and use-original buttons
    kb = build_keyboard([
        "Bo'sh qoldirish",
        "O`zini izohini qoldirish"
    ], include_back=False, row_size=2)
    await message.reply(
        "✍️ Iltimos, ushbu kitob uchun izoh yuboring yoki quyidagilardan birini tanlang:",
        reply_markup=kb
    )
    await AddBookStates.WAIT_CAPTION.set()


@dp.message_handler(state=AddBookStates.WAIT_FILE, content_types=types.ContentType.ANY)
async def enforce_document(message: types.Message):
    return await message.reply("⚠️ Iltimos, kitobni hujjat sifatida yuboring.")


@dp.message_handler(state=AddBookStates.WAIT_CAPTION, content_types=types.ContentType.TEXT)
async def add_book_caption(message: types.Message, state: FSMContext):
    text = message.text.strip()

    # Determine caption
    if text == "Bo'sh qoldirish":
        caption = ''
    elif text == "O`zini izohini qoldirish":
        data = await state.get_data()
        caption = data.get('file_caption', '')
    else:
        caption = text
    await state.update_data(caption=caption)

    # Prompt for category (top-level) without back
    top_cats = await sync_to_async(list)(
        Category.objects.filter(parent__isnull=True).order_by('name')
    )
    if not top_cats:
        await state.finish()
        return await message.reply("❗ Hech qanday bo‘lim mavjud emas. Bekor qilindi.")

    names = [cat.name for cat in top_cats]
    kb = build_keyboard(names, include_back=False)

    await state.update_data(parent_id=None)
    await message.reply("📚 Bo‘limni tanlang:", reply_markup=kb)
    await AddBookStates.CHOOSING.set()


@dp.message_handler(state=AddBookStates.CHOOSING, content_types=types.ContentType.TEXT)
async def add_book_choose_category(message: types.Message, state: FSMContext):
    text = message.text
    data = await state.get_data()
    parent_id = data.get('parent_id')
    file_id = data['file_id']
    caption = data.get('caption', '')

    # Handle back
    if text == "Ortga":
        if parent_id is None:
            new_parent_id = None
        else:
            parent_cat = await sync_to_async(Category.objects.get)(id=parent_id)
            new_parent_id = parent_cat.parent_id
        cats_query = Category.objects.filter(parent_id=new_parent_id).order_by('name')
        cats = await sync_to_async(list)(cats_query)
        names = [cat.name for cat in cats]
        kb = build_keyboard(names, include_back=(new_parent_id is not None))
        await state.update_data(parent_id=new_parent_id)
        return await message.reply("📚 Bo‘limni tanlang:", reply_markup=kb)

    # Find chosen
    chosen = await sync_to_async(Category.objects.filter(
        name=text, parent_id=parent_id
    ).first)()
    if not chosen:
        return await message.reply("⚠️ Noma'lum bo‘lim – iltimos, tugmalardan foydalaning.")

    # Check children
    children = await sync_to_async(list)(
        Category.objects.filter(parent=chosen).order_by('name')
    )
    if children:
        names = [c.name for c in children]
        kb = build_keyboard(names, include_back=True)
        await state.update_data(parent_id=chosen.id)
        return await message.reply(
            f"📂 *{chosen.name}* bo‘limining kichik bo‘limlari:",
            reply_markup=kb, parse_mode="Markdown"
        )

    # Leaf: save
    await sync_to_async(Book.objects.create)(
        category=chosen, file_id=file_id, caption=caption
    )
    await state.finish()
    return await message.reply(
        f"✅ Kitob *{chosen.name}* bo‘limiga saqlandi!",
        parse_mode="Markdown"
    )


@dp.message_handler(state=BookStates.CHOOSING, content_types=types.ContentType.TEXT)
async def pick_category(message: types.Message, state: FSMContext):
    text = message.text
    data = await state.get_data()
    parent_id = data.get('parent_id')

    # Handle back
    if text == "Ortga":
        if parent_id is None:
            new_parent_id = None
        else:
            parent_cat = await sync_to_async(Category.objects.get)(id=parent_id)
            new_parent_id = parent_cat.parent_id
        cats = await sync_to_async(list)(
            Category.objects.filter(parent_id=new_parent_id).order_by('name')
        )
        names = [c.name for c in cats]
        kb = build_keyboard(names, include_back=(new_parent_id is not None))
        await state.update_data(parent_id=new_parent_id)
        return await message.reply("📚 Bo‘limni tanlang:", reply_markup=kb)

    # Find chosen
    chosen_cat = await sync_to_async(Category.objects.filter(
        name=text, parent_id=parent_id
    ).first)()
    if not chosen_cat:
        return await message.reply("⚠️ Noma'lum bo‘lim – iltimos, tugmalardan foydalaning.")

    children = await sync_to_async(list)(chosen_cat.children.all())
    if children:
        names = [c.name for c in children]
        kb = build_keyboard(names, include_back=True)
        await state.update_data(parent_id=chosen_cat.id)
        return await message.reply(
            f"📂 *{chosen_cat.name}* bo‘limining kichik bo‘limlari:",
            reply_markup=kb, parse_mode="Markdown"
        )

    # Leaf: send books immediately
    books = await sync_to_async(list)(
        chosen_cat.books.all().order_by('-created_date')
    )
    if not books:
        return await message.reply("🚫 Ushbu bo‘limda kitob topilmadi.")
    for book in books:
        try:
            await bot.send_document(message.chat.id, book.file_id, caption=book.caption)
        except Exception:
            logging.error(f'Sending file error with id: {book.id}')
        await asyncio.sleep(0.1)

    # Keep same keyboard
    return


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
