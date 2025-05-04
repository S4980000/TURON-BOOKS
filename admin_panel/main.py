import logging
import os
import sys
import django

from asgiref.sync import sync_to_async
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.dispatcher.filters import CommandStart, Command
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
# ADMIN_IDS = os.getenv("ADMIN_IDS", "757652114")
# ADMIN_IDS = list(map(int, ADMIN_IDS.split(',')))

PROJECT_ROOT = os.path.dirname(__file__)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.contrib.auth.models import User
from library.models import Category, Book

# ADMIN_IDS = User.objects.all().values_list('first_name', flat=True)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())


class BookStates(StatesGroup):
    CHOOSING = State()


class AddBookStates(StatesGroup):
    CHOOSING = State()
    WAIT_FILE = State()


# default number of buttons per row in keyboards
ROW_SIZE = 2


def build_keyboard(options, include_back=False, row_size=ROW_SIZE):
    """
    Build a ReplyKeyboardMarkup with buttons for each option.
    If include_back=True, add an "Ortga" button in its own top row.
    Then arrange option buttons into rows of length `row_size`.
    """
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    # add back button as a separate row if requested
    if include_back:
        kb.row(types.KeyboardButton("Ortga"))
    # create buttons for options
    buttons = [types.KeyboardButton(opt) for opt in options]
    # chunk into rows
    for i in range(0, len(buttons), row_size):
        kb.row(*buttons[i:i + row_size])
    return kb


@dp.message_handler(CommandStart(), state="*")
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
    ADMIN_IDS = await sync_to_async(list)(
        User.objects.values_list('id', flat=True)
    )
    if message.from_user.id not in ADMIN_IDS:
        return await message.reply("❌ Sizga kitob qo‘shish huquqi berilmagan.")
    await state.finish()
    top_cats = await sync_to_async(list)(
        Category.objects.filter(parent__isnull=True).order_by('name')
    )
    if not top_cats:
        return await message.reply("❗ Hech qanday bo‘lim mavjud emas.")

    names = [cat.name for cat in top_cats]
    kb = build_keyboard(names, include_back=False)

    await state.update_data(parent_id=None)
    await message.reply("📚 Bo‘limni tanlang (kitob qo‘shish uchun):", reply_markup=kb)
    await AddBookStates.CHOOSING.set()


@dp.message_handler(state=AddBookStates.CHOOSING, content_types=types.ContentType.TEXT)
async def add_book_choose_category(message: types.Message, state: FSMContext):
    text = message.text
    data = await state.get_data()
    parent_id = data.get('parent_id')

    # Handle back navigation
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

    # Find chosen category
    chosen = await sync_to_async(Category.objects.filter(
        name=text, parent_id=parent_id
    ).first)()
    if not chosen:
        return await message.reply("⚠️ Noma'lum bo‘lim – iltimos, tugmalardan foydalaning.")

    # If category has children, drill down
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

    # Leaf category selected: prepare to collect files
    await state.update_data(category_id=chosen.id, files=[])  # initialize list

    # Show confirm/cancel buttons
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(types.KeyboardButton("Tasdiqlash ✔"), types.KeyboardButton("Bekor qilish ❌"))

    await message.reply(
        f"📥 Tanlangan bo‘lim: {chosen.name}\n"
        "Iltimos, kitob hujjatlarini yuboring.\n"
        "Yuborishni tugatgach «Tasdiqlash ✔» yoki «Bekor qilish ❌» tugmasini bosing.",
        reply_markup=kb
    )
    await AddBookStates.WAIT_FILE.set()


@dp.message_handler(state=AddBookStates.WAIT_FILE, content_types=types.ContentType.DOCUMENT)
async def collect_book_files(message: types.Message, state: FSMContext):
    """Collect each sent document into the session before confirmation."""
    data = await state.get_data()
    files = data.get('files', [])
    file_id = message.document.file_id
    file_name = message.document.file_name
    caption = message.caption or ''
    files.append({'file_id': file_id, 'file_name': file_name, 'caption': caption})
    await state.update_data(files=files)

    await message.reply("✅ Kitob hujjati qabul qilindi. Yana yuborishingiz yoki tasdiqlashingiz mumkin.")


@dp.message_handler(state=AddBookStates.WAIT_FILE, content_types=types.ContentType.TEXT)
async def process_book_confirmation(message: types.Message, state: FSMContext):
    """Handle confirmation or cancellation of collected files."""
    text = message.text
    if text == "Tasdiqlash ✔":
        data = await state.get_data()
        category_id = data['category_id']
        files = data.get('files', [])
        # Save all collected files as Book instances
        category = await sync_to_async(Category.objects.get)(id=category_id)
        for f in files:
            await sync_to_async(Book.objects.create)(
                category=category,
                file_id=f['file_id'],
                file_name=f['file_name'],
                caption=f['caption']
            )
        count = len(files)
        await state.finish()
        await message.reply(f"✅ {count} ta kitob saqlandi!", reply_markup=types.ReplyKeyboardRemove())

    elif text == "Bekor qilish ❌":
        await state.finish()
        await message.reply("❌ Kitob qo‘shish bekor qilindi.", reply_markup=types.ReplyKeyboardRemove())
    else:
        return await message.reply("⚠️ Noma'lum buyruq – iltimos, tugmalardan foydalaning.")


@dp.message_handler(state=AddBookStates.WAIT_FILE, content_types=types.ContentType.ANY)
async def enforce_document_or_confirm(message: types.Message):
    """Enforce that only documents or confirm/cancel texts are accepted."""
    return await message.reply(
        "⚠️ Iltimos, hujjat yuboring yoki «Tasdiqlash ✔»/«Bekor qilish ❌» tugmasini bosing."
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
        return await message.reply("Sizning so`rovingiz bo`yicha ma'lumot topilmadi.")
    for book in books:
        try:
            await bot.send_document(message.chat.id, book.file_id, caption=book.caption)
        except Exception:
            logging.error(f'Sending file error with id: {book.id}')
        # await asyncio.sleep(0.1)

    # Keep same keyboard
    return


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
