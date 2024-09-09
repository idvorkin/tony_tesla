Lets add bus support for Toni, only works in Seattle for now.

Real time Data Feed

<https://kingcounty.gov/en/dept/metro/rider-tools/mobile-and-web-apps#toc-developer-resources/>

Buses of Interest - from routes.txt

The route 48 is 100228

```csv
route_id,agency_id,route_short_name,route_long_name,route_desc,route_type,route_url,route_color,route_text_color
100228,1,"48","","Mt Baker - University District",3,https://kingcounty.gov/en/dept/metro/routes-and-service/schedules-and-maps/048.html,,
```

Trim to the trips for route 48

```zsh
cat tripupdates_pb.json | jq '.entity[] | select(.trip_update.trip.route_id == "100228")' > trim.json
```

Get all the stops

```zsh
cat tripupdates_pb.json | jq '.entity[] |
select(.trip_update.trip.route_id == "100228") |
.trip_update.stop_time_update[].stop_id' |
sort -u
```
