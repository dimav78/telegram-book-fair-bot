import logging
import os
import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from dotenv import load_dotenv

# --- Load environment variables ---
load_dotenv()

# --- Import your sheets functions ---
import sheets_handler

# --- Get configuration from environment ---
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

# --- Basic Logging Setup ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# --- Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the /start command is issued."""
    keyboard = [
        [InlineKeyboardButton("Выбор по автору", callback_data='select_author')],
        [InlineKeyboardButton("Корзина", callback_data='view_cart')],
        [InlineKeyboardButton("Итоги", callback_data='view_totals')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        'Добро пожаловать в кассу книжной ярмарки! Выберите действие:',
        reply_markup=reply_markup
    )


# --- Callback Query Handler ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles callback queries from inline keyboards."""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'select_author':
        await show_authors(query, context)
    elif query.data.startswith('author_'):
        author_id = int(query.data.split('_')[1])
        await show_products_by_author(query, context, author_id)
    elif query.data.startswith('product_'):
        product_id = int(query.data.split('_')[1])
        await show_product_details(query, context, product_id)
    elif query.data.startswith('add_to_cart_'):
        product_id = int(query.data.split('_')[3])
        await add_to_cart(query, context, product_id)
    elif query.data == 'view_cart':
        await show_cart(query, context)
    elif query.data == 'view_totals':
        await show_totals(query, context)
    elif query.data == 'back_to_main':
        await handle_back_to_main(query, context)


async def show_authors(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows a list of authors as inline keyboard buttons."""
    authors = sheets_handler.get_authors()
    
    if not authors:
        await query.edit_message_text("Извините, не удалось загрузить список авторов.")
        return
    
    keyboard = []
    for author in authors:
        author_name = author.get('Name', 'Неизвестный автор')
        author_id = author.get('AuthorID')
        keyboard.append([InlineKeyboardButton(author_name, callback_data=f'author_{author_id}')])
    
    # Add back button
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data='back_to_main')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text('Выберите автора:', reply_markup=reply_markup)


async def show_products_by_author(query, context: ContextTypes.DEFAULT_TYPE, author_id: int) -> None:
    """Shows products by selected author."""
    products = sheets_handler.get_products_by_author(author_id)
    
    if not products:
        keyboard = [[InlineKeyboardButton("⬅️ К авторам", callback_data='select_author')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("У этого автора пока нет доступных книг.", reply_markup=reply_markup)
        return
    
    keyboard = []
    for product in products:
        product_title = product.get('Title', 'Без названия')
        product_id = product.get('ProductID')
        keyboard.append([InlineKeyboardButton(product_title, callback_data=f'product_{product_id}')])
    
    # Add back button
    keyboard.append([InlineKeyboardButton("⬅️ К авторам", callback_data='select_author')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text('Выберите книгу:', reply_markup=reply_markup)


async def show_product_details(query, context: ContextTypes.DEFAULT_TYPE, product_id: int) -> None:
    """Shows product details with photo and add to cart button."""
    # Get all products to find the specific one
    authors = sheets_handler.get_authors()
    all_products = []
    
    for author in authors:
        author_id = author.get('AuthorID')
        products = sheets_handler.get_products_by_author(author_id)
        all_products.extend(products)
    
    product = None
    for p in all_products:
        if p.get('ProductID') == product_id:
            product = p
            break
    
    if not product:
        await query.edit_message_text("Книга не найдена.")
        return
    
    title = product.get('Title', 'Без названия')
    description = product.get('Description', 'Описание отсутствует')
    price = product.get('Price', 0)
    photo_url = product.get('Photo_URL', '')
    author_id = product.get('AuthorID')
    
    # Find author name
    author_name = 'Неизвестный автор'
    for author in authors:
        if author.get('AuthorID') == author_id:
            author_name = author.get('Name', 'Неизвестный автор')
            break
    
    message_text = f"📚 *{title}*\n\n👤 Автор: {author_name}\n💰 Цена: {price} руб.\n\n📝 {description}"
    
    keyboard = [
        [InlineKeyboardButton("🛒 Добавить в корзину", callback_data=f'add_to_cart_{product_id}')],
        [InlineKeyboardButton("⬅️ К книгам автора", callback_data=f'author_{author_id}')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        if photo_url:
            await query.edit_message_media(
                media=telegram.InputMediaPhoto(media=photo_url, caption=message_text, parse_mode='Markdown'),
                reply_markup=reply_markup
            )
        else:
            await query.edit_message_text(text=message_text, parse_mode='Markdown', reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error sending product details: {e}")
        await query.edit_message_text(text=message_text, parse_mode='Markdown', reply_markup=reply_markup)


async def add_to_cart(query, context: ContextTypes.DEFAULT_TYPE, product_id: int) -> None:
    """Adds a product to the user's cart."""
    if 'cart' not in context.user_data:
        context.user_data['cart'] = []
    
    # Find the product details
    authors = sheets_handler.get_authors()
    all_products = []
    
    for author in authors:
        author_id = author.get('AuthorID')
        products = sheets_handler.get_products_by_author(author_id)
        all_products.extend(products)
    
    product = None
    for p in all_products:
        if p.get('ProductID') == product_id:
            product = p
            break
    
    if product:
        context.user_data['cart'].append(product)
        title = product.get('Title', 'Без названия')
        await query.answer(f"✅ '{title}' добавлена в корзину!")
        
        # Show updated options
        keyboard = [
            [InlineKeyboardButton("🛒 Корзина", callback_data='view_cart')],
            [InlineKeyboardButton("➕ Добавить еще", callback_data='select_author')],
            [InlineKeyboardButton("🏠 Главное меню", callback_data='back_to_main')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"✅ '{title}' добавлена в корзину!\n\nЧто делаем дальше?",
            reply_markup=reply_markup
        )
    else:
        await query.answer("❌ Ошибка при добавлении в корзину")


async def show_cart(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows the contents of the user's cart."""
    cart = context.user_data.get('cart', [])
    
    if not cart:
        keyboard = [[InlineKeyboardButton("➕ Добавить книги", callback_data='select_author')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("🛒 Ваша корзина пуста", reply_markup=reply_markup)
        return
    
    message_lines = ["🛒 *Ваша корзина:*\n"]
    total = 0
    
    for i, product in enumerate(cart, 1):
        title = product.get('Title', 'Без названия')
        price = product.get('Price', 0)
        total += price
        message_lines.append(f"{i}. {title} - {price} руб.")
    
    message_lines.append(f"\n💰 *Общая сумма: {total} руб.*")
    
    keyboard = [
        [InlineKeyboardButton("💳 Безнал", callback_data='payment_cashless'),
         InlineKeyboardButton("💵 Наличные", callback_data='payment_cash')],
        [InlineKeyboardButton("🗑 Очистить корзину", callback_data='clear_cart')],
        [InlineKeyboardButton("➕ Добавить еще", callback_data='select_author')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text('\n'.join(message_lines), parse_mode='Markdown', reply_markup=reply_markup)


async def show_totals(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows daily totals (placeholder implementation)."""
    await query.edit_message_text("📊 Функция просмотра итогов будет реализована позднее.")


async def handle_back_to_main(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Returns to main menu."""
    keyboard = [
        [InlineKeyboardButton("Выбор по автору", callback_data='select_author')],
        [InlineKeyboardButton("Корзина", callback_data='view_cart')],
        [InlineKeyboardButton("Итоги", callback_data='view_totals')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        'Добро пожаловать в кассу книжной ярмарки! Выберите действие:',
        reply_markup=reply_markup
    )


# --- Main Bot Logic ---
def main() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # --- Register Handlers ---
    # Register the /start command
    application.add_handler(CommandHandler("start", start))
    
    # Register the callback query handler for button presses
    application.add_handler(CallbackQueryHandler(button_handler))

    # Start the Bot
    print("Bot is running...")
    application.run_polling()


if __name__ == '__main__':
    main()