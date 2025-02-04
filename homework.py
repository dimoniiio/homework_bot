import logging
import os
import time
import sys
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telebot import TeleBot
from telebot.apihelper import ApiException

from exceptions import StatusApi


load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

REQUIRED_ENV_VARS = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens(required_env_vars: list):
    """Проверяет наличие всех необходимых переменных окружения."""
    missing_vars = [var for var in required_env_vars if not globals()[var]]
    if missing_vars:
        raise ValueError(
            'Принудительная остановка программы из-за отсутствия '
            f'необходимых переменных окружения.{", ".join(missing_vars)}'
        )


def send_message(bot: TeleBot, message: str):
    """Отправка сообщения в чат ботом."""
    logging.debug('Бот отпраляет сообщение')
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    logging.debug(f'Сообщение успешно отправлено: {message}')


def get_api_answer(timestamp: int):
    """Делает запрос к API-сервиса."""
    try:
        logging.debug(f'Бот делает запрос к {ENDPOINT} '
                      f'c timestamp = {timestamp}')
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )

    except requests.RequestException as e:
        raise ConnectionError(f'Ошибка при запросе к API: {e}')

    if homework_statuses.status_code != HTTPStatus.OK:
        raise StatusApi(
            f'Статус ответа равен {homework_statuses.status_code} а не 200'
        )

    return homework_statuses.json()


def check_response(response: dict):
    """Проверяет ответ API на соответствие документации."""
    logging.debug('Начало проверки ответа API')
    if not isinstance(response, dict):
        raise TypeError(f'Получен {type(response)}, a ожидался словарь.')

    field = 'homeworks'
    if field not in response:
        raise KeyError(
            f'Отсутствует поле "{field}" в ответе API.'
        )

    if not isinstance(response[field], list):
        raise TypeError(
            f'Поле "{field}" имеет неверный тип данных. '
            'Ожидалось list, '
            f'получено {type(response[field]).__name__}.'
        )
    logging.info('Ответ API соответствует документации.')


def parse_status(homework: dict):
    """Функция извлекает из информации о домашней работе статус этой работы."""
    logging.debug('Бот извлекает статус домашней работы')
    keys_homework = ['homework_name', 'status']
    no_key = [key for key in keys_homework if not homework.get(key)]
    if no_key:
        raise KeyError(f'Нет ключей:"{", ".join(no_key)}".')
    homework_name = homework['homework_name']
    status_work = homework['status']
    if status_work not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неожиданный статус домашней работы: {status_work}.')
    verdict = HOMEWORK_VERDICTS.get(str(status_work))
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    try:
        check_tokens(REQUIRED_ENV_VARS)
    except ValueError as e:
        logging.critical(e)
        sys.exit()
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    old_massage = ''
    while True:
        try:
            response = get_api_answer(timestamp - RETRY_PERIOD)
            check_response(response)
            homework = response['homeworks']
            if not homework:
                logging.debug('Изменение статуса работы отсутствует.')
                continue
            message = parse_status(homework[0])
            if message != old_massage:
                send_message(bot, message)
                old_massage = message
            timestamp = response.get('current_date', timestamp)

        except (ApiException, requests.exceptions.RequestException) as e:
            logging.error(f'Ошибка при работе с Telegram или сетью: {e}')

        except Exception as error:
            new_error_massage = f'Сбой в работе программы: {error}'
            logging.error(new_error_massage)
            if new_error_massage != old_massage:
                try:
                    send_message(bot, 'Сбой в работе программы: '
                                 f'{new_error_massage}')
                    old_massage == new_error_massage
                except (
                    ApiException,
                    requests.exceptions.RequestException
                ) as e:
                    logging.error(
                        f'Не удалось отправить сообщение об ошибке: {e}')

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)s %(funcName)s:%(lineno)d %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    main()
