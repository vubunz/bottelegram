import os
import logging
from datetime import datetime, timedelta, time
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Get bot token from environment variable
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        'Xin chào! Tôi là bot XSMB. Gửi /help để xem hướng dẫn sử dụng.'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send help message."""
    help_message = """
🎯 HƯỚNG DẪN SỬ DỤNG BOT XỔ SỐ MIỀN BẮC 🎯

Các lệnh có sẵn:
/start    - Khởi động bot
/help     - Xem hướng dẫn sử dụng
/ketqua   - Xem kết quả xổ số ngày hôm nay
/ketqua_dd_mm - Xem kết quả theo ngày
/xien2_xx_xx - Kiểm tra xien 2
    
Cách sử dụng xem kết quả theo ngày:
- Cú pháp: /ketqua_dd_mm
- Trong đó: dd là ngày, mm là tháng
- Ví dụ: /ketqua_30_03 để xem kết quả ngày 30 tháng 3

⚠️ Lưu ý: 
- Các số ngày và tháng phải là số hợp lệ
- Định dạng phải chính xác như hướng dẫn
"""
    await update.message.reply_text(help_message)

async def get_full_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch and display current day XSMB result."""
    try:
        url = "https://rongbachkim.net/ketqua.html"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table', class_='ketqua')
        
        if table:
            # Parse and format result
            date_header = table.find('th', class_='kq_ngay').text.strip()
            message = format_result(table, date_header)
            await update.message.reply_text(message)
        else:
            await update.message.reply_text("Không thể tìm thấy kết quả xổ số. Vui lòng thử lại sau.")
            
    except Exception as e:
        logging.error(f"Error fetching XSMB result: {e}")
        await update.message.reply_text("Có lỗi xảy ra khi lấy kết quả. Vui lòng thử lại sau.")

async def get_result_by_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch XSMB result for specific date."""
    try:
        command = update.message.text.strip().lower()
        
        if not command.startswith('/ketqua_'):
            await help_command(update, context)
            return

        try:
            date_part = command[8:]
            day, month = map(int, date_part.split('_'))
            
            if not (1 <= day <= 31 and 1 <= month <= 12):
                raise ValueError
                
        except (ValueError, IndexError):
            await help_command(update, context)
            return

        # Kiểm tra ngày yêu cầu có trong phạm vi 2 ngày gần nhất không
        current_date = datetime.now()
        requested_date = datetime(current_date.year, month, day)
        yesterday = current_date - timedelta(days=1)

        if requested_date.date() > current_date.date():
            await update.message.reply_text(
                "❌ Không thể xem kết quả của ngày trong tương lai!\n"
                "Vui lòng chọn ngày khác."
            )
            return
        elif requested_date.date() < yesterday.date():
            await update.message.reply_text(
                f"❌ Rất tiếc, bot chỉ có thể xem kết quả của 2 ngày gần nhất "
                f"({yesterday.strftime('%d/%m')} và {current_date.strftime('%d/%m')}).\n\n"
                f"Để xem kết quả ngày {day:02d}/{month:02d}, "
                f"bạn có thể truy cập:\n"
                f"- https://xoso.me/xsmb-{day:02d}-{month:02d}-{current_date.year}\n"
                f"- https://www.minhngoc.net.vn/xo-so-mien-bac/{day:02d}-{month:02d}-{current_date.year}.html"
            )
            return

        # Tiếp tục code lấy kết quả như cũ nếu là 2 ngày gần nhất
        processing_message = await update.message.reply_text("⏳ Đang lấy kết quả...")

        current_year = datetime.now().year
        url = "https://rongbachkim.net/ketqua.html"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Tìm table dựa vào thuộc tính rel chứa ngày tháng
        target_date = f"{current_year}-{month:02d}-{day:02d}"
        table = soup.find('table', attrs={'rel': target_date})
        
        await processing_message.delete()

        if table:
            date_header = table.find('th', class_='kq_ngay').text.strip()
            message = format_result(table, date_header)
            await update.message.reply_text(message)
        else:
            await update.message.reply_text(
                f"❌ Không tìm thấy kết quả cho ngày {day:02d}/{month:02d}/{current_year}.\n"
                "Vui lòng thử lại với ngày khác."
            )
            
    except Exception as e:
        logging.error(f"Error fetching XSMB result for date: {e}")
        await update.message.reply_text(
            "❌ Có lỗi xảy ra khi lấy kết quả.\n"
            "Vui lòng thử lại sau."
        )

async def check_xien2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        command = update.message.text.strip().lower()
        
        # Lấy phần số sau /xien2_
        numbers_part = command[7:]
        num1, num2 = map(str, numbers_part.split('_'))
        
        # Chuyển số về format 2 chữ số
        num1 = num1.zfill(2)  # Thêm số 0 phía trước nếu cần
        num2 = num2.zfill(2)  # Thêm số 0 phía trước nếu cần
        
        # Kiểm tra tính hợp lệ của số
        if not (num1.isdigit() and num2.isdigit()):
            raise ValueError
            
        # Lấy kết quả xổ số ngày hiện tại
        current_datetime = datetime.now()
        cutoff_time = time(18, 30)

        # Kiểm tra thời gian để lấy kết quả phù hợp
        if current_datetime.time() >= cutoff_time:
            target_date = current_datetime.date()
        else:
            target_date = current_datetime.date() - timedelta(days=1)

        # Lấy kết quả xổ số
        url = "https://rongbachkim.net/ketqua.html"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Tìm bảng kết quả
        table = soup.find('table', class_='ketqua')
        
        if table:
            # Lấy tất cả các số trong bảng kết quả
            all_numbers = []
            for td in table.find_all('td', class_=lambda x: x and x.startswith('kq_')):
                number = td.text.strip()
                if number:
                    # Lấy 2 số cuối của mỗi giải
                    all_numbers.append(number[-2:] if len(number) >= 2 else number)

            # Kiểm tra xem cả 2 số có xuất hiện trong kết quả không
            found_numbers = []
            if num1 in all_numbers:
                found_numbers.append(num1)
            if num2 in all_numbers:
                found_numbers.append(num2)

            # Tạo thông báo kết quả
            date_str = target_date.strftime("%d/%m/%Y")
            if len(found_numbers) == 2:
                await update.message.reply_text(
                    f"🎉 CHÚC MỪNG!\n"
                    f"Cả hai số {num1} và {num2} đều xuất hiện trong kết quả ngày {date_str}!"
                )
            elif len(found_numbers) == 1:
                await update.message.reply_text(
                    f"😊 Số {found_numbers[0]} có xuất hiện trong kết quả ngày {date_str}\n"
                    f"Nhưng số {num2 if found_numbers[0] == num1 else num1} không xuất hiện."
                )
            else:
                await update.message.reply_text(
                    f"😔 Rất tiếc!\n"
                    f"Cả hai số {num1} và {num2} đều không xuất hiện trong kết quả ngày {date_str}."
                )
        else:
            await update.message.reply_text("❌ Không thể lấy được kết quả xổ số. Vui lòng thử lại sau.")
            
    except Exception as e:
        logging.error(f"Error checking xien2: {e}")
        await update.message.reply_text("❌ Có lỗi xảy ra. Vui lòng thử lại sau.")

def format_result(table, date_header):
    """Format XSMB result table."""
    message = "KẾT QUẢ XỔ SỐ MIỀN BẮC\n"
    message += f"{date_header}\n"
    message += "━━━━━━━━━━━━━━━━━━━━━\n"
    
    # Giải ĐB
    db = table.find('td', class_='kq_0').text.strip()
    message += f"Giải ĐB:   {db}\n"
    message += "━━━━━━━━━━━━━━━━━━━━━\n"
    
    # Giải nhất
    nhat = table.find('td', class_='kq_1').text.strip()
    message += f"Giải nhất: {nhat}\n"
    message += "━━━━━━━━━━━━━━━━━━━━━\n"
    
    # Giải nhì
    nhi_cells = table.find_all('td', class_=['kq_2', 'kq_3'])
    nhi = '    '.join([cell.text.strip() for cell in nhi_cells])
    message += f"Giải nhì:  {nhi}\n"
    message += "━━━━━━━━━━━━━━━━━━━━━\n"
    
    # Giải ba
    ba_cells = table.find_all('td', class_=['kq_4', 'kq_5', 'kq_6', 'kq_7', 'kq_8', 'kq_9'])
    ba_1 = '    '.join([ba_cells[i].text.strip() for i in range(3)])
    ba_2 = '    '.join([ba_cells[i].text.strip() for i in range(3, 6)])
    message += f"Giải ba:   {ba_1}\n"
    message += f"          {ba_2}\n"
    message += "━━━━━━━━━━━━━━━━━━━━━\n"
    
    # Giải tư
    tu_cells = table.find_all('td', class_=['kq_10', 'kq_11', 'kq_12', 'kq_13'])
    tu = '     '.join([cell.text.strip() for cell in tu_cells])
    message += f"Giải tư:   {tu}\n"
    message += "━━━━━━━━━━━━━━━━━━━━━\n"
    
    # Giải năm
    nam_cells = table.find_all('td', class_=['kq_14', 'kq_15', 'kq_16', 'kq_17', 'kq_18', 'kq_19'])
    nam_1 = '     '.join([nam_cells[i].text.strip() for i in range(3)])
    nam_2 = '     '.join([nam_cells[i].text.strip() for i in range(3, 6)])
    message += f"Giải năm:  {nam_1}\n"
    message += f"          {nam_2}\n"
    message += "━━━━━━━━━━━━━━━━━━━━━\n"
    
    # Giải sáu
    sau_cells = table.find_all('td', class_=['kq_20', 'kq_21', 'kq_22'])
    sau = '      '.join([cell.text.strip() for cell in sau_cells])
    message += f"Giải sáu:  {sau}\n"
    message += "━━━━━━━━━━━━━━━━━━━━━\n"
    
    # Giải bảy
    bay_cells = table.find_all('td', class_=['kq_23', 'kq_24', 'kq_25', 'kq_26'])
    bay = '       '.join([cell.text.strip() for cell in bay_cells])
    message += f"Giải bảy:  {bay}"
    
    return message

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle unknown commands and messages."""
    await help_command(update, context)

def main():
    """Start the bot."""
    application = Application.builder().token(TOKEN).build()

    # Thêm handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("ketqua", get_full_result))
    application.add_handler(MessageHandler(filters.Regex(r'^/ketqua_\d{1,2}_\d{1,2}$'), get_result_by_date))
    # Sửa lại pattern cho xien2 để bắt đúng format
    application.add_handler(MessageHandler(filters.Regex(r'^/xien2_\d{1,2}_\d{1,2}$'), check_xien2))
    
    # Handler cho các message không hợp lệ
    application.add_handler(MessageHandler(filters.TEXT, unknown))

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main() 