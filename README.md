# BankingSystem

A desktop banking application built with Python, PyQt6, and SQLite. The system provides account management, secure PIN verification, financial transactions, and transaction history through a graphical user interface.

## Features

- **Account Management:** Create and access bank accounts.
- **Secure PIN Handling:** PIN hashing and verification.
- **Deposits and Withdrawals:** Manage account balances.
- **Money Transfers:** Transfer funds between accounts.
- **Transaction History:** Review account transactions.
- **Statement Export:** Export transaction statements to CSV.
- **Login Protection:** Temporary lockout after repeated failed login attempts.
- **Data Persistence:** Store account and transaction data in SQLite.
- **Database Backups:** Create backups to help protect stored data.
- **Automated Tests:** Test important banking operations.

## Technologies Used

- Python
- PyQt6
- SQLite
- PyInstaller
- Git and GitHub

## Requirements

- Python 3.14 or a compatible Python version
- PyQt6

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/ishmael853/BankingSystem.git
   ```

2. Enter the project directory:

   ```bash
   cd BankingSystem
   ```

3. Install PyQt6:

   ```bash
   python -m pip install PyQt6
   ```

## Running the Application

Launch the graphical application:

```bash
python bank_gui.py
```

## Running Tests

Run the banking system tests:

```bash
python -m unittest test_bank_system.py test_bank_menu.py
```

## Project Structure

```text
BankingSystem/
├── bank_gui.py
├── bank_system.py
├── bank_database.py
├── test_bank_system.py
├── test_bank_menu.py
├── .gitignore
└── README.md
```

## Security Notes

- Keep database files, account records, and backups private.
- Never publish real account details, PINs, passwords, or other sensitive information.
- Use test accounts and sample data when demonstrating the application.
- Review the database and authentication implementation before using the system for real financial transactions.

## Future Improvements

- Improved reporting and analytics.
- Additional account security controls.
- Enhanced interface accessibility.
- More automated tests and error handling.

## Author

Developed as a Python desktop banking system project.
<!-- https://github.com/ishmael853 -->

## License

No license has been specified yet. All rights are reserved unless a license is added to this repository.
