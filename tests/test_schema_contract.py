"""Check the documented field contract and generated diagrams for drift."""

import re
from pathlib import Path

from sqlalchemy.dialects import postgresql

from code_review.adapters.outbound.postgres.base import Base
from scripts.export_erd import artifacts

ROOT = Path(__file__).resolve().parents[1]


def test_models_match_documented_fields():
    source = (ROOT / "docs/DATABASE_SCHEMA.md").read_text()
    sections = re.split(r"### DB-\d+ · ", source)[1:]
    assert len(sections) == 34
    for section in sections:
        name = section.split(" — ")[0]
        table_name = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
        fields = re.findall(r"^\| `([^`]+)` \| `([^`]+)` \| ([^|]+) \|", section, re.M)
        table = Base.metadata.tables[table_name]
        assert set(table.c.keys()) == {col for col, _, _ in fields}, name
        for col, typename, rule in fields:
            column = table.c[col]
            actual = str(column.type.compile(dialect=postgresql.dialect())).lower()
            assert actual.replace("timestamp with time zone", "timestamptz") == typename
            assert column.nullable == ("NULL" in rule and "NN" not in rule and "PK" not in rule)
            assert column.primary_key == ("PK" in rule)


def test_erd_matches_metadata():
    for filename, expected in artifacts().items():
        assert (ROOT / "docs/erd" / filename).read_text() == expected
