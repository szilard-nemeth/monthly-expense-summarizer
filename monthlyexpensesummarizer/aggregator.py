import logging
from typing import List, Dict

from monthlyexpensesummarizer.config import ItemType
from monthlyexpensesummarizer.parser import ParsedExpense
LOG = logging.getLogger(__name__)


class Aggregator:
    def __init__(self):
        self.by_payment_method: Dict[str, int] = {}
        self.by_payment_method_stringified: Dict[str, str] = {}
        self.by_day: Dict[str, int] = {}
        self.by_transaction_type: Dict[ItemType, int] = {}

    def aggregate(self, parsed_expenses: List[ParsedExpense]):
        for expense in parsed_expenses:
            key = expense.date
            if key not in self.by_day:
                self.by_day[key] = 0
            self.by_day[key] += expense.amount

            item_type = expense.item_type
            if item_type == ItemType.EXPENSE:
                key = expense.payment_method.display_name
                if key not in self.by_payment_method:
                    self.by_payment_method[key] = 0
                    self.by_payment_method_stringified[key] = ""
                self.by_payment_method[key] += expense.amount
                self.by_payment_method_stringified[key] += f"{expense.amount}+"

            key = item_type
            if key not in self.by_transaction_type:
                self.by_transaction_type[key] = 0
            self.by_transaction_type[key] += expense.amount

        LOG.info("Listing aggregates...")
        for payment_method, amount in self.by_payment_method.items():
            LOG.info("Aggregate expenses for payment method '%s': %d", payment_method, amount)
            LOG.info("Stringified aggregate expenses for payment method '%s': %s", payment_method, by_payment_method_stringified[payment_method])
        for day, amount in self.by_day.items():
            LOG.info("Aggregate expenses for day '%s': %d", day, amount)
        for tx_type, amount in self.by_transaction_type.items():
            LOG.info("Aggregate expenses by transaction type '%s': %d", tx_type, amount)

