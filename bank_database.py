import sqlite3
from pathlib import Path


class BankDatabase:
    """Handles persistent storage for the banking system."""

    def __init__(self, database_path="bank_data.db"):
        self.database_path = Path(database_path)
        self.create_tables()

    def connect(self):
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def create_tables(self):
        with self.connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    account_number TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    pin TEXT NOT NULL,
                    balance INTEGER NOT NULL CHECK (balance >= 0)
                )
            """)

            connection.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_number TEXT NOT NULL,
                    description TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (account_number)
                        REFERENCES accounts(account_number)
                        ON DELETE CASCADE
                )
            """)

    def save_account(self, account_number, name, pin, balance):
        with self.connect() as connection:
            connection.execute("""
                INSERT INTO accounts (
                    account_number, name, pin, balance
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(account_number) DO UPDATE SET
                    name = excluded.name,
                    pin = excluded.pin,
                    balance = excluded.balance
            """, (str(account_number), name, str(pin), int(balance)))

    def load_accounts(self):
        with self.connect() as connection:
            return connection.execute("""
                SELECT account_number, name, pin, balance
                FROM accounts
                ORDER BY CAST(account_number AS INTEGER)
            """).fetchall()

    def save_transaction(self, account_number, description):
        with self.connect() as connection:
            connection.execute("""
                INSERT INTO transactions (account_number, description)
                VALUES (?, ?)
            """, (str(account_number), description))

    def load_transactions(self, account_number):
        with self.connect() as connection:
            return connection.execute("""
                SELECT description, created_at
                FROM transactions
                WHERE account_number = ?
                ORDER BY id
            """, (str(account_number),)).fetchall()
