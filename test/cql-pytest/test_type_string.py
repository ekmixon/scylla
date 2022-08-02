# Copyright 2021-present ScyllaDB
#
# This file is part of Scylla.
#
# Scylla is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Scylla is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Scylla.  If not, see <http://www.gnu.org/licenses/>.

#############################################################################
# Tests for string-like types - ascii, blob, and text (a.k.a varchar).
# In the file test_validation.py we have additional tests for the different
# limitations of these different string types.
#############################################################################

import pytest
from util import unique_name, random_string, random_bytes

@pytest.fixture(scope="module")
def table1(cql, test_keyspace):
    table = f"{test_keyspace}.{unique_name()}"
    cql.execute(f"CREATE TABLE {table} (p text primary key, a ascii, b blob, t text, v varchar)")
    yield table
    cql.execute(f"DROP TABLE {table}")

# Test that "text" and "varchar" are not distinct types - they are nothing
# more than an alias to the same thing. We confirm this fact by checking the
# internal type stored in the schema system tables for the "t" and "v"
# columns of these two types - and seeing that the types are identical.
def test_text_varchar_same(cql, table1):
    [ks, cf] = table1.split('.')
    types = [x.type for x in cql.execute(f"SELECT * FROM system_schema.columns WHERE keyspace_name='{ks}' AND table_name='{cf}' AND column_name IN ('t', 'v')")]
    assert types[0] == types[1]
    # Not only do "text" and "varchar" map to the same type, its official
    # name listed in system_schema.columns (and therefore cqlsh's DESCRIBE
    # TABLE) is 'text':
    assert types == ['text', 'text']

# Test that the null character is allowed as a valid character inside all
# string types (including ascii!). In other words, CQL strings are *not*
# null-terminated strings as in C, and may contain nulls inside.
def test_null_char_in_string(cql, table1):
    for col in ['a', 't']:
        p = random_string()
        v = random_string() + '\x00' + random_string()
        # sanity check: verify that Python actually put the null in the string...
        assert 0 in v.encode('utf-8')
        stmt = cql.prepare(f'INSERT INTO {table1} (p, {col}) VALUES (?, ?)')
        cql.execute(stmt, [p, v])
        assert v == getattr(cql.execute(f"SELECT {col} FROM {table1} WHERE p='{p}'").one(), col)
 
def test_null_char_in_blob(cql, table1):
    p = random_string()
    v = random_bytes() + bytes([0]) + random_bytes()
    # sanity check: verify that Python actually put the null in the blob...
    assert 0 in v
    stmt = cql.prepare(f'INSERT INTO {table1} (p, b) VALUES (?, ?)')
    cql.execute(stmt, [p, v])
    assert v == cql.execute(f"SELECT b FROM {table1} WHERE p='{p}'").one().b

