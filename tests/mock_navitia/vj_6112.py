# coding=utf-8
# Copyright (c) 2001-2015, Canal TP and/or its affiliates. All rights reserved.
#
# This file is part of Navitia,
# the software to build cool stuff with public transport.
#
# powered by Canal TP (www.canaltp.fr).
# Help us simplify mobility and open public transport:
# a non ending quest to the responsive locomotion way of traveling!
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
import navitia_response

response = navitia_response.NavitiaResponse()

response.query = 'vehicle_journeys/?depth=2&since=20151006T121600&headsign=6112&show_codes=true&until=20151006T173400'

response.response_code = 404

response.json_response = """{
    "disruptions": [],
    "error": {
        "id": "unknown_object",
        "message": "ptref : Filters: Unable to find object"
    }
}
"""