import json
import logging
import os
import sys
import re

import pytz
import requests
from datetime import datetime, timedelta
from flask import Flask, abort, render_template, url_for, redirect, request
from typing import Any

base_url = "https://www.espn.com"

leagues = {
	"mlb": "mlb",
	"nba": "nba",
	"nfl": "nfl",
	"nhl": "nhl",
	"ncaam": "mens-college-basketball",
	"ncaaf": "college-football",
}

app = Flask(__name__)

formatter = logging.Formatter('%(asctime)s - %(levelname)10s - %(module)15s:%(funcName)30s:%(lineno)5s - %(message)s')
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
consoleHandler = logging.StreamHandler(sys.stdout)
consoleHandler.setFormatter(formatter)
logger.addHandler(consoleHandler)
logger.setLevel(os.environ['LOG_LEVEL'].upper())
logging.getLogger("requests").setLevel(logging.WARNING)


@app.route("/")
def root():
	logger.info(request.path)
	return redirect(url_for('index'))


@app.route(os.environ['WEB_ROOT'])
def index(web_root=os.environ['WEB_ROOT']):
	logger.info(request.path)
	try:
		return render_template('index.html', WEB_ROOT=web_root)
	except Exception as e:
		logger.error('Error on line {} {} {}'.format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e))
		abort(404)


@app.route(os.environ['WEB_ROOT'] + 'raw/<league>/', defaults={'game_date': None, 'raw': True})
@app.route(os.environ['WEB_ROOT'] + 'raw/<league>/<game_date>/', defaults={'raw': True})
@app.route(os.environ['WEB_ROOT'] + '<league>/', defaults={'game_date': None, 'raw': False})
@app.route(os.environ['WEB_ROOT'] + '<league>/<game_date>/', defaults={'raw': False})
def scoreboard(league, game_date, raw):
	try:
		if game_date is None:
			game_date = datetime.today().replace(tzinfo=pytz.UTC).astimezone(
				pytz.timezone(os.environ['TZ'])).strftime("%Y%m%d")
		datetime.strptime(game_date, '%Y%m%d')
	except ValueError:
		return "Invalid Date Format. Should be YYYYMMDD"
	except Exception as e:
		logger.error('Error on line {} {} {}'.format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e))
		return "Invalid League. Please choose MLB, NBA, NFL, NHL, NCAAM or NCAAF"

	url = format_url(league, game_date)

	logger.debug("Fetching Data from %s" % url)
	data = requests.get(url)
	events_raw = league_events(league, data)
	logger.info((league, game_date, raw, url, type(events_raw)))
	events_raw['date'] = game_date
	if raw:
		events = fix_json(events_raw)
	else:
		if league in ('nhl', 'nfl', 'ncaaf'):
			events = clean_alternate(events_raw)
		else:
			events = clean_default(events_raw)
	return json.dumps(events)


def nfl_start_week():
	url = "https://www.espn.com/nfl/scoreboard"
	data = league_events('nfl', requests.get(url))
	calendar = data['events'][0]['watchListen']['cmpttn']['lg']['calendar']
	for x in calendar:
		if x['label'] == 'Regular Season':
			return datetime.strptime(x['startDate'], '%Y-%m-%dT%I:%MZ')


def fix_json(data):
	for game in data['events']:
		if 'watchListen' in game:
			del game['watchListen']
	return data


def format_url(league, game_date):
	try:
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
	except Exception as e:
		logger.error('Error on line {} {} {}'.format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e))
		return "Invalid League. Please choose MLB, NBA, NFL, NHL, NCAAM or NCAAF"


def league_events(league, original_data):
	try:
		if league in ('nhl', 'nfl', 'ncaaf'):
			start = original_data.text.find('"scoreboard":{"league":{') + 13
			end = original_data.text.find(',"transition"', start + 1)-1
			data = original_data.text[start:end].replace(";", "").strip()
			events = json.loads(data)['evts']
		else:
			start = original_data.text.find("<script>window.espn.scoreboardData") + 38
			end = original_data.text.find("</script>", start - 1)
			data = original_data.text[start:end].replace(";", "").replace("window.espn.scoreboardData", "").replace(
				"if(!window.espn_ui.device.isMobile){window.espn.loadType = \"ready\"};", "").split(
				"window.espn.scoreboardSettings")[0].strip()
			events = json.loads(data)['events']
	except Exception as e:
		logger.error('Error on line {} {} {}'.format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e))
		events = {}
	return {'events': events}


def clean_default(data):
	try:
		game: Any
		for game in data['events']:
			game['teams'] = {}
			game['broadcast'] = {}
			for x in range(0, 2):
				game['teams'][game['competitions'][0]['competitors'][x]['homeAway']] = \
					game['competitions'][0]['competitors'][x]['team']
				game['teams'][game['competitions'][0]['competitors'][x]['homeAway']]['score'] = \
					game['competitions'][0]['competitors'][x]['score']
				if 'records' in game['competitions'][0]['competitors'][x]:
					for teams in game['competitions'][0]['competitors'][x]['records']:
						if teams['type'] == 'total':
							game['teams'][game['competitions'][0]['competitors'][x]['homeAway']]['standing'] = \
								game['competitions'][0]['competitors'][x]['records'][0]['summary']

			game['status']['state'] = game['status']['type']['state']
			game['status']['detail'] = game['status']['type']['detail']
			game['status']['shortDetail'] = game['status']['type']['shortDetail']
			game['status']['completed'] = game['status']['type']['completed']
			game['venue'] = game['competitions'][0]['venue']

			try:
				game['broadcast'] = game['competitions'][0]['broadcasts'][0]
			except IndexError:
				pass
			except KeyError:
				pass
			except Exception as e:
				logger.error('Error on line {} {} {}'.format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e))

			del game['season']
			del game['uid']
			del game['id']
			del game['links']
			del game['competitions']
			del game['status']['type']
			del game['status']['displayClock']

			for x in ['home', 'away']:
				del game['teams'][x]['links']
				del game['teams'][x]['id']
				del game['teams'][x]['uid']
				del game['teams'][x]['isActive']
				if 'name' in game['teams'][x]:
					del game['teams'][x]['name']
	except Exception as e:
		logger.error('Error on line {} {} {}'.format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e))
		data = {}

	return data


def clean_alternate(data):
	try:
		for game in data['events']:
			try:
				game['teams'] = {}
				for x in range(0, 2):
					try:
						game['teams']['home' if game['competitors'][x]['isHome'] else 'away'] = game['competitors'][x]

						if 'records' in game['competitors'][x]:
							for teams in game['competitors'][x]['records']:
								try:
									teams = teams[0]
								except KeyError:
									pass
								except Exception as e:
									logger.error('Error on line {} {} {}'.format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e))

								if teams:
									if teams['type'] == 'total':
										game['teams']['home' if game['competitors'][x]['isHome'] else 'away']['standing'] = \
											game['competitors'][x]['records'][0]['summary']
					except Exception as e:
						logger.error('Error on line {} {} {}'.format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e))

				game["name"] = game['teams']['away']['displayName'] + " at " + game['teams']['home']['displayName']
				game["shortName"] = game['teams']['away']['abbrev'] + " @ " + game['teams']['home']['abbrev']

				try:
					(clock, period) = game['status']['detail'].split(' - ')
					game['status']['period'] = re.sub("[^0-9]", "", period)
					game['status']['clock'] = clock
				except ValueError:
					game['status']['period'] = 0
					game['status']['clock'] = 0
				except Exception as e:
					logger.error('Error on line {} {} {}'.format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e))
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
					remove_element(game['teams'][x], 'recordSummary')
					remove_element(game['teams'][x], 'standingSummary')
					remove_element(game['teams'][x], 'isHome')
					remove_element(game['teams'][x], 'links')
					remove_element(game['teams'][x], 'records')
					remove_element(game['teams'][x], 'uid')

					game['teams'][x]['abbreviation'] = remove_element(game['teams'][x], 'abbrev')
					game['teams'][x]['alternateColor'] = remove_element(game['teams'][x], 'altColor')
					game['teams'][x]['color'] = remove_element(game['teams'][x], 'teamColor')

				remove_element(game['weather'], 'weatherLink')

				remove_element(game, 'watchListen')
				remove_element(game, 'tbd')
				remove_element(game, 'link')
				remove_element(game, 'links')
				remove_element(game, 'isTie')
				remove_element(game, 'tcktsAvail')
				remove_element(game, 'hdeScrDte')
				remove_element(game, 'tmInfo')
				remove_element(game, 'allStr')
				remove_element(game, 'gmeTmeFrmt')
				remove_element(game, 'rcpDta')
				remove_element(game, 'lnescrs')
				remove_element(game, 'tckts')
				remove_element(game, 'ldrs')
				remove_element(game, 'intlDate')
				remove_element(game, 'broadcasts')
				remove_element(game, 'league')
				remove_element(game, 'prfrmrTtl')
				remove_element(game, 'highlight')
				remove_element(game, 'highlights')
				remove_element(game, 'odds')
				remove_element(game, 'day')
				remove_element(game, 'month')
				remove_element(game, 'time')
				remove_element(game, 'hideScoreDate')
				remove_element(game, 'tickets')
				remove_element(game, 'competitors')
			except Exception as e:
				logger.error('Error on line {} {} {}'.format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e))
	except Exception as e:
		logger.error('Error on line {} {} {}'.format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e))
		data = {}

	return data


def remove_element(dict_temp, key):
	try:
		if dict_temp:
			return dict_temp.pop(key)
	except KeyError:
		pass
	except Exception as e:
		logger.info((dict_temp, key))
		logger.error('Error on line {} {} {}'.format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e))


start_week = nfl_start_week()


if __name__ == "__main__":
	app.run(host="0.0.0.0", port=8765, debug=True)
