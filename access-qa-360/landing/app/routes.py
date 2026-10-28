from flask import Blueprint, render_template

main = Blueprint("main", __name__)


@main.route("/")
def index():
    return render_template("pages/index.html")


@main.route("/about/")
def about():
    return render_template("pages/about.html")


@main.route("/features/")
def features():
    return render_template("pages/features.html")


@main.route("/pricing/")
def pricing():
    return render_template("pages/pricing.html")


@main.route("/contact/")
def contact():
    return render_template("pages/contact.html")


@main.route("/security-and-privacy/")
def security_and_privacy():
    return render_template("pages/security-and-privacy.html")


@main.route("/error/")
def error():
    return render_template("pages/error.html")
