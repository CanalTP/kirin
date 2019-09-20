# coding=utf-8

# Copyright (c) 2001-2015, Canal TP and/or its affiliates. All rights reserved.
#
# This file is part of Navitia,
#     the software to build cool stuff with public transport.
#
# Hope you'll enjoy and contribute to this project,
#     powered by Canal TP (www.canaltp.fr).
# Help us simplify mobility and open public transport:
#     a non ending quest to the responsive locomotion way of traveling!
#
# LICENCE: This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# Stay tuned using
# twitter @navitia
# IRC #navitia on freenode
# https://groups.google.com/d/forum/navitia
# www.navitia.io
from __future__ import absolute_import, print_function, unicode_literals, division
from contextlib import closing

from kirin import app, db
import pytest

from tests.docker_wrapper import postgres_docker


@pytest.yield_fixture(scope="session", autouse=True)
def pg_docker_fixture():
    """
    a docker providing a PostgreSQL database is started once for all tests
    """
    with closing(postgres_docker()) as pg_db:
        yield pg_db


@pytest.fixture(scope="session", autouse=True)
def init_flask_db(pg_docker_fixture):
    """
    when the docker is started, we init flask once for the new database
    """
    db_url = pg_docker_fixture.get_db_params().cnx_string()

    # re-init the db by overriding the db_url
    app.config[str("SQLALCHEMY_DATABASE_URI")] = db_url
    db.init_app(app)
