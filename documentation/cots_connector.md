# COTS Connector

## Overview
Realtime information for long distance trains of the SNCF network is received in a COTS stream. This document describes how a COTS realtime stream is modeled in Kirin.

## Input data description
A realtime COTS stream (link to provide) is obtained as a JSON file via a message queue mechanism. Each feed message represents an update on the information about a train (its status, the associated delay, causes, etc.).

The information concerning the displayed messages related to train modifications is referenced in a separate stream provided by an external web service. The latter returns a text message for all available situations associated with an id referenced in the COTS stream.

## Connector description
This document doesn't describe all the fields of the Kirin model. Only COTS relevant fields are described below. For example, the RealTimeUpdate.id field is managed by Kirin and is not detailed in the present specification.

### RealTimeUpdate

Kirin property | COTS object/value | Comment/Mapping rule
--- | --- | ---
connector |  | Fixed value `cots`
raw_data | _Complete received feed_ | 
contributor |  | Fixed value specified in the configuration of Kirin
trip_updates |  | List of trip updates information, see `TripUpdates` below

### TripUpdate
Kirin property | COTS object/value | Comment/Mapping rule
--- | --- | ---
vj_id | | Id of the `VehicleJourney` in Navitia updated by this `TripUpdate`. A COTS feed can udpate more than one `VehicleJourney`, see below for the mapping method
status | *nouvelleVersion/statutOperationnel* | If the value of *nouvelleVersion/statutOperationnel* is "AJOUTEE", this field value is `add`.<br/>If the value of *nouvelleVersion/statutOperationnel* is "SUPPRIMEE", then this field value is `delete`.<br/>If *nouvelleVersion/statutOperationnel* is empty or has the value "PERTURBEE", then this field value is `update`.
message | *nouvelleVersion/idMotifInterneReference* | The label of the message is referenced in the separate feed returned by the SNCF web service by the id that matches the value of *nouvelleVersion/idMotifInterneReference*
contibutor |  | Fixed value specified in the configuration of Kirin
stop_time_updates |  | List of arrival/departure time updates at stops for this trip, see `StopTimeUpdates` below
