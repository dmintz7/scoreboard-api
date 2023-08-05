import json
import logging
import os
import sys
import re

import pytz
import requests
from datetime import datetime, timedelta
from flask import Flask, render_template

base_url = "https://www.espn.com"

leagues = {
	"mlb": "mlb",
	"nba": "nba",
	"nfl": "nfl",
	"nhl": "nhl",
	"ncaam": "mens-college-basketball",
	"ncaaf": "college-football",
}

headers = {'User-Agent': 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36'}

app = Flask(__name__)

formatter = logging.Formatter('%(asctime)s - %(levelname)10s - %(module)15s:%(funcName)30s:%(lineno)5s - %(message)s')
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
consoleHandler = logging.StreamHandler(sys.stdout)
consoleHandler.setFormatter(formatter)
logger.addHandler(consoleHandler)
logger.setLevel(os.environ['LOG_LEVEL'].upper())
logging.getLogger("requests").setLevel(logging.WARNING)

if os.environ['WEB_ROOT'][-1] != "/":
	os.environ['WEB_ROOT'] += "/"

@app.route("/")
@app.route(os.environ['WEB_ROOT'])
def index(web_root=os.environ['WEB_ROOT']):
	return render_template('index.html', WEB_ROOT=web_root)


@app.route(os.environ['WEB_ROOT'] + 'raw/<league>/', defaults={'game_date': None, 'raw': True})
@app.route(os.environ['WEB_ROOT'] + 'raw/<league>/<game_date>/', defaults={'raw': True})
@app.route(os.environ['WEB_ROOT'] + '<league>/', defaults={'game_date': None, 'raw': False})
@app.route(os.environ['WEB_ROOT'] + '<league>/<game_date>/', defaults={'raw': False})
def scoreboard(league, game_date, raw):
	try:
		if game_date is None:
			game_date = datetime.today().replace(tzinfo=pytz.UTC).astimezone(pytz.timezone(os.environ['TZ'])).strftime("%Y%m%d")
		datetime.strptime(game_date, '%Y%m%d')
	except ValueError:
		return "Invalid Date Format. Should be YYYYMMDD"

	if not valid_league(league):
		return "Invalid League. Please choose MLB, NBA, NFL, NHL, NCAAM or NCAAF"

	url = format_url(league, game_date)

	logger.debug("Fetching Data from %s" % url)
	data = requests.get(url, headers=headers)
	events_raw = get_events(data)
	logger.debug((league, game_date, raw, url, type(events_raw)))
	events_raw['date'] = game_date
	if raw:
		events = fix_json(events_raw)
	else:
		events = clean_json(events_raw)
	return json.dumps(events)


def nfl_start_week():
	url = "https://www.espn.com/nfl/scoreboard"
	data = get_events(requests.get(url, headers=headers))
	calendar = data['events'][0]['watchListen']['cmpttn']['lg']['calendar']
	for x in calendar:
		if x['label'] == 'Regular Season':
			return datetime.strptime(x['startDate'], '%Y-%m-%dT%I:%MZ')


def fix_json(data):
	for game in data['events']:
		if 'watchListen' in game:
			del game['watchListen']
	return data

def valid_league(league):
	try:
		leagues[league]
		return True
	except KeyError:
		return False


def format_url(league, game_date):
	espn_league = leagues[league]
	if league == 'nfl':
		this_week = datetime.strptime(game_date, '%Y%m%d')+timedelta(days=1)
		week_num = this_week.isocalendar()[1] - start_week.isocalendar()[1]
		if start_week > this_week:
			week_num = 5 + week_num
			season = "1"
		else:
			season = "2"
		url = "%s/%s/scoreboard/_/year/%s/seasontype/%s/week/%s" % (base_url, espn_league, start_week.year, season, week_num)
	else:
		url = "%s/%s/scoreboard/_/date/%s" % (base_url, espn_league, game_date)
	return url


def get_events(original_data):
	start = original_data.text.find('"scoreboard":{"league":{') + 13
	end = original_data.text.find(',"transition"', start + 1)-1
	data = original_data.text[start:end].replace(";", "").strip()
	events = json.loads(data)['evts']
	return {'events': events}


def clean_json(data):
	for game in data['events']:
		for team in game['competitors']:
			try:
				if team['score'] == "":
					team['score'] = team['runs']
					del team['runs']
			except KeyError:
				pass

		game['teams'] = {}
		for x in range(0, 2):
			game['teams']['home' if game['competitors'][x]['isHome'] else 'away'] = game['competitors'][x]

			if 'records' in game['competitors'][x]:
				for teams in game['competitors'][x]['records']:
					try:
						teams = teams[0]
					except KeyError:
						pass

					if teams:
						if teams['type'] == 'total':
							game['teams']['home' if game['competitors'][x]['isHome'] else 'away']['standing'] = \
								game['competitors'][x]['records'][0]['summary']

		game["name"] = game['teams']['away']['displayName'] + " at " + game['teams']['home']['displayName']
		game["shortName"] = game['teams']['away']['abbrev'] + " @ " + game['teams']['home']['abbrev']

		try:
			(clock, period) = game['status']['detail'].split(' - ')
			game['status']['period'] = re.sub("[^0-9]", "", period)
			game['status']['clock'] = clock
		except ValueError:
			game['status']['period'] = 0
			game['status']['clock'] = 0

		remove_element(game, 'onWatch')
		game['weather'] = remove_element(game, 'wthr')
		game['lastPlay'] = remove_element(game, 'lstPly')
		game['situation'] = remove_element(game, 'situation')
		game['venue'] = remove_element(game, 'vnue')
		game['status']['completed'] = remove_element(game, 'completed')
		game['status']['shortDetail'] = remove_element(game['status'], 'detail')

		try:
			temp_text = remove_element(game['metadata'], 'downDistanceText')
			remove_element(game, 'metadata')
			game['situation']['downDistanceText'] = temp_text
		except KeyError:
			pass

		if len(game['broadcasts']) > 0:
			game['broadcasts'] = game['broadcasts'][0]

		for x in ['home', 'away']:
			for element in ['recordSummary', 'standingSummary', 'isHome', 'links', 'records', 'uid']:
				remove_element(game['teams'][x], element)

			for element in ['abbrev', 'altColor', 'teamColor']:
				game['teams'][x]['abbreviation'] = remove_element(game['teams'][x], element)

		remove_element(game['weather'], 'weatherLink')
		for element in ['watchListen', 'tbd', 'link', 'links', 'isTie', 'tcktsAvail', 'hdeScrDte', 'tmInfo', 'allStr', 'gmeTmeFrmt', 'rcpDta', 'lnescrs', 'tckts', 'ldrs', 'intlDate', 'league', 'prfrmrTtl', 'highlight', 'highlights', 'odds', 'day', 'month', 'time', 'hideScoreDate', 'tickets', 'competitors']:
			remove_element(game, element)

	return data

def remove_element(dict_temp, key):
	try:
		if dict_temp:
			return dict_temp.pop(key)
	except KeyError:
		pass


start_week = nfl_start_week()