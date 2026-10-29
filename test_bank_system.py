
import unittest
from unittest.mock import patch
from bank_system import BankAccount, BankSystem


class TestBankingSystem(unittest.TestCase):

    def setUp(self):
        self.bank = BankSystem()
        self.account1 = BankAccount("Ishmael", "1001", "2525", 5000)
        self.account2 = BankAccount("Florence", "1002", "1234", 1000)

        self.bank.accounts["1001"] = self.account1
        self.bank.accounts["1002"] = self.account2

    def test_account_creation(self):
        self.assertEqual(self.account1.account_holder, "Ishmael")
        self.assertEqual(self.account1.account_number, "1001")
        self.assertEqual(self.account1.balance, 5000)

    def test_correct_pin(self):
        self.assertTrue(self.account1.verify_pin("2525"))

    def test_incorrect_pin(self):
        self.assertFalse(self.account1.verify_pin("1111"))

    def test_successful_deposit(self):
        self.assertTrue(self.account1.deposit(500))
        self.assertEqual(self.account1.balance, 5500)

    def test_zero_deposit(self):
        self.assertFalse(self.account1.deposit(0))
        self.assertEqual(self.account1.balance, 5000)

    def test_negative_deposit(self):
        self.assertFalse(self.account1.deposit(-100))
        self.assertEqual(self.account1.balance, 5000)

    def test_invalid_deposit_type(self):
        self.assertFalse(self.account1.deposit("abc"))
        self.assertEqual(self.account1.balance, 5000)

    def test_successful_withdrawal(self):
        self.assertTrue(self.account1.withdraw(1000))
        self.assertEqual(self.account1.balance, 4000)

    def test_insufficient_funds(self):
        self.assertFalse(self.account1.withdraw(6000))
        self.assertEqual(self.account1.balance, 5000)

    def test_zero_withdrawal(self):
        self.assertFalse(self.account1.withdraw(0))
        self.assertEqual(self.account1.balance, 5000)

    def test_negative_withdrawal(self):
        self.assertFalse(self.account1.withdraw(-100))
        self.assertEqual(self.account1.balance, 5000)

    def test_successful_transfer(self):
        self.assertTrue(self.account1.transfer_to(self.account2, 1500))
        self.assertEqual(self.account1.balance, 3500)
        self.assertEqual(self.account2.balance, 2500)

    def test_transfer_insufficient_funds(self):
        self.assertFalse(self.account1.transfer_to(self.account2, 6000))
        self.assertEqual(self.account1.balance, 5000)
        self.assertEqual(self.account2.balance, 1000)

    def test_transfer_to_self(self):
        self.assertFalse(self.account1.transfer_to(self.account1, 100))
        self.assertEqual(self.account1.balance, 5000)

    def test_invalid_transfer_amount(self):
        self.assertFalse(self.account1.transfer_to(self.account2, -100))
        self.assertEqual(self.account1.balance, 5000)
        self.assertEqual(self.account2.balance, 1000)

    def test_change_pin(self):
        self.assertTrue(self.account1.change_pin("2525", "6789"))
        self.assertTrue(self.account1.verify_pin("6789"))
        self.assertFalse(self.account1.verify_pin("2525"))

    def test_reject_wrong_old_pin(self):
        self.assertFalse(self.account1.change_pin("0000", "6789"))
        self.assertTrue(self.account1.verify_pin("2525"))

    def test_reject_invalid_new_pin(self):
        self.assertFalse(self.account1.change_pin("2525", "123"))
        self.assertTrue(self.account1.verify_pin("2525"))

    def test_transaction_history(self):
        self.account1.deposit(500)
        with patch("builtins.print") as mocked_print:
            self.account1.show_transactions()

        printed = "\n".join(
            str(call) for call in mocked_print.call_args_list
        )
        self.assertIn("Account opened", printed)
        self.assertIn("Deposited Ksh 500", printed)

    def test_account_lookup(self):
        self.assertIs(self.bank.accounts.get("1001"), self.account1)
        self.assertIsNone(self.bank.accounts.get("9999"))

    
    def test_boolean_deposit_rejected(self):
        self.assertFalse(self.account1.deposit(True))
        self.assertEqual(self.account1.balance, 5000)

    def test_boolean_withdrawal_rejected(self):
        self.assertFalse(self.account1.withdraw(True))
        self.assertEqual(self.account1.balance, 5000)

    def test_boolean_transfer_rejected(self):
        self.assertFalse(self.account1.transfer_to(self.account2, True))
        self.assertEqual(self.account1.balance, 5000)
        self.assertEqual(self.account2.balance, 1000)

    def test_empty_pin_rejected(self):
        self.assertFalse(self.account1.verify_pin(""))

    def test_wrong_pin_does_not_change_balance(self):
        balance_before = self.account1.balance

        self.assertFalse(self.account1.verify_pin("9999"))
        self.assertEqual(self.account1.balance, balance_before)

    def test_balance_is_read_only(self):
        with self.assertRaises(AttributeError):
            self.account1.balance = 1000000

    def test_failed_transfer_does_not_change_recipient_balance(self):
        sender_before = self.account1.balance
        recipient_before = self.account2.balance

        result = self.account1.transfer_to(self.account2, 10000)

        self.assertFalse(result)
        self.assertEqual(self.account1.balance, sender_before)
        self.assertEqual(self.account2.balance, recipient_before)

    def test_transfer_history_for_both_accounts(self):
        self.account1.transfer_to(self.account2, 500)

        with patch("builtins.print") as sender_print:
            self.account1.show_transactions()

        with patch("builtins.print") as recipient_print:
            self.account2.show_transactions()

        sender_history = str(sender_print.call_args_list)
        recipient_history = str(recipient_print.call_args_list)

        self.assertIn("Transferred Ksh 500", sender_history)
        self.assertIn("1002", sender_history)
        self.assertIn("Received Ksh 500", recipient_history)
        self.assertIn("1001", recipient_history)


if __name__ == "__main__":
    unittest.main(verbosity=2)
