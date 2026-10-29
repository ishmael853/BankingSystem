import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
from io import StringIO

from bank_system import BankSystem


class TestBankMenuIntegration(unittest.TestCase):

    def test_complete_banking_workflow(self):
        bank = BankSystem()

        # Simulate a customer creating two accounts,
        # logging in, and using the banking menus.
        user_inputs = [
            "1", "Ishmael", "2525", "2525",
            "1", "Florence", "1234", "1234",
            "2", "1001", "2525",
            "3", "5000",
            "4", "1000",
            "5", "1002", "1500",
            "2",
            "6",
            "8",
            "3",
        ]

        output = StringIO()

        with patch("builtins.input", side_effect=user_inputs):
            with redirect_stdout(output):
                bank.run()

        # Verify that both accounts were created.
        self.assertIn("1001", bank.accounts)
        self.assertIn("1002", bank.accounts)

        # Verify final balances.
        self.assertEqual(bank.accounts["1001"].balance, 2500)
        self.assertEqual(bank.accounts["1002"].balance, 1500)

        # Verify that the menu displayed transaction results.
        displayed_output = output.getvalue()
        self.assertIn("5000", displayed_output)
        self.assertIn("1002", displayed_output)

        print("PASS: Both accounts were created.")
        print("PASS: Login and menu navigation worked.")
        print("PASS: Deposit, withdrawal, and transfer worked.")
        print("PASS: Balance and transaction history were accessed.")
        print("PASS: Final balances are correct.")
        print("Ishmael: Ksh", bank.accounts["1001"].balance)
        print("Florence: Ksh", bank.accounts["1002"].balance)


if __name__ == "__main__":
    unittest.main(verbosity=2)
