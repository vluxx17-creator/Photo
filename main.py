import io
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
from openai import OpenAI
from datetime import datetime
import pytz

# --- КОНФИГУРАЦИЯ ---
TELEGRAM_TOKEN = "8760052358:AAEiwAxCTDjwx-FCaG4ZhAMYX_ZNNto7GJU"
OPENAI_API_KEY = "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"

client = OpenAI(api_key=OPENAI_API_KEY)
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
geolocator = Nominatim(user_agent="geo_osint_pro")
tf = TimezoneFinder()

logging.basicConfig(level=logging.INFO)

def get_exif(image):
    """Извлекает метаданные напрямую из объекта Image"""
    try:
        exif = image._getexif()
        if not exif:
            return {}
        return {TAGS.get(tag, tag): value for tag, value in exif.items()}
    except Exception:
        return {}

def get_gps(exif_data):
    """Преобразует GPS-данные в координаты"""
    if "GPSInfo" not in exif_data:
        return None
    
    gps_info = exif_data["GPSInfo"]
    def to_deg(val):
        d = float(val[0])
        m = float(val[1])
        s = float(val[2])
        return d + (m / 60.0) + (s / 3600.0)

    try:
        lat = to_deg(gps_info[2])
        if gps_info[1] != 'N': lat = -lat
        lon = to_deg(gps_info[4])
        if gps_info[3] != 'E': lon = -lon
        return lat, lon
    except:
        return None

async def ai_analysis(photo_url):
    """Глубокое исследование изображения через GPT-4o Vision"""
    prompt = (
        "Проанализируй фото как эксперт OSINT. Твоя задача — определить локацию с максимальной точностью. "
        "Смотри на номера машин, дорожные знаки, архитектуру и растительность. "
        "Выдай ответ СТРОГО в таком формате (без лишних слов):\n\n"
        "Страна: \n"
        "Область: \n"
        "Город: \n"
        "Часовой пояс: \n"
        "Улица: \n"
        "Устройство: \n"
        "Владелец фото: \n\n"
        "Если данных нет в метаданных, сделай предположение 'Устройства' по качеству фото, "
        "а 'Владельца' определи по водяным знакам или напиши 'Неизвестен'."
    )
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": photo_url}},
                ],
            }
        ],
        max_tokens=600
    )
    return response.choices[0].message.content

@dp.message(F.photo | F.document)
async def handle_photo(message: types.Message):
    # Работаем только с картинками (фото или документы-картинки)
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document and message.document.mime_type.startswith("image/"):
        file_id = message.document.file_id
    else:
        return

    status_msg = await message.answer("🔍 *Провожу глубокое сканирование...*", parse_mode="Markdown")

    try:
        # Получаем данные файла
        file_info = await bot.get_file(file_id)
        file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_info.file_path}"
        
        # Скачиваем для EXIF
        downloaded_file = await bot.download_file(file_info.file_path)
        img = Image.open(io.BytesIO(downloaded_file.read()))
        
        # 1. Извлекаем то, что скрыто в файле
        exif = get_exif(img)
        gps_coords = get_gps(exif)
        
        device_exif = exif.get("Model", "Не определено")
        owner_exif = exif.get("Artist") or exif.get("Copyright") or "Неизвестен"
        
        # 2. Основной анализ через ИИ
        report = await ai_analysis(file_url)

        # 3. Если есть GPS, уточняем данные через картографию
        if gps_coords:
            lat, lon = gps_coords
            location = geolocator.reverse(f"{lat}, {lon}", language="ru")
            tz_name = tf.timezone_at(lng=lon, lat=lat)
            
            # Если GPS есть, переписываем отчет данными из координат для 100% точности
            addr = location.raw.get('address', {})
            tz_info = "Неизвестен"
            if tz_name:
                now = datetime.now(pytz.timezone(tz_name))
                tz_info = f"{tz_name} (UTC{now.strftime('%z')})"

            final_report = (
                f"Страна: {addr.get('country', '—')}\n"
                f"Область: {addr.get('state', '—')}\n"
                f"Город: {addr.get('city', addr.get('town', '—'))}\n"
                f"Часовой пояс: {tz_info}\n"
                f"Улица: {addr.get('road', '—')} {addr.get('house_number', '')}\n"
                f"Устройство: {device_exif}\n"
                f"Владелец фото: {owner_exif}\n"
                f"\n📍 *Точные координаты:* `{lat}, {lon}`"
            )
        else:
            # Если GPS нет — выводим отчет от ИИ
            final_report = report

        await status_msg.edit_text(f"✅ **ОТЧЕТ СФОРМИРОВАН:**\n\n{final_report}", parse_mode="Markdown")

    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка при анализе: {str(e)}")

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Пришлите фото для поиска места.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
