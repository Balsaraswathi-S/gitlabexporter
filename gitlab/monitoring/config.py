# GitLab Configuration
GITLAB_URL = "https://gitlab.com"
GITLAB_TOKEN = "glpat-s4HE2mftHACay3UD_CXH5286MQp1OmpkYXg3Cw.01.121cnnchg"

# AUTO-DISCOVER: Set to True to monitor ALL your accessible repositories
AUTO_DISCOVER_ALL_REPOS = False  # Disabled - use specific repos

# Repositories to monitor (used only if AUTO_DISCOVER_ALL_REPOS = False)
# Use full path format: username/reponame
REPOSITORIES = ["BalaS_1629/devops_project", "BalaS_1629/exporter_test", "BalaS_1629/gitlabexporter", "BalaS_1629/rework", "BalaS_1629/Rework"]

# Sync settings for real-time updates
CACHE_SECONDS = 5  # Refresh every 5 seconds (fast!)
MAX_MRS_PER_REPO = 200  # Get up to 200 MRs per repo
INCLUDE_CLOSED_MRS = True  # Set True to also monitor closed MRs
MONITOR_ALL_BRANCHES = True  # Monitor all branches, not just MR branches

# Your email for notifications
YOUR_EMAIL = "your.email@company.com"  # Update this

# SMTP for email alerts (optional - configure if you want email)
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = ""  # Leave empty to disable email
SMTP_PASSWORD = ""

# Labels 
LABEL_REWORK = "rework"
LABEL_IN_REVIEW = "in-review"
LABEL_REWORK_DONE = "rework-done"

