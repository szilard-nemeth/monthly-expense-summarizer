import logging
import os
import time
from pprint import pformat

from pythoncommons.constants import ExecutionMode
from pythoncommons.file_utils import FileUtils, FindResultType
from pythoncommons.logging_setup import SimpleLoggingSetupConfig, SimpleLoggingSetup
from pythoncommons.os_utils import OsUtils
from pythoncommons.project_utils import ProjectRootDeterminationStrategy, ProjectUtils, SimpleProjectUtils
from monthlyexpensesummarizer.argparser import ArgParser
from monthlyexpensesummarizer.common import MonthlyExpenseSummarizerEnvVar
from monthlyexpensesummarizer.constants import MONTHLY_EXPENSE_SUMMARIZER_MODULE_NAME, REPO_ROOT_DIRNAME
from monthlyexpensesummarizer.config import ParserConfigReader
from monthlyexpensesummarizer.parser import InputFileParser

LOG = logging.getLogger(__name__)


class LocalDirs:
    REPO_ROOT_DIR = FileUtils.find_repo_root_dir(__file__, REPO_ROOT_DIRNAME)


class MonthlyExpenseSummarizer:
    def __init__(self, execution_mode: ExecutionMode = ExecutionMode.PRODUCTION):
        self.env = {}
        self.project_out_root = None
        self.yarn_patch_dir = None
        self.setup_dirs(execution_mode=execution_mode)

    def setup_dirs(self, execution_mode: ExecutionMode = ExecutionMode.PRODUCTION):
        self.project_out_root = self._get_project_root(execution_mode)
        self.log_dir = FileUtils.join_path(self.project_out_root, 'logs')
        self.config_dir = FileUtils.join_path(self.project_out_root, 'config')
        # self.input_files = FileUtils.search_dir(self.project_out_root, "input-files")
        FileUtils.ensure_dir_created(self.log_dir)
        FileUtils.ensure_dir_created(self.config_dir)
        # FileUtils.ensure_dir_created(self.input_files)

    @staticmethod
    def _get_project_root(execution_mode):
        strategy = None
        if execution_mode == ExecutionMode.PRODUCTION:
            strategy = ProjectRootDeterminationStrategy.SYS_PATH
        elif execution_mode == ExecutionMode.TEST:
            strategy = ProjectRootDeterminationStrategy.COMMON_FILE
        if MonthlyExpenseSummarizerEnvVar.PROJECT_DETERMINATION_STRATEGY.value in os.environ:
            env_value = OsUtils.get_env_value(MonthlyExpenseSummarizerEnvVar.PROJECT_DETERMINATION_STRATEGY.value)
            LOG.info("Found specified project root determination strategy from env var: %s", env_value)
            strategy = ProjectRootDeterminationStrategy[env_value.upper()]
        if not strategy:
            raise ValueError("Unknown project root determination strategy!")
        LOG.info("Project root determination strategy is: %s", strategy)
        ProjectUtils.project_root_determine_strategy = strategy
        return ProjectUtils.get_output_basedir(MONTHLY_EXPENSE_SUMMARIZER_MODULE_NAME)

    def start(self):
        config_samples_dir = SimpleProjectUtils.get_project_dir(
            basedir=LocalDirs.REPO_ROOT_DIR,
            dir_to_find="parser_config",
            find_result_type=FindResultType.DIRS,
            parent_dir=REPO_ROOT_DIRNAME
        )
        input_files_dir = SimpleProjectUtils.get_project_dir(
            basedir=LocalDirs.REPO_ROOT_DIR,
            dir_to_find="expense_files",
            find_result_type=FindResultType.DIRS,
            parent_dir=REPO_ROOT_DIRNAME
        )
        sample_project_filename = os.path.join(config_samples_dir, "parserconfig.json")
        input_filename = os.path.join(input_files_dir, "expenses-202108")
        config = ParserConfigReader.read_from_file(filename=sample_project_filename)
        InputFileParser.parse(input_filename)
        LOG.info("Read project config: %s", pformat(config))


if __name__ == '__main__':
    start_time = time.time()

    args, parser = ArgParser.parse_args()
    expense_summarizer = MonthlyExpenseSummarizer()

    # Initialize logging
    verbose = True if args.verbose else False

    # Parse args, commands will be mapped to YarnDevTools functions in ArgParser.parse_args
    logging_config: SimpleLoggingSetupConfig = SimpleLoggingSetup.init_logger(
        project_name=MONTHLY_EXPENSE_SUMMARIZER_MODULE_NAME,
        logger_name_prefix=MONTHLY_EXPENSE_SUMMARIZER_MODULE_NAME,
        execution_mode=ExecutionMode.PRODUCTION,
        console_debug=args.debug,
        verbose_git_log=args.verbose,
    )

    LOG.info("Logging to files: %s", logging_config.log_file_paths)

    # Start build process
    expense_summarizer.start()

    end_time = time.time()
    LOG.info("Execution of script took %d seconds", end_time - start_time)