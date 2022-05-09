import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Pattern, Tuple, Union

from dataclasses_json import dataclass_json, LetterCase

LOG = logging.getLogger(__name__)


class ItemType(Enum):
    EXPENSE = "EXPENSE"
    INCOME = "INCOME"
    SPECIAL = "SPECIAL"


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class PaymentMethod:
    short_name: str
    display_name: str
    prefix_symbol: str
    postfix_symbols: List[str] = field(default_factory=list)
    name: str or None = field(default=None)


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class IncomeSettings:
    symbol: str
    requires_postfix: bool


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class ParserSettings:
    income_settings: IncomeSettings
    more_details_spans_to_multiple_lines: bool
    fail_on_unrecognized_payments: bool
    mandatory_postfix_for_payment_methods: List[str] = field(default_factory=list)
    special_item_prefixes: List[str] = field(default_factory=list)
    thousands_separator_chars: List[str] = field(default_factory=list)
    expense_more_details_separator_strings: List[str] = field(default_factory=list)
    expense_more_details_close_strings: List[str] = field(default_factory=list)


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class ExpenseCategory:
    display_name: str
    primary_value: str
    alternative_values: str
    name: str or None = field(default=None)


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class ParserConfig:
    parser_settings: ParserSettings
    payment_methods: Dict[str, PaymentMethod] = field(default_factory=dict)
    expense_categories: Dict[str, ExpenseCategory] = field(default_factory=dict)
    date_regexes: List[Pattern] = field(default_factory=list)
    payment_methods_by_prefix_and_postfix: Dict[Tuple[str, Union[str, None]], PaymentMethod] = field(default_factory=dict)

    # Dynamic properties
    expense_regex: str = None

    def __post_init__(self):
        for name, pm in self.payment_methods.items():
            pm.name = name
        for name, ec in self.expense_categories.items():
            ec.name = name
        for pm_key, pm in self.payment_methods.items():
            for postfix in pm.postfix_symbols:
                found_values = re.findall("[a-zA-Z0-9 ]+", postfix)
                if not found_values:
                    raise ValueError("Postfix is invalid, it should only contain alphanumeric characters and space. Current postfix: {}".format(postfix))
                sanitized_postfix = found_values[0]
                key = (pm.prefix_symbol, sanitized_postfix)
                if key in self.payment_methods_by_prefix_and_postfix:
                    payment_methods_with_dupe_key = [self.payment_methods_by_prefix_and_postfix[key], pm]
                    raise ValueError("Duplicate prefix+postfix key found: {}. Payment methods associated with this key: {}".format(key, payment_methods_with_dupe_key))
                self.payment_methods_by_prefix_and_postfix[key] = pm
            if pm_key not in self.parser_settings.mandatory_postfix_for_payment_methods:
                key = (pm.prefix_symbol, None)
                self.payment_methods_by_prefix_and_postfix[key] = pm

        LOG.info("Initialized parser config")
