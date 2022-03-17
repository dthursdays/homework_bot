import datetime
import logging
import os
import sys
import time

import requests
from dotenv import load_dotenv
from telegram import Bot

from exceptions import NothingNewError

load_dotenv()
PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')
RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='main.log',
    format='%(asctime)s, %(levelname)s, %(message)s'
)


def send_message(bot, message):
    """Отправка сообщений."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.info('Сообщение успешно отправлено')
    except Exception as error:
        logging.error(f'Ошибка при отправке сообщения: {error}')


def get_api_answer(current_timestamp):
    """Получение ответа от API ЯП."""
    timestamp = current_timestamp or int(time.time())
    payload = {'from_date': timestamp}
    response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    if response.status_code != 200:
        message = f'Эндпоинт не доступен. Код {response.status_code}'
        raise Exception(message)
    return response.json()


def check_response(response):
    """Проверка ответа от API ЯП."""
    if not isinstance(response, dict):
        raise TypeError('Неверный формат ответа от API')
    if response.get('error'):
        error = response.get('error').get('error')
        message = f'Ошибка проверки ответа от API: {error}'
        raise Exception(message)
    elif response.get('homeworks') == []:
        raise NothingNewError()
    elif response.get('homeworks') != []:
        return response.get('homeworks')[0]
    else:
        message = f'Неопознанные ключи в ответе сервера: {response}'
        raise Exception(message)


def parse_status(homework):
    """Парсинг полученных данных."""
    print(homework)
    if not isinstance(homework, dict):
        raise KeyError('Неверный формат данных о проверке ДЗ')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if homework_status not in HOMEWORK_STATUSES:
        raise Exception(f'Неизвестный статус'
                        f' домашней работы: {homework_status}')
    verdict = HOMEWORK_STATUSES.get(homework_status)

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка наличия токенов."""
    tokens = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']
    for name in tokens:
        if not globals()[name]:
            logging.critical(f'Критическая ошибка! Отстутствует токен {name}')
            return False
    return True


def main():
    """Основная логика работы бота."""

    if not check_tokens():
        print('Сбой, что-то не так с токенами')
        sys.exit()

    bot = Bot(token=TELEGRAM_TOKEN)
    date = datetime.datetime(2022, 2, 16)
    current_timestamp = int(date.timestamp())
    last_message = None

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            status = parse_status(homeworks)
            send_message(bot, status)
            logging.info('В Telegram отправлено сообщение')

            current_timestamp = int(time.time())
            time.sleep(RETRY_TIME)

        except NothingNewError:
            logging.debug('В ответе отсуствуют новые статусы')
            time.sleep(RETRY_TIME)

        except Exception as error:
            logging.error(error)
            message = f'Сбой в работе программы: {error}'
            if message != last_message:
                send_message(bot, message)
            last_message = message
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
