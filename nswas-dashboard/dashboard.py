from flask import Flask, redirect, request, session, render_template
import requests
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")
GUILD_ID = os.getenv("GUILD_ID")
DASHBOARD_ROLE_ID = os.getenv("DASHBOARD_ROLE_ID")
BOT_TOKEN = os.getenv("BOT_TOKEN")

DISCORD_API = "https://discord.com/api"


def get_user_guild_roles(user_id):
    url = f"{DISCORD_API}/guilds/{GUILD_ID}/members/{user_id}"
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        return []
    return r.json().get("roles", [])


@app.route("/")
def index():
    if "user" not in session:
        return redirect("/login")
    return redirect("/dashboard")


@app.route("/login")
def login():
    return redirect(
        f"{DISCORD_API}/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify%20guilds.members.read"
    )


@app.route("/auth/callback")
def callback():
    code = request.args.get("code")

    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    r = requests.post(f"{DISCORD_API}/oauth2/token", data=data, headers=headers)
    token = r.json().get("access_token")

    user = requests.get(
        f"{DISCORD_API}/users/@me",
        headers={"Authorization": f"Bearer {token}"}
    ).json()

    session["user"] = user

    # Check roles
    roles = get_user_guild_roles(user["id"])
    if DASHBOARD_ROLE_ID not in roles:
        return "❌ You do not have permission to access the NSWAS Dashboard."

    return redirect("/dashboard")


@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")

    return render_template("dashboard.html", user=session["user"])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
