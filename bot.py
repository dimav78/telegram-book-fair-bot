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
        [InlineKeyboardButton("Выбор по продукту", callback_data='select_product')],
        [InlineKeyboardButton("Корзина", callback_data='view_cart')],
        [InlineKeyboardButton("Итоги", callback_data='view_totals')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        'Добро пожаловать в кассу книжной ярмарки! Выберите действие:',
        reply_markup=reply_markup
    )


async def refresh(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clears all caches and forces fresh data from Google Sheets."""
    sheets_handler.clear_all_caches()
    await update.message.reply_text('🔄 Кэш очищен! Данные будут обновлены при следующем обращении к Google Таблицам.')


# --- Callback Query Handler ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles callback queries from inline keyboards."""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'select_author':
        await show_authors(query, context)
    elif query.data == 'select_product':
        await show_product_types(query, context)
    elif query.data.startswith('product_type_'):
        product_type = query.data.split('_')[2]
        await show_products_by_type(query, context, product_type)
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
    elif query.data == 'payment_cashless':
        await handle_cashless_payment(query, context)
    elif query.data == 'payment_cash':
        await handle_cash_payment(query, context)
    elif query.data == 'clear_cart':
        await clear_cart(query, context)
    elif query.data == 'confirm_cashless':
        await confirm_payment(query, context, 'cashless')
    elif query.data == 'confirm_cash':
        await confirm_payment(query, context, 'cash')
    elif query.data == 'back_to_main':
        await handle_back_to_main(query, context)
    elif query.data.startswith('products_page_'):
        parts = query.data.split('_')
        product_type = parts[2]
        page = int(parts[3])
        await show_products_by_type(query, context, product_type, page)


async def show_product_types(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows product type selection (Мерч/Книги)."""
    keyboard = [
        [InlineKeyboardButton("📚 Книги", callback_data='product_type_Книги')],
        [InlineKeyboardButton("🛍 Мерч", callback_data='product_type_Мерч')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_text('Выберите тип продукта:', reply_markup=reply_markup)
    except telegram.error.BadRequest as e:
        if "no text in the message to edit" in str(e).lower():
            await query.message.delete()
            await query.message.reply_text('Выберите тип продукта:', reply_markup=reply_markup)
        else:
            raise e


async def show_products_by_type(query, context: ContextTypes.DEFAULT_TYPE, product_type: str, page: int = 0) -> None:
    """Shows products by selected type with pagination."""
    # Get all products of the specific type
    all_products = sheets_handler.get_all_products()
    products = [p for p in all_products if p.get('ProductType', '').strip() == product_type]
    
    if not products:
        keyboard = [[InlineKeyboardButton("⬅️ К типам продуктов", callback_data='select_product')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"Продукты типа '{product_type}' не найдены.", reply_markup=reply_markup)
        return
    
    # Pagination settings
    items_per_page = 10
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    page_products = products[start_idx:end_idx]
    
    keyboard = []
    for product in page_products:
        product_title = product.get('Title', 'Без названия')
        product_id = product.get('ProductID')
        # Truncate title if too long for button
        if len(product_title) > 30:
            product_title = product_title[:27] + "..."
        keyboard.append([InlineKeyboardButton(product_title, callback_data=f'product_{product_id}')])
    
    # Add pagination buttons if needed
    pagination_row = []
    if page > 0:
        pagination_row.append(InlineKeyboardButton("⬅️ Пред.", callback_data=f'products_page_{product_type}_{page-1}'))
    if end_idx < len(products):
        pagination_row.append(InlineKeyboardButton("След. ➡️", callback_data=f'products_page_{product_type}_{page+1}'))
    
    if pagination_row:
        keyboard.append(pagination_row)
    
    # Add back button
    keyboard.append([InlineKeyboardButton("⬅️ К типам продуктов", callback_data='select_product')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Create message text with pagination info
    total_products = len(products)
    showing_from = start_idx + 1
    showing_to = min(end_idx, total_products)
    message_text = f"📦 {product_type} ({showing_from}-{showing_to} из {total_products})\n\nВыберите продукт:"
    
    try:
        await query.edit_message_text(message_text, reply_markup=reply_markup)
    except telegram.error.BadRequest as e:
        if "no text in the message to edit" in str(e).lower():
            await query.message.delete()
            await query.message.reply_text(message_text, reply_markup=reply_markup)
        else:
            raise e


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
    
    try:
        await query.edit_message_text('Выберите автора:', reply_markup=reply_markup)
    except telegram.error.BadRequest as e:
        if "no text in the message to edit" in str(e).lower():
            await query.message.delete()
            await query.message.reply_text('Выберите автора:', reply_markup=reply_markup)
        else:
            raise e


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
    
    try:
        await query.edit_message_text('Выберите книгу:', reply_markup=reply_markup)
    except telegram.error.BadRequest as e:
        if "no text in the message to edit" in str(e).lower():
            await query.message.delete()
            await query.message.reply_text('Выберите книгу:', reply_markup=reply_markup)
        else:
            raise e


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
        
        # Try to edit message text, if it fails (media message), send new message
        try:
            await query.edit_message_text(
                f"✅ '{title}' добавлена в корзину!\n\nЧто делаем дальше?",
                reply_markup=reply_markup
            )
        except telegram.error.BadRequest as e:
            if "no text in the message to edit" in str(e).lower():
                # Previous message was media, delete and send new text message
                await query.message.delete()
                await query.message.reply_text(
                    f"✅ '{title}' добавлена в корзину!\n\nЧто делаем дальше?",
                    reply_markup=reply_markup
                )
            else:
                raise e
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
    
    try:
        await query.edit_message_text('\n'.join(message_lines), parse_mode='Markdown', reply_markup=reply_markup)
    except telegram.error.BadRequest as e:
        if "no text in the message to edit" in str(e).lower():
            await query.message.delete()
            await query.message.reply_text('\n'.join(message_lines), parse_mode='Markdown', reply_markup=reply_markup)
        else:
            raise e


async def handle_cashless_payment(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles cashless payment with QR code or contact display."""
    cart = context.user_data.get('cart', [])
    
    if not cart:
        await query.answer("❌ Корзина пуста")
        return
    
    # Calculate total and get author info
    total = sum(product.get('Price', 0) for product in cart)
    
    # Get author info from first product (assuming single author per transaction)
    first_product = cart[0]
    author_id = first_product.get('AuthorID')
    
    # Find author details
    authors = sheets_handler.get_authors()
    author = None
    for a in authors:
        if a.get('AuthorID') == author_id:
            author = a
            break
    
    if not author:
        await query.edit_message_text("❌ Ошибка: автор не найден")
        return
    
    qr_code_url = str(author.get('QR_Code_URL', '')).strip()
    contact = str(author.get('Contact', '')).strip()
    author_name = author.get('Name', 'Неизвестный автор')
    
    # Create cart summary
    cart_lines = [f"💳 *Безналичная оплата*\n"]
    cart_lines.append(f"👤 Автор: {author_name}")
    cart_lines.append(f"💰 Сумма: {total} руб.\n")
    
    for i, product in enumerate(cart, 1):
        title = product.get('Title', 'Без названия')
        price = product.get('Price', 0)
        cart_lines.append(f"{i}. {title} - {price} руб.")
    
    message_text = '\n'.join(cart_lines)
    
    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить оплату", callback_data='confirm_cashless')],
        [InlineKeyboardButton("⬅️ Назад к корзине", callback_data='view_cart')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        if qr_code_url:
            # Display QR code image
            await query.edit_message_media(
                media=telegram.InputMediaPhoto(
                    media=qr_code_url, 
                    caption=message_text + f"\n\n📱 Отсканируйте QR-код для оплаты",
                    parse_mode='Markdown'
                ),
                reply_markup=reply_markup
            )
        elif contact:
            # Display contact info only
            try:
                await query.edit_message_text(
                    text=message_text + f"\n\n📞 Контакт для оплаты: {contact}",
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            except telegram.error.BadRequest as e:
                if "no text in the message to edit" in str(e).lower():
                    await query.message.delete()
                    await query.message.reply_text(
                        text=message_text + f"\n\n📞 Контакт для оплаты: {contact}",
                        parse_mode='Markdown',
                        reply_markup=reply_markup
                    )
                else:
                    raise e
        else:
            # No payment info available
            try:
                await query.edit_message_text(
                    text=message_text + "\n\n❌ Нет информации для оплаты",
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            except telegram.error.BadRequest as e:
                if "no text in the message to edit" in str(e).lower():
                    await query.message.delete()
                    await query.message.reply_text(
                        text=message_text + "\n\n❌ Нет информации для оплаты",
                        parse_mode='Markdown',
                        reply_markup=reply_markup
                    )
                else:
                    raise e
    except Exception as e:
        logger.error(f"Error displaying cashless payment: {e}")
        # Fallback to text only
        fallback_text = message_text
        if contact:
            fallback_text += f"\n\n📞 Контакт для оплаты: {contact}"
        else:
            fallback_text += "\n\n❌ Нет информации для оплаты"
        
        try:
            await query.edit_message_text(
                text=fallback_text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        except telegram.error.BadRequest as e:
            if "no text in the message to edit" in str(e).lower():
                await query.message.delete()
                await query.message.reply_text(
                    text=fallback_text,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            else:
                raise e


async def handle_cash_payment(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles cash payment."""
    cart = context.user_data.get('cart', [])
    
    if not cart:
        await query.answer("❌ Корзина пуста")
        return
    
    total = sum(product.get('Price', 0) for product in cart)
    
    # Create cart summary
    cart_lines = [f"💵 *Оплата наличными*\n"]
    cart_lines.append(f"💰 Сумма: {total} руб.\n")
    
    for i, product in enumerate(cart, 1):
        title = product.get('Title', 'Без названия')
        price = product.get('Price', 0)
        cart_lines.append(f"{i}. {title} - {price} руб.")
    
    message_text = '\n'.join(cart_lines)
    
    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить оплату", callback_data='confirm_cash')],
        [InlineKeyboardButton("⬅️ Назад к корзине", callback_data='view_cart')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_text(
            text=message_text + "\n\n💵 Примите оплату наличными",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    except telegram.error.BadRequest as e:
        if "no text in the message to edit" in str(e).lower():
            await query.message.delete()
            await query.message.reply_text(
                text=message_text + "\n\n💵 Примите оплату наличными",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            raise e


async def clear_cart(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clears the user's cart."""
    context.user_data['cart'] = []
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить книги", callback_data='select_author')],
        [InlineKeyboardButton("🏠 Главное меню", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_text(
            "🗑 Корзина очищена",
            reply_markup=reply_markup
        )
    except telegram.error.BadRequest as e:
        if "no text in the message to edit" in str(e).lower():
            await query.message.delete()
            await query.message.reply_text(
                "🗑 Корзина очищена",
                reply_markup=reply_markup
            )
        else:
            raise e


async def confirm_payment(query, context: ContextTypes.DEFAULT_TYPE, payment_method: str) -> None:
    """Confirms payment and records transactions."""
    cart = context.user_data.get('cart', [])
    
    if not cart:
        await query.answer("❌ Корзина пуста")
        return
    
    # Record each product as a separate transaction
    successful_transactions = 0
    failed_transactions = 0
    
    for product in cart:
        product_id = product.get('ProductID')
        author_id = product.get('AuthorID')
        price = product.get('Price', 0)
        
        success = sheets_handler.record_transaction(product_id, author_id, payment_method, price)
        if success:
            successful_transactions += 1
        else:
            failed_transactions += 1
    
    # Clear cart after recording transactions
    context.user_data['cart'] = []
    
    # Prepare result message
    total_amount = sum(product.get('Price', 0) for product in cart)
    payment_emoji = "💳" if payment_method == "cashless" else "💵"
    payment_text = "безналичная" if payment_method == "cashless" else "наличными"
    
    if failed_transactions == 0:
        result_message = f"✅ Оплата успешно завершена!\n\n{payment_emoji} {payment_text.capitalize()}: {total_amount} руб.\n📝 Записано транзакций: {successful_transactions}"
    else:
        result_message = f"⚠️ Оплата завершена с ошибками!\n\n{payment_emoji} {payment_text.capitalize()}: {total_amount} руб.\n✅ Успешно: {successful_transactions}\n❌ Ошибок: {failed_transactions}"
    
    keyboard = [
        [InlineKeyboardButton("➕ Новая продажа", callback_data='select_author')],
        [InlineKeyboardButton("🏠 Главное меню", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Try to edit message text, if it fails (media message), delete and send new message
    try:
        await query.edit_message_text(
            result_message,
            reply_markup=reply_markup
        )
    except telegram.error.BadRequest as e:
        if "no text in the message to edit" in str(e).lower():
            # Previous message was media, delete and send new text message
            await query.message.delete()
            await query.message.reply_text(
                result_message,
                reply_markup=reply_markup
            )
        else:
            raise e


async def show_totals(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows daily totals (placeholder implementation)."""
    await query.edit_message_text("📊 Функция просмотра итогов будет реализована позднее.")


async def handle_back_to_main(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Returns to main menu."""
    keyboard = [
        [InlineKeyboardButton("Выбор по автору", callback_data='select_author')],
        [InlineKeyboardButton("Выбор по продукту", callback_data='select_product')],
        [InlineKeyboardButton("Корзина", callback_data='view_cart')],
        [InlineKeyboardButton("Итоги", callback_data='view_totals')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_text(
            'Добро пожаловать в кассу книжной ярмарки! Выберите действие:',
            reply_markup=reply_markup
        )
    except telegram.error.BadRequest as e:
        if "no text in the message to edit" in str(e).lower():
            await query.message.delete()
            await query.message.reply_text(
                'Добро пожаловать в кассу книжной ярмарки! Выберите действие:',
                reply_markup=reply_markup
            )
        else:
            raise e


# --- Main Bot Logic ---
def main() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # --- Register Handlers ---
    # Register the /start command
    application.add_handler(CommandHandler("start", start))
    
    # Register the /refresh command
    application.add_handler(CommandHandler("refresh", refresh))
    
    # Register the callback query handler for button presses
    application.add_handler(CallbackQueryHandler(button_handler))

    # Start the Bot
    print("Bot is running...")
    application.run_polling(poll_interval=15)


if __name__ == '__main__':
    main()