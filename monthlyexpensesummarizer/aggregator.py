import logging
from typing import List

from monthlyexpensesummarizer.config import ItemType
from monthlyexpensesummarizer.parser import ParsedExpense
LOG = logging.getLogger(__name__)


class Aggregator:
    @classmethod
    def aggregate(cls, parsed_expenses: List[ParsedExpense]):
        by_payment_method = {}
        by_day = {}
        by_transaction_type = {}
        for expense in parsed_expenses:
            if expense.date not in by_day:
                by_day[expense.date] = 0
            by_day[expense.date] += expense.amount

            if expense.item_type == ItemType.EXPENSE:
                if expense.payment_method.display_name not in by_payment_method:
                    by_payment_method[expense.payment_method.display_name] = 0
                by_payment_method[expense.payment_method.display_name] += expense.amount

            if expense.item_type not in by_transaction_type:
                by_transaction_type[expense.item_type] = 0
            by_transaction_type[expense.item_type] += expense.amount

        LOG.info("Listing aggregates...")
        for payment_method, amount in by_payment_method.items():
            LOG.info("Aggregate expenses for payment method '%s': %d", payment_method, amount)
        for day, amount in by_day.items():
            LOG.info("Aggregate expenses for day '%s': %d", day, amount)
        for tx_type, amount in by_transaction_type.items():
            LOG.info("Aggregate expenses by transaction type '%s': %d", tx_type, amount)
