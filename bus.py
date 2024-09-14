#!/usr/bin/env python3


import csv
import json
import os
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
import pytz

import httpx
import typer
from icecream import ic
from loguru import logger
from pydantic import BaseModel
from rich.console import Console
import onebusaway
import asyncio
import time


console = Console()
app = typer.Typer(no_args_is_help=True)



class Routes(BaseModel):
    route_id: str
    agency_id: str
    route_short_name: str
    route_long_name: str
    route_desc: str
    route_type: str
    route_url: str
    route_color: str
    route_text_color: str


class Stops(BaseModel):
    stop_id: str
    stop_code: str
    stop_name: str
    stop_desc: str
    stop_lat: str
    stop_lon: str
    zone_id: str
    stop_url: str
    location_type: str

class Trip(BaseModel):
    trip_id: str
    route_id: str
    direction_id: int

class Arrival(BaseModel):
    time: int

class Departure(BaseModel):
    time: int

class StopTimeUpdate(BaseModel):
    stop_id: str
    arrival: Arrival | None  = None
    departure: Departure | None = None
    schedule_relationship: str

class Vehicle(BaseModel):
    id: str
    label: str

class TripUpdate(BaseModel):
    trip: Trip
    stop_time_update: list[StopTimeUpdate] 
    vehicle: Vehicle | None = None


# Set the root directory for all file operations
transit_path = Path("modal_readonly/transit")

# make this cached
@lru_cache
def get_routes():
    """Load and return routes from routes.txt file."""
    routes = {}
    with (transit_path / 'routes.txt').open('r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            routes[row['route_short_name']] = Routes(**row)
    return routes

@lru_cache
def get_trip_updates():
    """Load and return trip updates from tripupdates_pb.json file."""
    with (transit_path / 'tripupdates_pb.json').open('r') as file:
        entities = json.load(file)["entity"]
        trip_updates = [entity['trip_update'] for entity in entities if entity['trip_update'] is not None]
        trip_updates = [TripUpdate(**trip_update) for trip_update in trip_updates]
    return trip_updates

@lru_cache
def get_stops():
    """Load and return stops from stops.csv file."""
    # stops.txt looks like this:
    # stop_id,stop_code,stop_name,stop_desc,stop_lat,stop_lon,zone_id,stop_url,location_type,parent_station,stop_timezone,wheelchair_boarding
    # 100,100,"1st Ave & Spring St","",47.6051369,-122.336533,21,,0,,America/Los_Angeles,1
    # 10005,10005,"40th Ave NE & NE 51st St","",47.6658859,-122.284897,1,,0,,America/Los_Angeles,1
    # 10010,10010,"NE 55th St & 39th Ave NE","",47.6685791,-122.285667,1,,0,,America/Los_Angeles,1
    # 10020,10020,"NE 55th St & 37th Ave NE","",47.6685791,-122.2883,1,,0,,America/Los_Angeles,1
    # 10030,10030,"NE 55th St & 35th Ave NE","",47.6685791,-122.290512,1,,0,,America/Los_Angeles,1
    # 10040,10040,"NE 55th St & 33rd Ave NE","",47.6685829,-122.293015,1,,0,,America/Los_Angeles,1
    # 10050,10050,"NE 55th St & 30th Ave NE","",47.6685905,-122.295448,1,,0,,America/Los_Angeles,1

    # loads the stops.txt file into a dict of Stops
    stops = {}
    with (transit_path / 'stops.txt').open('r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            # if there is a failure in a row, skip it
            stop_id = row['stop_id']
            stops[stop_id] = Stops(**row)

    return stops

@app.command()
def stops_for_route(route: str):
    route_id = get_routes()[route].route_id
    trip_updates = get_trip_updates()
    the_route = get_routes()[route]
    tripupdates_for_route = [trip for trip in trip_updates if trip.trip.route_id == route_id and trip.stop_time_update]
    ic(len(tripupdates_for_route))
    # get the route+direction with the most stops

    grouped_by_route_direction = {}
    for trip in tripupdates_for_route:
        grouped_by_route_direction.setdefault(trip.trip.direction_id, []).append(trip)

    longest_update_per_route_direction = {
        direction_id: max(trips, key=lambda x: len(x.stop_time_update))
        for direction_id, trips in grouped_by_route_direction.items()
    }

    for trip in longest_update_per_route_direction.values():
        route_name = f"{the_route.route_short_name} - {the_route.route_desc}"
        print("# ROUTE: ", route_name, trip.trip.direction_id)
        for stop_time_update in trip.stop_time_update:
            stop_id = stop_time_update.stop_id
            stop = get_stops()[stop_id]
            stop_name = stop.stop_name
            if not stop_time_update.arrival:
                continue
            arrival_time = stop_time_update.arrival.time
            arrival_time_pst = datetime.fromtimestamp(arrival_time).astimezone(pytz.timezone('US/Pacific'))
            # make arrivat time just 07:43 pm
            arrival_time_pst = arrival_time_pst.strftime('%I:%M %p')
            # include the direction_id  
            direction_id = trip.trip.direction_id
            print(f"{stop_name} - {arrival_time_pst} - {direction_id} - {stop_id}")

@app.command()
def library_stops():
    client = onebusaway.OnebusawaySDK(
    api_key=os.environ.get("ONEBUSAWAY_API_KEY"),
)
    library_stop_id = "1_29249"
    response = client.arrival_and_departure.list(library_stop_id)
    trips = response.data.entry.arrivals_and_departures
    for trip in trips:
        at_time = trip.predicted_arrival_time / 1000
        at_time_pst = datetime.fromtimestamp(at_time)
        at_time_pst = at_time_pst.strftime('%I:%M %p')
        print(trip.trip_headsign)
        print(at_time_pst)
        #ic(trip)


@app.command()
def get_latest_data():

    async def download_file(url, filename):
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            if response.status_code == 200:
                with open(transit_path / filename, 'wb') as file:
                    file.write(response.content)
            else:
                logger.error(f"Failed to download {filename}. Status code: {response.status_code}")

    urls = [
        ("https://s3.amazonaws.com/kcm-alerts-realtime-prod/tripupdates_pb.json", "tripupdates_pb.json"),
        ("https://s3.amazonaws.com/kcm-alerts-realtime-prod/tripupdates_enhanced.json", "tripupdates_enhanced.json")
    ]

    async def main():
        start = time.time()
        tasks = [download_file(url, filename) for url, filename in urls]
        await asyncio.gather(*tasks)
        end = time.time()
        print(f"Time taken: {end - start} seconds")
    asyncio.run(main())



@logger.catch()
def app_wrap_loguru():
    app()


if __name__ == "__main__":
    app_wrap_loguru()