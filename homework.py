import logging
import os
import time
import sys

import requests
from dotenv import load_dotenv
from telebot import apihelper, TeleBot

from exceptions import ExpectedField, StatusApi


load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
ENV_VARS = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
REQUIRED_ENV_VARS = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def check_tokens(required_env_vars: list):
    """Проверяет наличие всех необходимых переменных окружения."""
    if not TELEGRAM_TOKEN:
        logger.critical(
            'Отсутствует TELEGRAM_TOKEN. Убедитесь, '
            'что он определен в переменных окружения.'
        )
        sys.exit(1)
    # тест проходит только если есть 41-46 строка
    missing_vars = [var for var in required_env_vars if os.getenv(var) is None]
    if missing_vars:
        logger.critical(
            f'Принудительная остановка программы из-за отсутствия '
            f'необходимых переменных окружения.{", ".join(missing_vars)}'
        )
        sys.exit()


def send_message(bot: TeleBot, message: str):
    """Отправка сообщения в чат ботом."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug(f'Сообщение успешно отправлено: {message}')
    except apihelper as e:
        logger.error(f'Ошибка при отправке сообщения в telegram: {e}')
    except Exception as e:
        logger.error(f'Ошибка при отправке сообщения: {e}')


def get_api_answer(timestamp: int):
    """Делает запрос к API-сервиса."""
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
        homework_statuses.raise_for_status()
        if homework_statuses.status_code != 200:
            raise StatusApi('Статут ответа не равен 200')
        return homework_statuses.json()

    except requests.RequestException as e:
        error_message = f'Ошибка при запросе к API: {e}'
        logger.error(error_message)
        return None, error_message


def check_response(response: dict):
    """Проверяет ответ API на соответствие документации."""
    expected_structure = {
        'current_date': int,
        'homeworks': list
    }
    if not isinstance(response, dict):
        raise TypeError('Ожидался словарь.')

    for field, expected_type in expected_structure.items():
        if field not in response:
            raise ExpectedField(
                f'Отсутствует поле "{field}" в ответе API.'
            )

        if not isinstance(response[field], expected_type):
            raise TypeError(
                f'Поле "{field}" имеет неверный тип данных. '
                f'Ожидалось {expected_type.__name__}, '
                f'получено {type(response[field]).__name__}.'
            )

    if not response.get('homeworks'):
        logger.debug('Изменение статуса работы отсутствует.')
        return False

    logger.info('Ответ API соответствует документации.')
    return True


def parse_status(homework: dict):
    """Функция извлекает из информации о домашней работе статус этой работы."""
    if not homework.get('homework_name'):
        raise ExpectedField('Нет ключа "homework_name".')

    homework_name = homework.get('homework_name')
    status_work = homework.get('status')
    if status_work not in HOMEWORK_VERDICTS.keys():
        raise ExpectedField('Неожиданный статус домашней работы.')
    verdict = HOMEWORK_VERDICTS.get(str(status_work))
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens(REQUIRED_ENV_VARS)
    bot = TeleBot(token=TELEGRAM_TOKEN)
    flag = True
    while True:
        try:
            timestamp = int(time.time())
            response = get_api_answer(timestamp - RETRY_PERIOD)
            if check_response(response):
                homework = response.get('homeworks')
                message = parse_status(homework[0])
                send_message(bot, message)

        except StatusApi as e:
            error_message = f'Ошибка при запросе к API: {e}'
            logger.error(error_message)
            if flag:
                flag = False
                send_message(bot, error_message)

        except ExpectedField as e:
            logger.error(e)
            send_message(bot, e)

        except KeyError as e:
            logger.error(f'В ответе нет: {e}')

        except TypeError as e:
            logger.error(e)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
