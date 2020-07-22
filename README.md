# ESPN-Scoreboard
API that scrapes ESPN Scoreboard

Access via http://localhost:EXTERNAL-PORT/:sport_name/:date

Blank date defaults to the current date

Supported Sports
* "mlb"
* "nba"
* "ncaam" (Men's College Basketball, only Top 25 Teams) 
* "ncaaf" (Men's College Football)
* "nfl"

Example Docker-Compose File

     espn-scoreboard:
        container_name: espn-scoreboard
        image: espn-scoreboard
        build:
            dockerfile: ./espn-scoreboard/Dockerfile
            context: ./espn-scoreboard
        ports:
            - EXTERNAL-PORT:80
        environment:
            - WEB_ROOT=/
        restart: unless-stopped
