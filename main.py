import asyncio
import os
import requests
import telegram

from dotenv import load_dotenv


load_dotenv()

# Конфігурація
BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ZENEDU_API_TOKEN = os.environ.get("ZENEDU_API_TOKEN")
ZENEDU_BOT_ID = os.environ.get("ZENEDU_BOT_ID")

# Словник матеріалів
MATERIALS = {
    1: {'title': 'ДСП', 'density': 0.70},
    2: {'title': 'МДФ', 'density': 0.90},
    3: {'title': 'Пробкове дерево', 'density': 0.12},
    4: {'title': 'Бетон', 'density': 2.40},
    5: {'title': 'Фанера', 'density': 0.45},
    6: {'title': 'Сталь', 'density': 7.80},
    7: {'title': 'Гіпсокартон', 'density': 0.90},
    8: {'title': 'Скло', 'density': 2.60},
    9: {'title': 'Мармур', 'density': 2.70},
    10: {'title': 'Тверда деревина, волога', 'density': 0.90},
    11: {'title': 'Тверда деревина, суха (бук)', 'density': 0.80},
    12: {'title': 'Кора пробкового дерева', 'density': 0.30},
    13: {'title': 'Пластик (PE)', 'density': 1.50},
    14: {'title': 'Акриловий пластик', 'density': 1.20},
    15: {'title': 'Папір', 'density': 1.10},
    16: {'title': 'Пориста деревина', 'density': 1.20},
    17: {'title': 'Картон', 'density': 0.45},
    18: {'title': 'М’яка деревина, волога', 'density': 0.70},
    19: {'title': 'М’яка деревина, суха (сосна)', 'density': 0.50},
}

# Ініціалізуємо словник для зберігання даних про стан користувачів
# Це простий приклад, для продакшн-версії краще використовувати базу даних
user_states = {}

def get_active_zenedu_subscribers():
    """Отримує список активних підписників Zenedu."""
    active_subscribers = []
    url = f"https://app.zenedu.io/api/v1/bot/{ZENEDU_BOT_ID}/subscribers"
    headers = {
        "Authorization": f"Bearer {ZENEDU_API_TOKEN}",
        "Accept": "application/json"
    }

    while url:
        response = requests.get(url, params={'per_page': '100'}, headers=headers)
        if response.status_code == 200:
            data = response.json()
            for subscriber in data.get('data', []):
                if subscriber.get('is_active') is True and subscriber.get('is_blocked') is False:
                    active_subscribers.append(subscriber.get('user_id'))
            url = data.get('links', {}).get('next')
        else:
            # Handle error
            print(f"Error: {response.url}")
            print(f"Error: {response.status_code}")
            print(f"Error message: {response.text}")
            url = None
    return active_subscribers

async def async_telegram_bot(request):
    """Головна функція, яка обробляє запити від Telegram."""
    bot = telegram.Bot(token=BOT_TOKEN)

    if request.method == "POST":
        update = telegram.Update.de_json(request.get_json(force=True), bot)
        
        chat_id = update.message.chat.id
        user_id = update.message.from_user.id
        text = update.message.text.strip()

        # Перевірка, чи є користувач активним підписником Zenedu
        await bot.send_message(chat_id=chat_id, text="Зачекайте, будь ласка. Йде перевірка підписки... "
        "(може зайняти до 1 хвилини)")
        active_subscribers = get_active_zenedu_subscribers()
        if user_id not in active_subscribers:
            await bot.send_message(chat_id=chat_id, text="Ви не маєте доступу до цього бота. " \
            "Ботом можуть користуватися лише підписники курсу https://mebliarynia.com.ua/")
            return "OK"
        
        # Обробка команд
        if text == '/start':
            # Скидаємо стан користувача і починаємо нову розмову
            user_states[user_id] = {'step': 1, 'values': {}}
            materials_list_str = "Привіт! Я калькулятор потужності газліфту. Оберіть матеріал зі списку:\n"
            for key, value in MATERIALS.items():
                materials_list_str += f"{key}. {value['title']}\n"
            materials_list_str += "Введіть номер матеріалу."
            await bot.send_message(chat_id=chat_id, text=materials_list_str)
            return "OK"

        # Обробка даних
        if user_id in user_states:
            current_state = user_states[user_id]
            current_step = current_state['step']
            
            try:
                value = float(text)
                
                if current_step == 1:
                    if int(value) in MATERIALS:
                        current_state['values']['material'] = int(value)
                        current_state['step'] = 2
                        await bot.send_message(chat_id=chat_id, text="Введіть висоту (мм).")
                    else:
                        await bot.send_message(chat_id=chat_id, text="Матеріал не знайдено. Введіть правильний номер матеріалу.")
                elif current_step == 2:
                    current_state['values']['height'] = value
                    current_state['step'] = 3
                    await bot.send_message(chat_id=chat_id, text="Введіть ширину (мм).")
                elif current_step == 3:
                    current_state['values']['width'] = value
                    current_state['step'] = 4
                    await bot.send_message(chat_id=chat_id, text="Введіть товщину (мм).")
                elif current_step == 4:
                    current_state['values']['thickness'] = value
                    
                    # Виконуємо розрахунок
                    material_id = current_state['values']['material']
                    density = MATERIALS[material_id]['density']
                    height = current_state['values']['height']
                    width = current_state['values']['width']
                    thickness = current_state['values']['thickness']
                    
                    weight = density * height * width * thickness / 1000000
                    power = (weight * 9.81 * (height / 1000 / 2)) / (2 * 0.1 * 0.6)
                    
                    await bot.send_message(chat_id=chat_id, text=f"Вага: {weight:.2f} кг\nПотужність: {power:.2f} N")
                    
                    # Завершуємо розмову
                    del user_states[user_id]
                
            except ValueError:
                await bot.send_message(chat_id=chat_id, text="Будь ласка, введіть числове значення.")
            
            return "OK"

        # Повідомлення про помилку або невідому команду
        await bot.send_message(chat_id=chat_id, text="Вибачте, я не знаю цієї команди. Будь ласка, почніть з /start.")
        return "OK"

    elif request.method == "GET":
        return "OK"

    return "Unsupported request method.", 405


def telegram_bot(request):
    return asyncio.run(async_telegram_bot(request))