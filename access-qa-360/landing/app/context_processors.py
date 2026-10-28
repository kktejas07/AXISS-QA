# app/context_processors.py
from flask import request
from slugify import slugify

# logos data

def global_logos():
    logos = [
        {'img': '/static/assets/img/client-logos/logo-01.svg'},
        {'img': '/static/assets/img/client-logos/logo-02.svg'},
        {'img': '/static/assets/img/client-logos/logo-03.svg'},
        {'img': '/static/assets/img/client-logos/logo-04.svg'},
        {'img': '/static/assets/img/client-logos/logo-05.svg'},
        {'img': '/static/assets/img/client-logos/logo-06.svg'},
        {'img': '/static/assets/img/client-logos/logo-07.svg'},
        {'img': '/static/assets/img/client-logos/logo-08.svg'},
        {'img': '/static/assets/img/client-logos/logo-01.svg'},
        {'img': '/static/assets/img/client-logos/logo-02.svg'},
        {'img': '/static/assets/img/client-logos/logo-03.svg'},
        {'img': '/static/assets/img/client-logos/logo-04.svg'},
    ]
    return {"logos": logos}


# process data

def global_process():
    process = [
        {
            'icon': '#processIcon-01',
            'name': 'Step 1',
            'title': 'Paste Any URL',
            'desc': 'Enter any web application URL — staging, production, or API endpoint. Access QA 360 auto-discovers sub-pages, API surfaces, and JavaScript-rendered content via Playwright.',
        },
        {
            'icon': '#processIcon-02',
            'name': 'Step 2',
            'title': 'AI Scans & Analyzes',
            'desc': 'The platform runs OWASP vulnerability detection, QA gap analysis, and AI test generation in parallel. Cyber findings, coverage gaps, and test cases — all from one scan.',
        },
        {
            'icon': '#processIcon-03',
            'name': 'Step 3',
            'title': 'Get Your Complete Report',
            'desc': 'Receive a unified report: vulnerability findings with CVSS scores, a QA coverage heatmap, and production-ready test cases (manual, automated, performance, and security) — export as PDF, Word, or code.',
        },
    ]
    return {"process": process}


# cases data — the 8 core modules

def global_cases():
    cases = [
        {
            'icon': '#useCaseIcon-07',
            'title': 'URL-Based Scanning Engine',
            'desc': 'Paste any URL and auto-crawl the entire application surface. Supports authenticated scanning, headless browser rendering, API detection, and configurable depth/rate controls.',
        },
        {
            'icon': '#useCaseIcon-08',
            'title': 'Cyber Security Detection',
            'desc': 'Full OWASP Top 10 coverage: SQL Injection, XSS, CSRF, broken auth, SSRF, IDOR, and more. Every finding includes CVSS score, proof-of-concept, CWE/CVE references, and remediation guidance.',
        },
        {
            'icon': '#useCaseIcon-09',
            'title': 'QA Gap Analysis',
            'desc': 'Visual coverage heatmap of all routes and flows. AI detects untested endpoints, missing edge cases, accessibility gaps, and orphaned tests. Upload a BRD for requirement-to-test traceability.',
        },
        {
            'icon': '#useCaseIcon-10',
            'title': 'AI Test Case Generation',
            'desc': 'Claude Sonnet generates manual, unit, smoke, regression, integration, performance, accessibility, and security tests — all from a single scan. Export as Playwright, pytest, k6, or Gherkin.',
        },
        {
            'icon': '#useCaseIcon-11',
            'title': 'Manual Testing Framework',
            'desc': 'Structured test plans, exploratory charters, bug report templates, traceability matrices, and sign-off checklists. Export to Word, PDF, or import into Jira, TestRail, and Zephyr.',
        },
        {
            'icon': '#useCaseIcon-04',
            'title': 'Automation & Reporting',
            'desc': 'Production-ready Playwright E2E suites with Page Object Model, pytest API tests, k6 performance scripts, and CI/CD workflows. Unified reports for executives, developers, and compliance teams.',
        },
    ]
    return {"cases": cases}


# testimonials data

def global_testimonials():
    testimonials = [
        {
            'img': '/static/assets/img/home/testimonial/testimonial-01.jpg',
            'name': 'Sarah Chen',
            'title': 'QA Lead, FinTech Startup',
            'desc': 'We replaced OWASP ZAP, Burp Suite, and TestRail with one platform. Access QA 360 found 14 vulnerabilities and generated 200+ test cases from a single URL scan.',
        },
        {
            'img': '/static/assets/img/home/testimonial/testimonial-02.jpg',
            'name': 'Marcus Johnson',
            'title': 'CTO, E-Commerce Platform',
            'desc': 'The combined cyber + QA report saved us weeks. We went from separate security and QA cycles to a single scan that covers both. Game changer for our release process.',
        },
        {
            'img': '/static/assets/img/home/testimonial/testimonial-03.jpg',
            'name': 'Priya Patel',
            'title': 'Engineering Manager, SaaS Co',
            'desc': 'We uploaded our BRD and the RAG pipeline mapped every requirement to generated test cases. Gaps we had missed for months were flagged in minutes.',
        },
        {
            'img': '/static/assets/img/home/testimonial/testimonial-01.jpg',
            'name': 'James Rodriguez',
            'title': 'VP Engineering, HealthTech',
            'desc': 'HIPAA compliance testing used to take us 3 weeks. Access QA 360 generates the compliance report automatically — mapped to control requirements. Down to 2 days.',
        },
        {
            'img': '/static/assets/img/home/testimonial/testimonial-02.jpg',
            'name': 'Emily Nakamura',
            'title': 'Senior Security Engineer',
            'desc': 'The OWASP vulnerability detection is thorough — SQL injection, XSS, CSRF, IDOR, SSRF — all with proof-of-concept payloads. And it generates regression tests to ensure fixes stick.',
        },
        {
            'img': '/static/assets/img/home/testimonial/testimonial-03.jpg',
            'name': 'David Okafor',
            'title': 'Product Manager, EdTech',
            'desc': 'Non-technical PMs can now see exactly which features have test coverage and which have security gaps. The executive summary gives me a risk scorecard I can share with the board.',
        },
        {
            'img': '/static/assets/img/home/testimonial/testimonial-04.jpg',
            'name': 'Lisa Andersson',
            'title': 'DevOps Lead, Logistics',
            'desc': 'CI/CD integration was seamless. Every PR triggers a scan — security findings and broken tests block the merge. Deployment confidence went from 60% to 99%.',
        },
        {
            'img': '/static/assets/img/home/testimonial/testimonial-05.jpg',
            'name': 'Kevin Park',
            'title': 'CTO, Marketplace Startup',
            'desc': 'We were paying $1,400/month across 5 different tools. Access QA 360 replaced all of them for $199. The ROI was immediate — first scan caught 3 critical SQL injection flaws.',
        },
        {
            'img': '/static/assets/img/home/testimonial/testimonial-06.jpg',
            'name': 'Rachel Green',
            'title': 'QA Director, Banking',
            'desc': 'The AI failure investigator triages every test failure with root cause analysis and a confidence score. Our team fixes the right things first instead of chasing symptoms.',
        },
        {
            'img': '/static/assets/img/home/testimonial/testimonial-04.jpg',
            'name': 'Tom Mueller',
            'title': 'Frontend Lead, Agency',
            'desc': 'Accessibility testing across all routes — WCAG 2.1 AA compliance checked automatically. The axe-core integration via Playwright catches issues we never would have found manually.',
        },
        {
            'img': '/static/assets/img/home/testimonial/testimonial-05.jpg',
            'name': 'Aisha Kamara',
            'title': 'Engineering Manager',
            'desc': 'The auto-selector healing is brilliant. When our UI changes break test selectors, Claude Sonnet proposes a patch with a confidence score and applies it automatically above 85%.',
        },
        {
            'img': '/static/assets/img/home/testimonial/testimonial-06.jpg',
            'name': 'Chris Taylor',
            'title': 'Startup Founder',
            'desc': 'As a solo developer, I couldn\'t afford a security team AND a QA team. Access QA 360 gives me both — vulnerability scanning and full test generation — for free on the starter plan.',
        },
        {
            'img': '/static/assets/img/home/testimonial/testimonial-07.jpg',
            'name': 'Nina Volkov',
            'title': 'SDET, Insurance Tech',
            'desc': 'The k6 performance scripts are production-ready — baseline load, spike tests, soak tests with auto-set thresholds based on our tech stack. Saved us a week of scripting.',
        },
        {
            'img': '/static/assets/img/home/testimonial/testimonial-08.jpg',
            'name': 'Alex Thompson',
            'title': 'Release Manager',
            'desc': 'Diff reports between scans show exactly what regressed, what was fixed, and what\'s new. Our release sign-off went from a 2-day process to a 30-minute review.',
        },
        {
            'img': '/static/assets/img/home/testimonial/testimonial-09.jpg',
            'name': 'Maria Santos',
            'title': 'QA Analyst, Retail',
            'desc': 'The coverage heatmap is incredible — every route colour-coded by test coverage status. Uncovered critical payment flows that had zero tests for 6 months.',
        },
        {
            'img': '/static/assets/img/home/testimonial/testimonial-07.jpg',
            'name': 'Ryan Kim',
            'title': 'Tech Lead, Gaming',
            'desc': 'Security regression tests replay confirmed vulnerability payloads against every deployment. We know our fixes actually stick — no more whack-a-mole with XSS bugs.',
        },
        {
            'img': '/static/assets/img/home/testimonial/testimonial-08.jpg',
            'name': 'Sophie Laurent',
            'title': 'VP Product, Travel Tech',
            'desc': 'PCI-DSS compliance mapping used to require an external audit. Now the compliance report maps findings to control requirements automatically. Auditors love it.',
        },
        {
            'img': '/static/assets/img/home/testimonial/testimonial-09.jpg',
            'name': 'Daniel Byrne',
            'title': 'CTO, PropTech',
            'desc': 'One URL, one scan, one report — vulnerabilities, coverage gaps, and test cases. No other tool does both cyber and QA. This is the first platform that actually unifies them.',
        },
    ]
    return {"testimonials": testimonials}


# integrations data

def global_integrations():
    integrations = [
        {
            'img': '/static/assets/img/integration/taskpilot.svg',
            'title': 'GitHub',
            'desc': 'Trigger scans on every pull request. Block merges on critical vulnerabilities, post security + QA results as PR comments, and auto-generate CI/CD workflows.',
            'btn': 'CI/CD',
            'data': 'cicd',
        },
        {
            'img': '/static/assets/img/integration/databridge.svg',
            'title': 'GitLab',
            'desc': 'Integrate with GitLab CI pipelines. Auto-scan on merge requests, track vulnerability trends and coverage deltas across branches.',
            'btn': 'CI/CD',
            'data': 'cicd',
        },
        {
            'img': '/static/assets/img/integration/chatsapot.svg',
            'title': 'Slack',
            'desc': 'Get real-time scan results in your channels. AI-powered vulnerability summaries, QA gap alerts, and failure triage delivered where your team works.',
            'btn': 'Notifications',
            'data': 'notifications',
        },
        {
            'img': '/static/assets/img/integration/leadboost.svg',
            'title': 'Jira',
            'desc': 'Auto-create Jira tickets from vulnerabilities and failed tests with AI-generated descriptions, CVSS scores, reproduction steps, and remediation guidance.',
            'btn': 'Project Mgmt',
            'data': 'project',
        },
        {
            'img': '/static/assets/img/integration/visualmaker.svg',
            'title': 'Jenkins',
            'desc': 'Add Access QA 360 as a Jenkins pipeline stage. Run security scans and test suites in parallel, gate deployments on vulnerability severity thresholds.',
            'btn': 'CI/CD',
            'data': 'cicd',
        },
        {
            'img': '/static/assets/img/integration/insightplulse.svg',
            'title': 'TestRail / Zephyr',
            'desc': 'Export generated manual test cases directly into TestRail or Zephyr. Sync test run results, maintain traceability matrices, and track coverage trends.',
            'btn': 'Test Mgmt',
            'data': 'project',
        },
    ]
    return {"integrations": integrations}


# teams data

def global_teams():
    teams = [
        {
            'img': '/static/assets/img/about/team-01.jpg',
            'name': 'Krishna Chintakayala',
            'title': 'Founder & CEO',
            'icon': '#linkedIn',
        },
        {
            'img': '/static/assets/img/about/team-02.jpg',
            'name': 'Arjun Reddy',
            'title': 'Head of Engineering',
            'icon': '#linkedIn',
        },
        {
            'img': '/static/assets/img/about/team-03.jpg',
            'name': 'Meera Iyer',
            'title': 'Lead AI Engineer',
            'icon': '#twitter',
        },
        {
            'img': '/static/assets/img/about/team-04.jpg',
            'name': 'Rahul Sharma',
            'title': 'Chief Technology Officer',
            'icon': '#linkedIn',
        },
        {
            'img': '/static/assets/img/about/team-05.jpg',
            'name': 'Ananya Gupta',
            'title': 'QA Architect',
            'icon': '#twitter',
        },
        {
            'img': '/static/assets/img/about/team-06.jpg',
            'name': 'Vikram Desai',
            'title': 'Product Designer',
            'icon': '#linkedIn',
        },
    ]
    return {"teams": teams}


# researchs data

def global_researchs():
    researchs = [
        {
            'img': '/static/assets/img/about/research-loog-01.svg',
            'name': 'ScanEngine',
            'title': 'URL crawling & surface discovery',
        },
        {
            'img': '/static/assets/img/about/research-loog-02.svg',
            'name': 'CyberProbe',
            'title': 'OWASP vulnerability detection',
        },
        {
            'img': '/static/assets/img/about/research-loog-03.svg',
            'name': 'GapIntel',
            'title': 'QA coverage analysis & heatmaps',
        },
        {
            'img': '/static/assets/img/about/research-loog-04.svg',
            'name': 'AutoHeal',
            'title': 'AI selector repair & flake detection',
        },
    ]
    return {"researchs": researchs}


# financials data

def global_financials():
    financials = [
        {
            'number': '0',
            'target': '6',
            'symbol': '',
            'symbol2': '',
            'symbol3': '',
            'style': '',
            'title': 'Tools Replaced',
            'desc': 'Access QA 360 replaces OWASP ZAP, Burp Suite, TestRail, Selenium IDE, Snyk, and more — one platform for cyber + QA.',
        },
        {
            'number': '0',
            'target': '87',
            'symbol': '',
            'symbol2': '%',
            'symbol3': '',
            'style': 'text-tertiary',
            'title': 'Cost Savings',
            'desc': 'Teams save $1,273/month on average — from $1,472 across six tools down to $199 with Access QA 360 Pro.',
        },
        {
            'number': '0',
            'target': '500',
            'symbol': '',
            'symbol2': '+',
            'symbol3': '',
            'style': 'text-tertiary',
            'title': 'Attack Vectors',
            'desc': 'Full OWASP Top 10 coverage with 500+ XSS payload vectors, SQL injection variants, CSRF probes, and SSRF detection.',
        },
    ]
    return {"financials": financials}


# blogs data

def global_blogs():
    blogs = [
        {
            'id': 1,
            'img': '/static/assets/img/blog/blog-01.png',
            'tag': 'Cyber + QA',
            'title': 'Why Security and QA Belong in One Platform',
            'desc': 'The market is fragmented — security tools don\'t generate tests, and QA tools don\'t scan for vulnerabilities. Access QA 360 is the first to do both.',
        },
        {
            'id': 2,
            'img': '/static/assets/img/blog/blog-02.png',
            'tag': 'OWASP',
            'title': 'OWASP Top 10: Automated Detection with AI',
            'desc': 'From SQL injection to SSRF, learn how Access QA 360 detects and triages every OWASP category with evidence-backed findings.',
        },
        {
            'id': 3,
            'img': '/static/assets/img/blog/blog-03.png',
            'tag': 'AI Testing',
            'title': 'How Claude Sonnet Generates Production-Ready Tests',
            'desc': 'Manual, unit, smoke, regression, integration, performance, accessibility, and security tests — all generated from a single scan.',
        },
        {
            'id': 4,
            'img': '/static/assets/img/blog/blog-04.png',
            'tag': 'BRD Alignment',
            'title': 'RAG-Powered BRD-to-Test Traceability',
            'desc': 'Upload your Business Requirements Document and the RAG pipeline checks whether each requirement has a corresponding test case.',
        },
        {
            'id': 5,
            'img': '/static/assets/img/blog/blog-05.png',
            'tag': 'Auto-Maintenance',
            'title': 'AI Selector Healing: End Flaky Tests Forever',
            'desc': 'When UI changes break selectors, Claude proposes a patch with a confidence score and applies it automatically — no human intervention needed.',
        },
        {
            'id': 6,
            'img': '/static/assets/img/blog/blog-06.png',
            'tag': 'Case Study',
            'title': 'How One Team Replaced 6 Tools with Access QA 360',
            'desc': 'A 15-person engineering team consolidated their entire security and QA stack into one platform — saving $1,273/month and catching 3x more issues.',
        },
    ]
    return {"blogs": blogs}


# blogs2 data

def global_blogs2():
    blogs2 = [
        {
            'id': 2,
            'img': '/static/assets/img/blog/blog-02.png',
            'tag': 'OWASP',
            'title': 'OWASP Top 10: Automated Detection with AI',
            'desc': 'From SQL injection to SSRF, learn how Access QA 360 detects and triages every OWASP category with evidence-backed findings.',
        },
        {
            'id': 3,
            'img': '/static/assets/img/blog/blog-03.png',
            'tag': 'AI Testing',
            'title': 'How Claude Sonnet Generates Production-Ready Tests',
            'desc': 'Manual, unit, smoke, regression, integration, performance, accessibility, and security tests — all generated from a single scan.',
        },
        {
            'id': 4,
            'img': '/static/assets/img/blog/blog-04.png',
            'tag': 'BRD Alignment',
            'title': 'RAG-Powered BRD-to-Test Traceability',
            'desc': 'Upload your Business Requirements Document and the RAG pipeline checks whether each requirement has a corresponding test case.',
        },
    ]
    return {"blogs2": blogs2}


# filters data

def global_filters():
    filters = [
        {
            'title': 'All Integrations',
            'data': '*',
            'pressed': 'true',
            'style': 'is-checked active',
        },
        {
            'title': 'CI/CD',
            'data': 'cicd',
            'pressed': '',
            'style': '',
        },
        {
            'title': 'Notifications',
            'data': 'notifications',
            'pressed': '',
            'style': '',
        },
        {
            'title': 'Test Mgmt',
            'data': 'project',
            'pressed': '',
            'style': '',
        },
    ]
    return {"filters": filters}


# browse_integrations data

def global_browse_integrations():
    browse_integrations = [
        {
            'title': 'Version Control',
            'desc': 'Connect with GitHub, GitLab, and Bitbucket to trigger scans and test runs on every push, pull request, and merge — automatically.',
            'tools': '3 Tools',
        },
        {
            'title': 'CI/CD Pipelines',
            'desc': 'Integrate with Jenkins, CircleCI, GitHub Actions, and GitLab CI to run security scans and test suites as pipeline stages with gated deployments.',
            'tools': '5 Tools',
        },
        {
            'title': 'Issue Tracking',
            'desc': 'Auto-create tickets in Jira, Linear, or GitHub Issues from vulnerabilities and failed tests with AI-generated CVSS scores and reproduction steps.',
            'tools': '4 Tools',
        },
        {
            'title': 'Team Communication',
            'desc': 'Get scan results, vulnerability alerts, failure summaries, and suggested fixes in Slack, Teams, or Discord — right where your team works.',
            'tools': '3 Tools',
        },
        {
            'title': 'Test Management',
            'desc': 'Export generated test cases to TestRail, Zephyr, or qTest. Sync execution results and maintain requirement-to-test traceability matrices.',
            'tools': '4 Tools',
        },
        {
            'title': 'Cloud & Compliance',
            'desc': 'Deploy on AWS, GCP, or Azure. Generate PCI-DSS, HIPAA, and OWASP ASVS compliance reports mapped to control requirements.',
            'tools': '3 Tools',
        },
    ]
    return {"browse_integrations": browse_integrations}


# Put all processor functions in a list for easy registration
all_context_processors = [
    global_logos,
    global_process,
    global_cases,
    global_testimonials,
    global_integrations,
    global_teams,
    global_researchs,
    global_financials,
    global_blogs,
    global_blogs2,
    global_filters,
    global_browse_integrations,
]
