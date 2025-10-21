import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Create tables
db.execute("CREATE TABLE IF NOT EXISTS records (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, symbol TEXT NOT NULL, shares INTEGER NOT NULL, UNIQUE(username, symbol))")
db.execute("CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, symbol TEXT NOT NULL, shares INTEGER NOT NULL, buy BOOLEAN NOT NULL, price REAL NOT NULL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
db.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, username TEXT NOT NULL, hash TEXT NOT NULL, cash NUMERIC NOT NULL DEFAULT 10000.00)")

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    row = db.execute("SELECT username, cash FROM users WHERE id = ?", session["user_id"])
    username = row[0]["username"]
    cash = row[0]["cash"]

    stocks = db.execute("SELECT * FROM records WHERE username = ?", username)
    # print(stocks)

    portfolio = {}
    sum = 0
    for stock in stocks:
        symbol = stock["symbol"]
        shares = stock["shares"]
        data = lookup(symbol)
        price = data["price"]

        if symbol in portfolio:
            portfolio[symbol]["shares"] += shares
            portfolio[symbol]["total_value"] += shares * price
            sum += shares * price
        else:
            portfolio[symbol] = {
                "shares": shares,
                "latest_price": price,
                "total_value": shares * price
            }
            sum += shares * price

    # print(portfolio)


    return render_template("index.html", username=username, cash=cash, portfolio=portfolio, sum=sum)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        # Get data
        data = lookup(request.form.get("symbol"))
        # Validation
        if not data:
            return apology("Invalid stock")
        if (request.form.get("shares").isdigit() == False) or int(request.form.get("shares")) < 1:
            return apology("Invalid share number")

        # Transaction
        cost = int(data["price"]) * int(request.form.get("shares"))
        balance = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        # Check if enough cash
        if cost > int(balance[0]["cash"]):
            return apology("Not enough cash")
        # Payment for shares
        db.execute("UPDATE users SET cash = ? WHERE id = ?", int(balance[0]["cash"]) - cost, session["user_id"])

        # Store transaction in table + history

        row = db.execute("SELECT username FROM users WHERE id = ?", session["user_id"])
        # Need to fix this - 1 username can have multiple stocks and 1 stock can have multiple users
        db.execute("INSERT INTO records (username, symbol, shares) VALUES (?, ?, ?) ON CONFLICT (username, symbol) DO UPDATE SET shares = shares + ?", row[0]["username"], request.form.get("symbol"), int(request.form.get("shares")), int(request.form.get("shares")))


        db.execute("INSERT INTO history (username, symbol, shares, buy, price) VALUES (?, ?, ?, 1, ?)", row[0]["username"], request.form.get("symbol"), int(request.form.get("shares")), data["price"])

        # Redirect
        return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    row = db.execute("SELECT username FROM users WHERE id = ?", session["user_id"])
    rows = db.execute("SELECT symbol, shares, buy, price, timestamp FROM history WHERE username = ?", row[0]["username"])
    return render_template("history.html", rows=rows)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        # Render new template with values
        if not request.form.get("symbol"):
            return apology("no symbol provided", 400)
        data = lookup(request.form.get("symbol"))
        # print(data)
        if not data:
            return apology("invalid symbol", 400)

        return render_template("quoted.html", name=data["name"], price=f"{data['price']:.2f}", symbol=data["symbol"])
    else:
        return render_template("quote.html")



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        # Check username submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)
        # Check password submitted
        if not request.form.get("password"):
            return apology("must provide password", 400)
        # Check password and confirm password are same
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("password not same as confirm password", 400)

        # Add user to database + Check username doesn't exist
        try:
            db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", request.form.get("username"), generate_password_hash(request.form.get("password")))
        except ValueError:
            return apology("username already exists", 400)

        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        if (request.form.get("shares").isdigit() == False) or int(request.form.get("shares")) < 1:
            return apology("Invalid share number")

        user = db.execute("SELECT username FROM users WHERE id = ?", session["user_id"])

        rows = db.execute("SELECT * FROM records WHERE username = ? AND symbol = ?", user[0]["username"] ,request.form.get("symbol"))
        if not rows:
            return apology("Invalid stock")
        if int(rows[0]["shares"]) < int(request.form.get("shares")):
            return apology("Not enough shares")

        # Update shares after selling
        db.execute("UPDATE records SET shares = ? WHERE username = ? AND symbol = ?", int(rows[0]["shares"]) - int(request.form.get("shares")), user[0]["username"] , request.form.get("symbol"))

        # Update cash after selling
        data = lookup(request.form.get("symbol"))
        if not data:
            return apology("Invalid stock")
        proceeds = int(data["price"]) * int(request.form.get("shares"))
        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", proceeds ,session["user_id"])

        # Add into history
        db.execute("INSERT INTO history (username, symbol, shares, buy, price) VALUES (?, ?, ?, 0, ?)", user[0]["username"], request.form.get("symbol"), int(request.form.get("shares")), int(data["price"]))


        print(rows)
        return redirect("/")
    else:
        user = db.execute("SELECT username FROM users WHERE id = ?", session["user_id"])
        symbols = db.execute("SELECT symbol FROM records WHERE username = ?", user[0]["username"])
        print(symbols)
        return render_template("sell.html", symbols=symbols)
