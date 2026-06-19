"""Generate 500 realistic candidate profiles and seed the database."""

import random
import uuid
from faker import Faker
from modules.database import insert_candidate, insert_engagement, get_connection

fake = Faker("en_IN")
random.seed(42)

# ── Role definitions ──────────────────────────────────────────────────────────

ROLES = {
    "Product Analyst": {
        "skills": ["SQL", "Python", "Tableau", "Power BI", "Product Analytics",
                   "A/B Testing", "Excel", "Stakeholder Management", "Dashboarding",
                   "Data Visualization", "Google Analytics", "Mixpanel", "Amplitude"],
        "industry": ["SaaS", "E-Commerce", "FinTech", "EdTech", "HealthTech"],
    },
    "Data Scientist": {
        "skills": ["Python", "Machine Learning", "Deep Learning", "NLP", "TensorFlow",
                   "PyTorch", "Scikit-learn", "SQL", "Statistics", "Feature Engineering",
                   "Model Deployment", "PySpark", "Pandas", "NumPy"],
        "industry": ["FinTech", "HealthTech", "SaaS", "E-Commerce", "AdTech"],
    },
    "Software Engineer": {
        "skills": ["Python", "Java", "Go", "Microservices", "REST APIs", "AWS",
                   "Docker", "Kubernetes", "PostgreSQL", "Redis", "Kafka",
                   "System Design", "CI/CD", "Git"],
        "industry": ["SaaS", "FinTech", "E-Commerce", "Gaming", "Cybersecurity"],
    },
    "Frontend Developer": {
        "skills": ["React", "TypeScript", "JavaScript", "Next.js", "CSS", "HTML5",
                   "Redux", "GraphQL", "Webpack", "Jest", "Figma", "Tailwind CSS",
                   "Vue.js", "Angular"],
        "industry": ["SaaS", "E-Commerce", "EdTech", "Media", "Gaming"],
    },
    "Backend Developer": {
        "skills": ["Node.js", "Python", "Java", "Go", "PostgreSQL", "MongoDB",
                   "Redis", "Kafka", "Docker", "Kubernetes", "AWS", "REST APIs",
                   "GraphQL", "Microservices"],
        "industry": ["SaaS", "FinTech", "E-Commerce", "HealthTech", "LogisTech"],
    },
    "ML Engineer": {
        "skills": ["Python", "MLOps", "TensorFlow", "PyTorch", "Kubeflow",
                   "Feature Store", "Model Serving", "Docker", "Kubernetes",
                   "PySpark", "SQL", "AWS SageMaker", "Airflow", "Triton"],
        "industry": ["FinTech", "HealthTech", "AdTech", "SaaS", "Autonomous Systems"],
    },
    "Data Engineer": {
        "skills": ["Python", "Spark", "Airflow", "dbt", "Kafka", "Snowflake",
                   "BigQuery", "Redshift", "SQL", "ETL", "Delta Lake", "AWS",
                   "PostgreSQL", "Databricks"],
        "industry": ["FinTech", "E-Commerce", "SaaS", "Media", "Healthcare"],
    },
    "Product Manager": {
        "skills": ["Product Strategy", "Roadmap Planning", "Stakeholder Management",
                   "A/B Testing", "User Research", "SQL", "Jira", "Agile",
                   "Go-to-Market", "OKRs", "Prioritization", "Wireframing"],
        "industry": ["SaaS", "E-Commerce", "FinTech", "EdTech", "HealthTech"],
    },
    "DevOps Engineer": {
        "skills": ["Kubernetes", "Docker", "Terraform", "AWS", "GCP", "CI/CD",
                   "Jenkins", "Ansible", "Prometheus", "Grafana", "Linux",
                   "GitHub Actions", "Helm", "ArgoCD"],
        "industry": ["SaaS", "FinTech", "E-Commerce", "Cybersecurity", "Media"],
    },
    "Business Analyst": {
        "skills": ["Business Analysis", "SQL", "Excel", "Power BI", "Tableau",
                   "Requirements Gathering", "Process Mapping", "Stakeholder Management",
                   "BPMN", "Agile", "User Stories", "JIRA"],
        "industry": ["FinTech", "Insurance", "Healthcare", "Retail", "Consulting"],
    },
    "QA Engineer": {
        "skills": ["Selenium", "Pytest", "Cypress", "Postman", "Test Automation",
                   "API Testing", "Performance Testing", "JMeter", "BDD",
                   "Python", "Java", "SQL", "Jenkins", "JIRA"],
        "industry": ["SaaS", "FinTech", "E-Commerce", "Gaming", "HealthTech"],
    },
    "Full Stack Developer": {
        "skills": ["React", "Node.js", "Python", "PostgreSQL", "MongoDB",
                   "REST APIs", "Docker", "AWS", "TypeScript", "Redis",
                   "GraphQL", "CI/CD", "Next.js", "Tailwind CSS"],
        "industry": ["SaaS", "E-Commerce", "EdTech", "FinTech", "Startup"],
    },
}

LOCATIONS = [
    "Bangalore", "Mumbai", "Delhi", "Hyderabad", "Pune",
    "Chennai", "Kolkata", "Noida", "Gurgaon", "Ahmedabad",
]

EDUCATION = [
    "B.Tech Computer Science – IIT Bombay",
    "B.Tech Information Technology – NIT Trichy",
    "M.Tech Data Science – IIT Delhi",
    "BCA – Pune University",
    "MCA – Delhi University",
    "B.E. Electronics – VTU",
    "MBA – IIM Bangalore",
    "B.Sc Computer Science – Christ University",
    "M.Sc Data Science – BITS Pilani",
    "B.Tech CSE – IIIT Hyderabad",
]


# ── Text generators ───────────────────────────────────────────────────────────

def _about(name: str, role: str, exp: int, skills: list, industry: str) -> str:
    top = random.sample(skills, min(4, len(skills)))
    return (
        f"{name} is a {role} with {exp} years of experience in the {industry} industry. "
        f"Proficient in {', '.join(top)}, with a track record of delivering high-impact "
        f"solutions. Known for strong analytical thinking, cross-functional collaboration, "
        f"and translating complex data insights into actionable business decisions. "
        f"Passionate about building scalable systems and driving measurable outcomes."
    )


def _project(role: str, skills: list) -> dict:
    project_templates = {
        "Product Analyst": [
            ("Customer Churn Prediction Dashboard",
             "Built an end-to-end churn prediction pipeline using SQL and Python, "
             "visualized through Tableau. Reduced churn by 12% through targeted interventions."),
            ("Funnel Optimization Analytics",
             "Analyzed user funnel drop-offs using Mixpanel and SQL. "
             "Implemented A/B tests that improved conversion by 18%."),
            ("Personalized Product Suggestions Engine",
             "Designed a recommendation system that increased avg order value by 22% "
             "using collaborative filtering and behavioral analytics."),
            ("Revenue Attribution Model",
             "Built multi-touch attribution model in Python to identify highest-ROI "
             "marketing channels, saving $200K in annual ad spend."),
        ],
        "Data Scientist": [
            ("Fraud Detection System",
             "Developed real-time fraud detection using XGBoost and anomaly detection. "
             "Achieved 96% precision at sub-50ms latency."),
            ("NLP-Based Customer Support Triage",
             "Built BERT-based classifier to auto-route support tickets. "
             "Reduced manual triage effort by 70%."),
            ("Demand Forecasting Engine",
             "Implemented LSTM-based demand forecasting for 10,000+ SKUs. "
             "Improved forecast accuracy by 34% vs. baseline."),
            ("Customer Lifetime Value Model",
             "Developed BG/NBD CLV model to segment high-value customers. "
             "Enabled targeted campaigns worth $1.5M additional revenue."),
        ],
        "Software Engineer": [
            ("Distributed Payments Microservice",
             "Architected high-throughput payment processing service handling "
             "50K TPS using Go, Kafka, and Redis."),
            ("API Gateway with Rate Limiting",
             "Built API gateway with token-bucket rate limiting and circuit breaker. "
             "Reduced downstream service failures by 85%."),
            ("Real-time Order Tracking System",
             "Designed WebSocket-based real-time order tracking serving 1M+ users. "
             "Achieved 99.99% uptime."),
            ("Search Infrastructure Overhaul",
             "Migrated monolithic search to Elasticsearch cluster. "
             "Reduced search latency from 800ms to 45ms."),
        ],
        "ML Engineer": [
            ("MLOps Platform",
             "Built end-to-end ML platform with Kubeflow, feature store, and "
             "automated retraining. Reduced model deployment time from weeks to hours."),
            ("Real-time Recommendation Serving",
             "Deployed low-latency recommendation engine using Triton Inference Server. "
             "Serving 5M+ predictions/day at p99 < 20ms."),
            ("Feature Store Implementation",
             "Designed enterprise feature store using Feast and Redis. "
             "Reduced feature engineering duplication across 12 ML teams."),
        ],
        "Data Engineer": [
            ("Real-time Data Pipeline",
             "Built Kafka + Spark Streaming pipeline processing 2TB/day. "
             "Reduced reporting latency from T+1 to near real-time."),
            ("Data Warehouse Migration",
             "Migrated 500TB data warehouse from Redshift to Snowflake. "
             "Achieved 40% cost reduction and 3x query performance improvement."),
            ("dbt Transformation Layer",
             "Implemented dbt-based transformation layer with 200+ models. "
             "Improved data quality score from 78% to 97%."),
        ],
    }

    generic_projects = [
        (f"{role} Platform Redesign",
         f"Led redesign of core platform component using {random.choice(skills)}. "
         f"Improved performance by {random.randint(20, 60)}% and user satisfaction scores."),
        (f"Automated {role} Workflow",
         f"Automated manual {role.lower()} process using {random.choice(skills)} and Python. "
         f"Saved {random.randint(5, 20)} hours per week across the team."),
        (f"Analytics Dashboard for {role}",
         f"Built comprehensive analytics dashboard using {random.choice(skills)}. "
         f"Enabled self-serve reporting for {random.randint(50, 200)} stakeholders."),
    ]

    pool = project_templates.get(role, []) + generic_projects
    title, desc = random.choice(pool)
    used_skills = random.sample(skills, min(3, len(skills)))
    return {
        "project_id": str(uuid.uuid4())[:8],
        "title": title,
        "description": desc,
        "skills_used": used_skills,
        "duration_months": random.randint(3, 12),
        "impact": f"{random.randint(10, 60)}% improvement in key metrics",
    }


def _work_experience(role: str, exp: int, industry: str) -> list[dict]:
    companies = [
        "Flipkart", "Zomato", "Swiggy", "Razorpay", "CRED", "Meesho",
        "Ola", "Byju's", "Unacademy", "Freshworks", "Zoho", "Infosys",
        "Wipro", "TCS", "Capgemini", "Accenture", "PhonePe", "Paytm",
        "PolicyBazaar", "Nykaa", "Udaan", "Delhivery", "ShareChat", "Dream11",
    ]
    exp_list = []
    remaining = exp
    while remaining > 0:
        tenure = min(remaining, random.randint(1, 4))
        remaining -= tenure
        company = random.choice(companies)
        titles = {
            "Product Analyst": ["Product Analyst", "Senior Product Analyst", "Lead Analyst"],
            "Data Scientist": ["Data Scientist", "Senior Data Scientist", "ML Researcher"],
            "Software Engineer": ["Software Engineer", "Senior SWE", "Staff Engineer"],
            "ML Engineer": ["ML Engineer", "Senior ML Engineer", "ML Platform Engineer"],
            "Data Engineer": ["Data Engineer", "Senior Data Engineer", "Principal DE"],
            "Product Manager": ["Product Manager", "Senior PM", "Group PM"],
            "DevOps Engineer": ["DevOps Engineer", "Senior DevOps", "Platform Engineer"],
            "Business Analyst": ["Business Analyst", "Senior BA", "Lead BA"],
            "QA Engineer": ["QA Engineer", "SDET", "Senior QA"],
            "Frontend Developer": ["Frontend Developer", "Senior FE", "UI Lead"],
            "Backend Developer": ["Backend Developer", "Senior BE", "API Lead"],
            "Full Stack Developer": ["Full Stack Developer", "Senior FS", "Tech Lead"],
        }
        title_list = titles.get(role, [role, f"Senior {role}"])
        exp_list.append({
            "company": company,
            "title": random.choice(title_list),
            "tenure_years": tenure,
            "industry": industry,
            "responsibilities": [
                f"Led cross-functional initiatives to improve {role.lower()} metrics",
                f"Collaborated with stakeholders to define product requirements",
                f"Managed end-to-end delivery of {random.randint(2, 8)} projects annually",
            ],
        })
    return exp_list


# ── Main generator ────────────────────────────────────────────────────────────

def generate_candidates(n: int = 500) -> list[dict]:
    candidates = []
    role_list = list(ROLES.keys())

    for i in range(n):
        role = random.choice(role_list)
        role_data = ROLES[role]
        exp = round(random.uniform(0.5, 15), 1)
        location = random.choice(LOCATIONS)
        industry = random.choice(role_data["industry"])
        skills_pool = role_data["skills"]
        skills = random.sample(skills_pool, random.randint(4, min(9, len(skills_pool))))
        name = fake.name()
        ctc_base = max(3, exp * random.uniform(1.5, 3.5))
        current_ctc = round(ctc_base + random.uniform(-1, 2), 2)
        expected_ctc = round(current_ctc * random.uniform(1.1, 1.4), 2)

        projects = [_project(role, skills) for _ in range(random.randint(2, 4))]
        work_exp = _work_experience(role, max(1, int(exp)), industry)

        candidate = {
            "candidate_id": f"C{str(i+1).zfill(4)}",
            "name": name,
            "email": fake.email(),
            "phone": fake.phone_number(),
            "location": location,
            "experience_years": exp,
            "current_ctc": current_ctc,
            "expected_ctc": expected_ctc,
            "skills": skills,
            "about_section": _about(name, role, int(exp), skills, industry),
            "projects": projects,
            "work_experience": work_exp,
            "industry": industry,
            "education": random.choice(EDUCATION),
            "role": role,  # kept for FAISS metadata, not stored in candidates table
        }
        candidates.append(candidate)

    return candidates


def generate_engagement(candidate_id: str) -> dict:
    response_rate = round(random.uniform(0.2, 1.0), 2)
    reply_speed = round(random.uniform(1, 72), 1)
    interview_att = round(random.uniform(0.5, 1.0), 2)
    app_completion = round(random.uniform(0.6, 1.0), 2)
    score = round(
        0.4 * response_rate +
        0.2 * (1 - reply_speed / 72) +
        0.25 * interview_att +
        0.15 * app_completion, 4
    )
    return {
        "candidate_id": candidate_id,
        "response_rate": response_rate,
        "reply_speed_hours": reply_speed,
        "interview_attendance": interview_att,
        "application_completion": app_completion,
        "engagement_score": round(score * 100, 2),
    }


def seed_database(n: int = 500):
    """Generate n candidates and write them to SQLite."""
    from modules.database import init_db
    init_db()

    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]
    conn.close()

    if count >= n:
        print(f"✅ Database already has {count} candidates – skipping seed")
        return

    print(f"🌱 Generating {n} candidates...")
    candidates = generate_candidates(n)
    for c in candidates:
        insert_candidate(c)
        insert_engagement(generate_engagement(c["candidate_id"]))

    print(f"✅ Seeded {n} candidates into SQLite")
    return candidates
