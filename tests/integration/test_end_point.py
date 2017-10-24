# Copyright (c) 2001-2015, Canal TP and/or its affiliates. All rights reserved.
#
# This file is part of Navitia,
#     the software to build cool stuff with public transport.
#
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

from tests.check_utils import api_get
from kirin.core import model
from kirin import app
from datetime import date, datetime
import pytest


def test_end_point():
    resp = api_get('/')
    assert 'status' in resp
    assert 'ire' in resp


def test_status(setup_database):
    resp = api_get('/status')

    assert 'version' in resp
    assert 'db_pool_status' in resp
    assert 'db_version' in resp
    assert 'navitia_url' in resp
    assert 'last_update' in resp
    assert 'realtime.ire' in resp['last_update']
    assert 'realtime.sherbrooke' in resp['last_update']

    assert '2015-11-04T07:32:00Z' in resp['last_update']['realtime.ire']
    assert '2015-11-04T07:42:00Z' in resp['last_update']['realtime.sherbrooke']


@pytest.fixture()
def setup_database():
    """
    we create two realtime_updates with the same vj but for different date
    and return a vj for navitia
    """
    with app.app_context():
        vj1 = model.VehicleJourney({'trip': {'id': 'vj:1'}}, date(2015, 11, 4))
        vj2 = model.VehicleJourney({'trip': {'id': 'vj:2'}}, date(2015, 11, 4))
        vj3 = model.VehicleJourney({'trip': {'id': 'vj:3'}}, date(2015, 11, 4))
        tu1 = model.TripUpdate(vj1, contributor='realtime.ire')
        tu2 = model.TripUpdate(vj2, contributor='realtime.ire')
        tu3 = model.TripUpdate(vj3, contributor='realtime.sherbrooke')
        rtu1 = model.RealTimeUpdate(None, 'ire', 'realtime.ire')
        rtu1.created_at = datetime(2015, 11, 4, 6, 32)
        rtu1.trip_updates.append(tu1)
        model.db.session.add(rtu1)
        rtu2 = model.RealTimeUpdate(None, 'ire', contributor='realtime.ire')
        rtu2.created_at = datetime(2015, 11, 4, 7, 32)
        rtu2.trip_updates.append(tu2)
        model.db.session.add(rtu2)

        rtu3 = model.RealTimeUpdate(None, 'gtfs-rt', contributor='realtime.sherbrooke')
        rtu3.created_at = datetime(2015, 11, 4, 7, 42)
        rtu3.trip_updates.append(tu3)
        model.db.session.add(rtu3)

        model.db.session.commit()

