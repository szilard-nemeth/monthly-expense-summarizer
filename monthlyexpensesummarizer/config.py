import json
import logging
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Set, Pattern, Tuple

from dataclasses_json import dataclass_json, LetterCase
from pythoncommons.date_utils import DateUtils
from pythoncommons.file_utils import JsonFileUtils
from pythoncommons.string_utils import auto_str
LOG = logging.getLogger(__name__)


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class PaymentMethod:
    short_name: str
    display_name: str
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
    AMOUNT_TITLE_SEP = "AMOUNT_TITLE_SEP"
    TITLE = "TITLE"
    DETAILS = "DETAILS"
    MORE_DETAILS = "MORE_DETAILS" # https://stackoverflow.com/a/587518/1106893
    PAYMENT_METHOD_POSTFIX = "PAYMENT_METHOD_POSTFIX"


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class ExpenseField:
    type: ExpenseFieldType
    value: str
    optional: bool
    extract_inner_group: bool = False


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class ExpenseFormat:
    format_string: str
    fields: Dict[str, ExpenseField] = field(default_factory=dict)
    variables: Dict[str, str] = field(default_factory=dict)
    FIELD_FORMAT: str = r'<([a-zA-Z0-9_ ]+)>'
    VAR_PATTERN: str = r'VAR\(([a-zA-Z_]+)\)'


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class GenericParserSettings:
    income_settings: IncomeSettings
    expense_format: ExpenseFormat
    more_details_spans_to_multiple_lines: bool
    thousands_separator_chars: List[str] = field(default_factory=list)
    expense_details_separator_strings: List[str] = field(default_factory=list)
    expense_more_details_separator_strings: List[str] = field(default_factory=list)
    expense_more_details_close_strings: List[str] = field(default_factory=list)
    date_formats: List[str] = field(default_factory=list) # https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes


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
    date_regexes: List[Pattern] = field(default_factory=list)
    expense_regex: str = None
    payment_methods_by_prefix_and_postfix: Dict[Tuple[str, str], PaymentMethod] = field(default_factory=dict)

    def __post_init__(self):
        for name, pm in self.payment_methods.items():
            pm.name = name
        for name, ec in self.expense_categories.items():
            ec.name = name
        for pm in self.payment_methods.values():
            for postfix in pm.postfix_symbols:
                found_values = re.findall("[a-zA-Z0-9 ]+", postfix)
                if not found_values:
                    raise ValueError("Postfix is invalid, it should only contain alphanumeric characters and space. Current postfic: {}".format(postfix))
                sanitized_postfix = found_values[0]
                key = (pm.prefix_symbol, sanitized_postfix)
                if key in self.payment_methods_by_prefix_and_postfix:
                    payment_methods_with_dupe_key = [self.payment_methods_by_prefix_and_postfix[key], pm]
                    raise ValueError("Duplicate prefix+postfix key found: {}. Payment methods associated with this key: {}".format(key, payment_methods_with_dupe_key))
                self.payment_methods_by_prefix_and_postfix[key] = pm

        LOG.info("Initialized parser config")


@auto_str
class ParserConfigReader:
    def __init__(self, data):
        self.data = data
        self.config: ParserConfig = self._parse()
        self.mandatory_field_names: Set[str] = set([e.value for e in list(MandatoryExpenseField)])
        self._validate()
        self._post_init()

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
        self.field_positions = list(re.findall(ExpenseFormat.FIELD_FORMAT, format_string))
        expected_field_names = set(self.field_positions)

        if not expected_field_names or any([fn == "" for fn in expected_field_names]):
            raise ValueError("Expected field names is empty, this is not expected. Value: {}".format(expected_field_names))

        diff = self.mandatory_field_names.difference(actual_field_names)
        if diff:
            raise ValueError("Found unknown field names: {}. Allowed field names: {}".format(diff, self.mandatory_field_names))

        diff = expected_field_names.difference(actual_field_names)
        if diff:
            raise ValueError("The following fields are not having the field config object {}. Expected field names: {}".format(diff, expected_field_names))

        # Try to find missing vars
        self._check_variables()
        self._validate_date_formats(self.config.generic_parser_settings.date_formats)
        self._validate_regexes()

    def _validate_regexes(self):
        fields = self.config.generic_parser_settings.expense_format.fields
        for field in fields.values(): # type: ExpenseField
            if field.extract_inner_group:
                if field.type != ExpenseFieldType.REGEX:
                    raise ValueError("Invalid config. If 'extractInnerGroup' is enabled, field type should be regex. Field object: {}".format(field))
                elif not (self._ensure_there_is_only_one_regex_group(field.value)):
                    raise ValueError(
                        "Invalid config. If 'extractInnerGroup' is enabled, the regex should only have at most one group. Field object: {}".format(
                            field))

    @staticmethod
    def _ensure_there_is_only_one_regex_group(regex: str):
        count_open = regex.count("(")
        count_close = regex.count(")")
        if count_open != count_close:
            return False
        if count_open > 1 or count_open == 0:
            return False
        return True

    def _check_variables(self):
        for field_name, field_object in self.config.generic_parser_settings.expense_format.fields.items():
            vars = re.findall(ExpenseFormat.VAR_PATTERN, field_object.value)
            vars_set = set(vars)
            if vars_set:
                LOG.debug("Find variables in field '%s': '%s'", field_name, field_object.value)
                available_vars = self.config.generic_parser_settings.expense_format.variables
                diff = set(vars_set).difference(set(available_vars.keys()))
                if diff:
                    raise ValueError("Unkown variables '{}' in {}: {}. Available variables: {}"
                                     .format(diff, field_name, field_object.value, available_vars.keys()))
                self._resolve_variables(available_vars, field_name, field_object, vars_set)

    @staticmethod
    def _resolve_variables(available_vars, field_name, field_object, vars_set):
        field_value = field_object.value
        LOG.debug("Resolving variables in string: %s", field_value)

        original_value = str(field_value)
        new_value = str(original_value)
        for var in vars_set:
            new_value = new_value.replace(f"VAR({var})", available_vars[var])
        LOG.debug("Resolved variables for '%s'. Old: %s, New: %s", field_name, original_value, new_value)
        field_object.value = new_value

    def _post_init(self):
        self._create_final_regex()
        self.config.date_regexes = self._convert_date_formats_to_patterns()

    def _create_final_regex(self):
        field_objects: Dict[str, ExpenseField] = self.config.generic_parser_settings.expense_format.fields
        final_regex = r""
        used_group_names = {}
        for field_name in self.field_positions:
            field_object = field_objects[field_name]
            group_name = field_name
            if group_name not in used_group_names:
                used_group_names[group_name] = 1
                final_regex += self._create_regex(group_name, field_object)
            else:
                if group_name not in self.mandatory_field_names:
                    used_group_names[group_name] += 1
                    group_name = f"{group_name}_{used_group_names[group_name]}"
                    final_regex += self._create_regex(group_name, field_object)
                else:
                    raise ValueError("Group name is already used in regex: {}".format(group_name))
        LOG.info("FINAL REGEX: %s", final_regex)
        self.config.expense_regex = final_regex

    @staticmethod
    def _create_regex(group_name, field_object: ExpenseField):
        regex_value = field_object.value
        if field_object.extract_inner_group:
            open_idx = regex_value.find('(')
            close_idx = regex_value.rfind(')')
            quantifier = regex_value[close_idx+1]
            if quantifier not in ["*", "?", "+"]:
                quantifier = ""
            start = regex_value[:open_idx]
            end = regex_value[close_idx+1:]
            group = regex_value[open_idx+1:close_idx] + quantifier
            grouped_regex = f"(?P<{group_name}>{group})"
            new_regex_value = f"{start}{grouped_regex}{end}"
            return new_regex_value
        grouped_regex = f"(?P<{group_name}>{regex_value})"
        if field_object.optional:
            grouped_regex += "*"
        return grouped_regex

    @staticmethod
    def _validate_date_formats(format_strings):
        for fmt in format_strings:
            LOG.debug("Formatting current date with format '%s': %s", fmt, DateUtils.now_formatted(fmt))

    def _convert_date_formats_to_patterns(self):
        formats = self.config.generic_parser_settings.date_formats
        mappings = {
            "%m": "\\d\\d",
            "%d": "\\d\\d",
            "%Y": "\\d\\d\\d\\d",
            ".": "\\."
        }
        regexes: List[Pattern] = []
        for fmt in formats:
            curr_regex = fmt
            for orig, pattern in mappings.items():
                curr_regex = curr_regex.replace(orig, pattern)
            curr_regex += "$"
            regexes.append(re.compile(curr_regex))
        return regexes

    def __repr__(self):
        return self.__str__()
