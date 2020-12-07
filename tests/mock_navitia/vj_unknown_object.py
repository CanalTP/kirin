# coding=utf-8

#  Copyright (c) 2001, Canal TP and/or its affiliates. All rights reserved.
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
from tests.mock_navitia import navitia_response

response = navitia_response.NavitiaResponse()

response.queries = [
    "vehicle_journeys/?depth=2&since=20121120T100000Z&headsign=151515&show_codes=true&until=20121120T170000Z",
    'vehicle_journeys/?filter=vehicle_journey.has_code("rt_piv", "2020-10-22:23188:1187:rail:regionalRail:FERRE")&depth=2&show_codes=true',
    'vehicle_journeys/?filter=vehicle_journey.has_code("rt_piv", "2020-10-22:23188:1180:rail:regionalRail:FEROUTIER")&depth=2&show_codes=true',
    'vehicle_journeys/?filter=vehicle_journey.has_code("rt_piv", "2020-10-22:23188:1190:rail:regionalRail:")&depth=2&show_codes=true',
]

response.response_code = 404

response.json_response = """{
    "disruptions": [],
    "error": {
        "id": "unknown_object",
        "message": "ptref : Filters: Unable to find object"
    }
}
"""
