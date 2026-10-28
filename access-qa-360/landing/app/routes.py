from flask import Blueprint, render_template, redirect
from slugify import slugify

main = Blueprint("main", __name__)

@main.context_processor
def inject_slugify():
    return {'slugify': slugify}

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


@main.route("/get-demo/")
def get_demo():
    return redirect("http://localhost:5173/login")


@main.route("/blog/")
def blog():
    return render_template("pages/blog.html")


@main.route("/blog-details/")
def blog_list_or_default():
    blogs = [
        {
            'id': 1,
            'img': '/static/assets/img/blog/blog-details.jpg',
            'title': 'How AI Is Transforming Software QA',
        }
    ]
    blog = blogs[0]
    return render_template("pages/blog-details.html", blog=blog)


@main.route("/blog-details/<string:title>/")
def blog_details(title):
    blogs = [
        {
            'id': 1,
            'img': '/static/assets/img/blog/blog-01.png',
            'tag': 'AI Testing',
            'title': 'How AI Is Transforming Software QA',
            'desc': 'AI-powered testing is changing how teams ship software.',
        },
        {
            'id': 2,
            'img': '/static/assets/img/blog/blog-02.png',
            'tag': 'Best Practices',
            'title': 'The Complete Guide to End-to-End Testing',
            'desc': 'E2E testing strategies for reliable, maintainable test suites.',
        },
        {
            'id': 3,
            'img': '/static/assets/img/blog/blog-03.png',
            'tag': 'Playwright',
            'title': 'Why We Chose Playwright Over Cypress',
            'desc': 'Cross-browser support, auto-waits, and native API testing.',
        },
    ]
    selected_blog = next((blog for blog in blogs if slugify(blog['title']) == title), None)

    if selected_blog:
        return render_template('pages/blog-details.html', blog=selected_blog)
    else:
        return "blog not found", 404


@main.route("/integration/")
def integration():
    return render_template("pages/integration.html")


@main.route("/integration-details/")
def integration_details():
    return render_template("pages/integration-details.html")


@main.route("/integration-category/")
def integration_category():
    return render_template("pages/integration-category.html")


@main.route("/security-and-privacy/")
def security_and_privacy():
    return render_template("pages/security-and-privacy.html")


@main.route("/use-cases/")
def use_cases():
    return render_template("pages/use-cases.html")


@main.route("/use-case-details/")
def use_case_details():
    return render_template("pages/use-case-details.html")


@main.route("/ai-policy/")
def ai_policy():
    return render_template("pages/ai-policy.html")


@main.route("/join-wishlist/")
def join_wishlist():
    return render_template("pages/join-wishlist.html")


@main.route("/password-protected/")
def password_protected():
    return render_template("pages/password-protected.html")


@main.route("/index-2/")
def index_2():
    return render_template("pages/index-2.html")


@main.route("/error/")
def error():
    return render_template("pages/error.html")
