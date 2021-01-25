import os, requests, json, pytz
from flask import Flask, abort, render_template
from datetime import datetime

base_url = "https://www.espn.com"

leagues = {
	"mlb": "mlb",
	"nba": "nba",
	"nfl": "nfl",
	"nhl": "nhl",
	"ncaam": "mens-college-basketball",
	"ncaaf": "college-football",
};

app = Flask(__name__)

@app.route(os.environ['WEB_ROOT'])
def index():
	try:
		return render_template('index.html', WEB_ROOT=os.environ['WEB_ROOT'])
	except:
		abort(404)
		
@app.route(os.environ['WEB_ROOT'] + '<league>/', defaults={'game_date': None})
@app.route(os.environ['WEB_ROOT'] + '<league>/<game_date>/')
def scoreboard(league, game_date):
	try:
		if game_date is None: game_date = datetime.today().replace(tzinfo=pytz.UTC).astimezone(pytz.timezone(os.environ['TIME_ZONE'])).strftime("%Y%m%d")
		datetime.strptime(game_date, '%Y%m%d')
	except ValueError:
		return "Invalid Date Format. Should be YYYYMMDD"
		
	try:
		espn_league = leagues[league]
	except:
		return "Invalid League. Please choose MLB, NBA, NFL, NHL, NCAAM or NCAAF"
		
	if league == 'nfl':
		week_num = datetime.strptime(game_date, '%Y%m%d').isocalendar()[1] - datetime.strptime(os.environ['NFL_WEEK_1_START'], '%Y%m%d').isocalendar()[1] + 1
		if datetime.strptime(os.environ['NFL_WEEK_1_START'], '%Y%m%d') > datetime.strptime(game_date, '%Y%m%d'):
			week_num = 5 + week_num
			season = "1"
		else:
			season = "2"
		url = base_url + "/" + espn_league + "/scoreboard/_/year/2020/seasontype/" + season + "/week/" + str(week_num)
	else:
		url = base_url + "/" + espn_league + "/scoreboard/_/date/" + game_date
	
	data = requests.get(url)
	if league == 'nhl':
		json_data = cleanNHL(data)
	else:
		json_data = cleanDefault(data)

	return json.dumps(json_data)
	
def cleanDefault(data):
	start = data.text.find("<script>window.espn.scoreboardData")+38
	end = data.text.find("</script>", start - 1)
	data = data.text[start:end].replace(";","").replace("window.espn.scoreboardData","").replace("if(!window.espn_ui.device.isMobile){window.espn.loadType = \"ready\"};","").split("window.espn.scoreboardSettings")[0].strip()
	try:
		json_data = json.loads(data)['events']
		for game in json_data:
			game['teams'] = {}
			for x in range(0,2):
				game['teams'][game['competitions'][0]['competitors'][x]['homeAway']] = game['competitions'][0]['competitors'][x]['team']
				game['teams'][game['competitions'][0]['competitors'][x]['homeAway']]['score'] = game['competitions'][0]['competitors'][x]['score']
				if 'records' in game['competitions'][0]['competitors'][x]:
					for teams in game['competitions'][0]['competitors'][x]['records']:
						if teams['type'] == 'total': game['teams'][game['competitions'][0]['competitors'][x]['homeAway']]['standing'] = game['competitions'][0]['competitors'][x]['records'][0]['summary']
			
			game['status']['state'] = game['status']['type']['state']
			game['status']['detail'] = game['status']['type']['detail']
			game['status']['shortDetail'] = game['status']['type']['shortDetail']
			game['status']['completed'] = game['status']['type']['completed']
			
			if len(game['competitions'][0]['broadcasts']) > 0: game['broadcast'] = game['competitions'][0]['broadcasts'][0]
			del game['season']
			del game['uid']
			del game['id']
			del game['links']
			del game['competitions']
			del game['status']['type']
			del game['status']['displayClock']
			
			for x in ['home','away']:
				del game['teams'][x]['links']
				del game['teams'][x]['id']
				del game['teams'][x]['uid']
				del game['teams'][x]['isActive']
				if 'name' in game['teams'][x]: del game['teams'][x]['name']
	except:
		json_data = {}

	return json_data
	
def cleanNHL(data):
	start = data.text.find(" <script type='text/javascript' >window['__espnfitt__']")+56
	end = data.text.find("</script>", start - 1)
	data = data.text[start:end].replace(";","").strip()
	try:
		json_data = json.loads(data)['page']['content']['scoreboard']['events'][0]
		for game in json_data:
			game['teams'] = {}
			for x in range(0,2):
				try:
					game['teams']['home' if game['competitors'][x]['isHome'] else 'away'] = game['competitors'][x]
					if 'records' in game['competitors'][x]:
						for teams in game['competitors'][x]['records']:
							if teams['type'] == 'total': game['teams']['home' if game['competitors'][x]['isHome'] else 'away']['standing'] = game['competitors'][x]['records'][0]['summary']
				except:
					pass
			
			game["name"] = game['teams']['away']['displayName'] + " at " + game['teams']['home']['displayName']
			game["shortName"] = game['teams']['away']['abbrev'] + " @ " + game['teams']['home']['abbrev']
			
			if len(game['broadcasts']) > 0: game['broadcast'] = game['broadcasts'][0]
			del game['id']
			del game['competitors']
			if 'tbd' in game: del game['tbd']
			if 'link' in game: del game['link']
			if 'note' in game: del game['note']
			if 'completed' in game: del game['completed']
			if 'tickets' in game: del game['tickets']
			if 'links' in game: del game['links']
			if 'hideScoreDate' in game: del game['hideScoreDate']
			if 'teamInfo' in game: del game['teamInfo']
			if 'allStar' in game: del game['allStar']
			if 'odds' in game: del game['odds']
			if 'highlights' in game: del game['highlights']
			if 'day' in game: del game['day']
			if 'month' in game: del game['month']
			if 'watchListen' in game: del game['watchListen']
			if 'leaders' in game: del game['leaders']
			if 'gameTimeFormat' in game: del game['gameTimeFormat']
			if 'performerTitle' in game: del game['performerTitle']
			if 'time' in game: del game['time']
			
			del game['status']['id']
			del game['status']['description']
			game['status']['shortDetail'] = game['status']['detail']

			for x in ['home','away']:
				del game['teams'][x]['recordSummary']
				del game['teams'][x]['standingSummary']
				del game['teams'][x]['isHome']
				del game['teams'][x]['links']
				del game['teams'][x]['records']
				del game['teams'][x]['id']
				del game['teams'][x]['uid']
			
				game['teams'][x]['abbreviation'] = game['teams'][x]['abbrev']
				game['teams'][x]['alternateColor'] = game['teams'][x]['altColor']
				game['teams'][x]['color'] = game['teams'][x]['teamColor']
				
				del game['teams'][x]['abbrev']
				del game['teams'][x]['altColor']
				del game['teams'][x]['teamColor']
	except:
		json_data = {}

	return json_data