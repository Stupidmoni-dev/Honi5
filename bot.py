import telebot
from telebot import types
import random
import psycopg2
from web3 import Web3
import json
import os
import time

# Initialize bot
bot = telebot.TeleBot('YOUR_BOT_TOKEN')

# Admin settings
ADMIN_ID = 6216175814

# Set up Web3 connection (Infura or Alchemy for Ethereum)
INFURA_URL = 'YOUR_INFURA_URL'
w3 = Web3(Web3.HTTPProvider(INFURA_URL))

# Contract ABI and address (replace with your deployed contract details)
contract_address = 'YOUR_CONTRACT_ADDRESS'
contract_abi = json.loads('[...]')  # ABI of your Escrow contract

# Initialize the contract
contract = w3.eth.contract(address=contract_address, abi=contract_abi)

# Connect to PostgreSQL
conn = psycopg2.connect(
    dbname="your_dbname",
    user="your_dbuser",
    password="your_dbpassword",
    host="localhost",
    port="5432"
)
cursor = conn.cursor()

# Create tables if not exist
cursor.execute('''CREATE TABLE IF NOT EXISTS trades (
                    trade_id INTEGER PRIMARY KEY,
                    buyer_id INTEGER,
                    seller_id INTEGER,
                    crypto TEXT,
                    amount REAL,
                    status TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS transactions (
                    trade_id INTEGER,
                    user_id INTEGER,
                    action TEXT,
                    timestamp TEXT)''')
conn.commit()

# Start command
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    item1 = types.KeyboardButton("Buy Cryptocurrency")
    item2 = types.KeyboardButton("Sell Cryptocurrency")
    markup.add(item1, item2)
    bot.send_message(message.chat.id, "Welcome to the Decentralized P2P Crypto Exchange! Choose your action:", reply_markup=markup)

# Handle buy/sell actions
@bot.message_handler(func=lambda message: message.text in ["Buy Cryptocurrency", "Sell Cryptocurrency"])
def handle_buy_sell(message):
    action = message.text
    markup = types.InlineKeyboardMarkup()
    item1 = types.InlineKeyboardButton("Bitcoin (BTC)", callback_data=f"{action.lower()}_btc")
    item2 = types.InlineKeyboardButton("Ethereum (ETH)", callback_data=f"{action.lower()}_eth")
    item3 = types.InlineKeyboardButton("Solana (SOL)", callback_data=f"{action.lower()}_sol")
    markup.add(item1, item2, item3)
    bot.send_message(message.chat.id, f"Choose the cryptocurrency you want to {action.lower()}:", reply_markup=markup)

# Handle buy/sell crypto
@bot.callback_query_handler(func=lambda call: call.data.startswith('buy') or call.data.startswith('sell'))
def buy_sell_crypto(call):
    action, crypto = call.data.split('_')
    action = "Buy" if action == "buy" else "Sell"
    
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, f"You selected {action} {crypto.upper()}. Please enter the amount.")
    bot.register_next_step_handler(call.message, process_trade, action, crypto)

# Process trade
def process_trade(message, action, crypto):
    try:
        amount = float(message.text)
        if amount <= 0:
            bot.send_message(message.chat.id, "Amount must be greater than 0. Please enter a valid amount.")
            return
        
        trade_id = random.randint(1000, 9999)
        
        # Store trade in database
        cursor.execute("INSERT INTO trades (trade_id, buyer_id, crypto, amount, status) VALUES (%s, %s, %s, %s, %s)", 
                       (trade_id, message.chat.id, crypto, amount, "pending"))
        conn.commit()

        # Log transaction
        cursor.execute("INSERT INTO transactions (trade_id, user_id, action, timestamp) VALUES (%s, %s, %s, %s)", 
                       (trade_id, message.chat.id, f"{action} initiated", time.strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()

        bot.send_message(message.chat.id, f"Trade created! Trade ID: {trade_id}. Awaiting confirmation.")
        bot.send_message(ADMIN_ID, f"New trade initiated: {crypto.upper()} for {amount} by user {message.chat.id}. Trade ID: {trade_id}")
    except ValueError:
        bot.send_message(message.chat.id, "Invalid amount. Please enter a valid number.")

# Admin Panel: View all trades
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.chat.id == ADMIN_ID:
        cursor.execute("SELECT * FROM trades WHERE status = 'pending'")
        trades = cursor.fetchall()
        if trades:
            trade_info = "\n".join([f"Trade ID: {trade[0]}, Crypto: {trade[3]}, Amount: {trade[4]}, Buyer: {trade[1]}" for trade in trades])
            bot.send_message(message.chat.id, f"Active Trades:\n{trade_info}")
        else:
            bot.send_message(message.chat.id, "No active trades.")
    else:
        bot.send_message(message.chat.id, "You do not have admin access.")

# Confirm trade and release funds
@bot.message_handler(commands=['confirm_trade'])
def confirm_trade(message):
    if message.chat.id == ADMIN_ID:
        bot.send_message(message.chat.id, "Enter the trade ID to confirm the transaction:")
        bot.register_next_step_handler(message, confirm_trade_process)
    else:
        bot.send_message(message.chat.id, "You do not have admin access to confirm trades.")

def confirm_trade_process(message):
    try:
        trade_id = int(message.text)
        # Simulate blockchain transaction confirmation and escrow release
        bot.send_message(message.chat.id, f"Trade ID {trade_id} confirmed. Funds will be released.")
        # Release funds logic with smart contract
        txn_hash = confirm_escrow(trade_id)
        bot.send_message(message.chat.id, f"Transaction completed! TX Hash: {txn_hash}")
    except ValueError:
        bot.send_message(message.chat.id, "Invalid Trade ID.")

# Blockchain Integration - Confirm the trade on the contract
def confirm_escrow(trade_id):
    # Assume buyer and seller have been confirmed in the database (implementation needed)
    buyer_private_key = "YOUR_BUYER_PRIVATE_KEY"
    buyer_address = Web3.toChecksumAddress("BUYER_ADDRESS")
    amount_in_wei = Web3.toWei(1, 'ether')  # Example amount (1 ETH)
    
    # Create transaction to call the smart contract's confirmBuyer() or confirmSeller() function
    transaction = contract.functions.confirmBuyer().buildTransaction({
        'from': buyer_address,
        'gas': 2000000,
        'gasPrice': w3.toWei('20', 'gwei'),
        'nonce': w3.eth.getTransactionCount(buyer_address),
    })

    # Sign the transaction
    signed_txn = w3.eth.account.signTransaction(transaction, buyer_private_key)

    # Send the transaction
    txn_hash = w3.eth.sendRawTransaction(signed_txn.rawTransaction)
    return txn_hash.hex()

# Start the bot
bot.polling()
