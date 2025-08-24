# itmo_telegram_bot.py
import json
import pandas as pd
import re
import logging
from typing import List, Dict, Optional
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    ContextTypes, ConversationHandler, filters
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния диалога
CHOOSING, TYPING_REPLY = range(2)

class ITMOTelegramBot:
    def __init__(self):
        self.programs_data = self.load_programs_data()
        self.curriculum_data = self.load_curriculum_data()
        
    def load_programs_data(self) -> List[Dict]:
        try:
            with open('itmo_programs_data.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error("Файл itmo_programs_data.json не найден")
            return []
    
    def load_curriculum_data(self) -> pd.DataFrame:
        try:
            return pd.read_csv('itmo_curriculum.csv', encoding='utf-8')
        except FileNotFoundError:
            logger.error("Файл itmo_curriculum.csv не найден")
            return pd.DataFrame()
    
    def get_main_keyboard(self):
        """Клавиатура главного меню"""
        keyboard = [
            ['📚 Список программ'],
            ['📖 Предметы программы', '🎯 Компетенции'],
            ['⏱️ Продолжительность', 'ℹ️ О программе'],
            ['❓ Помощь']
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def get_programs_keyboard(self):
        """Клавиатура выбора программы"""
        programs = [prog['program_name'] for prog in self.programs_data]
        keyboard = [programs[i:i+2] for i in range(0, len(programs), 2)]
        keyboard.append(['🔙 Назад'])
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.message.from_user
        welcome_text = f"""
👋 Привет, {user.first_name}!

🤖 Я бот-консультант по магистерским программам ИТМО в области искусственного интеллекта.

📊 Я могу рассказать о:
• Доступных программах
• Учебных планах и предметах
• Компетенциях выпускников
• Продолжительности обучения

Выберите опцию из меню ниже 👇
        """
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=self.get_main_keyboard()
        )
        return CHOOSING
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = """
📋 Доступные команды:

/start - Начать диалог
/help - Помощь
/programs - Список программ
/subjects - Предметы программы
/competencies - Компетенции
/duration - Продолжительность обучения

Или используйте кнопки меню 👇
        """
        await update.message.reply_text(help_text)
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений"""
        text = update.message.text.lower()
        
        if text == '📚 список программ':
            await self.show_programs(update, context)
        elif text == '📖 предметы программы':
            await self.ask_program_for_subjects(update, context)
        elif text == '🎯 компетенции':
            await self.ask_program_for_competencies(update, context)
        elif text == '⏱️ продолжительность':
            await self.show_duration(update, context)
        elif text == 'ℹ️ о программе':
            await self.ask_program_for_info(update, context)
        elif text == '❓ помощь':
            await self.help_command(update, context)
        elif text == '🔙 назад':
            await update.message.reply_text(
                "Главное меню:",
                reply_markup=self.get_main_keyboard()
            )
        else:
            # Попытка автоматического определения запроса
            response = self.auto_detect_response(text)
            await update.message.reply_text(response)
    
    async def show_programs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать список программ"""
        if not self.programs_data:
            await update.message.reply_text("Информация о программах временно недоступна.")
            return
        
        response = "🎓 Доступные магистерские программы:\n\n"
        for program in self.programs_data:
            response += f"• {program['program_name']}\n"
            response += f"  Код: {program.get('program_code', 'N/A')}\n"
            response += f"  Длительность: {program.get('duration', 'Не указана')}\n\n"
        
        await update.message.reply_text(response)
    
    async def ask_program_for_subjects(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Запросить выбор программы для показа предметов"""
        context.user_data['action'] = 'subjects'
        await update.message.reply_text(
            "Выберите программу для просмотра предметов:",
            reply_markup=self.get_programs_keyboard()
        )
    
    async def ask_program_for_competencies(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Запросить выбор программы для показа компетенций"""
        context.user_data['action'] = 'competencies'
        await update.message.reply_text(
            "Выберите программу для просмотра компетенций:",
            reply_markup=self.get_programs_keyboard()
        )
    
    async def ask_program_for_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Запросить выбор программы для информации"""
        context.user_data['action'] = 'info'
        await update.message.reply_text(
            "Выберите программу для подробной информации:",
            reply_markup=self.get_programs_keyboard()
        )
    
    async def handle_program_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора программы"""
        program_name = update.message.text
        action = context.user_data.get('action', '')
        
        program = self.find_program(program_name)
        if not program:
            await update.message.reply_text("Программа не найдена. Выберите из списка:")
            return
        
        if action == 'subjects':
            await self.show_program_subjects(update, program)
        elif action == 'competencies':
            await self.show_program_competencies(update, program)
        elif action == 'info':
            await self.show_program_info(update, program)
        else:
            await self.show_program_info(update, program)
        
        # Очищаем действие
        context.user_data['action'] = ''
    
    async def show_program_info(self, update: Update, program: Dict):
        """Показать информацию о программе"""
        response = f"""
📚 Программа: {program['program_name']}
🔢 Код: {program.get('program_code', 'N/A')}
⏱️ Продолжительность: {program.get('duration', 'Не указана')}

📝 Описание:
{program.get('description', 'Описание отсутствует')}

📊 Статистика:
• Дисциплин: {len(program.get('curriculum', []))}
• Компетенций: {len(program.get('competencies', []))}
        """
        await update.message.reply_text(response)
    
    async def show_program_subjects(self, update: Update, program: Dict):
        """Показать предметы программы"""
        program_name = program['program_name']
        subjects_df = self.curriculum_data[
            self.curriculum_data['program'].str.contains(program_name, na=False)
        ]
        
        if subjects_df.empty:
            await update.message.reply_text(f"Предметы для программы '{program_name}' не найдены.")
            return
        
        # Группируем по семестрам
        response = f"📖 Предметы программы '{program_name}':\n\n"
        
        for semester in sorted(subjects_df['semester'].unique()):
            sem_subjects = subjects_df[subjects_df['semester'] == semester]
            response += f"🎓 Семестр {semester}:\n"
            
            for _, subject in sem_subjects.iterrows():
                response += f"   • {subject['subject']} ({subject['credits']} кредитов)\n"
            response += "\n"
        
        # Если сообщение слишком длинное, разбиваем на части
        if len(response) > 4000:
            parts = [response[i:i+4000] for i in range(0, len(response), 4000)]
            for part in parts:
                await update.message.reply_text(part)
        else:
            await update.message.reply_text(response)
    
    async def show_program_competencies(self, update: Update, program: Dict):
        """Показать компетенции программы"""
        competencies = program.get('competencies', [])
        if not competencies:
            await update.message.reply_text("Компетенции не найдены.")
            return
        
        response = f"🎯 Компетенции программы '{program['program_name']}':\n\n"
        for i, comp in enumerate(competencies, 1):
            response += f"{i}. {comp}\n"
        
        await update.message.reply_text(response)
    
    async def show_duration(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать продолжительность обучения"""
        if not self.programs_data:
            await update.message.reply_text("Информация о программах недоступна.")
            return
        
        response = "⏱️ Продолжительность обучения:\n\n"
        for program in self.programs_data:
            response += f"• {program['program_name']}: {program.get('duration', '2 года')}\n"
        
        await update.message.reply_text(response)
    
    def find_program(self, program_name: str) -> Optional[Dict]:
        """Найти программу по названию"""
        for program in self.programs_data:
            if program_name.lower() in program['program_name'].lower():
                return program
        return None
    
    def auto_detect_response(self, text: str) -> str:
        """Автоматическое определение запроса"""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['привет', 'здравств', 'hello', 'hi']):
            return "👋 Привет! Чем могу помочь?"
        
        if any(word in text_lower for word in ['программ', 'program']):
            return self.get_programs_list_text()
        
        if any(word in text_lower for word in ['предмет', 'дисциплин', 'курс']):
            return "Выберите программу для просмотра предметов из меню 📖"
        
        if any(word in text_lower for word in ['компетенц', 'навык', 'умение']):
            return "Выберите программу для просмотра компетенций из меню 🎯"
        
        if any(word in text_lower for word in ['длительн', 'продолжительн', 'срок']):
            return self.get_duration_text()
        
        return "Не совсем понял ваш вопрос. Используйте кнопки меню или напишите /help для справки."
    
    def get_programs_list_text(self) -> str:
        """Текст списка программ"""
        if not self.programs_data:
            return "Информация о программах недоступна."
        
        response = "🎓 Доступные программы:\n\n"
        for program in self.programs_data:
            response += f"• {program['program_name']}\n"
        response += "\nВыберите программу из меню для подробной информации."
        return response
    
    def get_duration_text(self) -> str:
        """Текст продолжительности"""
        if not self.programs_data:
            return "Информация недоступна."
        
        response = "⏱️ Продолжительность:\n\n"
        for program in self.programs_data:
            response += f"• {program['program_name']}: {program.get('duration', '2 года')}\n"
        return response
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена диалога"""
        await update.message.reply_text(
            'Диалог завершен. Используйте /start для начала нового диалога.',
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

def main():
    """Запуск бота"""
    # Замените 'YOUR_BOT_TOKEN' на реальный токен вашего бота
    BOT_TOKEN = "YOUR_BOT_TOKEN"
    
    # Создаем бота
    bot = ITMOTelegramBot()
    
    # Создаем Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Создаем ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', bot.start)],
        states={
            CHOOSING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message),
                MessageHandler(filters.Regex('^(Искусственный интеллект|AI Product Management)$'), 
                             bot.handle_program_selection),
            ],
        },
        fallbacks=[CommandHandler('cancel', bot.cancel)],
    )
    
    # Добавляем обработчики
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('help', bot.help_command))
    application.add_handler(CommandHandler('programs', bot.show_programs))
    application.add_handler(CommandHandler('subjects', bot.ask_program_for_subjects))
    application.add_handler(CommandHandler('competencies', bot.ask_program_for_competencies))
    application.add_handler(CommandHandler('duration', bot.show_duration))
    
    # Запускаем бота
    print("🤖 Бот запущен...")
    application.run_polling()

if __name__ == "__main__":
    main()