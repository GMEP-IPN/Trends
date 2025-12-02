"""
Trends - Windows Desktop Application
Системный трей + веб-сервер
"""
import sys
import os
import threading
import webbrowser
import time
import logging
import traceback
from pathlib import Path
from datetime import datetime

# Добавляем корень проекта в путь
if getattr(sys, 'frozen', False):
    # Запущено как .exe - данные в _MEIPASS
    BASE_DIR = Path(sys._MEIPASS)
    APP_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent
    APP_DIR = BASE_DIR

sys.path.insert(0, str(BASE_DIR))
os.chdir(APP_DIR)  # Рабочая директория - где лежит .exe

# Настройка логирования в файл (рядом с .exe)
LOG_FILE = APP_DIR / "trends_app.log"

def setup_app_logging():
    """Настройка логирования приложения"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(LOG_FILE, encoding='utf-8', mode='a'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger('trends_app')

app_logger = setup_app_logging()
app_logger.info("="*60)
app_logger.info(f"Trends App Starting...")
app_logger.info(f"BASE_DIR: {BASE_DIR}")
app_logger.info(f"APP_DIR: {APP_DIR}")
app_logger.info(f"Frozen: {getattr(sys, 'frozen', False)}")
app_logger.info(f"Python: {sys.version}")
app_logger.info("="*60)

import pystray
from PIL import Image, ImageDraw, ImageFont
from pystray import MenuItem as item

from app.config.config_loader import load_config, setup_logging, get_logger
from app.storage import init_db, get_session, PLC
from app.services.collector_manager import CollectorManager, collector_status


class TrendsApp:
    """Главное приложение с системным треем"""
    
    def __init__(self):
        self.config = None
        self.logger = None
        self.manager: CollectorManager = None  # Используем CollectorManager
        self.web_thread = None
        self.running = False
        self.icon = None
        self.server_url = "http://127.0.0.1:8000"
        
    def create_icon_image(self, color="green"):
        """Создание иконки для трея"""
        size = 64
        image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Фон
        if color == "green":
            bg_color = (0, 200, 150)  # Зелёный - работает
        elif color == "yellow":
            bg_color = (255, 180, 0)  # Жёлтый - запуск
        else:
            bg_color = (200, 50, 50)  # Красный - остановлен
        
        # Рисуем круг
        draw.ellipse([4, 4, size-4, size-4], fill=bg_color)
        
        # Рисуем график (три столбца)
        bar_color = (255, 255, 255)
        draw.rectangle([16, 35, 24, 50], fill=bar_color)
        draw.rectangle([28, 25, 36, 50], fill=bar_color)
        draw.rectangle([40, 30, 48, 50], fill=bar_color)
        
        return image
    
    def start_server(self):
        """Запуск веб-сервера и коллектора"""
        try:
            app_logger.info("start_server() called")
            
            # Загрузка конфигурации
            config_path = BASE_DIR / 'config.yaml'
            app_logger.info(f"Config path: {config_path}")
            app_logger.info(f"Config exists: {config_path.exists()}")
            
            self.config = load_config(str(config_path))
            app_logger.info(f"Config loaded: host={self.config.api_host}, port={self.config.api_port}")
            
            self.logger = setup_logging(self.config)
            self.server_url = f"http://{self.config.api_host}:{self.config.api_port}"
            
            app_logger.info("🚀 Starting Trends application...")
            
            # Инициализация БД
            app_logger.info("Initializing database...")
            init_db()
            app_logger.info("Database initialized")
            
            # Запуск веб-сервера
            app_logger.info("Starting web server...")
            
            def run_web():
                try:
                    import uvicorn
                    from app.api.server import app
                    app_logger.info(f"Uvicorn starting on {self.config.api_host}:{self.config.api_port}")
                    
                    # Отключаем логирование uvicorn для .exe (нет консоли)
                    uvicorn.run(
                        app,
                        host=self.config.api_host,
                        port=self.config.api_port,
                        log_config=None  # Отключаем встроенное логирование
                    )
                except Exception as e:
                    app_logger.error(f"Web server error: {e}")
                    app_logger.error(traceback.format_exc())
            
            self.web_thread = threading.Thread(target=run_web, daemon=True)
            self.web_thread.start()
            
            # Даём серверу время запуститься
            app_logger.info("Waiting for web server to start...")
            time.sleep(2)
            
            # Запуск коллектора через CollectorManager
            app_logger.info("Starting collector service...")
            
            self.manager = CollectorManager(
                flush_interval_sec=self.config.flush_interval_sec
            )
            self.manager.start()
            
            app_logger.info(f"Collector running: {collector_status.running}")
            app_logger.info(f"Collector connections: {self.manager.collector.connections if self.manager.collector else 0}")
            
            self.running = True
            app_logger.info(f"✅ Server running at {self.server_url}")
            self.logger.info(f"✅ Server running at {self.server_url}")
            
            # Обновляем иконку
            if self.icon:
                self.icon.icon = self.create_icon_image("green")
            
            # Основной цикл обновления статуса
            while self.running:
                time.sleep(1)
                
                if self.manager:
                    # Обновляем статус подключения
                    self.manager.update_connection_status()
                    
                    # Проверяем запрос на перезапуск (логика в CollectorManager)
                    self.manager.check_restart_request()
                        
        except Exception as e:
            app_logger.error(f"CRITICAL ERROR in start_server: {e}")
            app_logger.error(traceback.format_exc())
            if self.logger:
                self.logger.error(f"Error: {e}")
    
    def stop_server(self):
        """Остановка сервера"""
        self.running = False
        
        if self.manager:
            self.manager.stop()
        
        if self.logger:
            self.logger.info("🛑 Server stopped")
    
    def open_browser(self, icon=None, item=None):
        """Открыть браузер"""
        webbrowser.open(self.server_url)
    
    def on_exit(self, icon, item):
        """Выход из приложения"""
        self.stop_server()
        icon.stop()
    
    def get_status_text(self):
        """Получить текст статуса"""
        if not self.running:
            return "Остановлен"
        
        if self.manager and self.manager.collector and self.manager.collector.connections:
            connected = sum(1 for c in self.manager.collector.connections.values() if c.client.connected)
            total = len(self.manager.collector.connections)
            if connected == total and total > 0:
                return f"Работает ({connected} ПЛК)"
            elif connected > 0:
                return f"Частично ({connected}/{total} ПЛК)"
            else:
                return "Нет подключения"
        
        return "Работает"
    
    def create_menu(self):
        """Создание меню трея"""
        return pystray.Menu(
            item('📊 Trends', None, enabled=False),
            item('─────────────', None, enabled=False),
            item('🌐 Открыть в браузере', self.open_browser, default=True),
            item('─────────────', None, enabled=False),
            item('❌ Выход', self.on_exit)
        )
    
    def run(self):
        """Запуск приложения"""
        # Создаём иконку (жёлтая - запуск)
        icon_image = self.create_icon_image("yellow")
        
        self.icon = pystray.Icon(
            "Trends",
            icon_image,
            "Trends - Запуск...",
            menu=self.create_menu()
        )
        
        # Запускаем сервер в отдельном потоке
        server_thread = threading.Thread(target=self.start_server, daemon=True)
        server_thread.start()
        
        # Ждём запуска и обновляем tooltip
        def update_tooltip():
            time.sleep(2)
            while self.icon._running:
                status = self.get_status_text()
                self.icon.title = f"Trends - {status}"
                time.sleep(2)
        
        tooltip_thread = threading.Thread(target=update_tooltip, daemon=True)
        tooltip_thread.start()
        
        # Запускаем трей (блокирующий вызов)
        self.icon.run()


def main():
    """Точка входа"""
    app = TrendsApp()
    app.run()


if __name__ == "__main__":
    main()

