import argparse
import logging
import re

LOG = logging.getLogger(__name__)


class ArgParser:
    @staticmethod
    def parse_args():
        """This function parses and return arguments passed in"""

        # Top-level parser
        parser = argparse.ArgumentParser()

        # Normal arguments
        parser.add_argument(
            "-v",
            "--verbose",
            action="store_true",
            dest="verbose",
            default=None,
            required=False,
            help="More verbose log (including gitpython verbose logs)",
        )
        parser.add_argument(
            "-d",
            "--debug",
            action="store_true",
            dest="debug",
            default=None,
            required=False,
            help="Turn on console debug level logs",
        )

        args = parser.parse_args()
        if args.verbose:
            print("Args: " + str(args))
        return args, parser
