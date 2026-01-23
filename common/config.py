from dotenv import load_dotenv
from pathlib import Path
import os
import logging
import logging.config
import logging.handlers

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

MYSQL_CFG = {
    'host': os.environ.get("MYSQL_HOST"),
    'user': os.environ.get("MYSQL_USER"),
    'password': os.environ.get("MYSQL_PASSWORD"),
    'database': os.environ.get("MYSQL_DATABASE"),
    'pool_size': 32,
}

OPENAI_TOKEN = os.environ.get("OPENAI_TOKEN")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

TELEGRAM_SECRET = os.environ.get("TELEGRAM_SECRET")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

DOCKER_MOUNTPOINT = "/root/telegram_bot_api/volume/"

DOCKER_VIDEO_MOUNTPOINT = f'{DOCKER_MOUNTPOINT}{TELEGRAM_TOKEN}/videos/'
DOCKER_AUDIO_MOUNTPOINT = f'{DOCKER_MOUNTPOINT}{TELEGRAM_TOKEN}/music/'
DOCKER_VIDEONOTE_MOUNTPOINT = f'{DOCKER_MOUNTPOINT}{TELEGRAM_TOKEN}/video_notes/'
DOCKER_VOICE_MOUNTPOINT = f'{DOCKER_MOUNTPOINT}{TELEGRAM_TOKEN}/voice/'

TELEGRAM_WHITELIST = [6562294167, 733014989]

NATS_CFG = {
    'servers': os.environ.get("NATS_URL"),
    'name': os.environ.get("NATS_NAME"),
    'reconnect_time_wait': 2,
    'max_reconnect_attempts': 10
}

FASTAPI_CFG = {
    'host': os.environ.get("FASTAPI_HOST", "127.0.0.1"),
    'port': int(os.environ.get("FASTAPI_PORT", 8000))
}

LOGGING_CFG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(name)s %(process)d %(thread)d %(message)s',
        },
        'simple': {
            'format': '%(levelname)s %(message)s',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'main_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.environ.get("LOG_PATH")+"main.log",
            'formatter': 'verbose',
            'encoding': 'utf-8',
            'maxBytes': 10*1024*1024,
            'backupCount': 5,
        },
        'mysql_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.environ.get("LOG_PATH")+"mysql.log",
            'formatter': 'verbose',
            'encoding': 'utf-8',
            'maxBytes': 10*1024*1024,
            'backupCount': 5,
        },
        'nats_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.environ.get("LOG_PATH")+"nats.log",
            'formatter': 'verbose',
            'encoding': 'utf-8',
            'maxBytes': 10*1024*1024,
            'backupCount': 5,
        },
        'fastapi_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.environ.get("LOG_PATH")+"fastapi.log",
            'formatter': 'verbose',
            'encoding': 'utf-8',
            'maxBytes': 10*1024*1024,
            'backupCount': 5,
        },
        'scheduler_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.environ.get("LOG_PATH")+"scheduler.log",
            'formatter': 'verbose',
            'encoding': 'utf-8',
            'maxBytes': 10*1024*1024,
            'backupCount': 5,
        },
        'filemanager_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.environ.get("LOG_PATH")+"filemanager.log",
            'formatter': 'verbose',
            'encoding': 'utf-8',
            'maxBytes': 10*1024*1024,
            'backupCount': 5,
        },
    },
    'loggers': {
        '': {
            'handlers': ['console', 'main_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'mysql': {
            'handlers': ['console', 'mysql_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'nats': {
            'handlers': ['console', 'nats_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'fastapi': {
            'handlers': ['console', 'fastapi_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'scheduler': {
            'handlers': ['console', 'scheduler_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'filemanager': {
            'handlers': ['console', 'filemanager_file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

logging.config.dictConfig(LOGGING_CFG)
