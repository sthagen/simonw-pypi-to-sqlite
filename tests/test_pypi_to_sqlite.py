from click.testing import CliRunner
import json
import pathlib
from pypi_to_sqlite.cli import cli
import pytest
import sqlite_utils

fixture = json.loads(
    (pathlib.Path(__file__).parent / "datasette-block.json").read_text()
)
fixture2 = json.loads(
    (pathlib.Path(__file__).parent / "datasette-block-2.json").read_text()
)


@pytest.mark.parametrize("prefix", ("", "pypi_"))
@pytest.mark.parametrize("use_file", (True, False))
def test_import_package(httpx_mock, prefix, use_file):
    args = []
    runner = CliRunner()

    expected_schema1 = (
        f"CREATE TABLE [{prefix}packages] (\n"
        "   [name] TEXT PRIMARY KEY,\n"
        "   [summary] TEXT,\n"
        "   [classifiers] TEXT,\n"
        "   [description] TEXT,\n"
        "   [author] TEXT,\n"
        "   [author_email] TEXT,\n"
        "   [description_content_type] TEXT,\n"
        "   [home_page] TEXT,\n"
        "   [keywords] TEXT,\n"
        "   [license] TEXT,\n"
        "   [maintainer] TEXT,\n"
        "   [maintainer_email] TEXT,\n"
        "   [package_url] TEXT,\n"
        "   [platform] TEXT,\n"
        "   [project_url] TEXT,\n"
        "   [project_urls] TEXT,\n"
        "   [release_url] TEXT,\n"
        "   [requires_dist] TEXT,\n"
        "   [requires_python] TEXT,\n"
        "   [version] TEXT,\n"
        "   [yanked] INTEGER,\n"
        "   [yanked_reason] TEXT\n"
        ");\n"
        f"CREATE TABLE [{prefix}versions] (\n"
        "   [id] TEXT PRIMARY KEY,\n"
        f"   [package] TEXT REFERENCES [{prefix}packages]([name]),\n"
        "   [name] TEXT\n"
        ");\n"
        f"CREATE TABLE [{prefix}releases] (\n"
        "   [md5_digest] TEXT PRIMARY KEY,\n"
        f"   [package] TEXT REFERENCES [{prefix}packages]([name]),\n"
        f"   [version] TEXT REFERENCES [{prefix}versions]([id]),\n"
        "   [packagetype] TEXT,\n"
        "   [filename] TEXT,\n"
        "   [comment_text] TEXT,\n"
        "   [digests] TEXT,\n"
        "   [has_sig] INTEGER,\n"
        "   [python_version] TEXT,\n"
        "   [requires_python] TEXT,\n"
        "   [size] INTEGER,\n"
        "   [upload_time] TEXT,\n"
        "   [upload_time_iso_8601] TEXT,\n"
        "   [url] TEXT,\n"
        "   [yanked] INTEGER,\n"
        "   [yanked_reason] TEXT\n"
        ");"
    )

    with runner.isolated_filesystem():
        if use_file:
            open("package.json", "w").write(json.dumps(fixture))
            args = ["-f", "package.json"]
        else:
            args = ["datasette-block"]
            httpx_mock.add_response(
                url="https://pypi.org/pypi/datasette-block/json", json=fixture
            )
        if prefix:
            args.extend(["--prefix", prefix])
        result = runner.invoke(cli, ["pypi.db"] + args, catch_exceptions=False)
        assert result.exit_code == 0
        db = sqlite_utils.Database("pypi.db")
        assert db.schema == expected_schema1
        assert "dynamic" not in db["{prefix}packages"].columns_dict
        assert list(db.query(f"select name from {prefix}packages")) == [
            {"name": "datasette-block"}
        ]
        if not use_file:
            assert len(httpx_mock.get_requests()) == 1
        # Should be safe to run twice
        result2 = runner.invoke(cli, ["pypi.db"] + args, catch_exceptions=False)
        assert result2.exit_code == 0
        if not use_file:
            assert len(httpx_mock.get_requests()) == 2
        assert list(db.query(f"select name from {prefix}packages")) == [
            {"name": "datasette-block"}
        ]
        # Now try running it a second time against the new data
        httpx_mock.reset(True)
        if not use_file:
            httpx_mock.add_response(
                url="https://pypi.org/pypi/datasette-block/json", json=fixture2
            )
        else:
            open("package.json", "w").write(json.dumps(fixture2))
        result3 = runner.invoke(cli, ["pypi.db"] + args, catch_exceptions=False)
        if not use_file:
            assert len(httpx_mock.get_requests()) == 1
        assert result3.exit_code == 0
        # Should have a "dynamic" column now
        assert "dynamic" in db[f"{prefix}packages"].columns_dict
