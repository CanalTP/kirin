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
from datetime import timedelta

import pytest
import ujson
from navitia_wrapper import as_time

from kirin.core import model
from kirin.core.build_wrapper import handle
from kirin.core.merge_utils import convert_nav_stop_list_to_stu_list
from kirin.core.model import RealTimeUpdate, TripUpdate, VehicleJourney, StopTimeUpdate
from kirin.core.types import ConnectorType, ModificationType
from kirin.gtfs_rt import gtfs_rt
from kirin.utils import make_rt_update, db_commit
from tests import mock_navitia
from tests.integration.conftest import GTFS_CONTRIBUTOR_ID
import datetime
from kirin import app, db
from tests.check_utils import _dt
from tests.mock_navitia import vj_pass_midnight_utc


@pytest.fixture(scope="function", autouse=True)
def navitia(monkeypatch):
    """
    Mock all calls to navitia for this fixture and get_publication_date
    """
    monkeypatch.setattr("navitia_wrapper._NavitiaWrapper.query", mock_navitia.mock_navitia_query)
    monkeypatch.setattr(
        "navitia_wrapper._NavitiaWrapper.get_publication_date", mock_navitia.mock_publication_date
    )


def create_trip_update(
    id, trip_id, circulation_date, stops, status="update", contributor_id=GTFS_CONTRIBUTOR_ID
):
    trip_update = TripUpdate(
        VehicleJourney(
            {
                "trip": {"id": trip_id},
                "stop_times": [
                    {"utc_arrival_time": datetime.time(8, 10), "stop_point": {"stop_area": {"timezone": "UTC"}}}
                ],
            },
            datetime.datetime.combine(circulation_date, datetime.time(7, 10)),
            datetime.datetime.combine(circulation_date, datetime.time(9, 10)),
        ),
        contributor_id,
        status,
    )
    trip_update.id = id
    for stop in stops:
        st = StopTimeUpdate({"id": stop["id"]}, stop["departure"], stop["arrival"])
        st.arrival_status = stop["arrival_status"]
        st.departure_status = stop["departure_status"]
        trip_update.stop_time_updates.append(st)

    db.session.add(trip_update)
    return trip_update


@pytest.fixture()
def setup_database():
    """
    we create two realtime_updates with the same vj but for different date
    and return a vj for navitia
    """
    with app.app_context():
        vju = create_trip_update(
            "70866ce8-0638-4fa1-8556-1ddfa22d09d3",
            "vehicle_journey:1",
            datetime.date(2015, 9, 8),
            [
                {
                    "id": "sa:1",
                    "departure": _dt("8:15"),
                    "arrival": None,
                    "departure_status": "update",
                    "arrival_status": "none",
                },
                {
                    "id": "sa:2",
                    "departure": _dt("9:10"),
                    "arrival": _dt("9:05"),
                    "departure_status": "none",
                    "arrival_status": "none",
                },
                {
                    "id": "sa:3",
                    "departure": None,
                    "arrival": _dt("10:05"),
                    "departure_status": "none",
                    "arrival_status": "none",
                },
            ],
        )
        rtu = make_rt_update(None, ConnectorType.gtfs_rt.value, contributor_id=GTFS_CONTRIBUTOR_ID)
        rtu.id = "10866ce8-0638-4fa1-8556-1ddfa22d09d3"
        rtu.trip_updates.append(vju)
        db.session.add(rtu)
        vju = create_trip_update(
            "70866ce8-0638-4fa1-8556-1ddfa22d09d4",
            "vehicle_journey:1",
            datetime.date(2015, 9, 7),
            [
                {
                    "id": "sa:1",
                    "departure": _dt("8:35", day=7),
                    "arrival": None,
                    "departure_status": "update",
                    "arrival_status": "none",
                },
                {
                    "id": "sa:2",
                    "departure": _dt("9:40", day=7),
                    "arrival": _dt("9:35", day=7),
                    "departure_status": "update",
                    "arrival_status": "update",
                },
                {
                    "id": "sa:3",
                    "departure": None,
                    "arrival": _dt("10:35", day=7),
                    "departure_status": "none",
                    "arrival_status": "update",
                },
            ],
        )
        rtu = make_rt_update(None, ConnectorType.gtfs_rt.value, contributor_id=GTFS_CONTRIBUTOR_ID)
        rtu.id = "20866ce8-0638-4fa1-8556-1ddfa22d09d3"
        rtu.trip_updates.append(vju)
        db_commit(rtu)


@pytest.fixture()
def navitia_vj():
    return {
        "trip": {"id": "vehicle_journey:1"},
        "stop_times": [
            {
                "utc_arrival_time": None,
                "utc_departure_time": datetime.time(8, 10),
                "stop_point": {"id": "sa:1", "stop_area": {"timezone": "UTC"}},
            },
            {
                "utc_arrival_time": datetime.time(9, 5),
                "utc_departure_time": datetime.time(9, 10),
                "stop_point": {"id": "sa:2", "stop_area": {"timezone": "UTC"}},
            },
            {
                "utc_arrival_time": datetime.time(10, 5),
                "utc_departure_time": None,
                "stop_point": {"id": "sa:3", "stop_area": {"timezone": "UTC"}},
            },
        ],
    }


def _create_db_vj(navitia_vj):
    return VehicleJourney(
        navitia_vj, datetime.datetime(2015, 9, 8, 7, 10, 0), datetime.datetime(2015, 9, 8, 11, 5, 0)
    )


def test_handle_basic():

    with app.app_context():
        contributor = model.Contributor(
            id=GTFS_CONTRIBUTOR_ID, navitia_coverage=None, connector_type=ConnectorType.gtfs_rt.value
        )
        builder = gtfs_rt.KirinModelBuilder(contributor)

        with pytest.raises(TypeError):
            handle(builder, None, [])

        # a RealTimeUpdate without any TripUpdate doesn't do anything
        real_time_update = make_rt_update(
            raw_data=None, connector_type=ConnectorType.gtfs_rt.value, contributor_id=GTFS_CONTRIBUTOR_ID
        )
        res, _ = handle(builder, real_time_update, [])
        assert res == real_time_update


def test_handle_new_vj():
    """an easy one: we have one vj with only one stop time updated"""
    navitia_vj = {
        "trip": {"id": "vehicle_journey:1"},
        "stop_times": [
            {
                "utc_arrival_time": None,
                "utc_departure_time": datetime.time(8, 10),
                "stop_point": {"id": "sa:1", "stop_area": {"timezone": "UTC"}},
            },
            {
                "utc_arrival_time": datetime.time(9, 10),
                "utc_departure_time": None,
                "stop_point": {"id": "sa:2", "stop_area": {"timezone": "UTC"}},
            },
        ],
    }
    with app.app_context():
        contributor = model.Contributor(
            id=GTFS_CONTRIBUTOR_ID, navitia_coverage=None, connector_type=ConnectorType.gtfs_rt.value
        )
        builder = gtfs_rt.KirinModelBuilder(contributor)

        trip_update = TripUpdate(_create_db_vj(navitia_vj), contributor_id=contributor.id, status="update")
        st = StopTimeUpdate({"id": "sa:1"}, departure_delay=timedelta(minutes=5), dep_status="update")
        real_time_update = make_rt_update(
            raw_data=None, connector_type=ConnectorType.gtfs_rt.value, contributor_id=contributor.id
        )
        trip_update.stop_time_updates.append(st)
        res, _ = handle(builder, real_time_update, [trip_update])

        assert len(res.trip_updates) == 1
        trip_update = res.trip_updates[0]
        assert trip_update.status == "update"
        assert len(trip_update.stop_time_updates) == 2

        assert trip_update.stop_time_updates[0].stop_id == "sa:1"
        assert trip_update.stop_time_updates[0].departure == _dt("8:15")
        assert trip_update.stop_time_updates[0].arrival == _dt("8:15")

        assert trip_update.stop_time_updates[1].stop_id == "sa:2"
        assert trip_update.stop_time_updates[1].departure == _dt("9:10")
        assert trip_update.stop_time_updates[1].arrival == _dt("9:10")

        # testing that RealTimeUpdate is persisted in db
        db_trip_updates = real_time_update.query.from_self(TripUpdate).all()
        assert len(db_trip_updates) == 1
        assert db_trip_updates[0].status == "update"

        db_st_updates = real_time_update.query.from_self(StopTimeUpdate).order_by("stop_id").all()
        assert len(db_st_updates) == 2
        assert db_st_updates[0].stop_id == "sa:1"
        assert db_st_updates[0].departure == _dt("8:15")
        assert db_st_updates[0].arrival == _dt("8:15")
        assert db_st_updates[0].trip_update_id == db_trip_updates[0].vj_id

        assert db_st_updates[1].stop_id == "sa:2"
        assert db_st_updates[1].departure == _dt("9:10")
        assert db_st_updates[1].arrival == _dt("9:10")
        assert db_st_updates[1].trip_update_id == db_trip_updates[0].vj_id


def test_past_midnight():
    """
    integration of a past midnight
    """
    navitia_vj = {
        "trip": {"id": "vehicle_journey:1"},
        "stop_times": [
            {
                "utc_arrival_time": datetime.time(22, 10),
                "utc_departure_time": datetime.time(22, 15),
                "stop_point": {"id": "sa:1"},
            },
            # arrive at sa:2 at 23:10 and leave the day after
            {
                "utc_arrival_time": datetime.time(23, 10),
                "utc_departure_time": datetime.time(2, 15),
                "stop_point": {"id": "sa:2", "stop_area": {"timezone": "UTC"}},
            },
            {
                "utc_arrival_time": datetime.time(3, 20),
                "utc_departure_time": datetime.time(3, 25),
                "stop_point": {"id": "sa:3", "stop_area": {"timezone": "UTC"}},
            },
        ],
    }
    with app.app_context():
        contributor = model.Contributor(
            id=GTFS_CONTRIBUTOR_ID, navitia_coverage=None, connector_type=ConnectorType.gtfs_rt.value
        )
        builder = gtfs_rt.KirinModelBuilder(contributor)

        vj = VehicleJourney(
            navitia_vj, datetime.datetime(2015, 9, 8, 21, 15, 0), datetime.datetime(2015, 9, 9, 4, 20, 0)
        )
        trip_update = TripUpdate(vj, status="update", contributor_id=contributor.id)
        st = StopTimeUpdate({"id": "sa:2"}, departure_delay=timedelta(minutes=31), dep_status="update", order=1)
        real_time_update = make_rt_update(
            raw_data=None, connector_type=ConnectorType.gtfs_rt.value, contributor_id=contributor.id
        )
        trip_update.stop_time_updates.append(st)
        res, _ = handle(builder, real_time_update, [trip_update])

        assert len(res.trip_updates) == 1
        trip_update = res.trip_updates[0]
        assert trip_update.status == "update"
        assert len(trip_update.stop_time_updates) == 3

        assert trip_update.stop_time_updates[0].stop_id == "sa:1"
        assert trip_update.stop_time_updates[0].arrival == _dt("22:10")
        assert trip_update.stop_time_updates[0].departure == _dt("22:15")

        assert trip_update.stop_time_updates[1].stop_id == "sa:2"
        assert trip_update.stop_time_updates[1].arrival == _dt("23:10")
        assert trip_update.stop_time_updates[1].arrival_delay == timedelta(0)
        assert trip_update.stop_time_updates[1].departure == _dt("2:46", day=9)
        assert trip_update.stop_time_updates[1].departure_delay == timedelta(minutes=31)

        assert trip_update.stop_time_updates[2].stop_id == "sa:3"
        assert trip_update.stop_time_updates[2].arrival == _dt("3:20", day=9)
        assert trip_update.stop_time_updates[2].arrival_delay == timedelta(0)
        assert trip_update.stop_time_updates[2].departure == _dt("3:25", day=9)
        assert trip_update.stop_time_updates[2].departure_delay == timedelta(0)


def test_handle_new_trip_out_of_order(navitia_vj):
    """
    We have one vj with only one stop time updated, but it's not the first
    so we have to reorder the stop times in the resulting trip_update
    """
    with app.app_context():
        contributor = model.Contributor(
            id=GTFS_CONTRIBUTOR_ID, navitia_coverage=None, connector_type=ConnectorType.gtfs_rt.value
        )
        builder = gtfs_rt.KirinModelBuilder(contributor)

        trip_update = TripUpdate(_create_db_vj(navitia_vj), status="update", contributor_id=contributor.id)
        st = StopTimeUpdate(
            {"id": "sa:2"},
            departure_delay=timedelta(minutes=40),
            dep_status="update",
            arrival_delay=timedelta(minutes=44),
            arr_status="update",
            order=1,
        )
        real_time_update = make_rt_update(
            raw_data=None, connector_type=ConnectorType.gtfs_rt.value, contributor_id=contributor.id
        )
        trip_update.stop_time_updates.append(st)
        res, _ = handle(builder, real_time_update, [trip_update])

        assert len(res.trip_updates) == 1
        trip_update = res.trip_updates[0]
        assert len(trip_update.stop_time_updates) == 3

        assert trip_update.stop_time_updates[0].stop_id == "sa:1"
        assert trip_update.stop_time_updates[0].departure == _dt("8:10")
        assert trip_update.stop_time_updates[0].arrival == _dt("8:10")

        assert trip_update.stop_time_updates[1].stop_id == "sa:2"
        assert trip_update.stop_time_updates[1].departure == _dt("9:50")
        assert trip_update.stop_time_updates[1].arrival == _dt("9:49")

        assert trip_update.stop_time_updates[2].stop_id == "sa:3"
        assert trip_update.stop_time_updates[2].departure == _dt("10:05")
        assert trip_update.stop_time_updates[2].arrival == _dt("10:05")


def test_manage_consistency(navitia_vj):
    """
    we receive an update for a vj already in the database

                          sa:1           sa:2             sa:3
    VJ navitia           08:10        09:05-09:10        10:05
    update kirin           -         *10:15-09:20*         -
    expected result   08:10-08:10     10:15-10:15     11:10-11:10
    """
    with app.app_context():
        contributor = model.Contributor(
            id=GTFS_CONTRIBUTOR_ID, navitia_coverage=None, connector_type=ConnectorType.gtfs_rt.value
        )
        builder = gtfs_rt.KirinModelBuilder(contributor)

        trip_update = TripUpdate(_create_db_vj(navitia_vj), status="update", contributor_id=contributor.id)
        st = StopTimeUpdate(
            {"id": "sa:2"},
            arrival_delay=timedelta(minutes=70),
            dep_status="update",
            departure_delay=timedelta(minutes=10),
            arr_status="update",
            order=1,
        )
        st.arrival_status = st.departure_status = "update"
        real_time_update = make_rt_update(
            raw_data=None, connector_type=ConnectorType.gtfs_rt.value, contributor_id=contributor.id
        )
        real_time_update.id = "30866ce8-0638-4fa1-8556-1ddfa22d09d3"
        trip_update.stop_time_updates.append(st)
        res, _ = handle(builder, real_time_update, [trip_update])

        assert len(res.trip_updates) == 1
        trip_update = res.trip_updates[0]
        assert trip_update.status == "update"
        assert len(trip_update.real_time_updates) == 1
        assert len(trip_update.stop_time_updates) == 3

        stu_map = {stu.stop_id: stu for stu in trip_update.stop_time_updates}

        assert "sa:1" in stu_map
        assert stu_map["sa:1"].arrival == _dt("8:10")
        assert stu_map["sa:1"].departure == _dt("8:10")

        assert "sa:2" in stu_map
        assert stu_map["sa:2"].arrival == _dt("10:15")
        assert stu_map["sa:2"].departure == _dt("10:15")

        assert "sa:3" in stu_map
        assert stu_map["sa:3"].arrival == _dt("11:10")
        assert stu_map["sa:3"].departure == _dt("11:10")


def test_handle_update_vj(setup_database, navitia_vj):
    """
    this time we receive an update for a vj already in the database

                      sa:1        sa:2       sa:3
    VJ navitia        8:10     9:05-9:10     10:05
    VJ in db          8:15*    9:05-9:10     10:05
    update kirin       -      *9:15-9:20*      -
    """
    with app.app_context():
        contributor = model.Contributor(
            id=GTFS_CONTRIBUTOR_ID, navitia_coverage=None, connector_type=ConnectorType.gtfs_rt.value
        )
        builder = gtfs_rt.KirinModelBuilder(contributor)

        trip_update = TripUpdate(_create_db_vj(navitia_vj), status="update", contributor_id=contributor.id)
        st = StopTimeUpdate(
            {"id": "sa:2"},
            arrival_delay=timedelta(minutes=10),
            dep_status="update",
            departure_delay=timedelta(minutes=10),
            arr_status="update",
            order=1,
        )
        st.arrival_status = st.departure_status = "update"
        real_time_update = make_rt_update(
            raw_data=None, connector_type=ConnectorType.gtfs_rt.value, contributor_id=contributor.id
        )
        real_time_update.id = "30866ce8-0638-4fa1-8556-1ddfa22d09d3"
        trip_update.stop_time_updates.append(st)
        res, _ = handle(builder, real_time_update, [trip_update])

        assert len(res.trip_updates) == 1
        trip_update = res.trip_updates[0]
        assert trip_update.status == "update"
        assert len(trip_update.real_time_updates) == 2
        assert len(trip_update.stop_time_updates) == 3

        stu_map = {stu.stop_id: stu for stu in trip_update.stop_time_updates}

        assert "sa:1" in stu_map
        assert stu_map["sa:1"].arrival == _dt("8:15")
        assert stu_map["sa:1"].departure == _dt("8:15")

        assert "sa:2" in stu_map
        assert stu_map["sa:2"].arrival == _dt("9:15")
        assert stu_map["sa:2"].departure == _dt("9:20")

        assert "sa:3" in stu_map
        assert stu_map["sa:3"].arrival == _dt("10:05")
        assert stu_map["sa:3"].departure == _dt("10:05")

        # testing that RealTimeUpdate is persisted in db
        db_trip_updates = TripUpdate.query.join(VehicleJourney).order_by("start_timestamp").all()
        assert len(db_trip_updates) == 2
        assert real_time_update.query.from_self(TripUpdate).all()[0].status == "update"
        st_updates = real_time_update.query.from_self(StopTimeUpdate).order_by("stop_id").all()
        assert len(st_updates) == 6

        # testing that trip update on 2015/09/07 is remaining correctly stored in db
        assert len(db_trip_updates[0].stop_time_updates) == 3
        db_stu_map = {stu.stop_id: stu for stu in db_trip_updates[0].stop_time_updates}

        assert "sa:1" in db_stu_map
        assert db_stu_map["sa:1"].arrival is None
        assert db_stu_map["sa:1"].departure == _dt("8:35", day=7)

        assert "sa:2" in db_stu_map
        assert db_stu_map["sa:2"].arrival == _dt("9:35", day=7)
        assert db_stu_map["sa:2"].departure == _dt("9:40", day=7)

        assert "sa:3" in db_stu_map
        assert db_stu_map["sa:3"].arrival == _dt("10:35", day=7)
        assert db_stu_map["sa:3"].departure is None

        # testing that trip update on 2015/09/08 is correctly merged and stored in db
        assert len(db_trip_updates[1].stop_time_updates) == 3
        db_stu_map = {stu.stop_id: stu for stu in db_trip_updates[1].stop_time_updates}

        assert "sa:1" in db_stu_map
        assert db_stu_map["sa:1"].arrival == _dt("8:15")
        assert db_stu_map["sa:1"].departure == _dt("8:15")

        assert "sa:2" in db_stu_map
        assert db_stu_map["sa:2"].arrival == _dt("9:15")
        assert db_stu_map["sa:2"].departure == _dt("9:20")

        assert "sa:3" in db_stu_map
        assert db_stu_map["sa:3"].arrival == _dt("10:05")
        assert db_stu_map["sa:3"].departure == _dt("10:05")


def test_simple_delay(navitia_vj):
    """Test on delay when there is nothing in the db"""
    with app.app_context():
        contributor = model.Contributor(
            id=GTFS_CONTRIBUTOR_ID, navitia_coverage=None, connector_type=ConnectorType.gtfs_rt.value
        )
        builder = gtfs_rt.KirinModelBuilder(contributor)

        trip_update = TripUpdate(_create_db_vj(navitia_vj), status="update", contributor_id=contributor.id)
        st = StopTimeUpdate(
            {"id": "sa:1"},
            departure_delay=timedelta(minutes=10),
            dep_status="update",
            arrival_delay=timedelta(minutes=5),
            arr_status="update",
            order=0,
        )
        real_time_update = make_rt_update(
            raw_data=None, connector_type=ConnectorType.gtfs_rt.value, contributor_id=contributor.id
        )
        trip_update.stop_time_updates.append(st)
        res, _ = handle(builder, real_time_update, [trip_update])
        assert len(res.trip_updates) == 1
        trip_update = res.trip_updates[0]
        assert trip_update.status == "update"
        assert len(trip_update.stop_time_updates) == 3

        assert trip_update.stop_time_updates[0].stop_id == "sa:1"
        assert trip_update.stop_time_updates[0].arrival == _dt("8:20")  # departure
        assert trip_update.stop_time_updates[0].arrival_delay == timedelta(minutes=5)
        assert trip_update.stop_time_updates[0].arrival_status == "update"
        assert trip_update.stop_time_updates[0].departure == _dt("8:20")  # 8:10 + 10mn
        assert trip_update.stop_time_updates[0].departure_delay == timedelta(minutes=10)
        assert trip_update.stop_time_updates[0].departure_status == "update"

        assert trip_update.stop_time_updates[1].stop_id == "sa:2"
        assert trip_update.stop_time_updates[1].arrival == _dt("9:05")
        assert trip_update.stop_time_updates[1].arrival_delay == timedelta(0)
        assert trip_update.stop_time_updates[1].arrival_status == "none"
        assert trip_update.stop_time_updates[1].departure == _dt("9:10")
        assert trip_update.stop_time_updates[1].departure_delay == timedelta(0)
        assert trip_update.stop_time_updates[1].departure_status == "none"

        # testing that RealTimeUpdate is persisted in db
        db_trip_updates = real_time_update.query.from_self(TripUpdate).all()
        assert len(db_trip_updates) == 1
        assert db_trip_updates[0].status == "update"

        db_st_updates = real_time_update.query.from_self(StopTimeUpdate).order_by("stop_id").all()
        assert len(db_st_updates) == 3
        assert db_st_updates[0].stop_id == "sa:1"
        assert db_st_updates[0].arrival == _dt("8:20")  # departure
        assert db_st_updates[0].arrival_delay == timedelta(minutes=5)
        assert db_st_updates[0].arrival_status == "update"
        assert db_st_updates[0].departure == _dt("8:20")  # 8:10 + 10mn
        assert db_st_updates[0].departure_delay == timedelta(minutes=10)
        assert db_st_updates[0].departure_status == "update"

        assert db_st_updates[1].stop_id == "sa:2"
        assert db_st_updates[1].arrival == _dt("9:05")
        assert db_st_updates[1].departure == _dt("9:10")
        assert db_st_updates[1].trip_update_id == db_trip_updates[0].vj_id

        assert db_st_updates[2].stop_id == "sa:3"


def _check_multiples_delay(res):
    assert len(res.trip_updates) == 1
    trip_update = res.trip_updates[0]
    assert trip_update.status == "update"
    assert len(trip_update.stop_time_updates) == 3
    assert len(trip_update.real_time_updates) == 2

    stu = trip_update.stop_time_updates
    # Note: order is important
    assert stu[0].stop_id == "sa:1"
    assert stu[0].arrival_status == "none"
    assert stu[0].departure == _dt("8:20")
    assert stu[0].departure_status == "update"

    assert stu[1].stop_id == "sa:2"
    assert stu[1].arrival == _dt("9:07")
    assert stu[1].arrival_status == "update"
    assert stu[1].arrival_delay == timedelta(minutes=2)
    assert stu[1].departure == _dt("9:10")
    assert stu[1].departure_status == "none"
    assert stu[1].departure_delay == timedelta(0)

    assert stu[2].stop_id == "sa:3"
    assert stu[2].arrival == _dt("10:05")
    assert stu[2].arrival_status == "none"
    assert stu[2].departure == _dt("10:05")
    assert stu[2].departure_status == "none"


def test_multiple_delays(setup_database, navitia_vj):
    """
    We receive a delay on the first and second stoptimes of a vj, and there was already some delay on the
    first st of this vj

                      sa:1        sa:2       sa:3
    VJ navitia        8:10     9:05-9:10     10:05
    VJ in db          8:15*    9:05-9:10     10:05
    update kirin      8:20*   *9:07-9:10     10:05
    """
    with app.app_context():
        contributor = model.Contributor(
            id=GTFS_CONTRIBUTOR_ID, navitia_coverage=None, connector_type=ConnectorType.gtfs_rt.value
        )
        builder = gtfs_rt.KirinModelBuilder(contributor)

        trip_update = TripUpdate(_create_db_vj(navitia_vj), status="update", contributor_id=contributor.id)
        real_time_update = make_rt_update(
            raw_data=None, connector_type=ConnectorType.gtfs_rt.value, contributor_id=contributor.id
        )
        trip_update.stop_time_updates = [
            # Note: the delay is based of the navitia's vj
            StopTimeUpdate({"id": "sa:1"}, departure_delay=timedelta(minutes=10), dep_status="update"),
            StopTimeUpdate({"id": "sa:2"}, arrival_delay=timedelta(minutes=2), arr_status="update"),
        ]
        res, _ = handle(builder, real_time_update, [trip_update])

        _check_multiples_delay(res)

        # we also check that there is what we want in the db
        db_trip_updates = res.query.from_self(TripUpdate).all()
        assert len(db_trip_updates) == 2
        for tu in db_trip_updates:
            assert tu.status == "update"
        assert len(RealTimeUpdate.query.all()) == 3  # 2 already in db, one new update
        assert len(StopTimeUpdate.query.all()) == 6  # 3 st * 2 vj in the db


def test_multiple_delays_in_2_updates(navitia_vj):
    """
    same test as test_multiple_delays, but with nothing in the db and with 2 trip updates
    """
    with app.app_context():
        contributor = model.Contributor(
            id=GTFS_CONTRIBUTOR_ID, navitia_coverage=None, connector_type=ConnectorType.gtfs_rt.value
        )
        builder = gtfs_rt.KirinModelBuilder(contributor)

        trip_update = TripUpdate(_create_db_vj(navitia_vj), status="update", contributor_id=contributor.id)
        real_time_update = make_rt_update(
            raw_data=None, connector_type=ConnectorType.gtfs_rt.value, contributor_id=contributor.id
        )
        trip_update.stop_time_updates = [
            StopTimeUpdate({"id": "sa:1"}, departure_delay=timedelta(minutes=5), dep_status="update")
        ]
        handle(builder, real_time_update, [trip_update])

        trip_update = TripUpdate(_create_db_vj(navitia_vj), status="update", contributor_id=contributor.id)
        real_time_update = make_rt_update(
            raw_data=None, connector_type=ConnectorType.gtfs_rt.value, contributor_id=contributor.id
        )
        trip_update.stop_time_updates = [
            StopTimeUpdate({"id": "sa:1"}, departure_delay=timedelta(minutes=10), dep_status="update"),
            StopTimeUpdate({"id": "sa:2"}, arrival_delay=timedelta(minutes=2), arr_status="update"),
        ]
        res, _ = handle(builder, real_time_update, [trip_update])

        _check_multiples_delay(res)
        # we also check that there is what we want in the db
        db_trip_updates = res.query.from_self(TripUpdate).all()
        assert len(db_trip_updates) == 1
        assert db_trip_updates[0].status == "update"
        assert len(RealTimeUpdate.query.all()) == 2
        assert len(StopTimeUpdate.query.all()) == 3


def test_delays_then_cancellation(setup_database, navitia_vj):
    """
    We have a delay on the first st of a vj in the db and we receive a cancellation on this vj,
    we should have a cancelled vj in the end

                      sa:1        sa:2       sa:3
    VJ navitia        8:10     9:05-9:10     10:05
    VJ in db          8:15*    9:05-9:10     10:05
    update kirin                   -
    """
    with app.app_context():
        contributor = model.Contributor(
            id=GTFS_CONTRIBUTOR_ID, navitia_coverage=None, connector_type=ConnectorType.gtfs_rt.value
        )
        builder = gtfs_rt.KirinModelBuilder(contributor)

        trip_update = TripUpdate(_create_db_vj(navitia_vj), status="delete", contributor_id=contributor.id)
        real_time_update = make_rt_update(
            raw_data=None, connector_type=ConnectorType.gtfs_rt.value, contributor_id=contributor.id
        )
        res, _ = handle(builder, real_time_update, [trip_update])

        assert len(res.trip_updates) == 1
        trip_update = res.trip_updates[0]
        assert trip_update.status == "delete"
        assert len(trip_update.stop_time_updates) == 0
        assert len(trip_update.real_time_updates) == 2


def test_delays_then_cancellation_in_2_updates(navitia_vj):
    """
    Same test as above, but with nothing in the db, and with 2 updates
    """
    with app.app_context():
        contributor = model.Contributor(
            id=GTFS_CONTRIBUTOR_ID, navitia_coverage=None, connector_type=ConnectorType.gtfs_rt.value
        )
        builder = gtfs_rt.KirinModelBuilder(contributor)

        trip_update = TripUpdate(_create_db_vj(navitia_vj), status="update", contributor_id=contributor.id)
        real_time_update = make_rt_update(
            raw_data=None, connector_type=ConnectorType.gtfs_rt.value, contributor_id=contributor.id
        )
        trip_update.stop_time_updates = [
            StopTimeUpdate({"id": "sa:1"}, departure_delay=timedelta(minutes=5), dep_status="update")
        ]
        handle(builder, real_time_update, [trip_update])

        trip_update = TripUpdate(_create_db_vj(navitia_vj), status="delete", contributor_id=contributor.id)
        real_time_update = make_rt_update(
            raw_data=None, connector_type=ConnectorType.gtfs_rt.value, contributor_id=contributor.id
        )
        res, _ = handle(builder, real_time_update, [trip_update])

        assert len(res.trip_updates) == 1
        trip_update = res.trip_updates[0]
        assert trip_update.status == "delete"
        assert len(trip_update.stop_time_updates) == 0
        assert len(trip_update.real_time_updates) == 2


def _check_cancellation_then_delay(res):
    assert len(res.trip_updates) == 1
    trip_update = res.trip_updates[0]
    assert trip_update.status == "update"
    assert len(trip_update.stop_time_updates) == 3
    assert len(trip_update.real_time_updates) == 2

    stu = trip_update.stop_time_updates
    # Note: order is important
    assert stu[0].stop_id == "sa:1"
    assert stu[0].arrival == _dt("8:10")
    assert stu[0].arrival_status == "none"
    assert stu[0].departure == _dt("8:10")
    assert stu[0].departure_status == "none"

    assert stu[1].stop_id == "sa:2"
    assert stu[1].arrival == _dt("9:05")
    assert stu[1].arrival_status == "none"
    assert stu[1].arrival_delay == timedelta(0)
    assert stu[1].departure == _dt("9:10")
    assert stu[1].departure_status == "none"
    assert stu[1].departure_delay == timedelta(0)

    assert stu[2].stop_id == "sa:3"
    assert stu[2].arrival == _dt("10:45")
    assert stu[2].arrival_status == "update"
    assert stu[2].departure == _dt("10:45")
    assert stu[2].departure_status == "none"

    # db checks
    db_trip_updates = TripUpdate.query.all()
    assert len(TripUpdate.query.all()) == 1
    assert db_trip_updates[0].status == "update"
    assert len(RealTimeUpdate.query.all()) == 2
    assert len(StopTimeUpdate.query.all()) == 3


def test_cancellation_then_delay(navitia_vj):
    """
    we have a cancelled vj in the db, and we receive an update on the 3rd stoptime,
    at the end we have a delayed vj

                      sa:1        sa:2       sa:3
    VJ navitia        8:10     9:05-9:10     10:05
    VJ in db                       -
    update kirin      8:10     9:05-9:10     10:45*
    """
    with app.app_context():
        vju = create_trip_update(
            "70866ce8-0638-4fa1-8556-1ddfa22d09d3",
            "vehicle_journey:1",
            datetime.date(2015, 9, 8),
            [],
            status="delete",
        )
        rtu = make_rt_update(None, ConnectorType.gtfs_rt.value, contributor_id=GTFS_CONTRIBUTOR_ID)
        rtu.id = "10866ce8-0638-4fa1-8556-1ddfa22d09d3"
        rtu.trip_updates.append(vju)
        db_commit(rtu)

    with app.app_context():
        contributor = model.Contributor(
            id=GTFS_CONTRIBUTOR_ID, navitia_coverage=None, connector_type=ConnectorType.gtfs_rt.value
        )
        builder = gtfs_rt.KirinModelBuilder(contributor)

        trip_update = TripUpdate(_create_db_vj(navitia_vj), status="update", contributor_id=contributor.id)
        real_time_update = make_rt_update(
            raw_data=None, connector_type=ConnectorType.gtfs_rt.value, contributor_id=contributor.id
        )
        trip_update.stop_time_updates = [
            StopTimeUpdate({"id": "sa:3"}, arrival_delay=timedelta(minutes=40), arr_status="update", order=2)
        ]
        res, _ = handle(builder, real_time_update, [trip_update])

        _check_cancellation_then_delay(res)


def test_cancellation_then_delay_in_2_updates(navitia_vj):
    """
    same as test_cancellation_then_delay, but with a clear db and in 2 updates
    """
    with app.app_context():
        contributor = model.Contributor(
            id=GTFS_CONTRIBUTOR_ID, navitia_coverage=None, connector_type=ConnectorType.gtfs_rt.value
        )
        builder = gtfs_rt.KirinModelBuilder(contributor)

        trip_update = TripUpdate(_create_db_vj(navitia_vj), status="delete", contributor_id=contributor.id)
        trip_update.stop_time_updates = []
        real_time_update = make_rt_update(
            raw_data=None, connector_type=ConnectorType.gtfs_rt.value, contributor_id=contributor.id
        )
        handle(builder, real_time_update, [trip_update])

        trip_update = TripUpdate(_create_db_vj(navitia_vj), status="update", contributor_id=contributor)
        real_time_update = make_rt_update(
            raw_data=None, connector_type=ConnectorType.gtfs_rt.value, contributor_id=contributor.id
        )
        trip_update.stop_time_updates = [
            StopTimeUpdate({"id": "sa:3"}, arrival_delay=timedelta(minutes=40), arr_status="update", order=2)
        ]
        res, _ = handle(builder, real_time_update, [trip_update])

        _check_cancellation_then_delay(res)


def test_convert_nav_stop_list_to_stu_list():
    nav_stop_times = ujson.loads(vj_pass_midnight_utc.response.json_response)["vehicle_journeys"][0][
        "stop_times"
    ]
    # prepare dict the same way navitia_wrapper does
    for stop_time in nav_stop_times:
        if "arrival_time" in stop_time:
            stop_time["arrival_time"] = as_time(stop_time["arrival_time"])
        if "departure_time" in stop_time:
            stop_time["departure_time"] = as_time(stop_time["departure_time"])
        if "utc_arrival_time" in stop_time:
            stop_time["utc_arrival_time"] = as_time(stop_time["utc_arrival_time"])
        if "utc_departure_time" in stop_time:
            stop_time["utc_departure_time"] = as_time(stop_time["utc_departure_time"])

    stus = convert_nav_stop_list_to_stu_list(nav_stop_times, datetime.date(2020, 11, 13))
    assert len(stus) == 5
    stu = stus[0]
    assert stu.order == 0
    assert stu.stop_id == "StopR1"
    assert stu.arrival == datetime.datetime(2020, 11, 13, 23, 30)
    assert stu.departure == datetime.datetime(2020, 11, 13, 23, 30)
    stu = stus[1]
    assert stu.order == 1
    assert stu.stop_id == "StopR2"
    assert stu.arrival == datetime.datetime(2020, 11, 13, 23, 59)
    assert stu.departure == datetime.datetime(2020, 11, 14, 0, 0)
    stu = stus[2]
    assert stu.order == 2
    assert stu.stop_id == "StopR2-bis"
    assert stu.arrival == datetime.datetime(2020, 11, 14, 0, 0)
    assert stu.departure == datetime.datetime(2020, 11, 14, 0, 0)
    stu = stus[3]
    assert stu.order == 3
    assert stu.stop_id == "StopR3"
    assert stu.arrival == datetime.datetime(2020, 11, 14, 0, 0)
    assert stu.departure == datetime.datetime(2020, 11, 14, 0, 1)
    stu = stus[4]
    assert stu.order == 4
    assert stu.stop_id == "StopR4"
    assert stu.arrival == datetime.datetime(2020, 11, 14, 0, 30)
    assert stu.departure == datetime.datetime(2020, 11, 14, 0, 30)
    for stu in stus:
        assert stu.arrival_status == ModificationType.none.name
        assert stu.departure_status == ModificationType.none.name
        assert stu.arrival_delay == datetime.timedelta(0)
        assert stu.departure_delay == datetime.timedelta(0)
        assert stu.message is None
