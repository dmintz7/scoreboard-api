import os, requests, json
from flask import Flask, abort, render_template
from datetime import datetime

base_url = "https://www.espn.com"

leagues = {
	"mlb": "mlb",
	"nba": "nba",
	"nfl": "nfl",
	"ncaam": "mens-college-basketball",
	"ncaaf": "college-football",
};

app = Flask(__name__)

@app.route(os.environ['WEB_ROOT'], strict_slashes=False)
def index():
	try:
		return render_template('index.html', WEB_ROOT=os.environ['WEB_ROOT'])
	except:
		abort(404)
		
@app.route(os.environ['WEB_ROOT'] + '<league>', defaults={'game_date': datetime.today().strftime("%Y%m%d")})
@app.route(os.environ['WEB_ROOT'] + '<league>' + '/<game_date>')
def scoreboard(league, game_date):
	try:
		datetime.strptime(game_date, '%Y%m%d')
	except ValueError:
		return "Invalid Date Format. Should be YYYYMMDD"
		
	try:
		espn_league = leagues[league]
	except:
		return "Invalid League. Please choose MLB, NBA, NFL, NCAAM or NCAAF"
	
	url = base_url + "/" + espn_league + "/scoreboard/_/date/" + game_date
	r = requests.get(url)
	start = r.text.find("<script>window.espn.scoreboardData")+38
	end = r.text.find("</script>", start - 1)
	data = r.text[start:end].replace(";","").replace("window.espn.scoreboardData","").replace("if(!window.espn_ui.device.isMobile){window.espn.loadType = \"ready\"};","").split("window.espn.scoreboardSettings")[0].strip()
	json_data = json.loads(data)['events']
	for game in json_data:
		game['teams'] = {}
		game['teams'][game['competitions'][0]['competitors'][0]['homeAway']] = game['competitions'][0]['competitors'][0]['team']
		game['teams'][game['competitions'][0]['competitors'][1]['homeAway']] = game['competitions'][0]['competitors'][1]['team']
		game['teams'][game['competitions'][0]['competitors'][0]['homeAway']]['score'] = game['competitions'][0]['competitors'][0]['score']
		game['teams'][game['competitions'][0]['competitors'][1]['homeAway']]['score'] = game['competitions'][0]['competitors'][1]['score']
		
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
		del game['teams']['home']['links']
		del game['teams']['home']['id']
		del game['teams']['home']['uid']
		del game['teams']['away']['links']
		del game['teams']['away']['id']
		if 'uid' in game['teams']['away']:del game['teams']['away']['uid']
		
	return json.dumps(json_data)