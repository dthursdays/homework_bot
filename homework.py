import json
import logging
import os
import sys
import time
from http import HTTPStatus
from logging.handlers import RotatingFileHandler

import requests
import telegram
from dotenv import load_dotenv
from telegram import Bot

from exceptions import (ApiError, CodeNot200Error,
                        HomeworkStatusError, NothingNewError)

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

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

handler = RotatingFileHandler('main.log', maxBytes=50000000, backupCount=5)
logger.addHandler(handler)

formatter = logging.Formatter(
    '%(asctime)s, %(levelname)s, %(message)s'
)
handler.setFormatter(formatter)


def send_message(bot, message):
    """Отправка сообщений."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info('Сообщение успешно отправлено')
    except telegram.TelegramError as error:
        logger.error(f'Ошибка Telegram: {error}')
    except Exception as error:
        logger.error(f'Ошибка при отправке сообщения: {error}')


def get_api_answer(current_timestamp):
    """Получение ответа от API ЯП."""
    timestamp = current_timestamp or int(time.time())
    payload = {'from_date': timestamp}

    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except requests.exceptions.RequestException as error:
        logger.error(f'Ошибка запроса к URL: {error}')
        sys.exit()

    if response.status_code != HTTPStatus.OK:
        message = f'Эндпоинт не доступен. Код {response.status_code}'
        raise CodeNot200Error(message)

    try:
        return response.json()
    except json.decoder.JSONDecodeError:
        logger.error("Ошибка декодирования JSON")


def check_response(response):
    """Проверка ответа от API ЯП."""
    if not isinstance(response, dict):
        raise TypeError('Неверный формат ответа от API')

    if response.get('error'):
        error = response.get('error').get('error')
        message = f'Ошибка в ответе от API: {error}'
        raise ApiError(message)

    if 'homeworks' not in response:
        message = f'Неопознанные ключи в ответе от API: {response}'
        raise ApiError(message)

    homeworks = response.get('homeworks')
    if not homeworks:
        raise NothingNewError('В ответе отсуствуют новые статусы')
    return homeworks[0]


def parse_status(homework):
    """Парсинг полученных данных."""
    if not isinstance(homework, dict) or not homework:
        raise KeyError('Неверный формат данных о проверке ДЗ')

    homework_name = homework.get('homework_name')
    if not homework_name:
        raise KeyError('Не удалось получить название домашней работы')

    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_STATUSES:
        raise HomeworkStatusError('Неизвестный статус'
                                  f' домашней работы: {homework_status}')
    verdict = HOMEWORK_STATUSES.get(homework_status)

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка наличия токенов."""
    tokens = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']
    for name in tokens:
        if not globals()[name]:
            logger.critical(f'Критическая ошибка! Отстутствует токен {name}')
            return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        sys.exit()

    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    last_message = None

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            status = parse_status(homeworks)
            send_message(bot, status)

            current_timestamp = int(time.time())
            time.sleep(RETRY_TIME)

        except NothingNewError as error:
            logger.debug(error)
            time.sleep(RETRY_TIME)

        except Exception as error:
            logger.error(error)
            message = f'Сбой в работе программы: {error}'
            if message != last_message:
                send_message(bot, message)
            last_message = message
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
