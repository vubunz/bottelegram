import os
import random
import asyncio
import sys
import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from pymongo import MongoClient

# Load environment variables
load_dotenv()

# Get bot token and MongoDB connection string
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
MONGODB_URI = os.getenv('MONGODB_URI')

if not TOKEN:
    print("Error: Telegram bot token not found in .env file")
    sys.exit(1)

if not MONGODB_URI:
    print("Error: MongoDB URI not found in .env file")
    sys.exit(1)

# Connect to MongoDB
try:
    # Simple connection with minimal parameters
    client = MongoClient(MONGODB_URI)
    
    # Test connection
    client.admin.command('ping')
    
    # Get database and collections
    db = client.get_database()
    users_collection = db.users
    transactions_collection = db.transactions
    game_history_collection = db.game_history
    
    # Create basic index
    users_collection.create_index([("user_id", 1)], unique=True)
    
    print("✅ Connected to MongoDB successfully!")
except Exception as e:
    print(f"❌ Error connecting to MongoDB: {e}")
    print("Please check:")
    print("1. MongoDB connection string in .env file")
    print("2. Network connection")
    print("3. IP whitelist in MongoDB Atlas")
    sys.exit(1)

# Admin username
ADMIN_USERNAME = "vubunz"

# Dictionary to store game states
user_game_states = {}  # Store user's game state (chosen side)
recharge_states = {}  # Store recharge state (waiting for amount and user_id)
admin_recharge_data = {}  # Store admin recharge data (target_user_id)

def is_admin(username: str) -> bool:
    """Check if user is admin."""
    return username == ADMIN_USERNAME

async def get_user_balance(user_id: int) -> int:
    """Get user balance and info from database."""
    try:
        user = users_collection.find_one({'user_id': user_id})
        if user is None:
            # Initialize new user with 1000 coins
            users_collection.insert_one({
                'user_id': user_id,
                'username': '',
                'balance': 1000,
                'created_at': datetime.datetime.utcnow(),
                'updated_at': datetime.datetime.utcnow()
            })
            return 1000
        return user['balance']
    except Exception as e:
        print(f"Error getting user balance: {e}")
        return 1000  # Return default balance on error

async def update_user_balance(user_id: int, new_balance: int, username: str = ''):
    """Update user balance and info in database."""
    try:
        update_data = {
            'balance': new_balance,
            'updated_at': datetime.datetime.utcnow()
        }
        
        # Only update username if provided
        if username:
            update_data['username'] = username
            
        users_collection.update_one(
            {'user_id': user_id},
            {
                '$set': update_data,
                '$setOnInsert': {
                    'created_at': datetime.datetime.utcnow()
                }
            },
            upsert=True
        )
    except Exception as e:
        print(f"Error updating user balance: {e}")

async def get_user_info(user_id: int):
    """Get full user info from database."""
    try:
        return users_collection.find_one({'user_id': user_id})
    except Exception as e:
        print(f"Error getting user info: {e}")
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    user = update.effective_user
    user_id = user.id
    
    if user_id not in user_game_states:
        user_game_states[user_id] = None
    
    # Update user info in database
    await update_user_balance(user_id, await get_user_balance(user_id), user.username)
    
    welcome_message = (
        f"Xin chào {user.first_name}! 👋\n\n"
        f"Số dư của bạn: {await get_user_balance(user_id)} 💰\n\n"
        "Sử dụng lệnh /taixiu để chơi tài xỉu!\n"
        "Sử dụng lệnh /balance để xem số dư!"
    )
    await update.message.reply_text(welcome_message)

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's current balance."""
    user_id = update.effective_user.id
    if user_id not in user_game_states:
        user_game_states[user_id] = None
    
    await update.message.reply_text(f"Số dư của bạn: {await get_user_balance(user_id)} 💰")

async def taixiu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start a tài xỉu game."""
    user_id = update.effective_user.id
    if user_id not in user_game_states:
        user_game_states[user_id] = None
    
    if await get_user_balance(user_id) <= 0:
        await update.message.reply_text("Bạn đã hết tiền! Hãy chờ admin nạp thêm!")
        return

    keyboard = [
        [
            InlineKeyboardButton("Tài (11-18)", callback_data="choose_tai"),
            InlineKeyboardButton("Xỉu (3-10)", callback_data="choose_xiu")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Chọn Tài hoặc Xỉu:",
        reply_markup=reply_markup
    )

async def show_bet_amounts(update: Update, context: ContextTypes.DEFAULT_TYPE, choice: str):
    """Show betting amount options."""
    keyboard = [
        [
            InlineKeyboardButton("50 💰", callback_data=f"bet_{choice}_50"),
            InlineKeyboardButton("100 💰", callback_data=f"bet_{choice}_100"),
        ],
        [
            InlineKeyboardButton("500 💰", callback_data=f"bet_{choice}_500"),
            InlineKeyboardButton("1000 💰", callback_data=f"bet_{choice}_1000"),
        ],
        [
            InlineKeyboardButton("Tự nhập số tiền", callback_data=f"custom_{choice}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        text="Chọn mức cược:",
        reply_markup=reply_markup
    )

async def handle_custom_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle custom bet amount input."""
    user_id = update.message.from_user.id
    if user_id not in user_game_states:
        await update.message.reply_text("Vui lòng bắt đầu game mới với /taixiu")
        return

    try:
        bet_amount = int(update.message.text)
        if bet_amount <= 0:
            await update.message.reply_text("Mức cược phải lớn hơn 0!")
            return
        if bet_amount > await get_user_balance(user_id):
            await update.message.reply_text("Bạn không đủ tiền để đặt mức cược này!")
            return
        
        # Get the saved choice (tai/xiu)
        choice = user_game_states[user_id]
        # Clear the game state
        del user_game_states[user_id]
        # Process the game
        await process_game(update, context, choice, bet_amount)
    except ValueError:
        await update.message.reply_text("Vui lòng nhập số tiền hợp lệ!")

async def process_game(update: Update, context: ContextTypes.DEFAULT_TYPE, choice: str, bet_amount: int):
    """Process the game with chosen side and bet amount."""
    user_id = update.effective_user.id if hasattr(update, 'effective_user') else update.message.from_user.id
    
    # Send initial message
    if hasattr(update, 'callback_query') and update.callback_query:
        message = await update.callback_query.edit_message_text("🎲 Đang lắc xúc xắc...")
    else:
        message = await update.message.reply_text("🎲 Đang lắc xúc xắc...")

    # Roll and show each dice with animation
    dice_results = []
    for i in range(3):
        if hasattr(update, 'callback_query') and update.callback_query:
            dice_msg = await update.callback_query.message.reply_dice(emoji='🎲')
        else:
            dice_msg = await update.message.reply_dice(emoji='🎲')
        dice_results.append(dice_msg.dice.value)
        if i < 2:  # Don't wait after the last dice
            await asyncio.sleep(2)  # Wait between dice rolls
    
    total = sum(dice_results)
    result = "tai" if total >= 11 and total <= 18 else "xiu"
    
    # Update balance and log game
    current_balance = await get_user_balance(user_id)
    if choice == result:
        new_balance = current_balance + bet_amount
        await update_user_balance(user_id, new_balance)
        await log_transaction(user_id, bet_amount, 'win', f'Won {bet_amount} from tài xỉu game')
        await log_game(user_id, choice, bet_amount, 'win', dice_results)
        result_message = (
            f"🎲 Kết quả: {' + '.join(str(x) for x in dice_results)} = {total} ({result.upper()})\n"
            f"Chúc mừng! Bạn thắng {bet_amount} 💰\n"
            f"Số dư: {new_balance}"
        )
    else:
        new_balance = current_balance - bet_amount
        await update_user_balance(user_id, new_balance)
        await log_transaction(user_id, -bet_amount, 'loss', f'Lost {bet_amount} in tài xỉu game')
        await log_game(user_id, choice, bet_amount, 'loss', dice_results)
        result_message = (
            f"🎲 Kết quả: {' + '.join(str(x) for x in dice_results)} = {total} ({result.upper()})\n"
            f"Rất tiếc! Bạn thua {bet_amount} 💰\n"
            f"Số dư: {new_balance}"
        )
    
    # Wait a moment for all dice animations to complete
    await asyncio.sleep(3)
    
    # Get user stats
    stats = await get_user_stats(user_id)
    if stats:
        result_message += f"\n\nThống kê:\nTổng ván: {stats['total_games']}\nThắng: {stats['wins']}\nThua: {stats['losses']}"
    
    # Send result message
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.message.reply_text(result_message)
    else:
        await message.reply_text(result_message)

async def show_help_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help menu with buttons."""
    user = update.message.from_user
    keyboard = [
        [
            InlineKeyboardButton("🎮 Chơi Tài Xỉu", callback_data="play_taixiu"),
            InlineKeyboardButton("💰 Xem Số Dư", callback_data="check_balance")
        ],
        [
            InlineKeyboardButton("ℹ️ Hướng Dẫn", callback_data="show_guide"),
            InlineKeyboardButton("🆔 Xem ID", callback_data="show_id")
        ]
    ]
    
    # Add recharge button if user is admin
    if is_admin(user.username):
        keyboard.append([
            InlineKeyboardButton("💎 Nạp Tiền", callback_data="admin_recharge")
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    help_message = (
        "🎲 *HƯỚNG DẪN CHƠI TÀI XỈU* 🎲\n\n"
        "1️⃣ Sử dụng lệnh /taixiu để bắt đầu\n"
        "2️⃣ Chọn Tài (11-18) hoặc Xỉu (3-10)\n"
        "3️⃣ Chọn mức cược\n"
        "4️⃣ Xem kết quả và nhận thưởng\n\n"
        "💰 Kiểm tra số dư: /balance\n"
        "🎮 Chơi mới: /taixiu"
    )
    
    await update.message.reply_text(help_message, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_recharge_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle recharge amount input from admin."""
    user = update.message.from_user
    if not is_admin(user.username):
        return
        
    # Check if user is in recharge state and has target user_id
    if user.id not in recharge_states or not recharge_states[user.id] or user.id not in admin_recharge_data:
        return
    
    try:
        amount = int(update.message.text)
        target_user_id = admin_recharge_data[user.id]
            
        if amount <= 0:
            await update.message.reply_text("❌ Số tiền phải lớn hơn 0!")
            return

        # Check if target user exists in database
        target_user = users_collection.find_one({'user_id': target_user_id})
        if not target_user:
            # Clear states
            del recharge_states[user.id]
            del admin_recharge_data[user.id]
            
            # Show error message and menu
            keyboard = [
                [
                    InlineKeyboardButton("🎮 Chơi Tài Xỉu", callback_data="play_taixiu"),
                    InlineKeyboardButton("💰 Xem Số Dư", callback_data="check_balance")
                ],
                [
                    InlineKeyboardButton("💎 Thử lại nạp tiền", callback_data="admin_recharge")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"❌ Không tìm thấy người dùng với ID: {target_user_id}\n"
                "Vui lòng kiểm tra lại ID người dùng!",
                reply_markup=reply_markup
            )
            return
                
        # Add money
        current_balance = target_user['balance']
        new_balance = current_balance + amount
        await update_user_balance(target_user_id, new_balance)
            
        # Log the recharge transaction
        await log_transaction(target_user_id, amount, 'recharge', f'Admin recharge {amount} coins')
            
        await update.message.reply_text(
            f"✅ Đã nạp {amount} 💰 cho user {target_user_id}\n"
            f"Số dư cũ: {current_balance} 💰\n"
            f"Số dư mới: {new_balance} 💰"
        )
            
        # Clear states
        del recharge_states[user.id]
        del admin_recharge_data[user.id]
            
        # Show help menu after recharge
        keyboard = [
            [
                InlineKeyboardButton("🎮 Chơi Tài Xỉu", callback_data="play_taixiu"),
                InlineKeyboardButton("💰 Xem Số Dư", callback_data="check_balance")
            ],
            [
                InlineKeyboardButton("💎 Nạp Thêm", callback_data="admin_recharge")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Bạn có muốn thực hiện thao tác khác?",
            reply_markup=reply_markup
        )
    except ValueError:
        await update.message.reply_text(
            "❌ Vui lòng nhập số tiền hợp lệ!"
        )

async def handle_recharge_userid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user ID input for recharge."""
    user = update.message.from_user
    if not is_admin(user.username):
        return
        
    # Check if user is waiting for user_id input
    if user.id not in recharge_states or not recharge_states[user.id]:
        return
        
    try:
        target_user_id = int(update.message.text)
        
        # Check if target user exists in database
        target_user = users_collection.find_one({'user_id': target_user_id})
        if not target_user:
            keyboard = [
                [
                    InlineKeyboardButton("❌ Thoát", callback_data="cancel_recharge")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"❌ Không tìm thấy người dùng với ID: {target_user_id}\n"
                "Vui lòng nhập lại ID người dùng khác hoặc bấm thoát:",
                reply_markup=reply_markup
            )
            return
        
        # Store target user_id and wait for amount
        admin_recharge_data[user.id] = target_user_id
        
        keyboard = [
            [
                InlineKeyboardButton("❌ Thoát", callback_data="cancel_recharge")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"🎯 ID người nhận: {target_user_id}\n"
            f"👤 Tên người nhận: {target_user.get('username', 'Không có tên')}\n"
            f"💰 Số dư hiện tại: {target_user.get('balance', 0)}\n\n"
            "💎 Vui lòng nhập số tiền cần nạp:",
            reply_markup=reply_markup
        )
    except ValueError:
        keyboard = [
            [
                InlineKeyboardButton("❌ Thoát", callback_data="cancel_recharge")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "❌ ID người dùng không hợp lệ!\n"
            "Vui lòng nhập lại ID (chỉ nhập số) hoặc bấm thoát:",
            reply_markup=reply_markup
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all button callbacks."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    callback_data = query.data

    # Handle help menu buttons
    if callback_data == "play_taixiu":
        if user_id not in user_game_states:
            user_game_states[user_id] = None
        
        if await get_user_balance(user_id) <= 0:
            await query.edit_message_text("Bạn đã hết tiền! Hãy chờ admin nạp thêm!")
            return

        keyboard = [
            [
                InlineKeyboardButton("Tài (11-18)", callback_data="choose_tai"),
                InlineKeyboardButton("Xỉu (3-10)", callback_data="choose_xiu")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text="Chọn Tài hoặc Xỉu:",
            reply_markup=reply_markup
        )
    elif callback_data == "check_balance":
        if user_id not in user_game_states:
            user_game_states[user_id] = None
        
        keyboard = [
            [
                InlineKeyboardButton("🎮 Chơi Tài Xỉu", callback_data="play_taixiu"),
                InlineKeyboardButton("ℹ️ Hướng Dẫn", callback_data="show_guide")
            ]
        ]
        
        # Add recharge button if user is admin
        if is_admin(query.from_user.username):
            keyboard.append([
                InlineKeyboardButton("💎 Nạp Tiền", callback_data="admin_recharge")
            ])
            
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=f"Số dư của bạn: {await get_user_balance(user_id)} 💰",
            reply_markup=reply_markup
        )
    elif callback_data == "show_id":
        keyboard = [
            [
                InlineKeyboardButton("🎮 Chơi Tài Xỉu", callback_data="play_taixiu"),
                InlineKeyboardButton("💰 Xem Số Dư", callback_data="check_balance")
            ],
            [
                InlineKeyboardButton("ℹ️ Hướng Dẫn", callback_data="show_guide")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=f"🆔 ID của bạn là: `{user_id}`\n\nLưu ý: ID này dùng để nạp tiền.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    elif callback_data == "admin_recharge" and is_admin(query.from_user.username):
        # Set recharge state and clear previous data
        recharge_states[user_id] = True
        if user_id in admin_recharge_data:
            del admin_recharge_data[user_id]
            
        keyboard = [
            [
                InlineKeyboardButton("❌ Thoát", callback_data="cancel_recharge")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "💎 *NẠP TIỀN*\n\n"
            "Vui lòng nhập ID người nhận:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    elif callback_data == "cancel_recharge":
        # Clear recharge states
        if user_id in recharge_states:
            del recharge_states[user_id]
        if user_id in admin_recharge_data:
            del admin_recharge_data[user_id]
            
        # Show main menu
        keyboard = [
            [
                InlineKeyboardButton("🎮 Chơi Tài Xỉu", callback_data="play_taixiu"),
                InlineKeyboardButton("💰 Xem Số Dư", callback_data="check_balance")
            ],
            [
                InlineKeyboardButton("ℹ️ Hướng Dẫn", callback_data="show_guide"),
                InlineKeyboardButton("🆔 Xem ID", callback_data="show_id")
            ]
        ]
        
        # Add recharge button if user is admin
        if is_admin(query.from_user.username):
            keyboard.append([
                InlineKeyboardButton("💎 Nạp Tiền", callback_data="admin_recharge")
            ])
            
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "Đã hủy thao tác nạp tiền.\nBạn có thể chọn thao tác khác:",
            reply_markup=reply_markup
        )
    elif callback_data == "show_guide":
        guide_text = (
            "*LUẬT CHƠI TÀI XỈU*\n\n"
            "• Tài: Tổng 3 xúc xắc từ 11-18\n"
            "• Xỉu: Tổng 3 xúc xắc từ 3-10\n"
            "• Thắng: Nhận lại số tiền cược\n"
            "• Thua: Mất số tiền cược\n\n"
            "Chúc bạn chơi game vui vẻ! 🎉"
        )
        keyboard = [
            [
                InlineKeyboardButton("🎮 Chơi Ngay", callback_data="play_taixiu"),
                InlineKeyboardButton("💰 Xem Số Dư", callback_data="check_balance")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=guide_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    # Handle game buttons
    elif callback_data.startswith("choose_"):
        choice = callback_data.split("_")[1]
        await show_bet_amounts(update, context, choice)
    elif callback_data.startswith("bet_"):
        _, choice, amount = callback_data.split("_")
        bet_amount = int(amount)
        
        if bet_amount > await get_user_balance(user_id):
            await query.edit_message_text("Bạn không đủ tiền để đặt mức cược này!")
            return
        
        await process_game(update, context, choice, bet_amount)
    elif callback_data.startswith("custom_"):
        choice = callback_data.split("_")[1]
        user_game_states[user_id] = choice
        await query.edit_message_text(
            "Vui lòng nhập số tiền bạn muốn cược:"
        )

async def create_or_update_user(user_id: int, username: str = '', first_name: str = ''):
    """Create or update user in database."""
    try:
        update_data = {
            'username': username,
            'first_name': first_name,
            'updated_at': datetime.datetime.utcnow()
        }
        
        users_collection.update_one(
            {'user_id': user_id},
            {
                '$set': update_data,
                '$setOnInsert': {
                    'balance': 1000,
                    'created_at': datetime.datetime.utcnow(),
                    'total_games': 0,
                    'wins': 0,
                    'losses': 0
                }
            },
            upsert=True
        )
    except Exception as e:
        print(f"Error creating/updating user: {e}")

async def log_transaction(user_id: int, amount: int, transaction_type: str, description: str = ''):
    """Log transaction in database."""
    try:
        transactions_collection.insert_one({
            'user_id': user_id,
            'amount': amount,
            'type': transaction_type,  # 'recharge', 'win', 'loss'
            'description': description,
            'timestamp': datetime.datetime.utcnow()
        })
    except Exception as e:
        print(f"Error logging transaction: {e}")

async def log_game(user_id: int, choice: str, bet_amount: int, result: str, dice_results: list):
    """Log game result in database."""
    try:
        game_history_collection.insert_one({
            'user_id': user_id,
            'choice': choice,
            'bet_amount': bet_amount,
            'result': result,
            'dice_results': dice_results,
            'total': sum(dice_results),
            'timestamp': datetime.datetime.utcnow()
        })
        
        # Update user statistics
        update_data = {
            '$inc': {
                'total_games': 1,
                'wins' if result == 'win' else 'losses': 1
            }
        }
        users_collection.update_one({'user_id': user_id}, update_data)
    except Exception as e:
        print(f"Error logging game: {e}")

async def get_user_stats(user_id: int):
    """Get user statistics from database."""
    try:
        user = users_collection.find_one({'user_id': user_id})
        if user:
            return {
                'total_games': user.get('total_games', 0),
                'wins': user.get('wins', 0),
                'losses': user.get('losses', 0),
                'balance': user.get('balance', 0)
            }
        return None
    except Exception as e:
        print(f"Error getting user stats: {e}")
        return None

# Custom filters
class RechargeAmountFilter(filters.MessageFilter):
    def filter(self, message):
        return (message.from_user.id in admin_recharge_data and 
                message.text and message.text.isdigit())

class RechargeUserIDFilter(filters.MessageFilter):
    def filter(self, message):
        return (message.from_user.id in recharge_states and 
                recharge_states.get(message.from_user.id) and
                message.text and message.text.isdigit())

class CustomBetFilter(filters.MessageFilter):
    def filter(self, message):
        return (message.from_user.id in user_game_states and 
                user_game_states.get(message.from_user.id) is not None and
                message.text and message.text.isdigit())

def main():
    """Start the bot."""
    try:
        # Create the Application and pass it your bot's token
        application = Application.builder().token(TOKEN).build()

        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("balance", balance))
        application.add_handler(CommandHandler("taixiu", taixiu))
        
        # Add single callback handler for all buttons
        application.add_handler(CallbackQueryHandler(button_callback))
        
        # Create custom filters
        recharge_amount_filter = RechargeAmountFilter()
        recharge_userid_filter = RechargeUserIDFilter()
        custom_bet_filter = CustomBetFilter()
        
        # Add message handlers in specific order
        # 1. Handle recharge amount input (highest priority)
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & recharge_amount_filter,
            handle_recharge_amount
        ))
        
        # 2. Handle recharge user ID input
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & recharge_userid_filter,
            handle_recharge_userid
        ))
        
        # 3. Handle custom bet amount
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & custom_bet_filter,
            handle_custom_bet
        ))
        
        # 4. Handle all other text messages (lowest priority)
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            show_help_menu
        ))

        # Start the Bot
        print("Bot is running...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        print(f"Error running bot: {e}")
    finally:
        # Close MongoDB connection when bot stops
        client.close()
        print("MongoDB connection closed")

if __name__ == '__main__':
    main() 