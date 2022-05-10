import logging
import pprint
import re
from dataclasses import dataclass
from enum import Enum
from typing import Pattern, Dict, List, Tuple

from pythoncommons.file_parser import ParserConfigReader, GenericParserConfig, RegexGenerator
from pythoncommons.file_utils import FileUtils

from monthlyexpensesummarizer.config import ParserConfig, PaymentMethod, ItemType

MULTI_LINE_EXPENSE_CONTINUED = (-1, -1)
MULTI_LINE_EXPENSE_HEADER = (-2, -2)

LOG = logging.getLogger(__name__)


class DiagnosticInfoType(Enum):
    PARSED_EXPENSES = ("PARSED_EXPENSES", "Parsed expenses: %s")
    MATCH_OBJECT = ("MATCH_OBJECT", "Match object: %s")
    MULTI_LINE_EXPENSE = ("MULTI_LINE_EXPENSE", "Found multi-line expense: %s")
    DATE_LINE = ("DATE_LINE", "Found date line: %s")
    LINE_RANGE = ("LINE_RANGE", "Found expense in line range: %s")

    def __init__(self, value, log_pattern):
        self.log_pattern = log_pattern


class DiagnosticConfig:
    def __init__(self, print_date_lines: bool = False,
                 print_multi_line_expenses: bool = False,
                 print_expense_line_ranges: bool = False,
                 print_match_objs: bool = False,
                 print_parsed_expenses: bool = True):
        self.print_match_objs = print_match_objs
        self.print_parsed_expenses = print_parsed_expenses
        self.print_date_lines = print_date_lines
        self.print_multi_line_expenses = print_multi_line_expenses
        self.print_expense_line_ranges = print_expense_line_ranges
        self.conf_dict: Dict[DiagnosticInfoType, bool] = {DiagnosticInfoType.MULTI_LINE_EXPENSE: self.print_multi_line_expenses,
                                                          DiagnosticInfoType.DATE_LINE: self.print_date_lines,
                                                          DiagnosticInfoType.LINE_RANGE: self.print_expense_line_ranges,
                                                          DiagnosticInfoType.MATCH_OBJECT: self.print_match_objs,
                                                          DiagnosticInfoType.PARSED_EXPENSES: self.print_parsed_expenses}


class DiagnosticPrinter:
    def __init__(self, diagnostic_config: DiagnosticConfig):
        self.diagnostic_config = diagnostic_config

    def print_line(self, line, info_type: DiagnosticInfoType):
        enabled = self.diagnostic_config.conf_dict[info_type]
        if enabled:
            LOG.debug(info_type.log_pattern, line)

    def pretty_print(self, obj, info_type: DiagnosticInfoType):
        enabled = self.diagnostic_config.conf_dict[info_type]
        if enabled:
            LOG.debug(info_type.log_pattern, pprint.pformat(obj))


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


# TODO Move as much parser functionality as possible to pythoncommons / file_parser.py
class ExpenseInputFileParser:
    def __init__(self, config_reader: ParserConfigReader, diagnostic_config: DiagnosticConfig):
        self.printer = DiagnosticPrinter(diagnostic_config)
        self.extended_config: ParserConfig = config_reader.extended_config
        self.generic_parser_config: GenericParserConfig = config_reader.config
        self.extended_config.expense_regex = RegexGenerator.create_final_regex(self.generic_parser_config)

        self.multi_line_expense_open_chars = ExpenseInputFileParser._get_multiline_expense_open_chars(self.extended_config)
        self.multi_line_expense_close_chars = ExpenseInputFileParser._get_multiline_expense_close_chars(self.extended_config)

        self.multiline_start_idx = -1
        self.multiline_end_idx = -1
        self.line_ranges_of_blocks: List[Tuple[int, int]] = []
        self.excluded_lines: List[int] = []
        self.inside_multiline = False

    def parse(self, file: str):
        file_contents = FileUtils.read_file(file)
        self.lines_of_file = file_contents.split("\n")
        for idx, line in enumerate(self.lines_of_file):
            if self._determine_if_line_excluded(line):
                self.excluded_lines.append(idx)
            else:
                line_range = self._get_line_ranges_of_blocks(line, idx)
                if line_range not in (MULTI_LINE_EXPENSE_CONTINUED, MULTI_LINE_EXPENSE_HEADER):
                    self.line_ranges_of_blocks.append(line_range)

        parsed_expenses = self._process_line_ranges()
        self.printer.pretty_print(parsed_expenses, DiagnosticInfoType.PARSED_EXPENSES)
        return parsed_expenses

    def _determine_if_line_excluded(self, line) -> bool:
        for date_regex in self.generic_parser_config.date_regexes:  # type: Pattern
            match = date_regex.match(line)
            if match:
                self.printer.print_line(line, DiagnosticInfoType.DATE_LINE)
                return True
        return False

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

    def _get_line_ranges_of_blocks(self, line, idx: int) -> Tuple[int, int]:
        multi_line_opened: bool = any([char in line for char in self.multi_line_expense_open_chars])
        multi_line_closed: bool = any([char in line for char in self.multi_line_expense_close_chars])
        if multi_line_opened and not self.inside_multiline:
            self.inside_multiline = True
            self.multiline_start_idx = idx
            self.printer.print_line(line, DiagnosticInfoType.MULTI_LINE_EXPENSE)
            return MULTI_LINE_EXPENSE_HEADER
        elif multi_line_closed and self.inside_multiline:
            self.inside_multiline = False
            self.multiline_end_idx = idx
            line_range = (self.multiline_start_idx, self.multiline_end_idx)
            self.printer.print_line(line_range, DiagnosticInfoType.LINE_RANGE)
            return line_range
        elif not multi_line_closed and self.inside_multiline:
            return MULTI_LINE_EXPENSE_CONTINUED
        elif idx not in self.excluded_lines and (line and not line.isspace()):
            # Single line expense
            line_range = (idx, idx)
            self.printer.print_line(line_range, DiagnosticInfoType.LINE_RANGE)
            return line_range

    def _process_line_ranges(self):
        self.lines_by_ranges: List[Tuple[List[str], str]] = self._get_lines_by_ranges()

        parsed_expenses: List[ParsedExpense] = []
        for list_of_lines, date in self.lines_by_ranges:
            lines = "\n".join(list_of_lines)
            match = re.match(self.extended_config.expense_regex, lines, re.MULTILINE)
            if not match:
                LOG.error("Expense not matched: %s", lines)
                continue
            self.printer.print_line(match, DiagnosticInfoType.MATCH_OBJECT)
            parsed_expenses.append(self._parse_expense_obj_from_match_groups(match, date))
        return parsed_expenses

    def _get_lines_by_ranges(self):
        result: List[Tuple[List[str], str]] = []
        curr_date_idx = 0
        for range in self.line_ranges_of_blocks:
            list_of_lines = self.lines_of_file[range[0]:range[1] + 1]
            if (len(self.excluded_lines) - 1) != curr_date_idx and range[1] > self.excluded_lines[curr_date_idx + 1]:
                curr_date_idx += 1
            date_idx = self.excluded_lines[curr_date_idx]
            date = self.lines_of_file[date_idx]
            result.append((list_of_lines, date))
        return result

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

