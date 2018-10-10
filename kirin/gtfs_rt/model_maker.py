# coding=utf-8

# Copyright (c) 2001-2017, Canal TP and/or its affiliates. All rights reserved.
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
import datetime
from kirin import gtfs_realtime_pb2
import logging
import pytz

from kirin import core
from kirin.core import model
from kirin.exceptions import KirinException, InvalidArguments, ObjectNotFound
from kirin.utils import make_navitia_wrapper, make_rt_update, floor_datetime
from kirin import new_relic
from kirin.utils import record_internal_failure, record_call
from kirin.utils import get_timezone
from kirin import app
import itertools
import calendar

def handle(proto, navitia_wrapper, contributor):
    data = str(proto)  # temp, for the moment, we save the protobuf as text
    rt_update = make_rt_update(data, 'gtfs-rt', contributor=contributor)
    start_datetime = datetime.datetime.utcnow()
    try:
        trip_updates = KirinModelBuilder(navitia_wrapper, contributor).build(rt_update, data=proto)
        record_call('OK', contributor=contributor)
    except KirinException as e:
        rt_update.status = 'KO'
        rt_update.error = e.data['error']
        model.db.session.add(rt_update)
        model.db.session.commit()
        record_call('failure', reason=str(e), contributor=contributor)
        raise
    except Exception as e:
        rt_update.status = 'KO'
        rt_update.error = e.message
        model.db.session.add(rt_update)
        model.db.session.commit()
        record_call('failure', reason=str(e), contributor=contributor)
        raise

    real_time_update, log_dict = core.handle(rt_update, trip_updates, contributor)

    # After merging trip_updates information of gtfs-rt, navitia and kirin database, if there is no new information
    # destinated to navitia, update real_time_update with status = 'KO' and a proper error message.
    if not real_time_update.trip_updates and real_time_update.status == 'OK':
        real_time_update.status = 'KO'
        real_time_update.error = 'No new information destinated to navitia for this gtfs-rt ' \
                                 'with timestamp: {}'.format(proto.header.timestamp)
        logging.getLogger(__name__).error('No new information destinated to navitia for this gtfs-rt '
                                          'with timestamp: {}'.format(proto.header.timestamp))
        model.db.session.add(rt_update)
        model.db.session.commit()
    duration = (datetime.datetime.utcnow() - start_datetime).total_seconds()
    log_dict.update({'duration': duration,
                     'input_timestamp': datetime.datetime.utcfromtimestamp(proto.header.timestamp)})
    record_call('Simple feed publication', **log_dict)
    logging.getLogger(__name__).info('Simple feed publication', extra=log_dict)


def to_str(date):
    # the date is in UTC, thus we don't have to care about the coverage's timezone
    return date.strftime("%Y%m%dT%H%M%SZ")


class KirinModelBuilder(object):

    def __init__(self, nav, contributor=None):
        self.navitia = nav
        self.contributor = contributor
        self.log = logging.getLogger(__name__)
        # TODO better period handling
        self.period_filter_tolerance = datetime.timedelta(hours=3)
        self.stop_code_key = 'source'  # TODO conf
        self.instance_data_pub_date = self.navitia.get_publication_date()

    def build(self, rt_update, data):
        """
        parse the protobuf in the rt_update object
        and return a list of trip updates

        The TripUpdates are not yet associated with the RealTimeUpdate
        """
        data_time = datetime.datetime.utcfromtimestamp(data.header.timestamp)
        self.log.debug("Start processing GTFS-rt: timestamp = {} ({})"
                       .format(data.header.timestamp, data_time))

        trip_updates = []

        for entity in data.entity:
            if not entity.trip_update:
                continue
            tu = self._make_trip_updates(entity.trip_update, data_time=data_time)
            trip_updates.extend(tu)

        if not trip_updates:
            rt_update.status = 'KO'
            rt_update.error = 'No information for this gtfs-rt with timestamp: {}'.format(data.header.timestamp)
            self.log.error('No information for this gtfs-rt with timestamp: {}'.format(data.header.timestamp))

        return trip_updates

    def _get_stop_code(self, nav_stop):
        for c in nav_stop.get('codes', []):
            if c['type'] == self.stop_code_key:
                return c['value']

    def _make_trip_updates(self, input_trip_update, data_time):
        """
        If trip_update.stop_time_updates is not a strict ending subset of vj.stop_times we reject the trip update
        On the other hand:
        1. For the stop point present in trip_update.stop_time_updates we create a trip_update merging informations
        with that of navitia stop
        2. For the first stop point absent in trip_update.stop_time_updates we create a stop_time_update
        with no delay for that stop
        """
        vjs = self._get_navitia_vjs(input_trip_update.trip, data_time=data_time)
        trip_updates = []
        for vj in vjs:
            trip_update = model.TripUpdate(vj=vj)
            trip_update.contributor = self.contributor

            is_tu_valid = True
            vj_stop_order = len(vj.navitia_vj.get('stop_times', [])) - 1
            for vj_stop, tu_stop in itertools.izip_longest(reversed(vj.navitia_vj.get('stop_times', [])),
                                                           reversed(input_trip_update.stop_time_update)):
                if vj_stop is None:
                    is_tu_valid = False
                    break

                vj_stop_point = vj_stop.get('stop_point')
                if vj_stop_point is None:
                    is_tu_valid = False
                    break

                if tu_stop is not None:
                    if self._get_stop_code(vj_stop_point) != tu_stop.stop_id:
                        is_tu_valid = False
                        break

                    tu_stop.stop_sequence = vj_stop_order
                    st_update = self._make_stoptime_update(tu_stop, vj_stop_point)
                    if st_update is not None:
                        trip_update.stop_time_updates.append(st_update)
                else:
                    #Initialize stops absent in trip_updates but present in vj
                    st_update = self._init_stop_update(vj_stop_point, vj_stop_order)
                    if st_update is not None:
                        trip_update.stop_time_updates.append(st_update)

                vj_stop_order -= 1

            if is_tu_valid:
                #Since vj.stop_times are managed in reversed order, we re sort stop_time_updates by order.
                trip_update.stop_time_updates.sort(cmp=lambda x, y: cmp(x.order, y.order))
                trip_updates.append(trip_update)
            else:
                self.log.error('stop_time_update do not match with stops in navitia for trip : {} timestamp: {}'
                               .format(input_trip_update.trip.trip_id, calendar.timegm(data_time.utctimetuple())))
                record_internal_failure('stop_time_update do not match with stops in navitia',
                                        contributor=self.contributor)
                del trip_update.stop_time_updates[:]

        return trip_updates

    def __repr__(self):
        """ Allow this class to be cacheable
        """
        return '{}.{}.{}'.format(self.__class__, self.navitia.url, self.instance_data_pub_date)

    @app.cache.memoize(timeout=1200)
    def _make_db_vj(self, vj_source_code, since, until):
        navitia_vjs = self.navitia.vehicle_journeys(q={
            'filter': 'vehicle_journey.has_code({}, {})'.format(self.stop_code_key, vj_source_code),
            'since': to_str(since),
            'until': to_str(until),
            'depth': '2',  # we need this depth to get the stoptime's stop_area
        })

        if not navitia_vjs:
            self.log.info('impossible to find vj {t} on [{s}, {u}]'
                          .format(t=vj_source_code,
                                  s=since,
                                  u=until))
            record_internal_failure('missing vj', contributor=self.contributor)
            return []

        if len(navitia_vjs) > 1:
            vj_ids = [vj.get('id') for vj in navitia_vjs]
            self.log.info('too many vjs found for {t} on [{s}, {u}]: {ids}'
                          .format(t=vj_source_code,
                                  s=since,
                                  u=until,
                                  ids=vj_ids
                                  ))
            record_internal_failure('duplicate vjs', contributor=self.contributor)
            return []

        nav_vj = navitia_vjs[0]

        # Now we compute the real circulate_date of VJ from since, until and vj's first stop_time
        # We do this to prevent cases like pass midnight when [since, until] is too large
        # we need local timezone circulate_date (and it's sometimes different from UTC date)
        first_stop_time = nav_vj.get('stop_times', [{}])[0]
        tzinfo = get_timezone(first_stop_time)

        # 'since' and 'until' must have a timezone before being converted to local timezone
        local_since = pytz.utc.localize(since).astimezone(tzinfo)
        local_until = pytz.utc.localize(until).astimezone(tzinfo)

        circulate_date = None

        if local_since.date() == local_until.date():
            circulate_date = local_since.date()
        else:
            arrival_time = first_stop_time['arrival_time']
            # At first, we suppose that the circulate_date is local_since's date
            if local_since <= tzinfo.localize(datetime.datetime.combine(local_since.date(),
                                                                       arrival_time)) <= local_until:
                circulate_date = local_since.date()
            elif local_since <= tzinfo.localize(datetime.datetime.combine(local_until.date(),
                                                                         arrival_time)) <= local_until:
                circulate_date = local_until.date()

        if circulate_date is None:
            self.log.error('impossible to calculate the circulate date (local) of vj: {}'.format(nav_vj.get('id')))
            record_internal_failure('impossible to calculate the circulate date of vj', contributor=self.contributor)
            return []

        try:
            vj = model.VehicleJourney(nav_vj, circulate_date)
            return [vj]
        except Exception as e:
            self.log.exception('Error while creating kirin VJ of {}: {}'.format(nav_vj.get('id'), e))
            record_internal_failure('Error while creating kirin VJ', contributor=self.contributor)
            return []

    def _get_navitia_vjs(self, trip, data_time):
        vj_source_code = trip.trip_id

        since = floor_datetime(data_time - self.period_filter_tolerance)
        until = floor_datetime(data_time + self.period_filter_tolerance + datetime.timedelta(hours=1))
        self.log.debug('searching for vj {} on [{}, {}] in navitia'.format(vj_source_code, since, until))

        return self._make_db_vj(vj_source_code, since, until)

    def _init_stop_update(self, nav_stop, stop_sequence):
        st_update = model.StopTimeUpdate(nav_stop, departure_delay=None, arrival_delay=None,
                                         dep_status='none', arr_status='none', order=stop_sequence)
        return st_update

    def _make_stoptime_update(self, input_st_update, nav_stop):
        # TODO handle delay uncertainty
        # TODO handle schedule_relationship
        def read_delay(st_event):
            if st_event and st_event.delay:
                return datetime.timedelta(seconds=st_event.delay)
        dep_delay = read_delay(input_st_update.departure)
        arr_delay = read_delay(input_st_update.arrival)
        dep_status = 'none' if dep_delay is None else 'update'
        arr_status = 'none' if arr_delay is None else 'update'
        st_update = model.StopTimeUpdate(nav_stop, departure_delay=dep_delay, arrival_delay=arr_delay,
                                         dep_status=dep_status, arr_status=arr_status,
                                         order=input_st_update.stop_sequence)

        return st_update
