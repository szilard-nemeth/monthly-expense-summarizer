import json
import logging
import os
from dataclasses import dataclass, field
from typing import List, Dict

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


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class GenericParserSettings:
    income_settings: IncomeSettings
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
    expense_categories: Dict[str, ExpenseCategory] = field(default_factory=list)

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

    def __repr__(self):
        return self.__str__()
