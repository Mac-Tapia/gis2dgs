from gis2dgs.cli.main import build_parser


def test_cli_parser_has_program_name() -> None:
    assert build_parser().prog == "gis2dgs"
