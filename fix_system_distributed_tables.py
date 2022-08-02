#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2017-present ScyllaDB
#
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
# You should have received a copy of the GNU General Public License
# along with Scylla.  If not, see <http://www.gnu.org/licenses/>.
#
import argparse
import sys

from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider

events_cols = {
    'session_id': 'uuid',
    'event_id': 'timeuuid',
    'activity': 'text',
    'source': 'inet',
    'source_elapsed': 'int',
    'thread': 'text',
    'scylla_span_id': 'bigint',
    'scylla_parent_id': 'bigint'
}

sessions_cols = {
    'session_id': 'uuid',
    'command': 'text',
    'client': 'inet',
    'coordinator': 'inet',
    'duration': 'int',
    'parameters': 'map<text, text>',
    'request': 'text',
    'started_at': 'timestamp',
    'request_size': 'int',
    'response_size': 'int',
    'username': 'text'
}

slow_query_log_cols = {
    'node_ip': 'inet',
    'shard': 'int',
    'session_id': 'uuid',
    'date': 'timestamp',
    'start_time': 'timeuuid',
    'command': 'text',
    'duration': 'int',
    'parameters': 'map<text, text>',
    'source_ip': 'inet',
    'table_names': 'set<text>',
    'username': 'text'
}

traces_tables_defs = {
    'events': events_cols,
    'sessions': sessions_cols,
    'node_slow_log': slow_query_log_cols
}
################################################################################
credentials_cols = {
    'username': 'text',
    'options': 'map<text, text>',
    'salted_hash': 'text'
}

permissions_cols = {
    'username': 'text',
    'resource': 'text',
    'permissions': 'set<text>'
}

users_cols = {
    'name': 'text',
    'super': 'boolean'
}

auth_tables_defs = {
    'credentials': credentials_cols,
    'permissions': permissions_cols,
    'users': users_cols
}
################################################################################
ks_defs = {
    'system_traces': traces_tables_defs,
    'system_auth': auth_tables_defs
}
################################################################################


def validate_and_fix(args):
    res = True
    if args.user:
        auth_provider = PlainTextAuthProvider(username=args.user, password=args.password)
        cluster = Cluster(auth_provider=auth_provider, contact_points=[args.node], port=args.port)
    else:
        cluster = Cluster(contact_points=[args.node], port=args.port)

    try:
        session = cluster.connect()
        cluster_meta = session.cluster.metadata
        for ks, tables_defs in ks_defs.items():
            if ks not in cluster_meta.keyspaces:
                print(f"keyspace {ks} doesn't exist - skipping")
                continue

            ks_meta = cluster_meta.keyspaces[ks]
            for table_name, table_cols in tables_defs.items():

                if table_name not in ks_meta.tables:
                    print(f"{ks}.{table_name} doesn't exist - skipping")
                    continue

                print(f"Adjusting {ks}.{table_name}")

                table_meta = ks_meta.tables[table_name]
                for column_name, column_type in table_cols.items():
                    if column_name in table_meta.columns:
                        column_meta = table_meta.columns[column_name]
                        if column_meta.cql_type != column_type:
                            print(
                                f"ERROR: {ks}.{table_name}::{column_name} column has an unexpected column type: expected '{column_type}' found '{column_meta.cql_type}'"
                            )

                            res = False
                    else:
                        try:
                            session.execute(
                                f"ALTER TABLE {ks}.{table_name} ADD {column_name} {column_type}"
                            )

                            print(
                                f"{ks}.{table_name}: added column '{column_name}' of the type '{column_type}'"
                            )

                        except Exception:
                            print(
                                f"ERROR: {ks}.{table_name}: failed to add column '{column_name}' with type '{column_type}': {sys.exc_info()}"
                            )

                            res = False
    except Exception:
        print(f"ERROR: {sys.exc_info()}")
        res = False

    return res


################################################################################
if __name__ == '__main__':
    argp = argparse.ArgumentParser(description='Validate distributed system keyspaces')
    argp.add_argument('--user', '-u')
    argp.add_argument('--password', '-p', default='none')
    argp.add_argument('--node', default='127.0.0.1', help='Node to connect to.')
    argp.add_argument('--port', default=9042, help='Port to connect to.', type=int)

    args = argp.parse_args()
    if res := validate_and_fix(args):
        sys.exit(0)
    else:
        sys.exit(1)
