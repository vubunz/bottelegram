# 🎲 Bot Tài Xỉu Telegram

Bot chơi game Tài Xỉu trên Telegram với tính năng quản lý người chơi và lưu trữ dữ liệu qua MongoDB.

## 📋 Tính năng

- 🎮 Chơi game Tài Xỉu với 3 xúc xắc
- 💰 Quản lý số dư người chơi
- 📊 Thống kê kết quả chơi
- 💎 Nạp tiền (chỉ dành cho admin)
- 📱 Giao diện nút bấm thân thiện
- 🗄️ Lưu trữ dữ liệu với MongoDB

## 🎯 Luật chơi

- **Tài**: Tổng 3 xúc xắc từ 11-18
- **Xỉu**: Tổng 3 xúc xắc từ 3-10
- **Thắng**: Nhận lại số tiền cược
- **Thua**: Mất số tiền cược

## 🛠️ Cài đặt

1. Cài đặt Python và pip

2. Cài đặt các thư viện cần thiết:

```bash
pip install -r requirements.txt
```

3. Tạo file `.env` với nội dung:

```
TELEGRAM_BOT_TOKEN=your_bot_token_here
MONGODB_URI=your_mongodb_uri_here
```

4. Cấu hình trong `bot.py`:

```python
ADMIN_USERNAME = "your_telegram_username"  # Thay đổi username admin
```

## 📝 Cấu trúc Database

### Collection: users

- user_id: ID Telegram của người dùng
- username: Username Telegram
- balance: Số dư hiện tại
- total_games: Tổng số ván đã chơi
- wins: Số ván thắng
- losses: Số ván thua
- created_at: Thời điểm tạo tài khoản
- updated_at: Thời điểm cập nhật gần nhất

### Collection: transactions

- user_id: ID người dùng
- amount: Số tiền (dương: thắng/nạp, âm: thua)
- type: Loại giao dịch ('recharge', 'win', 'loss')
- description: Mô tả giao dịch
- timestamp: Thời điểm giao dịch

### Collection: game_history

- user_id: ID người dùng
- choice: Lựa chọn ('tai' hoặc 'xiu')
- bet_amount: Số tiền cược
- result: Kết quả ('win' hoặc 'loss')
- dice_results: Kết quả xúc xắc [số1, số2, số3]
- total: Tổng điểm xúc xắc
- timestamp: Thời điểm chơi

## 🎮 Cách sử dụng

1. **Bắt đầu**: Gửi lệnh `/start` để bắt đầu
2. **Xem số dư**: Sử dụng `/balance` hoặc nút "Xem Số Dư"
3. **Chơi game**:
   - Sử dụng `/taixiu` hoặc nút "Chơi Tài Xỉu"
   - Chọn Tài hoặc Xỉu
   - Chọn mức cược hoặc tự nhập số tiền
4. **Nạp tiền** (chỉ admin):
   - Bấm nút "Nạp Tiền"
   - Nhập ID người nhận
   - Nhập số tiền cần nạp

## 🔑 Lệnh Admin

- Nạp tiền: Bấm nút "Nạp Tiền" và làm theo hướng dẫn
- Định dạng nạp tiền: Nhập ID người dùng → Nhập số tiền

## 🚀 Chạy bot

```bash
python bot.py
```

## 📌 Lưu ý

- Người chơi mới sẽ được tặng 1000 coins khi bắt đầu
- Chỉ admin mới có quyền nạp tiền cho người chơi
- Bot sẽ tự động lưu trữ lịch sử chơi và giao dịch
- Đảm bảo đã whitelist IP trong MongoDB Atlas
