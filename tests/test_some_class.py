import logging
import os
import sys
import unittest

from pythoncommons.file_utils import FileUtils, FindResultType


LOG = logging.getLogger(__name__)
CMD_LOG = logging.getLogger(__name__)
SOME_PARENT_DIR = "some_parent_dir"
REPO_ROOT_DIRNAME = "some_repo_root_dirname"
TEST_DIR_NAME = "somedir"


class XyzTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._ensure_env_var_is_present("test_env_var")
        cls._setup_logging()
        cls.repo_root_dir = FileUtils.find_repo_root_dir(__file__, REPO_ROOT_DIRNAME)
        cls._setup_dirs()

    @classmethod
    def tearDownClass(cls) -> None:
        pass

    def setUp(self):
        self.test_instance = self

    def tearDown(self) -> None:
        pass

    @classmethod
    def _ensure_env_var_is_present(cls, env_name):
        if env_name not in os.environ:
            raise ValueError(f"Please set '{env_name}' env var and re-run the test!")

    @classmethod
    def _setup_logging(cls):
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
        handler = logging.StreamHandler(stream=sys.stdout)
        CMD_LOG.propagate = False
        CMD_LOG.addHandler(handler)
        handler.setFormatter(logging.Formatter("%(message)s"))

    @classmethod
    def _setup_dirs(cls):
        found_dirs = FileUtils.find_files(
            cls.repo_root_dir,
            find_type=FindResultType.DIRS,
            regex=TEST_DIR_NAME,
            parent_dir=SOME_PARENT_DIR,
            single_level=False,
            full_path_result=True,
        )
        if len(found_dirs) != 1:
            raise ValueError(
                f"Expected to find 1 dir with name {TEST_DIR_NAME} "
                f"and parent dir '{SOME_PARENT_DIR}'. "
                f"Actual results: {found_dirs}"
            )
        cls.repo_root_dir = found_dirs[0]
        cls.some_other_dir = FileUtils.join_path(cls.repo_root_dir, "some-other-dir")

    @staticmethod
    def find_cdsw_runner_script(parent_dir):
        results = FileUtils.search_files(parent_dir, CDSW_RUNNER_PY)
        if not results:
            raise ValueError(f"Expected to find file: {CDSW_RUNNER_PY}")
        return results[0]

    def test_x(self):
        pass

    def test_y(self):
        pass
