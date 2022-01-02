import logging
from typing import List, Dict

from monthlyexpensesummarizer.config import ItemType
from monthlyexpensesummarizer.parser import ParsedExpense
LOG = logging.getLogger(__name__)


class Aggregator:
    @classmethod
    def aggregate(cls, parsed_expenses: List[ParsedExpense]):
        by_payment_method: Dict[str, int] = {}
        by_payment_method_stringified: Dict[str, str] = {}
        by_day: Dict[str, int] = {}
        by_transaction_type: Dict[ItemType, int] = {}
        for expense in parsed_expenses:
            key = expense.date
            if key not in by_day:
                by_day[key] = 0
            by_day[key] += expense.amount

            item_type = expense.item_type
            if item_type == ItemType.EXPENSE:
                key = expense.payment_method.display_name
                if key not in by_payment_method:
                    by_payment_method[key] = 0
                    by_payment_method_stringified[key] = ""
                by_payment_method[key] += expense.amount
                by_payment_method_stringified[key] += f"{expense.amount}+"

            key = item_type
            if key not in by_transaction_type:
                by_transaction_type[key] = 0
            by_transaction_type[key] += expense.amount

        LOG.info("Listing aggregates...")
        for payment_method, amount in by_payment_method.items():
            LOG.info("Aggregate expenses for payment method '%s': %d", payment_method, amount)
            LOG.info("Stringified aggregate expenses for payment method '%s': %s", payment_method, by_payment_method_stringified[payment_method])
        for day, amount in by_day.items():
            LOG.info("Aggregate expenses for day '%s': %d", day, amount)
        for tx_type, amount in by_transaction_type.items():
            LOG.info("Aggregate expenses by transaction type '%s': %d", tx_type, amount)


