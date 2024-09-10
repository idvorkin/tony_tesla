#!/usr/bin/env python3


import csv
import json
import os
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from uuid import uuid4
import pytz

import dateutil.parser
import httpx
import typer
from icecream import ic
from loguru import logger
from pydantic import BaseModel
from typing import Optional
from rich.console import Console

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


# make this cached
@lru_cache
def get_routes():
    """Load and return routes from routes.csv file."""
    # routes.csv looks like this:
    # route_id,agency_id,route_short_name,route_long_name,route_desc,route_type,route_url,route_color,route_text_color
    # 100001,1,"1","","Kinnear - Downtown Seattle",3,https://kingcounty.gov/en/dept/metro/routes-and-service/schedules-and-maps/001.html,,
    # 100002,1,"10","","Capitol Hill - Downtown Seattle",3,https://kingcounty.gov/en/dept/metro/routes-and-service/schedules-and-maps/010.html,,
    # 100003,1,"101","","Renton Transit Center - Downtown Seattle",3,https://kingcounty.gov/en/dept/metro/routes-and-service/schedules-and-maps/101.html,,
    # 100004,1,"105","","Renton Highlands - Renton Transit Center",3,https://kingcounty.gov/en/dept/metro/routes-and-service/schedules-and-maps/105.html,,
    # 100005,1,"106","","Renton Transit Center - Skyway - Downtown Seattle",3,https://kingcounty.gov/en/dept/metro/routes-and-service/schedules-and-maps/106.html,,
    # 100006,1,"107","","Renton Transit Center - Rainier Beach",3,https://kingcounty.gov/en/dept/metro/routes-and-service/schedules-and-maps/107.html,,
    # 100009,1,"11","","Madison Park - Capitol Hill - Downtown Seattle",3,https://kingcounty.gov/en/dept/metro/routes-and-service/schedules-and-maps/011.html,,

    # loads the routes.csv file into a dict of Routes
    routes = {}
    with open('routes.txt', 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            routes[row['route_short_name']] = Routes(**row)
    return routes

@lru_cache
def get_trip_updates():
    """Load and return trip updates from tripupdates_pb.json file."""
    trip_updates = []
    with open('tripupdates_pb.json', 'r') as file:
        entities = json.load(file)["entity"]
        trip_updates = [entity['trip_update']for entity in entities if entity['trip_update'] is not None]  
        # convert each trip_update to a TripUpdate
        # only load entities which are trip_updates
        ic(trip_updates[0])
        trip_updates = [TripUpdate(**trip_update) for trip_update in trip_updates]
        
    ic(len(trip_updates))
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
    with open('stops.txt', 'r', encoding='utf-8') as file:
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
    for trip_update in trip_updates:
        # do it trip by trip, 
        trips = [trip for trip in trip_updates if trip.trip.route_id == route_id]
        for trip in trips:
            print("# TRIP: ", trip.trip.trip_id, trip.trip.direction_id, trip.trip.)
            for stop_time_update in trip.stop_time_update:
                stop_id = stop_time_update.stop_id
                stop = get_stops()[stop_id]
                stop_name = stop.stop_name
                arrival_time = stop_time_update.arrival.time
                arrival_time_pst = datetime.fromtimestamp(arrival_time).astimezone(pytz.timezone('US/Pacific'))
                # make arrivat time just 07:43 pm
                arrival_time_pst = arrival_time_pst.strftime('%I:%M %p')
                # include the direction_id  
                direction_id = trip_update.trip.direction_id
                print(f"{stop_name} - {arrival_time_pst} - {direction_id}")


@app.command()
def get_latest_data():
    import asyncio

    import httpx

    async def download_file(url, filename):
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            if response.status_code == 200:
                with open(filename, 'wb') as file:
                    file.write(response.content)
            else:
                logger.error(f"Failed to download {filename}. Status code: {response.status_code}")

    urls = [
        ("https://s3.amazonaws.com/kcm-alerts-realtime-prod/tripupdates_pb.json", "tripupdates_pb.json"),
        ("https://s3.amazonaws.com/kcm-alerts-realtime-prod/tripupdates_enhanced.json", "tripupdates_enhanced.json")
    ]

    async def main():
        tasks = [download_file(url, filename) for url, filename in urls]
        await asyncio.gather(*tasks)

    asyncio.run(main())



@logger.catch()
def app_wrap_loguru():
    app()


if __name__ == "__main__":
    app_wrap_loguru()