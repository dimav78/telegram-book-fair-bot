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
    elif query.data.startswith('add_to_cart_discount_'):
        product_id = int(query.data.split('_')[4])
        await add_to_cart(query, context, product_id, with_discount=True)
    elif query.data.startswith('add_to_cart_'):
        product_id = int(query.data.split('_')[3])
        await add_to_cart(query, context, product_id)
    elif query.data == 'view_cart':
        await show_cart(query, context)
    elif query.data == 'view_totals':
        await show_totals(query, context)
    elif query.data.startswith('totals_date_'):
        date = query.data.split('_')[2]
        await show_sales_summary(query, context, date)
    elif query.data.startswith('author_details_'):
        parts = query.data.split('_')
        author_id = int(parts[2])
        date = parts[3] if len(parts) > 3 else None
        await show_author_details(query, context, author_id, date)
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
    discount = product.get('Discount', 0)
    
    # Find author name
    author_name = 'Неизвестный автор'
    for author in authors:
        if author.get('AuthorID') == author_id:
            author_name = author.get('Name', 'Неизвестный автор')
            break
    
    # Check if product is part of the "3 for 2" promotion
    promotion_text = ""
    promotion_type = product.get('Promotion', '').strip().lower()
    if promotion_type == '3for2':
        promotion_text = "\n🎉 *Участвует в акции «3 за 2»!*"
    
    message_text = f"📚 *{title}*\n\n👤 Автор: {author_name}\n💰 Цена: {price} руб.{promotion_text}\n\n📝 {description}"
    
    keyboard = [
        [InlineKeyboardButton("🛒 Добавить в корзину", callback_data=f'add_to_cart_{product_id}')],
    ]
    
    # Add discount button if discount is available
    if discount and discount > 0:
        keyboard.insert(1, [InlineKeyboardButton(f"В корзину со скидкой {int(discount)} руб.", callback_data=f'add_to_cart_discount_{product_id}')])
    
    keyboard.append([InlineKeyboardButton("⬅️ К книгам автора", callback_data=f'author_{author_id}')])
    
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


async def add_to_cart(query, context: ContextTypes.DEFAULT_TYPE, product_id: int, with_discount: bool = False) -> None:
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
        # Create a copy of the product to modify if discount is applied
        cart_product = product.copy()
        
        if with_discount:
            discount = product.get('Discount', 0)
            if discount and discount > 0:
                original_price = product.get('Price', 0)
                discounted_price = max(0, original_price - discount)
                cart_product['Price'] = discounted_price
                cart_product['DiscountApplied'] = discount
        
        context.user_data['cart'].append(cart_product)
        title = product.get('Title', 'Без названия')
        
        if with_discount and product.get('Discount', 0) > 0:
            discount_amount = product.get('Discount', 0)
            await query.answer(f"✅ '{title}' добавлена в корзину со скидкой {int(discount_amount)} руб.!")
        else:
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
    
    # Calculate totals with promotions
    original_total = sum(product.get('Price', 0) for product in cart)
    final_total, promotion_discounts = calculate_cart_with_promotions(cart)
    
    message_lines = ["🛒 *Ваша корзина:*\n"]
    
    # Create a map of products that get promotion discounts for display
    promo_discount_map = {}
    for discount_info in promotion_discounts:
        product_id = discount_info['product'].get('ProductID')
        promo_discount_map[product_id] = discount_info
    
    for i, product in enumerate(cart, 1):
        title = product.get('Title', 'Без названия')
        price = product.get('Price', 0)
        product_id = product.get('ProductID')
        
        # Check for existing discount (monetary)
        if product.get('DiscountApplied', 0) > 0:
            discount_amount = product.get('DiscountApplied', 0)
            message_lines.append(f"{i}. {title} - {price} руб. (скидка {int(discount_amount)} руб.)")
        # Check for promotion discount
        elif product_id in promo_discount_map:
            promo_info = promo_discount_map[product_id]
            message_lines.append(f"{i}. {title} - {price} руб. → БЕСПЛАТНО ({promo_info['reason']})")
        else:
            message_lines.append(f"{i}. {title} - {price} руб.")
    
    # Show promotion savings if any
    if original_total != final_total:
        savings = original_total - final_total
        message_lines.append(f"\n💰 К доплате: {original_total} руб.")
        message_lines.append(f"🎉 Экономия по акции «3 за 2»: {savings} руб.")
        message_lines.append(f"💵 *Итого к оплате: {final_total} руб.*")
    else:
        message_lines.append(f"\n💰 *Общая сумма: {final_total} руб.*")
    
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
    
    # Calculate total with promotions and get author info
    original_total = sum(product.get('Price', 0) for product in cart)
    total, promotion_discounts = calculate_cart_with_promotions(cart)
    
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
        if product.get('DiscountApplied', 0) > 0:
            discount_amount = product.get('DiscountApplied', 0)
            cart_lines.append(f"{i}. {title} - {price} руб. (скидка {int(discount_amount)} руб.)")
        else:
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
    
    original_total = sum(product.get('Price', 0) for product in cart)
    total, promotion_discounts = calculate_cart_with_promotions(cart)
    
    # Create cart summary
    cart_lines = [f"💵 *Оплата наличными*\n"]
    cart_lines.append(f"💰 Сумма: {total} руб.\n")
    
    for i, product in enumerate(cart, 1):
        title = product.get('Title', 'Без названия')
        price = product.get('Price', 0)
        if product.get('DiscountApplied', 0) > 0:
            discount_amount = product.get('DiscountApplied', 0)
            cart_lines.append(f"{i}. {title} - {price} руб. (скидка {int(discount_amount)} руб.)")
        else:
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


def calculate_cart_with_promotions(cart):
    """Calculate cart total with '3 for the price of 2' promotion based on Google Sheets data."""
    if not cart:
        return 0, []
    
    # Separate promotion products from regular products based on Promotion column
    promotion_products = []
    regular_products = []
    
    for product in cart:
        promotion_type = product.get('Promotion', '').strip().lower()
        if promotion_type == '3for2':
            promotion_products.append(product)
        else:
            regular_products.append(product)
    
    # Calculate regular products total (includes existing discount logic)
    regular_total = sum(product.get('Price', 0) for product in regular_products)
    
    # Calculate promotion products with "3 for 2" logic
    promotion_total = 0
    promotion_discounts = []
    
    if promotion_products:
        # Sort promotion products by price (descending) to identify cheapest in each group of 3
        sorted_promo = sorted(promotion_products, key=lambda p: p.get('Price', 0), reverse=True)
        
        for i in range(0, len(sorted_promo), 3):
            group = sorted_promo[i:i+3]
            
            if len(group) == 3:
                # Full group of 3: pay for 2, cheapest is free
                group_prices = [p.get('Price', 0) for p in group]
                cheapest_price = min(group_prices)
                group_total = sum(group_prices) - cheapest_price
                promotion_total += group_total
                
                # Track which product gets the discount
                cheapest_product = min(group, key=lambda p: p.get('Price', 0))
                promotion_discounts.append({
                    'product': cheapest_product,
                    'discount_amount': cheapest_price,
                    'reason': '3 за 2'
                })
            else:
                # Incomplete group: pay full price
                promotion_total += sum(p.get('Price', 0) for p in group)
    
    total = regular_total + promotion_total
    return total, promotion_discounts


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
    
    # Calculate final prices with promotions
    total_amount, promotion_discounts = calculate_cart_with_promotions(cart)
    
    # Create a map of promotion discounts for transaction recording
    promo_discount_map = {}
    for discount_info in promotion_discounts:
        product_id = discount_info['product'].get('ProductID')
        promo_discount_map[product_id] = discount_info
    
    # Record each product as a separate transaction
    successful_transactions = 0
    failed_transactions = 0
    
    for product in cart:
        product_id = product.get('ProductID')
        author_id = product.get('AuthorID')
        
        # Use promotion-adjusted price if applicable
        if product_id in promo_discount_map:
            # Product is free due to "3 for 2" promotion
            price = 0
        else:
            # Use original price (which may already include monetary discounts)
            price = product.get('Price', 0)
        
        success = sheets_handler.record_transaction(product_id, author_id, payment_method, price)
        if success:
            successful_transactions += 1
        else:
            failed_transactions += 1
    
    # Clear cart after recording transactions
    context.user_data['cart'] = []
    
    # Prepare result message
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
    """Shows date selection for totals view."""
    from datetime import datetime, timedelta
    
    # Generate date options
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    keyboard = [
        [InlineKeyboardButton("📅 Сегодня", callback_data=f'totals_date_{today.strftime("%Y-%m-%d")}')],
        [InlineKeyboardButton("📅 Вчера", callback_data=f'totals_date_{yesterday.strftime("%Y-%m-%d")}')],
        [InlineKeyboardButton("📅 За неделю", callback_data=f'totals_date_{week_ago.strftime("%Y-%m-%d")}')],
        [InlineKeyboardButton("📅 За месяц", callback_data=f'totals_date_{month_ago.strftime("%Y-%m-%d")}')],
        [InlineKeyboardButton("📅 Все время", callback_data='totals_date_all')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_text(
            "📊 *Итоги продаж*\n\nВыберите период для просмотра:",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    except telegram.error.BadRequest as e:
        if "no text in the message to edit" in str(e).lower():
            await query.message.delete()
            await query.message.reply_text(
                "📊 *Итоги продаж*\n\nВыберите период для просмотра:",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            raise e


async def show_sales_summary(query, context: ContextTypes.DEFAULT_TYPE, date: str) -> None:
    """Shows sales summary by author for the selected date."""
    try:
        # Get sales data
        start_date = None if date == 'all' else date
        summary = sheets_handler.get_sales_summary_by_author(start_date)
        
        if not summary:
            keyboard = [[InlineKeyboardButton("⬅️ К выбору периода", callback_data='view_totals')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "📊 Нет данных о продажах за выбранный период.",
                reply_markup=reply_markup
            )
            return
        
        # Format date string for display
        from datetime import datetime
        if date == 'all':
            period_text = "за все время"
        else:
            try:
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                period_text = f"с {date_obj.strftime('%d.%m.%Y')}"
            except:
                period_text = f"с {date}"
        
        message_lines = [f"📊 *Итоги продаж {period_text}*\n"]
        
        # Calculate totals
        total_cash = sum(author_data['cash'] for author_data in summary.values())
        total_cashless = sum(author_data['cashless'] for author_data in summary.values())
        grand_total = total_cash + total_cashless
        
        # Sort authors by total sales (descending)
        sorted_authors = sorted(summary.items(), key=lambda x: x[1]['total'], reverse=True)
        
        keyboard = []
        for author_name, author_data in sorted_authors:
            cash = author_data['cash']
            cashless = author_data['cashless']
            total = author_data['total']
            author_id = author_data['author_id']
            
            # Format amounts
            if cash > 0 and cashless > 0:
                amounts_text = f"{total:.0f}₽ (💵{cash:.0f} + 💳{cashless:.0f})"
            elif cash > 0:
                amounts_text = f"{total:.0f}₽ (💵 наличные)"
            elif cashless > 0:
                amounts_text = f"{total:.0f}₽ (💳 безнал)"
            else:
                amounts_text = "0₽"
            
            # Create button for author details
            button_text = f"{author_name}: {amounts_text}"
            # Truncate if too long
            if len(button_text) > 45:
                button_text = button_text[:42] + "..."
            
            callback_data = f'author_details_{author_id}_{date}' if date != 'all' else f'author_details_{author_id}_all'
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        # Add summary at the end of message
        message_lines.append("📈 *ОБЩИЙ ИТОГ:*")
        if total_cash > 0:
            message_lines.append(f"💵 Наличные: {total_cash:.0f} руб.")
        if total_cashless > 0:
            message_lines.append(f"💳 Безнал: {total_cashless:.0f} руб.")
        message_lines.append(f"💰 **Всего: {grand_total:.0f} руб.**")
        
        # Add back button
        keyboard.append([InlineKeyboardButton("⬅️ К выбору периода", callback_data='view_totals')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            '\n'.join(message_lines),
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Error showing sales summary: {e}")
        keyboard = [[InlineKeyboardButton("⬅️ К выбору периода", callback_data='view_totals')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "❌ Ошибка при загрузке данных.",
            reply_markup=reply_markup
        )


async def show_author_details(query, context: ContextTypes.DEFAULT_TYPE, author_id: int, date: str = None) -> None:
    """Shows detailed sales information for a specific author."""
    try:
        # Get author info
        authors = sheets_handler.get_authors()
        author = None
        for a in authors:
            if a.get('AuthorID') == author_id:
                author = a
                break
        
        if not author:
            await query.edit_message_text("❌ Автор не найден.")
            return
        
        author_name = author.get('Name', 'Неизвестный автор')
        start_date = None if date == 'all' else date
        
        # Get detailed transactions
        transactions = sheets_handler.get_author_transactions_detail(author_id, start_date)
        
        if not transactions:
            keyboard = [[InlineKeyboardButton("⬅️ Назад к итогам", callback_data=f'totals_date_{date}')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"📚 *{author_name}*\n\nНет продаж за выбранный период.",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            return
        
        # Calculate totals
        total_amount = 0
        cash_amount = 0
        cashless_amount = 0
        
        for transaction in transactions:
            amount = transaction['amount']
            if isinstance(amount, str):
                try:
                    amount = float(amount)
                except ValueError:
                    amount = 0
            
            total_amount += amount
            payment_method = transaction['payment_method'].lower()
            if payment_method == 'cash':
                cash_amount += amount
            elif payment_method == 'cashless':
                cashless_amount += amount
        
        # Format period text
        if date == 'all':
            period_text = "за все время"
        else:
            try:
                from datetime import datetime
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                period_text = f"с {date_obj.strftime('%d.%m.%Y')}"
            except:
                period_text = f"с {date}"
        
        # Build message
        message_lines = [f"📚 *{author_name}*"]
        message_lines.append(f"📊 Продажи {period_text}\n")
        
        # Summary
        message_lines.append("💰 *Итого:*")
        if cash_amount > 0:
            message_lines.append(f"💵 Наличные: {cash_amount:.0f} руб.")
        if cashless_amount > 0:
            message_lines.append(f"💳 Безнал: {cashless_amount:.0f} руб.")
        message_lines.append(f"**Всего: {total_amount:.0f} руб.**\n")
        
        # Transactions list
        message_lines.append(f"📋 *Продано товаров: {len(transactions)}*")
        
        # Show up to 10 most recent transactions
        for i, transaction in enumerate(transactions[:10]):
            payment_emoji = "💵" if transaction['payment_method'].lower() == 'cash' else "💳"
            timestamp = transaction['timestamp'].split(' ')[0] if transaction['timestamp'] else 'Неизвестно'
            try:
                from datetime import datetime
                date_obj = datetime.strptime(timestamp, '%Y-%m-%d')
                formatted_date = date_obj.strftime('%d.%m')
            except:
                formatted_date = timestamp
            
            amount = transaction['amount']
            if isinstance(amount, str):
                try:
                    amount = float(amount)
                except ValueError:
                    amount = 0
            
            message_lines.append(f"{i+1}. {transaction['product_title']} - {payment_emoji} {amount:.0f}₽ ({formatted_date})")
        
        if len(transactions) > 10:
            message_lines.append(f"... и еще {len(transactions) - 10} транзакций")
        
        keyboard = [[InlineKeyboardButton("⬅️ Назад к итогам", callback_data=f'totals_date_{date}')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            '\n'.join(message_lines),
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Error showing author details: {e}")
        keyboard = [[InlineKeyboardButton("⬅️ Назад к итогам", callback_data=f'totals_date_{date}' if date else 'view_totals')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "❌ Ошибка при загрузке данных автора.",
            reply_markup=reply_markup
        )


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