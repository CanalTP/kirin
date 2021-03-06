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
import logging
from datetime import datetime

import six
import ujson
from aniso8601 import parse_date
from dateutil import parser
from pythonjsonlogger import jsonlogger
from flask.globals import current_app
from pytz import utc

from kirin import new_relic
from redis.exceptions import ConnectionError
from contextlib import contextmanager
from kirin.core import model
from kirin.core.model import RealTimeUpdate
from kirin.exceptions import InternalException, InvalidArguments
import requests

from kirin.new_relic import must_never_log, record_exception


def floor_datetime(datetime):
    return datetime.replace(minute=0, second=0, microsecond=0)


def str_to_date(value):
    if not value:
        return None
    try:
        return parse_date(value)
    except:
        logging.getLogger(__name__).info("[{value} invalid date.".format(value=value))
        return None


def as_utc_naive_dt(str_time):
    try:
        return (
            parser.parse(str_time, dayfirst=False, yearfirst=True, ignoretz=False)
            .astimezone(utc)
            .replace(tzinfo=None)
        )
    except Exception as e:
        raise InvalidArguments(
            'Impossible to parse timezoned datetime from "{s}": {m}'.format(s=str_time, m=e.message)
        )


def get_value(sub_json, key, nullable=False):
    """
    get a unique element in an json dict
    raise an exception if the element does not exists
    """
    res = sub_json.get(key)
    if res is None and not nullable:
        raise InvalidArguments(
            'invalid json, impossible to find "{key}" in json dict {elt}'.format(
                key=key, elt=ujson.dumps(sub_json)
            )
        )
    return res


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """
    jsonformatter with extra params

    you can add additional params to it (like the environment name) at configuration time
    """

    def __init__(self, *args, **kwargs):
        self.extras = kwargs.pop("extras", {})
        jsonlogger.JsonFormatter.__init__(self, *args, **kwargs)

    def process_log_record(self, log_record):
        log_record.update(self.extras)
        return log_record


def to_navitia_utc_str(naive_utc_dt):
    """
    format a naive UTC datetime to a navitia-readable UTC-aware str
    (to avoid managing coverage's timezone,
    as Navitia considers datetime without timezone as local to the coverage)
    """
    if naive_utc_dt.tzinfo is not None:
        raise InternalException("Invalid datetime provided: must be naive (and UTC)")
    return naive_utc_dt.strftime("%Y%m%dT%H%M%SZ")


def as_duration(seconds):
    """
    transform a number of seconds into a timedelta
    >>> as_duration(None)

    >>> as_duration(900)
    datetime.timedelta(0, 900)
    >>> as_duration(-400)
    datetime.timedelta(-1, 86000)
    >>> as_duration("bob")
    Traceback (most recent call last):
    TypeError: a float is required
    """
    if seconds is None:
        return None
    return datetime.utcfromtimestamp(seconds) - datetime.utcfromtimestamp(0)


def db_commit(orm_object):
    """
    receive an ORM object (from model.py) and persist it in the database
    """
    model.db.session.add(orm_object)
    model.db.session.commit()


def make_rt_update(raw_data, connector_type, contributor_id, status="OK"):
    """
    Create an RealTimeUpdate object for the query and persist it
    """
    rt_update = model.RealTimeUpdate(
        raw_data, connector_type=connector_type, contributor_id=contributor_id, status=status
    )
    new_relic.record_custom_parameter("real_time_update_id", rt_update.id)

    db_commit(rt_update)
    return rt_update


def record_input_retrieval(contributor, duration_ms, **kwargs):
    params = {"duration": duration_ms, "contributor": contributor}
    params.update(kwargs)
    logging.getLogger(__name__).info("Input retrieval", extra=params)
    new_relic.record_custom_event("kirin_input_retrieval", params)


def record_internal_failure(log, **kwargs):
    params = {"log": log}
    params.update(kwargs)
    new_relic.record_custom_event("kirin_internal_failure", params)


def record_call(status, **kwargs):
    """
    status can be in: ok, warning, a message text or failure with reason.
    parameters: contributor, timestamp, trip_update_count, size...
    """
    params = {"status": status}
    params.update(kwargs)
    new_relic.record_custom_event("kirin_status", params)


def should_retry_exception(exception):
    return isinstance(exception, ConnectionError)


def make_kirin_lock_name(*args):
    from kirin import app

    return "|".join([app.config[str("TASK_LOCK_PREFIX")]] + [a for a in args])


def make_kirin_last_call_dt_name(*args):
    from kirin import app

    return "|".join([app.config[str("TASK_LAST_CALL_DATETIME_PREFIX")]] + [a for a in args])


def build_redis_etag_key(contributor):
    # type: (unicode) -> unicode
    return "|".join([contributor, "polling_HEAD"])


def allow_reprocess_same_data(contributor_id):
    # type: (unicode) -> None
    from kirin import redis_client

    redis_client.delete(build_redis_etag_key(contributor_id))  # wipe previous' ETag memory


def set_rtu_status_ko(rtu, error, is_reprocess_same_data_allowed):
    # type: (RealTimeUpdate, unicode, bool) -> None
    """
    Set RealTimeUpdate's status to KO, handling all in one
    except commit and logs
    :param rtu: RealTimeUpdate object to amend
    :param error: error message to associate to RTU
    :param is_reprocess_same_data_allowed: If the same input is provided next time, should we
    reprocess it (hoping a happier ending)
    """
    if is_reprocess_same_data_allowed:
        allow_reprocess_same_data(rtu.contributor_id)

    rtu.status = "KO"
    rtu.error = error


def save_rt_data_with_error(data, connector_type, contributor_id, error, is_reprocess_same_data_allowed):
    """
    Create and save RTU using given data, connector, contributor with a status KO
    :param data: realtime input
    :param connector_type: connector type
    :param contributor_id: contributor id
    :param error: error message to associate to RTU
    :param is_reprocess_same_data_allowed: If the same input is provided next time, should we
    reprocess it (hoping a happier ending)
    """
    raw_data = six.binary_type(data)
    rt_update = make_rt_update(raw_data, connector_type=connector_type, contributor_id=contributor_id)
    set_rtu_status_ko(rt_update, error, is_reprocess_same_data_allowed)
    db_commit(rt_update)
    return rt_update


def poke_updated_at(rtu):
    """
    just update the updated_at of the RealTimeUpdate object provided
    """
    if rtu:
        status = rtu.status
        rtu.status = "pending" if status != "pending" else "OK"  # just to poke updated_at
        model.db.session.commit()
        rtu.status = status
        model.db.session.commit()


def manage_db_error(data, connector_type, contributor_id, error, is_reprocess_same_data_allowed):
    """
    If the last RTUpdate contains the same error (and data, status) we just change updated_at:
    This way, we know we had this error between created_at and updated_at, but we don't get extra rows in db

    Otherwise, we create a new one, as we want to track error changes

    :param is_reprocess_same_data_allowed: If the same input is provided next time, should we
    reprocess it (hoping a happier ending)
    """
    last = model.RealTimeUpdate.get_last_rtu(connector_type, contributor_id)
    if last and last.status == "KO" and last.error == error and last.raw_data == six.binary_type(data):
        poke_updated_at(last)
        if is_reprocess_same_data_allowed:
            allow_reprocess_same_data(contributor_id)
    else:
        last = save_rt_data_with_error(
            data, connector_type, contributor_id, error, is_reprocess_same_data_allowed
        )
    return last


def manage_db_no_new(connector_type, contributor_id):
    last = model.RealTimeUpdate.get_last_rtu(connector_type, contributor_id)
    poke_updated_at(last)


def can_connect_to_navitia():
    try:
        response = requests.head(current_app.config[str("NAVITIA_URL")], timeout=1)
        return response.status_code == 200
    except Exception:
        return False


def can_connect_to_database():
    try:
        engine = model.db.engine
        connection = engine.connect()
        connection.close()
    except Exception:
        return False
    return True


def get_database_version():
    try:
        return model.db.engine.scalar("select version_num from alembic_version;")
    except Exception:
        return None


def get_database_info():
    try:
        return model.RealTimeUpdate.get_probes_by_contributor()
    except Exception:
        return {"last_update": {}, "last_valid_update": {}, "last_update_error": {}}


def get_database_pool_status():
    try:
        return model.db.engine.pool.status()
    except Exception:
        return None


@contextmanager
def get_lock(logger, lock_name, lock_timeout):
    from kirin import redis_client

    logger.debug("getting lock %s", lock_name)
    try:
        lock = redis_client.lock(lock_name, timeout=lock_timeout)
        locked = lock.acquire(blocking=False)
    except ConnectionError:
        logging.exception("Exception with redis while locking")
        raise

    try:
        yield locked
    finally:
        if locked:
            logger.debug("releasing lock %s", lock_name)
            lock.release()


def log_exception(exception, exception_source):
    """
    log all exceptions
    """
    logger = logging.getLogger(__name__)
    message = ""
    if hasattr(exception, "data"):
        message = exception.data
    error = "{ex}: {data} - {orig}".format(ex=exception.__class__.__name__, data=message, orig=exception_source)

    if must_never_log(exception):
        logger.debug(error)
    else:
        logger.exception(error)

    # Record all exceptions by default
    # See CONTRIBUTING.md for newrelic's error filtering
    record_exception()
