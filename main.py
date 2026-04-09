import io
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
import google.generativeai as genai

# --- КОНФИГУРАЦИЯ ---
# Ваш бесплатный ключ Google Gemini
GEMINI_API_KEY = "AIzaSyB6tP3wXWFvQeRCfr3idXyTAIVZDikdPX4"
# Ваш токен Telegram
TELEGRAM_TOKEN = "8760052358:AAEiwAxCTDjwx-FCaG4ZhAMYX_ZNNto7GJU"

# Настройка Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

async def analyze_with_gemini(image_bytes):
    """Анализ изображения через Gemini 1.5 Flash"""
    try:
        # Формируем контент для Gemini
        img_part = {"mime_type": "image/jpeg", "data": image_bytes}
        
        prompt = (
            "Ты — эксперт OSINT и криминалист. Проанализируй это фото и определи местоположение. "
            "Ищи любые зацепки: знаки, архитектуру, язык, растительность, тип розеток, номера машин. "
            "Выдай максимально четкий отчет строго по пунктам:\n\n"
            "🌍 СТРАНА:\n"
            "📍 ОБЛАСТЬ/РЕГИОН:\n"
            "🏙 ГОРОД:\n"
            "🛣 УЛИЦА:\n"
            "🕒 ЧАСОВОЙ ПОЯС:\n"
            "📸 ВЕРОЯТНОЕ УСТРОЙСТВО:\n"
            "👤 ВЛАДЕЛЕЦ (если есть зацепки):\n\n"
            "Если точных данных нет, напиши наиболее вероятный вариант на основе улик."
        )
        
        response = model.generate_content([prompt, img_part])
        return response.text
    except Exception as e:
        return f"Ошибка при анализе: {str(e)}"

@dp.message(F.photo | F.document)
async def handle_photo(message: types.Message):
    # Проверка: фото или документ-картинка
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document and message.document.mime_type.startswith("image/"):
        file_id = message.document.file_id
    else:
        return

    status_msg = await message.answer("🔍 *Изучаю изображение...*", parse_mode="Markdown")

    try:
        # Скачиваем файл в буфер памяти
        file_info = await bot.get_file(file_id)
        downloaded_file = await bot.download_file(file_info.file_path)
        image_bytes = downloaded_file.read()
        
        # Отправляем в ИИ
        report = await analyze_with_gemini(image_bytes)
        
        await status_msg.edit_text(f"✅ **РЕЗУЛЬТАТ АНАЛИЗА:**\n\n{report}", parse_mode="Markdown")
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Произошла ошибка: {str(e)}")

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Пришлите фото, и я определю, где оно было сделано.")

async def main():
    print("Бот запущен на базе Gemini)...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
