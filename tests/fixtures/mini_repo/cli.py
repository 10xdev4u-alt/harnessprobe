import argparse
import click


def parse_config(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parsed_args = parser.parse_args(argv)
    return parsed_args


def make_completion_script(options: list[str]) -> str:
    completion = "\n".join(options)
    return completion
