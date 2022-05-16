import logging
from dataclasses import dataclass

from pythoncommons.file_parser.input_file_parser import GenericBlockBasedInputFileParser, DiagnosticConfig
from pythoncommons.file_parser.parser_config_reader import ParserConfigReader, RegexGenerator, GenericBlockParserConfig

from monthlyexpensesummarizer.config import ParserConfig, PaymentMethod, ItemType

LOG = logging.getLogger(__name__)


# TODO Rename to ParsedItem?
@dataclass
class ParsedExpense:
    date: str
    payment_method_marker: str
    payment_method_postfix: str
    amount: int
    title: str
    details: str
    more_details: str
    amount_title_sep: str
    payment_method: PaymentMethod or None = None
    item_type: ItemType = None

    def post_init(self, config: ParserConfig):
        payment_method_key = (self.payment_method_marker, self.payment_method_postfix)

        found_unrecognized_payment_method = False
        if self.payment_method_marker == config.parser_settings.income_settings.symbol:
            self.item_type = ItemType.INCOME
        elif self.payment_method_marker in config.parser_settings.special_item_prefixes:
            self.item_type = ItemType.SPECIAL
        elif payment_method_key not in config.payment_methods_by_prefix_and_postfix:
            found_unrecognized_payment_method = True
            LOG.error("Unrecognized payment method for expense: %s", self)
            self.payment_method = None
            self.item_type = ItemType.EXPENSE
        else:
            self.payment_method = config.payment_methods_by_prefix_and_postfix[payment_method_key]
            self.item_type = ItemType.EXPENSE

        if config.parser_settings.fail_on_unrecognized_payments and found_unrecognized_payment_method:
            raise ValueError("Found unrecognized payment methods, stopping execution as per config setting!")


class ExpenseInputFileParser:
    def __init__(self, config_reader: ParserConfigReader):
        diagnostic_config = DiagnosticConfig(print_date_lines=True,
                                             print_multi_line_block_headers=True,
                                             print_multi_line_blocks=True)

        self.generic_parser_config: GenericBlockParserConfig = config_reader.config
        self.extended_config: ParserConfig = config_reader.extended_config
        multi_line_expense_open_chars = ExpenseInputFileParser._get_multiline_expense_open_chars(self.extended_config)
        multi_line_expense_close_chars = ExpenseInputFileParser._get_multiline_expense_close_chars(self.extended_config)
        excluded_line_patterns = self.generic_parser_config.date_regexes
        self.generic_block_parser = GenericBlockBasedInputFileParser(block_regex=RegexGenerator.create_final_regex(self.generic_parser_config),
                                                                     block_open_chars=multi_line_expense_open_chars,
                                                                     block_close_chars=multi_line_expense_close_chars,
                                                                     diagnostic_config=diagnostic_config,
                                                                     excluded_line_patterns=excluded_line_patterns)

    def parse(self, file: str):
        return self.generic_block_parser.parse(file,
                                               parsed_object_dataclass=ParsedExpense,
                                               block_to_obj_parser_func=self._parse_expense_obj_from_match_groups)

    @staticmethod
    def _get_multiline_expense_open_chars(config):
        results_list = [config.parser_settings.expense_more_details_separator_strings]
        chars = set().union(*results_list)
        return chars

    @staticmethod
    def _get_multiline_expense_close_chars(config):
        results_list = [config.parser_settings.expense_more_details_close_strings]
        chars = set().union(*results_list)
        return chars

    def _parse_expense_obj_from_match_groups(self, match, date: str):
        # https://stackoverflow.com/a/587518/1106893
        prop_dict = {"date": date}
        for mandatory_field in self.generic_parser_config.generic_parser_settings.parsed_block_format.mandatory_fields:
            prop_dict[mandatory_field.lower()] = match.group(mandatory_field)
            # TODO convert amount with self._convert_amount_str(amount)
        parsed_expense = ParsedExpense(**prop_dict)
        parsed_expense.post_init(self.extended_config)
        return parsed_expense

    def _convert_amount_str(self, amount: str) -> int:
        new_amount = amount
        sep_chars = self.extended_config.parser_settings.thousands_separator_chars
        for sep in sep_chars:
            if sep in amount:
                new_amount = new_amount.replace(sep, "")
        return int(new_amount)

