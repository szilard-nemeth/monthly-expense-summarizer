import logging
import pprint
import re
from dataclasses import dataclass
from enum import Enum
from typing import Pattern, Dict, List, Tuple

from pythoncommons.file_utils import FileUtils

from monthlyexpensesummarizer.config import ParserConfig, MandatoryExpenseField, PaymentMethod

LOG = logging.getLogger(__name__)


class InfoType(Enum):
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
        self.conf_dict: Dict[InfoType, bool] = {InfoType.MULTI_LINE_EXPENSE: self.print_multi_line_expenses,
                                                InfoType.DATE_LINE: self.print_date_lines,
                                                InfoType.LINE_RANGE: self.print_expense_line_ranges,
                                                InfoType.MATCH_OBJECT: self.print_match_objs,
                                                InfoType.PARSED_EXPENSES: self.print_parsed_expenses}


class DiagnosticPrinter:
    def __init__(self, diagnostic_config: DiagnosticConfig):
        self.diagnostic_config = diagnostic_config

    def print_line(self, line, info_type: InfoType):
        enabled = self.diagnostic_config.conf_dict[info_type]
        if enabled:
            LOG.debug(info_type.log_pattern, line)

    def pretty_print(self, obj, info_type: InfoType):
        enabled = self.diagnostic_config.conf_dict[info_type]
        if enabled:
            LOG.debug(info_type.log_pattern, pprint.pformat(obj))


@dataclass
class ParsedExpense:
    payment_method_marker: str
    payment_method_postfix: str
    amount: int
    title: str
    details: str
    more_details: str
    payment_method: PaymentMethod or None = None

    def post_init(self, config: ParserConfig):
        found_prefix = True if self.payment_method_marker in config.payment_methods_by_prefix_symbol else False
        found_postfix = True if self.payment_method_postfix in config.payment_methods_by_postfix else False

        if not found_prefix:
            LOG.error("Unrecognized payment method marker for expense: %s", self)
            self.payment_method = None
        else:
            self.payment_method = config.payment_methods_by_prefix_symbol[self.payment_method_marker]

        if not found_postfix:
            LOG.error("Unrecognized payment method postfix for expense: %s", self)
            self.payment_method = None
        else:
            self.payment_method = config.payment_methods_by_postfix[self.payment_method_postfix]


class InputFileParser:
    def __init__(self, config: ParserConfig, diagnostic_config: DiagnosticConfig):
        self.printer = DiagnosticPrinter(diagnostic_config)
        self.config: ParserConfig = config
        self.multi_line_expense_open_chars = InputFileParser._get_multiline_expense_open_chars(config)
        self.multi_line_expense_close_chars = InputFileParser._get_multiline_expense_close_chars(config)

        self.multiline_start_idx = -1
        self.multiline_end_idx = -1
        self.expense_line_ranges: List[Tuple[int, int]] = []
        self.date_lines: List[int] = []
        self.inside_multiline = False
        self.parsed_expenses: List[ParsedExpense] = []

    def parse(self, file: str):
        file_contents = FileUtils.read_file(file)
        self.lines_of_file = file_contents.split("\n")
        for idx, line in enumerate(self.lines_of_file):
            match = self._match_date_line_regexes(line)
            if match:
                self.date_lines.append(idx)
            else:
                line_range = self._get_line_range_of_expense(line, idx)
                if line_range:
                    self.expense_line_ranges.append(line_range)

        self.parsed_expenses = self._process_line_ranges()
        self.printer.pretty_print(self.parsed_expenses, InfoType.PARSED_EXPENSES)

    def _match_date_line_regexes(self, line):
        for date_regex in self.config.date_regexes:  # type: Pattern
            match = date_regex.match(line)
            if match:
                self.printer.print_line(line, InfoType.DATE_LINE)
                return match
        return None

    @staticmethod
    def _get_multiline_expense_open_chars(config):
        results_list = [config.generic_parser_settings.expense_details_separator_strings,
                        config.generic_parser_settings.expense_more_details_separator_strings]
        chars = set().union(*results_list)
        return chars

    @staticmethod
    def _get_multiline_expense_close_chars(config):
        results_list = [config.generic_parser_settings.expense_details_separator_strings,
                        config.generic_parser_settings.expense_more_details_close_strings]
        chars = set().union(*results_list)
        return chars

    def _get_line_range_of_expense(self, line, idx: int):
        multi_line_opened = any([c in line for c in self.multi_line_expense_open_chars])
        multi_line_closed = any([c in line for c in self.multi_line_expense_close_chars])
        if not self.inside_multiline and multi_line_opened:
            self.inside_multiline = True
            self.multiline_start_idx = idx
            self.printer.print_line(line, InfoType.MULTI_LINE_EXPENSE)
        elif self.inside_multiline and multi_line_closed:
            self.multiline_end_idx = idx
            line_range = (self.multiline_start_idx, self.multiline_end_idx)
            self.printer.print_line(line_range, InfoType.LINE_RANGE)
            self.inside_multiline = False
            return line_range
        elif self.inside_multiline and not multi_line_closed:
            # Multi line expense continued
            return
        elif idx not in self.date_lines and (line and not line.isspace()):
            # Single line expense
            line_range = (idx, idx)
            self.printer.print_line(line_range, InfoType.LINE_RANGE)
            return line_range

    def _get_lines_by_ranges(self):
        result: List[List[str]] = []
        for range in self.expense_line_ranges:
            result.append(self.lines_of_file[range[0]:range[1] + 1])
        return result

    def _process_line_ranges(self):
        self.lines_by_ranges: List[List[str]] = self._get_lines_by_ranges()

        parsed_expenses: List[ParsedExpense] = []
        for list_of_lines in self.lines_by_ranges:
            lines = "\n".join(list_of_lines)
            match = re.match(self.config.expense_regex, lines, re.MULTILINE)
            if not match:
                LOG.error("Expense not matched: %s", lines)
                continue
            self.printer.print_line(match, InfoType.MATCH_OBJECT)
            parsed_expenses.append(self._create_expense_from_match_groups(match))
        return parsed_expenses

    def _create_expense_from_match_groups(self, match):
        payment_method_marker = match.group(MandatoryExpenseField.PAYMENT_METHOD_MARKER.value)
        amount = match.group(MandatoryExpenseField.AMOUNT.value)
        title = match.group(MandatoryExpenseField.TITLE.value)
        details = match.group(MandatoryExpenseField.DETAILS.value)
        more_details = match.group(MandatoryExpenseField.MORE_DETAILS.value)
        payment_method_postfix = match.group(MandatoryExpenseField.PAYMENT_METHOD_POSTFIX.value)
        parsed_expense = ParsedExpense(payment_method_marker, payment_method_postfix, self._convert_amount_str(amount), title, details, more_details)
        parsed_expense.post_init(self.config)
        return parsed_expense

    def _convert_amount_str(self, amount: str) -> int:
        new_amount = amount
        sep_chars = self.config.generic_parser_settings.thousands_separator_chars
        for sep in sep_chars:
            if sep in amount:
                new_amount = new_amount.replace(sep, "")
        return int(new_amount)

