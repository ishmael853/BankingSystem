import csv
import hashlib
import hmac
import os
import sqlite3
import time
import sys
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget, QInputDialog, QFileDialog
)

DB_DIR = Path.home() / "AppData" / "Local" / "BankingSystem"
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "bank_data.db"
HASH_PREFIX = "pbkdf2_sha256$"


def hash_pin(pin: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, 250_000)
    return HASH_PREFIX + salt.hex() + "$" + digest.hex()


def verify_pin(pin: str, stored: str) -> bool:
    # Accept legacy plaintext PINs once, then upgrade them to a hash on login.
    if not stored.startswith(HASH_PREFIX):
        return hmac.compare_digest(pin, stored)
    try:
        _, salt_hex, digest_hex = stored.split("$", 2)
        digest = hashlib.pbkdf2_hmac(
            "sha256", pin.encode("utf-8"), bytes.fromhex(salt_hex), 250_000
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


class BankStore:
    def __init__(self, path=DB_PATH):
        self.path = str(path)
        self.setup()
        self.create_backup()


    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def setup(self):
        with self.connect() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    account_number TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    pin TEXT NOT NULL,
                    balance INTEGER NOT NULL CHECK(balance >= 0)
                )
            """)
            con.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_number TEXT NOT NULL,
                    description TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(account_number) REFERENCES accounts(account_number)
                    ON DELETE CASCADE
                )
            """)
            con.execute("""
                CREATE TABLE IF NOT EXISTS login_attempts (
                    account_number TEXT PRIMARY KEY,
                    failed_attempts INTEGER NOT NULL DEFAULT 0,
                    locked_until REAL NOT NULL DEFAULT 0,
                    FOREIGN KEY(account_number) REFERENCES accounts(account_number)
                    ON DELETE CASCADE
                )
            """)
            # Upgrade any legacy plaintext PINs in the existing database.
            rows = con.execute("SELECT account_number, pin FROM accounts").fetchall()
            for account_number, pin in rows:
                if not pin.startswith(HASH_PREFIX):
                    con.execute(
                        "UPDATE accounts SET pin=? WHERE account_number=?",
                        (hash_pin(pin), account_number),
                    )

    def create_account(self, name, pin):
        with self.connect() as con:
            row = con.execute(
                "SELECT MAX(CAST(account_number AS INTEGER)) FROM accounts"
            ).fetchone()
            number = str(max(1000, row[0] or 1000) + 1)
            con.execute(
                "INSERT INTO accounts(account_number,name,pin,balance) VALUES(?,?,?,0)",
                (number, name, hash_pin(pin)),
            )
            con.execute(
                "INSERT INTO transactions(account_number,description) VALUES(?,?)",
                (number, "Account opened with Ksh 0"),
            )
        return number

    def authenticate(self, number, pin):
        with self.connect() as con:
            row = con.execute(
                "SELECT name,pin FROM accounts WHERE account_number=?", (number,)
            ).fetchone()
            if not row or not verify_pin(pin, row[1]):
                return None
            # Migrate plaintext PINs if any survived or were inserted externally.
            if not row[1].startswith(HASH_PREFIX):
                con.execute(
                    "UPDATE accounts SET pin=? WHERE account_number=?",
                    (hash_pin(pin), number),
                )
            return row[0]

    def create_backup(self):
        """Create a timestamped SQLite backup and keep the latest ten."""
        import sqlite3
        import time
        from pathlib import Path

        database = Path(self.path)
        if not database.is_file():
            print("Backup skipped: database file does not exist.")
            return None

        backup_dir = database.parent / "backups"
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"bank_data_{timestamp}.db"

            # Avoid overwriting a backup if two starts occur in the same second.
            if backup_path.exists():
                timestamp = time.strftime("%Y%m%d_%H%M%S") + f"_{time.time_ns()}"
                backup_path = backup_dir / f"bank_data_{timestamp}.db"

            src = sqlite3.connect(str(database))
            dst = sqlite3.connect(str(backup_path))
            try:
                src.backup(dst)
            finally:
                dst.close()
                src.close()

            # Keep the ten newest backups; never delete the live database.
            backups = sorted(
                backup_dir.glob("bank_data_*.db"),
                key=lambda item: item.stat().st_mtime,
                reverse=True,
            )
            for old_backup in backups[10:]:
                old_backup.unlink()

            print(f"Database backup created: {backup_path}")
            return str(backup_path)

        except (OSError, sqlite3.Error) as exc:
            print(f"WARNING: Database backup failed: {exc}")
            return None

    def login_lock_remaining(self, number):
        """Return remaining lockout seconds, or zero if the account is unlocked."""
        with self.connect() as con:
            row = con.execute(
                "SELECT locked_until FROM login_attempts WHERE account_number=?",
                (number,),
            ).fetchone()

            if row is None:
                return 0

            remaining = row[0] - time.time()
            if remaining <= 0:
                con.execute(
                    "DELETE FROM login_attempts WHERE account_number=?",
                    (number,),
                )
                return 0

            return int(remaining) + 1

    def record_failed_login(self, number):
        """Count a failed login for an existing account; lock it after five failures."""
        with self.connect() as con:
            exists = con.execute(
                "SELECT 1 FROM accounts WHERE account_number=?", (number,)
            ).fetchone()

            # Do not create lockout records for nonexistent account numbers.
            if exists is None:
                return 0, 0

            row = con.execute(
                "SELECT failed_attempts, locked_until FROM login_attempts "
                "WHERE account_number=?",
                (number,),
            ).fetchone()

            now = time.time()
            attempts = row[0] if row else 0
            locked_until = row[1] if row else 0

            if locked_until > now:
                return attempts, int(locked_until - now) + 1

            attempts += 1
            new_lock = now + 300 if attempts >= 5 else 0

            con.execute(
                """
                INSERT INTO login_attempts(account_number, failed_attempts, locked_until)
                VALUES(?, ?, ?)
                ON CONFLICT(account_number) DO UPDATE SET
                    failed_attempts=excluded.failed_attempts,
                    locked_until=excluded.locked_until
                """,
                (number, attempts, new_lock),
            )

            return attempts, max(0, int(new_lock - now) + 1)

    def clear_failed_logins(self, number):
        """Reset the failed-login counter after successful authentication."""
        with self.connect() as con:
            con.execute(
                "DELETE FROM login_attempts WHERE account_number=?", (number,)
            )

    def account(self, number):
        with self.connect() as con:
            return con.execute(
                "SELECT account_number,name,balance FROM accounts WHERE account_number=?",
                (number,),
            ).fetchone()

    def balance(self, number):
        row = self.account(number)
        return row[2] if row else None

    def transact(self, number, kind, amount, recipient=None):
        if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
            raise ValueError("Enter a whole-number amount greater than zero.")
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute(
                "SELECT balance FROM accounts WHERE account_number=?", (number,)
            ).fetchone()
            if not row:
                raise ValueError("Account not found.")
            if kind in ("Withdrawal", "Transfer") and row[0] < amount:
                raise ValueError("Insufficient funds.")
            if kind == "Transfer":
                if recipient == number:
                    raise ValueError("You cannot transfer money to the same account.")
                other = con.execute(
                    "SELECT balance FROM accounts WHERE account_number=?", (recipient,)
                ).fetchone()
                if not other:
                    raise ValueError("Recipient account not found.")
                con.execute("UPDATE accounts SET balance=balance-? WHERE account_number=?",
                            (amount, number))
                con.execute("UPDATE accounts SET balance=balance+? WHERE account_number=?",
                            (amount, recipient))
                con.execute("INSERT INTO transactions(account_number,description) VALUES(?,?)",
                            (number, f"Transferred Ksh {amount} to account {recipient}"))
                con.execute("INSERT INTO transactions(account_number,description) VALUES(?,?)",
                            (recipient, f"Received Ksh {amount} from account {number}"))
            elif kind == "Deposit":
                con.execute("UPDATE accounts SET balance=balance+? WHERE account_number=?",
                            (amount, number))
                con.execute("INSERT INTO transactions(account_number,description) VALUES(?,?)",
                            (number, f"Deposited Ksh {amount}"))
            elif kind == "Withdrawal":
                con.execute("UPDATE accounts SET balance=balance-? WHERE account_number=?",
                            (amount, number))
                con.execute("INSERT INTO transactions(account_number,description) VALUES(?,?)",
                            (number, f"Withdrew Ksh {amount}"))

    def change_pin(self, number, old_pin, new_pin):
        if len(new_pin) != 4 or not new_pin.isdigit():
            raise ValueError("PIN must contain exactly four digits.")
        with self.connect() as con:
            row = con.execute("SELECT pin FROM accounts WHERE account_number=?",
                              (number,)).fetchone()
            if not row or not verify_pin(old_pin, row[0]):
                raise ValueError("Incorrect current PIN.")
            if old_pin == new_pin:
                raise ValueError("The new PIN must differ from the old PIN.")
            con.execute("UPDATE accounts SET pin=? WHERE account_number=?",
                        (hash_pin(new_pin), number))
            con.execute("INSERT INTO transactions(account_number,description) VALUES(?,?)",
                        (number, "Account PIN changed."))

    def history(self, number):
        with self.connect() as con:
            return con.execute(
                "SELECT created_at,description FROM transactions "
                "WHERE account_number=? ORDER BY id", (number,)
            ).fetchall()

    def export_statement(self, number, destination):
        account = self.account(number)
        history = self.history(number)
        with open(destination, "w", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file)
            writer.writerow(["Account Statement"])
            writer.writerow(["Account number", account[0]])
            writer.writerow(["Account holder", account[1]])
            writer.writerow(["Current balance (Ksh)", account[2]])
            writer.writerow([])
            writer.writerow(["Date and time", "Transaction"])
            writer.writerows(history)


class CreateAccountDialog(QDialog):
    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("Create bank account")
        self.setMinimumWidth(360)
        layout = QFormLayout(self)
        self.name = QLineEdit()
        self.pin = QLineEdit()
        self.pin.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm = QLineEdit()
        self.confirm.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("Account holder:", self.name)
        layout.addRow("Four-digit PIN:", self.pin)
        layout.addRow("Confirm PIN:", self.confirm)
        create = QPushButton("Create account")
        create.clicked.connect(self.create)
        layout.addRow(create)

    def create(self):
        name = self.name.text().strip()
        pin = self.pin.text()
        if not name:
            QMessageBox.warning(self, "Invalid name", "Enter the account holder's name.")
            return
        if len(pin) != 4 or not pin.isdigit():
            QMessageBox.warning(self, "Invalid PIN", "PIN must contain exactly four digits.")
            return
        if pin != self.confirm.text():
            QMessageBox.warning(self, "PIN mismatch", "The PINs do not match.")
            return
        try:
            number = self.store.create_account(name, pin)
        except sqlite3.Error as exc:
            QMessageBox.critical(self, "Database error", str(exc))
            return
        QMessageBox.information(
            self, "Account created",
            f"Account created successfully.\nAccount holder: {name}\nAccount number: {number}\nOpening balance: Ksh 0\n\nKeep your account number safe."
        )
        self.accept()


class LoginDialog(QDialog):
    def __init__(self, store):
        super().__init__()
        self.store = store
        self.failed_attempts = 0
        self.account_number = None
        self.account_name = None
        self.setWindowTitle("Bank account login")
        self.setMinimumWidth(360)
        layout = QFormLayout(self)
        self.number = QLineEdit()
        self.pin = QLineEdit()
        self.pin.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("Account number:", self.number)
        layout.addRow("PIN:", self.pin)
        button = QPushButton("Log in")
        button.clicked.connect(self.login)
        layout.addRow(button)
        create_button = QPushButton("Create Account")
        create_button.clicked.connect(self.open_create_account)
        layout.addRow(create_button)


    def open_create_account(self):
        dialog = CreateAccountDialog(self.store, self)
        dialog.exec()

    def login(self):
        number = self.number.text().strip()
        pin = self.pin.text()

        if not number or not pin:
            QMessageBox.warning(
                self, "Missing details", "Enter your account number and PIN."
            )
            return

        remaining_seconds = self.store.login_lock_remaining(number)
        if remaining_seconds > 0:
            minutes = remaining_seconds // 60
            seconds = remaining_seconds % 60
            QMessageBox.critical(
                self,
                "Login temporarily blocked",
                f"This account is temporarily locked. Try again in "
                f"{minutes} minute(s) and {seconds} second(s)."
            )
            self.reject()
            return

        name = self.store.authenticate(number, pin)

        if name is None:
            self.failed_attempts += 1
            attempts, lock_seconds = self.store.record_failed_login(number)
            remaining = 5 - self.failed_attempts

            if lock_seconds > 0:
                QMessageBox.critical(
                    self,
                    "Login temporarily blocked",
                    "Five failed PIN attempts have been reached. "
                    "This account is locked for 5 minutes."
                )
                self.reject()
            elif remaining <= 0:
                QMessageBox.critical(
                    self,
                    "Login blocked",
                    "Too many failed attempts. The login window will close."
                )
                self.reject()
            else:
                QMessageBox.warning(
                    self,
                    "Login failed",
                    f"Invalid account number or PIN.\n"
                    f"Attempts remaining in this window: {remaining}"
                )
            return

        self.store.clear_failed_logins(number)
        self.account_number = number
        self.account_name = name
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self, store, account_number, account_name):
        super().__init__()
        self.store = store
        self.number = account_number
        self.name = account_name
        self.setWindowTitle("Python Banking System")
        self.resize(760, 520)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        heading = QLabel(f"Welcome, {self.name}  |  Account: {self.number}")
        heading.setStyleSheet("font-size: 18px; font-weight: 600; padding: 8px;")
        layout.addWidget(heading)

        self.balance_label = QLabel()
        self.balance_label.setStyleSheet("font-size: 22px; font-weight: 700; padding: 8px;")
        layout.addWidget(self.balance_label)

        actions = QHBoxLayout()
        for text, callback in [
            ("Deposit", self.deposit),
            ("Withdraw", self.withdraw),
            ("Transfer", self.transfer),
            ("Change PIN", self.change_pin),
            ("Refresh", self.refresh),
            ("Export statement", self.export_statement),
        ]:
            button = QPushButton(text)
            button.clicked.connect(callback)
            actions.addWidget(button)
        layout.addLayout(actions)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Date and time", "Transaction"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(QLabel("Transaction history"))
        layout.addWidget(self.table)

        self.statusBar().showMessage("Account data is stored locally in SQLite.")
        self.refresh()

    def amount_prompt(self, title):
        amount, ok = QInputDialog.getInt(
            self, title, "Amount in Ksh:", 500, 1, 2_000_000_000, 1
        )
        return amount if ok else None

    def deposit(self):
        amount = self.amount_prompt("Deposit")
        if amount is not None:
            self.do_transaction("Deposit", amount)

    def withdraw(self):
        amount = self.amount_prompt("Withdrawal")
        if amount is not None:
            self.do_transaction("Withdrawal", amount)

    def transfer(self):
        recipient, ok = QInputDialog.getText(
            self, "Transfer", "Recipient account number:"
        )
        if not ok:
            return
        amount = self.amount_prompt("Transfer")
        if amount is not None:
            self.do_transaction("Transfer", amount, recipient.strip())

    def do_transaction(self, kind, amount, recipient=None):
        try:
            self.store.transact(self.number, kind, amount, recipient)
            QMessageBox.information(self, "Success", f"{kind} completed successfully.")
            self.refresh()
        except (ValueError, sqlite3.Error) as exc:
            QMessageBox.warning(self, "Transaction failed", str(exc))

    def change_pin(self):
        old_pin, ok = QInputDialog.getText(
            self, "Change PIN", "Current PIN:", QLineEdit.EchoMode.Password
        )
        if not ok:
            return
        new_pin, ok = QInputDialog.getText(
            self, "Change PIN", "New four-digit PIN:", QLineEdit.EchoMode.Password
        )
        if not ok:
            return
        try:
            self.store.change_pin(self.number, old_pin, new_pin)
            QMessageBox.information(self, "PIN changed", "Your PIN was changed successfully.")
            self.refresh()
        except (ValueError, sqlite3.Error) as exc:
            QMessageBox.warning(self, "Could not change PIN", str(exc))

    def refresh(self):
        account = self.store.account(self.number)
        if not account:
            QMessageBox.critical(self, "Account missing", "This account no longer exists.")
            self.close()
            return
        self.balance_label.setText(f"Available balance: Ksh {account[2]:,}")
        rows = self.store.history(self.number)
        self.table.setRowCount(len(rows))
        for row_index, (created_at, description) in enumerate(rows):
            self.table.setItem(row_index, 0, QTableWidgetItem(created_at))
            self.table.setItem(row_index, 1, QTableWidgetItem(description))
        self.table.resizeColumnsToContents()

    def export_statement(self):
        suggested = f"statement_{self.number}.csv"
        destination, _ = QFileDialog.getSaveFileName(
            self, "Save account statement", suggested, "CSV files (*.csv)"
        )
        if not destination:
            return
        try:
            self.store.export_statement(self.number, destination)
            QMessageBox.information(self, "Statement saved", f"Statement saved to:\n{destination}")
        except (OSError, sqlite3.Error) as exc:
            QMessageBox.critical(self, "Export failed", str(exc))


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    store = BankStore()
    login = LoginDialog(store)
    login.setModal(True)
    if login.exec() != QDialog.DialogCode.Accepted:
        return 0
    window = MainWindow(store, login.account_number, login.account_name)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

