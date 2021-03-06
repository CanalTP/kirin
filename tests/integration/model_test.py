# coding=utf-8

# Copyright (c) 2001, Canal TP and/or its affiliates. All rights reserved.
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
# [matrix] channel #navitia:matrix.org (https://app.element.io/#/room/#navitia:matrix.org)
# https://groups.google.com/d/forum/navitia
# www.navitia.io

from __future__ import absolute_import, print_function, unicode_literals, division

from sqlalchemy.orm.exc import FlushError

from kirin.core.model import TripUpdate, StopTimeUpdate, Contributor
from kirin.core.types import ConnectorType
from kirin.utils import db_commit
from tests.integration.conftest import COTS_CONTRIBUTOR_ID, GTFS_CONTRIBUTOR_ID
from tests.integration.utils_test import create_trip_update, create_rt_update_and_trip_update
from kirin import db, app
import datetime
import pytest


@pytest.fixture()
def setup_database():
    with app.app_context():
        create_trip_update(
            "70866ce8-0638-4fa1-8556-1ddfa22d09d3",
            "vehicle_journey:1",
            datetime.date(2015, 9, 8),
            COTS_CONTRIBUTOR_ID,
        )
        create_trip_update(
            "70866ce8-0638-4fa1-8556-1ddfa22d09d4",
            "vehicle_journey:2",
            datetime.date(2015, 9, 8),
            COTS_CONTRIBUTOR_ID,
        )
        create_trip_update(
            "70866ce8-0638-4fa1-8556-1ddfa22d09d5",
            "vehicle_journey:2",
            datetime.date(2015, 9, 9),
            COTS_CONTRIBUTOR_ID,
        )
        db.session.commit()


def test_find_by_vj(setup_database):
    with app.app_context():
        assert TripUpdate.find_by_dated_vj("vehicle_journey:1", datetime.datetime(2015, 9, 9, 8, 0)) is None
        row = TripUpdate.find_by_dated_vj("vehicle_journey:1", datetime.datetime(2015, 9, 8, 8, 0))
        assert row is not None
        assert row.vj_id == "70866ce8-0638-4fa1-8556-1ddfa22d09d3"

        row = TripUpdate.find_by_dated_vj("vehicle_journey:2", datetime.datetime(2015, 9, 8, 8, 0))
        assert row is not None
        assert row.vj_id == "70866ce8-0638-4fa1-8556-1ddfa22d09d4"


def test_find_stop():
    with app.app_context():
        vj = create_trip_update(
            "70866ce8-0638-4fa1-8556-1ddfa22d09d3", "vj1", datetime.date(2015, 9, 8), COTS_CONTRIBUTOR_ID
        )
        st1 = StopTimeUpdate({"id": "sa:1"}, None, None, order=0)
        vj.stop_time_updates.append(st1)
        st2 = StopTimeUpdate({"id": "sa:2"}, None, None, order=1)
        vj.stop_time_updates.append(st2)
        st3 = StopTimeUpdate({"id": "sa:3"}, None, None, order=2)
        vj.stop_time_updates.append(st3)

        assert vj.find_stop("sa:1", 0) == st1
        assert vj.find_stop("sa:1") == st1
        assert vj.find_stop("sa:2", 1) == st2
        assert vj.find_stop("sa:3", 2) == st3
        assert vj.find_stop("sa:4") is None


def test_find_activate():
    with app.app_context():
        create_rt_update_and_trip_update(
            "70866ce8-0638-4fa1-8556-1ddfa22d09d3",
            COTS_CONTRIBUTOR_ID,
            ConnectorType.cots.value,
            "70866ce8-0638-4fa1-8556-1ddfa22d09d3",
            "vj1",
            datetime.date(2015, 9, 8),
        )
        create_rt_update_and_trip_update(
            "70866ce8-0638-4fa1-8556-1ddfa22d09d4",
            COTS_CONTRIBUTOR_ID,
            ConnectorType.cots.value,
            "70866ce8-0638-4fa1-8556-1ddfa22d09d4",
            "vj2",
            datetime.date(2015, 9, 10),
        )
        create_rt_update_and_trip_update(
            "70866ce8-0638-4fa1-8556-1ddfa22d09d5",
            COTS_CONTRIBUTOR_ID,
            ConnectorType.cots.value,
            "70866ce8-0638-4fa1-8556-1ddfa22d09d5",
            "vj3",
            datetime.date(2015, 9, 12),
        )

        create_rt_update_and_trip_update(
            "70866ce8-0638-4fa1-8556-1ddfa22d09d6",
            GTFS_CONTRIBUTOR_ID,
            ConnectorType.cots.value,
            "70866ce8-0638-4fa1-8556-1ddfa22d09d6",
            "vj4",
            datetime.date(2015, 9, 12),
        )
        db.session.commit()

        """
        contributor                     COTS_CONTRIBUTOR_ID
        VehicleJourney                  vj1
        Circulation date                20150908                         20150910                20150912
                                            |                               |                       |
        request date            20150906    |                               |                       |
        """

        rtu = TripUpdate.find_by_contributor_period([COTS_CONTRIBUTOR_ID], datetime.date(2015, 9, 6))
        assert len(rtu) == 3
        assert rtu[0].vj_id == "70866ce8-0638-4fa1-8556-1ddfa22d09d3"
        assert rtu[1].vj_id == "70866ce8-0638-4fa1-8556-1ddfa22d09d4"
        assert rtu[2].vj_id == "70866ce8-0638-4fa1-8556-1ddfa22d09d5"

        """
        contributor                     COTS_CONTRIBUTOR_ID
        VehicleJourney                  vj1
        Circulation date                20150908                         20150910                20150912
                                            |                               |                       |
        request date                    20150908                            |                       |
        """
        rtu = TripUpdate.find_by_contributor_period([COTS_CONTRIBUTOR_ID], datetime.date(2015, 9, 8))
        assert len(rtu) == 3

        """
        contributor                     COTS_CONTRIBUTOR_ID
        VehicleJourney                  vj1
        Circulation date                20150908                         20150910                20150912
                                            |                               |                       |
        request date                        |   20150909                    |                       |
        """
        rtu = TripUpdate.find_by_contributor_period([COTS_CONTRIBUTOR_ID], datetime.date(2015, 9, 9))
        assert len(rtu) == 2
        assert rtu[0].vj_id == "70866ce8-0638-4fa1-8556-1ddfa22d09d4"
        assert rtu[1].vj_id == "70866ce8-0638-4fa1-8556-1ddfa22d09d5"

        """
        contributor                     COTS_CONTRIBUTOR_ID
        VehicleJourney                  vj1
        Circulation date                20150908                         20150910                20150912
                                            |                               |                       |
        request date                        |                            20150910                   |
        """

        rtu = TripUpdate.find_by_contributor_period([COTS_CONTRIBUTOR_ID], datetime.date(2015, 9, 10))
        assert len(rtu) == 2

        """
        contributor                     COTS_CONTRIBUTOR_ID
        VehicleJourney                  vj1
        Circulation date                20150908                         20150910                20150912
                                            |                               |                       |
        request date                        |                               |   20150911            |
        """

        rtu = TripUpdate.find_by_contributor_period([COTS_CONTRIBUTOR_ID], datetime.date(2015, 9, 11))
        assert len(rtu) == 1
        assert rtu[0].vj_id == "70866ce8-0638-4fa1-8556-1ddfa22d09d5"

        """
        contributor                     COTS_CONTRIBUTOR_ID
        VehicleJourney                  vj1
        Circulation date                20150908                         20150910                20150912
                                            |                               |                       |
        request date                        |                               |                    20150912
        """

        rtu = TripUpdate.find_by_contributor_period([COTS_CONTRIBUTOR_ID], datetime.date(2015, 9, 12))
        assert len(rtu) == 1

        """
        contributor                     COTS_CONTRIBUTOR_ID
        VehicleJourney                  vj1
        Circulation date                20150908                         20150910                20150912
                                            |                               |                       |
        request date                        |                               |                       |   20150913
        """

        rtu = TripUpdate.find_by_contributor_period([COTS_CONTRIBUTOR_ID], datetime.date(2015, 9, 13))
        assert len(rtu) == 0

        """
        contributor                            COTS_CONTRIBUTOR_ID
        VehicleJourney                          vj1
        Circulation date                        20150908                         20150910                20150912
                                                    |                               |                       |
        request interval date  |---------|          |                               |                       |
                            20150905   20150906
        """

        rtu = TripUpdate.find_by_contributor_period(
            [COTS_CONTRIBUTOR_ID], datetime.date(2015, 9, 5), datetime.date(2015, 9, 6)
        )
        assert len(rtu) == 0

        """
        contributor                            COTS_CONTRIBUTOR_ID
        VehicleJourney                          vj1
        Circulation date                        20150908                         20150910                20150912
                                                    |                               |                       |
        request interval date  |--------------------|                               |                       |
                            20150905            20150908
        """

        rtu = TripUpdate.find_by_contributor_period(
            [COTS_CONTRIBUTOR_ID], datetime.date(2015, 9, 5), datetime.date(2015, 9, 8)
        )
        assert len(rtu) == 0

        """
        contributor                            COTS_CONTRIBUTOR_ID
        VehicleJourney                          vj1
        Circulation date                        20150908                         20150910                20150912
                                                    |                               |                       |
        request interval date  |-------------------------|                          |                       |
                            20150905                    20150909
        """

        rtu = TripUpdate.find_by_contributor_period(
            [COTS_CONTRIBUTOR_ID], datetime.date(2015, 9, 5), datetime.date(2015, 9, 9)
        )
        assert len(rtu) == 1

        """
        contributor                            COTS_CONTRIBUTOR_ID
        VehicleJourney                          vj1
        Circulation date                        20150908                         20150910                20150912
                                                    |                               |                       |
        request interval date  |----------------------------------------------------|                       |
                            20150905                                             20150910
        """

        rtu = TripUpdate.find_by_contributor_period(
            [COTS_CONTRIBUTOR_ID], datetime.date(2015, 9, 5), datetime.date(2015, 9, 10)
        )
        assert len(rtu) == 1

        """
        contributor                            COTS_CONTRIBUTOR_ID
        VehicleJourney                          vj1
        Circulation date                        20150908                         20150910                20150912
                                                    |                               |                       |
        request interval date  |----------------------------------------------------------------|           |
                            20150905                                                          20150911
        """

        rtu = TripUpdate.find_by_contributor_period(
            [COTS_CONTRIBUTOR_ID], datetime.date(2015, 9, 5), datetime.date(2015, 9, 11)
        )
        assert len(rtu) == 2

        """
        contributor                            COTS_CONTRIBUTOR_ID
        VehicleJourney                          vj1
        Circulation date                        20150908                         20150910                20150912
                                                    |                               |                       |
        request interval date  |----------------------------------------------------------------------------|
                            20150905                                                                     20150912
        """

        rtu = TripUpdate.find_by_contributor_period(
            [COTS_CONTRIBUTOR_ID], datetime.date(2015, 9, 5), datetime.date(2015, 9, 12)
        )
        assert len(rtu) == 2

        """
        contributor                            COTS_CONTRIBUTOR_ID
        VehicleJourney                          vj1
        Circulation date                        20150908                         20150910                20150912
                                                    |                               |                       |
        request interval date  |--------------------------------------------------------------------------------------|
                            20150905                                                                                20150914
        """

        rtu = TripUpdate.find_by_contributor_period(
            [COTS_CONTRIBUTOR_ID], datetime.date(2015, 9, 5), datetime.date(2015, 9, 14)
        )
        assert len(rtu) == 3

        """
        contributor                            COTS_CONTRIBUTOR_ID
        VehicleJourney                          vj1
        Circulation date                        20150908                         20150910                20150912
                                                    |                               |                       |
        request interval date                       |------------------------------------------------------------------|
                                                    20150908                                                        20150914
        """

        rtu = TripUpdate.find_by_contributor_period(
            [COTS_CONTRIBUTOR_ID], datetime.date(2015, 9, 8), datetime.date(2015, 9, 14)
        )
        assert len(rtu) == 3

        """
        contributor                            COTS_CONTRIBUTOR_ID
        VehicleJourney                          vj1
        Circulation date                        20150908                         20150910                20150912
                                                    |                               |                       |
        request interval date                         |----------------------------------------------------------------|
                                                      20150909                                                      20150914
        """

        rtu = TripUpdate.find_by_contributor_period(
            [COTS_CONTRIBUTOR_ID], datetime.date(2015, 9, 9), datetime.date(2015, 9, 14)
        )
        assert len(rtu) == 2

        """
        contributor                            COTS_CONTRIBUTOR_ID
        VehicleJourney                          vj1
        Circulation date                        20150908                         20150910                20150912
                                                    |                               |                       |
        request interval date                                                       |-----------------------------------|
                                                                                    20150910                        20150914
        """

        rtu = TripUpdate.find_by_contributor_period(
            [COTS_CONTRIBUTOR_ID], datetime.date(2015, 9, 10), datetime.date(2015, 9, 14)
        )
        assert len(rtu) == 2

        """
        contributor                            COTS_CONTRIBUTOR_ID
        VehicleJourney                          vj1
        Circulation date                        20150908                         20150910                20150912
                                                    |                               |                       |
        request interval date                                                          |--------------------------------|
                                                                                       20150911                     20150914
        """

        rtu = TripUpdate.find_by_contributor_period(
            [COTS_CONTRIBUTOR_ID], datetime.date(2015, 9, 11), datetime.date(2015, 9, 14)
        )
        assert len(rtu) == 1

        """
        contributor                            COTS_CONTRIBUTOR_ID
        VehicleJourney                          vj1
        Circulation date                        20150908                         20150910                20150912
                                                    |                               |                       |
        request interval date                                                                               |-----------|
                                                                                                         20150912   20150914
        """

        rtu = TripUpdate.find_by_contributor_period(
            [COTS_CONTRIBUTOR_ID], datetime.date(2015, 9, 12), datetime.date(2015, 9, 14)
        )
        assert len(rtu) == 1

        """
        contributor                            COTS_CONTRIBUTOR_ID
        VehicleJourney                          vj1
        Circulation date                        20150908                         20150910                20150912
                                                    |                               |                       |
        request interval date                                                                                 |---------|
                                                                                                           20150913 20150914
        """

        rtu = TripUpdate.find_by_contributor_period(
            [COTS_CONTRIBUTOR_ID], datetime.date(2015, 9, 13), datetime.date(2015, 9, 14)
        )
        assert len(rtu) == 0

        rtu = TripUpdate.find_by_contributor_period([GTFS_CONTRIBUTOR_ID], datetime.date(2015, 9, 6))
        assert len(rtu) == 1

        rtu = TripUpdate.find_by_contributor_period([GTFS_CONTRIBUTOR_ID], datetime.date(2015, 9, 12))
        assert len(rtu) == 1

        rtu = TripUpdate.find_by_contributor_period(
            [COTS_CONTRIBUTOR_ID, GTFS_CONTRIBUTOR_ID], datetime.date(2015, 9, 12)
        )
        assert len(rtu) == 2


def test_update_stoptime():
    with app.app_context():
        st = StopTimeUpdate(
            {"id": "foo"},
            departure_delay=datetime.timedelta(minutes=10),
            arrival_delay=datetime.timedelta(minutes=10),
            dep_status="update",
            arr_status="update",
        )

        st.update_arrival(time=None, status=None, delay=datetime.timedelta(minutes=0))
        assert st.arrival_delay == datetime.timedelta(minutes=0)

        st.update_departure(time=None, status=None, delay=datetime.timedelta(minutes=0))
        assert st.departure_delay == datetime.timedelta(minutes=0)


def test_contributor_creation():
    with app.app_context():
        contrib = Contributor("realtime.george", "idf", ConnectorType.cots.value)

        db_commit(contrib)

        assert contrib.id == "realtime.george"
        assert contrib.navitia_coverage == "idf"
        assert contrib.connector_type == ConnectorType.cots.value

        contrib_with_same_id = Contributor("realtime.george", "another-coverage", ConnectorType.cots.value)

        with pytest.raises(FlushError):
            """
            Adding a second contributor with the same id should fail
            """
            db_commit(contrib_with_same_id)
