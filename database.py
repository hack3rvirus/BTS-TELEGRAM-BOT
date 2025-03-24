# database.py
import mysql.connector
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_db_connection():
    host = os.getenv("DB_HOST") or "mysql.railway.internal"
    port = int(os.getenv("DB_PORT", 3306))
    user = os.getenv("DB_USER") or "root"
    password = os.getenv("DB_PASSWORD") or "qItgFGuqsyxICAvhiBitaijtiQZuujAD"
    database = os.getenv("DB_NAME") or "railway"
    print(f"DB_HOST: {host}")
    print(f"DB_PORT: {port}")
    print(f"DB_USER: {user}")
    print(f"DB_PASSWORD: {password}")
    print(f"DB_NAME: {database}")
    return mysql.connector.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database
    )
def setup_database():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Create users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id BIGINT PRIMARY KEY,
            username VARCHAR(255),
            chat_id BIGINT
        )
    """)
    # Create interactions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS interactions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            telegram_id BIGINT,
            message TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
        )
    """)
    # Create subscriptions table with payment_confirmed column
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            telegram_id BIGINT PRIMARY KEY,
            start_date DATE,
            end_date DATE,
            payment_confirmed BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
        )
    """)
    conn.commit()
    cursor.close()
    conn.close()

def save_user(telegram_id, username, chat_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (telegram_id, username, chat_id)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE username = %s, chat_id = %s
    """, (telegram_id, username, chat_id, username, chat_id))
    conn.commit()
    cursor.close()
    conn.close()

def user_exists(telegram_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_id FROM users WHERE telegram_id = %s", (telegram_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result is not None

def log_interaction(telegram_id, message):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO interactions (telegram_id, message) VALUES (%s, %s)", (telegram_id, message))
    conn.commit()
    cursor.close()
    conn.close()

def get_all_users():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT telegram_id, username, chat_id FROM users")
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    return users

def save_subscription(telegram_id, start_date, end_date):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO subscriptions (telegram_id, start_date, end_date, payment_confirmed)
        VALUES (%s, %s, %s, FALSE)
        ON DUPLICATE KEY UPDATE start_date = %s, end_date = %s, payment_confirmed = FALSE
    """, (telegram_id, start_date, end_date, start_date, end_date))
    conn.commit()
    cursor.close()
    conn.close()

def confirm_payment(telegram_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE subscriptions SET payment_confirmed = TRUE WHERE telegram_id = %s", (telegram_id,))
    conn.commit()
    cursor.close()
    conn.close()

def has_paid(telegram_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT payment_confirmed FROM subscriptions WHERE telegram_id = %s", (telegram_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result and result['payment_confirmed']

def get_subscriptions():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT telegram_id, start_date, end_date, payment_confirmed FROM subscriptions")
    subscriptions = cursor.fetchall()
    cursor.close()
    conn.close()
    return subscriptions

def get_pending_payments():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT s.telegram_id, u.username
        FROM subscriptions s
        JOIN users u ON s.telegram_id = u.telegram_id
        WHERE s.payment_confirmed = FALSE
    """)
    pending = cursor.fetchall()
    cursor.close()
    conn.close()
    return pending

def test_connection():
    try:
        conn = get_db_connection()
        print("Database connection successful!")
        conn.close()
    except Exception as e:
        print(f"Database connection failed: {e}")

if __name__ == "__main__":
    setup_database()
    test_connection()