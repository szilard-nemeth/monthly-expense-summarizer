import json
import logging
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Set

from dataclasses_json import dataclass_json, LetterCase
from pythoncommons.file_utils import JsonFileUtils
from pythoncommons.string_utils import auto_str
LOG = logging.getLogger(__name__)


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class PaymentMethod:
    short_name: str
    prefix_symbol: str
    postfix_symbols: List[str] = field(default_factory=list)
    name: str or None = field(default=None)


@dataclass
class IncomeSettings:
    symbol: str


class ExpenseFieldType(Enum):
    REGEX = "regex"
    LITERAL = "literal"


class MandatoryExpenseField(Enum):
    PAYMENT_METHOD_MARKER = "PAYMENT_METHOD_MARKER"
    AMOUNT = "AMOUNT"
    WHITESPACES = "WHITESPACES"
    AMOUNT_TITLE_SEP = "AMOUNT_TITLE_SEP"
    TITLE = "TITLE"
    DETAILS = "DETAILS"
    MORE_DETAILS = "MORE_DETAILS"


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(frozen=True)
class ExpenseField:
    type: ExpenseFieldType
    value: str


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class ExpenseFormat:
    format_string: str
    fields: Dict[str, ExpenseField] = field(default_factory=dict)
    FIELD_FORMAT: str = r'<([a-zA-Z0-9_ ]+)>'


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class GenericParserSettings:
    income_settings: IncomeSettings
    expense_format: ExpenseFormat
    expense_details_separator_strings: List[str] = field(default_factory=list)
    expense_more_details_separator_strings: List[str] = field(default_factory=list)


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
    generic_parser_settings: GenericParserSettings
    payment_methods: Dict[str, PaymentMethod] = field(default_factory=dict)
    expense_categories: Dict[str, ExpenseCategory] = field(default_factory=dict)

    def __post_init__(self):
        for name, pm in self.payment_methods.items():
            pm.name = name
        for name, ec in self.expense_categories.items():
            ec.name = name
        LOG.info("Initialized parser config")


@auto_str
class ParserConfigReader:
    def __init__(self, data):
        self.data = data
        self.config: ParserConfig = self._parse()
        self._validate()

    @staticmethod
    def read_from_file(dir=None, filename=None):
        if filename:
            parser_conf_file = filename
        elif dir:
            parser_conf_file = os.path.join(dir, "parserconfig.json")
        else:
            parser_conf_file = "parserconfig.json"

        data_dict = JsonFileUtils.load_data_from_json_file(parser_conf_file)
        return ParserConfigReader(data_dict)

    def _parse(self):
        parser_config = ParserConfig.from_json(json.dumps(self.data))
        LOG.info("Parser config: %s", parser_config)
        return parser_config

    def _validate(self):
        format_string = self.config.generic_parser_settings.expense_format.format_string
        actual_field_names = frozenset((self.config.generic_parser_settings.expense_format.fields.keys()))
        allowed_field_names: Set[str] = set([e.value for e in list(MandatoryExpenseField)])
        expected_field_names = set(re.findall(ExpenseFormat.FIELD_FORMAT, format_string))

        if not expected_field_names or any([fn == "" for fn in expected_field_names]):
            raise ValueError("Expected field names is empty, this is not expected. Value: {}".format(expected_field_names))

        diff = actual_field_names.difference(allowed_field_names)
        if diff:
            raise ValueError("Found unknown field names: {}. Allowed field names: {}".format(diff, allowed_field_names))

        diff = expected_field_names.difference(actual_field_names)
        if diff:
            raise ValueError("The following fields are not having the field config object {}. Expected field names: {}".format(diff, expected_field_names))




    def __repr__(self):
        return self.__str__()
