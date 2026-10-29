from datetime import datetime

from bank_database import BankDatabase


# ----------- BANK ACCOUNT -----------
class BankAccount:
    def __init__(
        self,
        account_holder,
        account_number,
        pin,
        balance=0,
        database=None,
        transactions=None,
        record_opening=True,
    ):
        self.account_holder = account_holder
        self.account_number = str(account_number)

        # Encapsulated attributes
        self.__pin = str(pin)
        self.__balance = balance
        self.__database = database
        self.__transactions = list(transactions) if transactions is not None else []

        if record_opening:
            self.__record_transaction(f"Account opened with Ksh {balance}")

    def __record_transaction(self, description):
        time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        transaction = f"{time} | {description}"
        self.__transactions.append(transaction)

        if self.__database is not None:
            self.__database.save_transaction(self.account_number, description)

    def __save_account(self):
        if self.__database is not None:
            self.__database.save_account(
                self.account_number,
                self.account_holder,
                self.__pin,
                self.__balance,
            )

    @property
    def balance(self):
        return self.__balance

    def verify_pin(self, pin):
        return self.__pin == pin

    def deposit(self, amount):
        if not isinstance(amount, int) or isinstance(amount, bool):
            print("Enter a whole-number amount in Ksh.")
            return False
        if amount <= 0:
            print("Deposit amount must be greater than zero.")
            return False

        self.__balance += amount
        self.__save_account()
        self.__record_transaction(f"Deposited Ksh {amount}")

        print(f"Successfully deposited Ksh {amount:,}.")
        print(f"New balance: Ksh {self.__balance:,}")
        return True

    def withdraw(self, amount):
        if not isinstance(amount, int) or isinstance(amount, bool):
            print("Enter a whole-number amount in Ksh.")
            return False
        if amount <= 0:
            print("Withdrawal amount must be greater than zero.")
            return False
        if amount > self.__balance:
            print("Insufficient funds.")
            return False

        self.__balance -= amount
        self.__save_account()
        self.__record_transaction(f"Withdrew Ksh {amount}")

        print(f"Successfully withdrew Ksh {amount:,}.")
        print(f"Remaining balance: Ksh {self.__balance:,}.")
        return True

    def transfer_to(self, recipient, amount):
        if not isinstance(amount, int) or isinstance(amount, bool):
            print("Enter a whole-number amount in Ksh.")
            return False
        if not isinstance(recipient, BankAccount):
            print("Invalid recipient account.")
            return False
        if recipient is self:
            print("You cannot transfer money to the same account.")
            return False
        if amount <= 0:
            print("Transfer amount must be greater than zero.")
            return False
        if amount > self.__balance:
            print("Insufficient funds for this transfer.")
            return False

        self.__balance -= amount
        recipient.__balance += amount
        self.__save_account()
        recipient.__save_account()

        self.__record_transaction(
            f"Transferred Ksh {amount} to account {recipient.account_number}"
        )
        recipient.__record_transaction(
            f"Received Ksh {amount} from account {self.account_number}"
        )

        print("Transfer successful.")
        print(f"Recipient: {recipient.account_holder}")
        print(f"Your new balance: Ksh {self.__balance:,}")
        return True

    def change_pin(self, old_pin, new_pin):
        if not self.verify_pin(old_pin):
            print("Incorrect current PIN.")
            return False
        if not (
            isinstance(new_pin, str)
            and len(new_pin) == 4
            and new_pin.isdigit()
        ):
            print("The new PIN must contain exactly four digits.")
            return False
        if new_pin == old_pin:
            print("The new PIN must be different from the old PIN.")
            return False

        self.__pin = new_pin
        self.__save_account()
        self.__record_transaction("Account PIN changed.")
        print("PIN changed successfully.")
        return True

    def display_details(self):
        print("\n--- ACCOUNT DETAILS ---")
        print(f"Account holder: {self.account_holder}")
        print(f"Account number: {self.account_number}")
        print("Account type: Savings")
        print(f"Current balance: Ksh {self.__balance:,}")

    def show_transactions(self):
        print("\n--- TRANSACTION HISTORY ---")
        if not self.__transactions:
            print("No transactions available.")
            return
        for transaction in self.__transactions:
            print(transaction)


# ----------- BANK MANAGEMENT CLASS -----------
class BankSystem:
    def __init__(self, database_path=None):
        # Keeping database_path=None allows existing tests to use a clean,
        # in-memory system. The real application passes "bank_data.db".
        self.database = BankDatabase(database_path) if database_path else None
        self.accounts = {}
        self.next_account_number = 1001

        if self.database is not None:
            self.__load_saved_accounts()

    def __load_saved_accounts(self):
        rows = self.database.load_accounts()
        for account_number, name, pin, balance in rows:
            saved_rows = self.database.load_transactions(account_number)
            transactions = [
                f"{created_at} | {description}"
                for description, created_at in saved_rows
            ]
            self.accounts[account_number] = BankAccount(
                account_holder=name,
                account_number=account_number,
                pin=pin,
                balance=balance,
                database=self.database,
                transactions=transactions,
                record_opening=False,
            )

        if self.accounts:
            self.next_account_number = max(
                int(number) for number in self.accounts
            ) + 1

    def create_account(self):
        print("\n--- CREATE A BANK ACCOUNT ---")
        name = input("Enter account holder's name: ").strip()
        if not name:
            print("Name cannot be empty.")
            return

        pin = input("Create a four-digit PIN: ")
        if len(pin) != 4 or not pin.isdigit():
            print("PIN must contain exactly four digits.")
            return

        confirm_pin = input("Confirm your PIN: ")
        if pin != confirm_pin:
            print("PINs do not match.")
            return

        account_number = str(self.next_account_number)

        # Save the account first so the opening transaction satisfies the
        # database foreign-key constraint.
        if self.database is not None:
            self.database.save_account(account_number, name, pin, 0)

        account = BankAccount(
            account_holder=name,
            account_number=account_number,
            pin=pin,
            balance=0,
            database=self.database,
        )
        self.accounts[account_number] = account
        self.next_account_number += 1

        print("\nAccount created successfully!")
        print(f"Account holder: {name}")
        print(f"Account number: {account_number}")
        print("Opening balance: Ksh 0")
        print("Keep your account number safe.")

    def login(self):
        print("\n--- ACCOUNT LOGIN ---")
        account_number = input("Enter account number: ").strip()
        pin = input("Enter your four-digit PIN: ")
        account = self.accounts.get(account_number)

        if account is None or not account.verify_pin(pin):
            print("Invalid account number or PIN.")
            return

        print(f"\nWelcome, {account.account_holder}!")
        self.account_menu(account)

    def account_menu(self, account):
        while True:
            print("\n-------- ACCOUNT MENU --------")
            print("1. View account details")
            print("2. Check balance")
            print("3. Deposit money")
            print("4. Withdraw money")
            print("5. Transfer money")
            print("6. View transaction history")
            print("7. Change PIN")
            print("8. Logout")

            choice = input("Choose an option (1-8): ").strip()

            if choice == "1":
                account.display_details()
            elif choice == "2":
                print(f"Available balance: Ksh {account.balance:,}")
            elif choice == "3":
                amount = self.get_amount("Enter deposit amount: ")
                if amount is not None:
                    account.deposit(amount)
            elif choice == "4":
                amount = self.get_amount("Enter withdrawal amount: ")
                if amount is not None:
                    account.withdraw(amount)
            elif choice == "5":
                recipient_number = input(
                    "Enter recipient's account number: "
                ).strip()
                recipient = self.accounts.get(recipient_number)
                if recipient is None:
                    print("Recipient not found.")
                    continue
                amount = self.get_amount("Enter transfer amount: ")
                if amount is not None:
                    account.transfer_to(recipient, amount)
            elif choice == "6":
                account.show_transactions()
            elif choice == "7":
                old_pin = input("Enter the current PIN: ")
                new_pin = input("Enter new four-digit PIN: ")
                account.change_pin(old_pin, new_pin)
            elif choice == "8":
                print("You have logged out successfully.")
                break
            else:
                print("Invalid option. Choose a number from 1 to 8.")

    @staticmethod
    def get_amount(prompt):
        value = input(prompt).strip()
        try:
            amount = int(value)
            if amount <= 0:
                print("Amount must be greater than zero.")
                return None
            return amount
        except ValueError:
            print("Invalid amount. Enter a whole number, e.g. 5000.")
            return None

    def run(self):
        while True:
            print("\n--- BANKING SYSTEM ---")
            print("1. Create account")
            print("2. Login to account")
            print("3. Exit")
            choice = input("Choose an option (1, 2, or 3): ").strip()

            if choice == "1":
                self.create_account()
            elif choice == "2":
                self.login()
            elif choice == "3":
                print("Thank you for using our banking system.")
                break
            else:
                print("Invalid option. Choose 1, 2, or 3.")


if __name__ == "__main__":
    bank = BankSystem(database_path="bank_data.db")
    bank.run()
