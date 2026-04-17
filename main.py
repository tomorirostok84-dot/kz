import asyncio
import sqlite3
import time
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.types import BotCommand

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8772367182:AAE1QIMRpMYuBIai-cGusOzYSXaqjeGfMw4"
OWNER_ID = 8777986259 

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- БАЗА ДАННЫХ ---
conn = sqlite3.connect("gladiator_pro.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS numbers 
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, 
                   number TEXT, status TEXT, vstal_time REAL, slet_time REAL)''')
cursor.execute('CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)')
cursor.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (OWNER_ID,))
conn.commit()

# --- СОСТОЯНИЯ ---
class Process(StatesGroup):
    waiting_number = State()
    waiting_screenshot = State()
    add_admin = State()
    rem_admin = State()
    transfer_owner = State()

# --- ФУНКЦИИ ---
def is_admin(user_id):
    cursor.execute("SELECT 1 FROM admins WHERE user_id=?", (user_id,))
    return cursor.fetchone() is not None

# --- КЛАВИАТУРЫ ---
def main_kb():
    builder = ReplyKeyboardBuilder()
    builder.row(types.KeyboardButton(text="➕ Добавить номер"))
    builder.row(types.KeyboardButton(text="👤 Профиль"), types.KeyboardButton(text="⌛ Очередь"))
    builder.row(types.KeyboardButton(text="⚙️ Админка"))
    return builder.as_markup(resize_keyboard=True)

def admin_panel_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить админа", callback_data="adm_add")
    builder.button(text="➖ Снять админа", callback_data="adm_rem")
    builder.button(text="📜 Список админов", callback_data="adm_list")
    builder.button(text="🟢 Активные", callback_data="adm_active")
    builder.button(text="📊 Статистика", callback_data="adm_stats")
    builder.button(text="👑 Передать владельца", callback_data="adm_transfer")
    builder.button(text="❌ Закрыть", callback_data="adm_close")
    builder.adjust(2)
    return builder.as_markup()

# --- ЛОГИКА ПОЛЬЗОВАТЕЛЯ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    text = (
        f"👋 **Добро пожаловать в Gladiator Team!**\n\n"
        f"┌ Безхолд: 6$ 20 минут\n"
        f"└ ФБХ: 3$ 5 минут\n\n"
        f"⚠️ Примечание: Оплата будет в отдельной группе\n\n"
        f"👇 **Выберите раздел:**"
    )
    await message.answer(text, reply_markup=main_kb(), parse_mode="Markdown")

@dp.message(F.text == "👤 Профиль")
async def show_profile(message: types.Message):
    u_id = message.from_user.id
    username = f"@{message.from_user.username}" if message.from_user.username else "Нет"
    
    cursor.execute("SELECT COUNT(*) FROM numbers WHERE user_id=? AND status='Слет' AND vstal_time IS NOT NULL", (u_id,))
    count_accs = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM numbers WHERE status='Обработка' OR status='Активен'")
    in_work = cursor.fetchone()[0]
    
    text = (
        f"👤 **ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ**\n\n"
        f"┏ Имя: {message.from_user.full_name}\n"
        f"┣ Юзернейм: {username}\n"
        f"┗ ID: `{u_id}`\n\n"
        f"📱 **СДАННЫЕ АККАУНТЫ**\n"
        f"┏ WhatsApp аккаунтов: {count_accs} шт.\n"
        f"┗ Доступно номеров: {max(0, 100 - in_work)} из 100"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "⌛ Очередь")
async def show_q(message: types.Message):
    cursor.execute("SELECT COUNT(*) FROM numbers WHERE status='Обработка'")
    await message.answer(f"⌛ Сейчас номеров в очереди: **{cursor.fetchone()[0]}**", parse_mode="Markdown")

@dp.message(F.text == "➕ Добавить номер")
async def ask_num(message: types.Message, state: FSMContext):
    await state.set_state(Process.waiting_number)
    await message.answer("📲 Введите номер телефона (ОБЯЗАТЕЛЬНО С \"+\")")

@dp.message(Process.waiting_number)
async def get_num(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        return
    u_in = message.text.replace(" ", "").replace("-", "")
    if u_in.startswith('+77') and len(u_in) == 12:
        cursor.execute("INSERT INTO numbers (user_id, username, number, status) VALUES (?, ?, ?, ?)", (message.from_user.id, message.from_user.username, u_in, "Обработка"))
        db_id = cursor.lastrowid
        conn.commit()
        kb = InlineKeyboardBuilder().button(text="📥 Дать код", callback_data=f"adm_give_{db_id}_{message.from_user.id}").as_markup()
        await bot.send_message(OWNER_ID, f"📱 Номер #{db_id}\nОт: @{message.from_user.username}\n`{u_in}`", reply_markup=kb)
        await message.answer("✅ Ваш номер был принят в обработку, ожидайте кода!")
        await state.clear()
    else:
        await message.answer("❌ Ошибка! Формат: +77XXXXXXXXX")

# --- ЛОГИКА АДМИНКИ ---

@dp.message(F.text == "⚙️ Админка")
async def adm_main(message: types.Message):
    if not is_admin(message.from_user.id): return
    await message.answer("🛠 **Панель администратора Gladiator Team**", reply_markup=admin_panel_kb(), parse_mode="Markdown")

@dp.callback_query(F.data == "adm_active")
async def adm_active_list(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return
    cursor.execute("SELECT id, username, number FROM numbers WHERE status='Активен'")
    rows = cursor.fetchall()
    if not rows: return await callback.answer("Активных номеров нет", show_alert=True)
    
    kb = InlineKeyboardBuilder()
    for r in rows:
        kb.button(text=f"#{r[0]} | @{r[1]}", callback_data=f"manage_{r[0]}")
    kb.adjust(1)
    await callback.message.answer("🟢 Активные номера (нажми для слета):", reply_markup=kb.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith("manage_"))
async def manage_num(callback: types.CallbackQuery):
    db_id = callback.data.split("_")[1]
    cursor.execute("SELECT username, number, vstal_time FROM numbers WHERE id=?", (db_id,))
    res = cursor.fetchone()
    dur = round((time.time() - res[2]) / 60, 1)
    
    kb = InlineKeyboardBuilder().button(text="♻️ ОТМЕТИТЬ СЛЕТ", callback_data=f"kill_{db_id}")
    await callback.message.answer(f"📦 Номер: `{res[1]}`\n👤 Юзер: @{res[0]}\n⏳ Простоял: {dur} мин.", reply_markup=kb.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith("kill_"))
async def kill_num(callback: types.CallbackQuery):
    db_id = callback.data.split("_")[1]
    now = time.time()
    cursor.execute("SELECT user_id, vstal_time FROM numbers WHERE id=?", (db_id,))
    res = cursor.fetchone()
    u_id, v_time = res[0], res[1]
    dur = round((now - v_time) / 60, 1)
    
    cursor.execute("UPDATE numbers SET status='Слет', slet_time=? WHERE id=?", (now, db_id))
    conn.commit()
    
    await bot.send_message(u_id, f"❌ Ваш номер слетел. Простоял: {dur} мин.")
    await callback.message.edit_text(f"Зафиксирован слет #{db_id}. Простоял: {dur} мин.")

@dp.callback_query(F.data == "adm_list")
async def adm_list_show(callback: types.CallbackQuery):
    cursor.execute("SELECT user_id FROM admins")
    admins = cursor.fetchall()
    text = "📜 **Список администраторов:**\n\n"
    for a in admins:
        role = "👑 Владелец" if a[0] == OWNER_ID else "🛠 Админ"
        text += f"• `{a[0]}` ({role})\n"
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "adm_add")
async def adm_add_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != OWNER_ID: return await callback.answer("Только для владельца!", show_alert=True)
    await state.set_state(Process.add_admin)
    await callback.message.answer("Введите ID нового админа:")
    await callback.answer()

@dp.message(Process.add_admin)
async def adm_add_fin(message: types.Message, state: FSMContext):
    if message.text.isdigit():
        cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (int(message.text),))
        conn.commit()
        await message.answer(f"✅ Пользователь `{message.text}` назначен админом.")
    await state.clear()

@dp.callback_query(F.data == "adm_rem")
async def adm_rem_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != OWNER_ID: return await callback.answer("Только для владельца!", show_alert=True)
    await state.set_state(Process.rem_admin)
    await callback.message.answer("Введите ID админа, которого нужно СНЯТЬ:")
    await callback.answer()

@dp.message(Process.rem_admin)
async def adm_rem_fin(message: types.Message, state: FSMContext):
    if message.text.isdigit():
        target = int(message.text)
        if target != OWNER_ID:
            cursor.execute("DELETE FROM admins WHERE user_id=?", (target,))
            conn.commit()
            await message.answer(f"❌ Админ `{target}` снят.")
        else:
            await message.answer("❌ Нельзя снять владельца.")
    await state.clear()

@dp.callback_query(F.data.startswith("adm_give_"))
async def adm_give(callback: types.CallbackQuery, state: FSMContext):
    d = callback.data.split("_")
    await state.update_data(target_db_id=d[2], target_u_id=d[3])
    await state.set_state(Process.waiting_screenshot)
    await callback.message.answer(f"Пришлите код для #{d[2]}")
    await callback.answer()

@dp.message(Process.waiting_screenshot)
async def adm_send_code(message: types.Message, state: FSMContext):
    data = await state.get_data()
    kb = InlineKeyboardBuilder().button(text="✅ Ввел", callback_data=f"u_vvel_{data['target_db_id']}").as_markup()
    cap = "⚠️ **Введите код в течении 3 минут!**"
    if message.photo: await bot.send_photo(data['target_u_id'], message.photo[-1].file_id, caption=cap, reply_markup=kb)
    else: await bot.send_message(data['target_u_id'], f"Код: `{message.text}`\n\n{cap}", reply_markup=kb)
    await message.answer("Отправлено.")
    await state.clear()

@dp.callback_query(F.data.startswith("u_vvel_"))
async def u_vvel(callback: types.CallbackQuery):
    db_id = callback.data.split("_")[2]
    kb = InlineKeyboardBuilder().button(text="💎 Встал", callback_data=f"fin_vstal_{db_id}").button(text="♻️ Слет", callback_data=f"fin_slet_{db_id}").as_markup()
    await bot.send_message(OWNER_ID, f"👤 Юзер @{callback.from_user.username} ввел код для #{db_id}", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("fin_"))
async def fin_deal(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    res, db_id = parts[1], parts[2]
    cursor.execute("SELECT user_id FROM numbers WHERE id=?", (db_id,))
    u_id = cursor.fetchone()[0]
    if res == "vstal":
        cursor.execute("UPDATE numbers SET status='Активен', vstal_time=? WHERE id=?", (time.time(), db_id))
        await bot.send_message(u_id, "✅ Номер встал!")
    else:
        cursor.execute("UPDATE numbers SET status='Слет', slet_time=0 WHERE id=?", (db_id,))
        await bot.send_message(u_id, "❌ Слет.")
    conn.commit()
    await callback.message.edit_text(f"Завершено: {res.upper()}")

@dp.callback_query(F.data == "adm_stats")
async def show_stats(callback: types.CallbackQuery):
    cursor.execute("SELECT id, username, number, vstal_time, slet_time FROM numbers WHERE status='Слет' AND vstal_time IS NOT NULL ORDER BY id DESC LIMIT 10")
    rows = cursor.fetchall()
    text = "📊 **Статистика:**\n\n"
    for r in rows:
        dur = round((r[4] - r[3]) / 60, 1) if r[4] > 0 else 0
        text += f"📱 `{r[2]}` | @{r[1]}\n⏱ Простоял: {dur} мин.\n---\n"
    await callback.message.answer(text if rows else "Пусто", parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "adm_close")
async def close_adm(callback: types.CallbackQuery):
    await callback.message.delete()

async def main():
    await bot.set_my_commands([BotCommand(command='/start', description='Запустить')])
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
