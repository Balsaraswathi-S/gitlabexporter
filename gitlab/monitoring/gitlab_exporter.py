import time
import requests
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from collections import defaultdict
import smtplib
from email.mime.text import MIMEText
import config


metrics_cache = {
    "last_update": 0,
    "data": {}
}

def gitlab_api(endpoint):
    """Call GitLab API"""
    headers = {"PRIVATE-TOKEN": config.GITLAB_TOKEN}
    url = f"{config.GITLAB_URL}/api/v4/{endpoint}"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"[ERROR] GitLab API: {e}")
        return []

def get_all_projects():
    """Get all projects to monitor by repository name"""
    projects = []
    for repo_name in config.REPOSITORIES:
        # Search for project by name (all accessible projects)
        result = gitlab_api(f"projects?search={repo_name}&membership=true")
        if result:
            for proj in result:
                if proj['path'] == repo_name or proj['name'] == repo_name:
                    projects.append(proj)
                    print(f"[FOUND] {proj.get('path_with_namespace')}")
                    break
            else:
                print(f"[NOT FOUND] Repository '{repo_name}' not accessible")
    return projects

def get_merge_requests(project_id):
    """Get all merge requests for a project"""
    return gitlab_api(f"projects/{project_id}/merge_requests?state=opened&per_page=100")

def get_mr_label_events(project_id, mr_iid):
    """Get label change events for an MR"""
    return gitlab_api(f"projects/{project_id}/merge_requests/{mr_iid}/resource_label_events")

def calculate_time_in_state(mr, project_id):
    """Calculate time spent in each state based on label events"""
    events = get_mr_label_events(project_id, mr.get("iid"))
    if not events:
        return None, None, None
    
    # Track when labels were added
    rework_added = None
    in_review_added = None
    rework_done_added = None
    created_at = datetime.fromisoformat(mr.get("created_at").replace("Z", "+00:00"))
    
    for event in events:
        event_time = datetime.fromisoformat(event.get("created_at").replace("Z", "+00:00"))
        label = event.get("label")
        if not label:
            continue
        label_name = label.get("name")
        action = event.get("action")  # "add" or "remove"
        
        if action == "add":
            if label_name == config.LABEL_REWORK and not rework_added:
                rework_added = event_time
            elif label_name == config.LABEL_IN_REVIEW and not in_review_added:
                in_review_added = event_time
            elif label_name == config.LABEL_REWORK_DONE and not rework_done_added:
                rework_done_added = event_time
    
    # Calculate durations in hours
    time_in_rework = None
    time_in_review = None
    time_to_complete = None
    
    if rework_added and rework_done_added:
        time_in_rework = (rework_done_added - rework_added).total_seconds() / 3600
    
    if in_review_added:
        now = datetime.now(in_review_added.tzinfo)
        if rework_done_added:
            time_in_review = (rework_done_added - in_review_added).total_seconds() / 3600
        else:
            time_in_review = (now - in_review_added).total_seconds() / 3600
    
    if rework_done_added:
        time_to_complete = (rework_done_added - created_at).total_seconds() / 3600
    
    return time_in_rework, time_in_review, time_to_complete

def send_email_alert(subject, body):
    """Send email notification"""
    if not all([config.SMTP_USER, config.SMTP_PASSWORD, config.YOUR_EMAIL]):
        return  # Email not configured
    
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = config.SMTP_USER
        msg['To'] = config.YOUR_EMAIL
        
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
            server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.send_message(msg)
        print(f"[EMAIL] Sent: {subject}")
    except Exception as e:
        pass  # Silently fail if email not configured

def collect_metrics():
    """Collect GitLab metrics"""
    now = time.time()
    
    # Cache for 10 seconds for real-time updates
    if now - metrics_cache["last_update"] < 10:
        return metrics_cache["data"]
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Collecting GitLab metrics...")
    
    metrics = defaultdict(lambda: defaultdict(int))
    branch_metrics = []  # List of dicts with branch-level data
    rework_mrs = []
    
    projects = get_all_projects()
    
    for project in projects:
        project_id = project.get("id")
        project_name = project.get("path_with_namespace", "unknown")
        
        # Initialize all metrics to 0 for this project
        metrics[project_name]["total_mrs"] = 0
        metrics[project_name]["rework_mrs"] = 0
        metrics[project_name]["rework_assigned_to_me"] = 0
        metrics[project_name]["in_review_mrs"] = 0
        metrics[project_name]["rework_done_mrs"] = 0
        
        mrs = get_merge_requests(project_id)
        
        for mr in mrs:
            labels = mr.get("labels", [])
            assignees = [a.get("username") for a in mr.get("assignees", [])]
            source_branch = mr.get("source_branch", "unknown")
            target_branch = mr.get("target_branch", "main")
            mr_title = mr.get("title", "")
            mr_id = mr.get("iid")
            
            # Total MRs
            metrics[project_name]["total_mrs"] += 1
            
            # Calculate time metrics for this specific MR
            time_in_rework, time_in_review, time_to_complete = calculate_time_in_state(mr, project_id)
            
            # Store branch-level metrics
            branch_data = {
                "project": project_name,
                "branch": source_branch,
                "target_branch": target_branch,
                "mr_title": mr_title,
                "time_in_rework": time_in_rework or 0,
                "time_in_review": time_in_review or 0,
                "time_to_complete": time_to_complete or 0,
                "has_rework": config.LABEL_REWORK in labels,
                "has_in_review": config.LABEL_IN_REVIEW in labels,
                "has_rework_done": config.LABEL_REWORK_DONE in labels
            }
            branch_metrics.append(branch_data)
            
            # Track by label
            if config.LABEL_REWORK in labels:
                metrics[project_name]["rework_mrs"] += 1
                
                # Check if assigned to YOU (check assignee username)
                if config.YOUR_EMAIL.split("@")[0] in assignees:
                    metrics[project_name]["rework_assigned_to_me"] += 1
                    rework_mrs.append({
                        "title": mr.get("title"),
                        "url": mr.get("web_url"),
                        "created": mr.get("created_at"),
                        "project": project_name
                    })
            
            if config.LABEL_IN_REVIEW in labels:
                metrics[project_name]["in_review_mrs"] += 1
            
            if config.LABEL_REWORK_DONE in labels:
                metrics[project_name]["rework_done_mrs"] += 1
    
    # Send email if new rework MRs assigned to you
    if rework_mrs and metrics_cache.get("last_rework_count", 0) < len(rework_mrs):
        body = "You have been assigned REWORK on the following MRs:\n\n"
        for mr in rework_mrs:
            body += f"• {mr['title']}\n  {mr['url']}\n  Project: {mr['project']}\n\n"
        send_email_alert("⚠️ GitLab: Rework Assigned to You", body)
    
    result = {
        "project_metrics": dict(metrics),
        "branch_metrics": branch_metrics
    }
    
    metrics_cache["data"] = result
    metrics_cache["last_update"] = now
    metrics_cache["last_rework_count"] = len(rework_mrs)
    
    return result

class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP handler for Prometheus /metrics endpoint"""
    
    def do_GET(self):
        if self.path == "/metrics":
            try:
                data = collect_metrics()
                project_metrics = data.get("project_metrics", {})
                branch_metrics = data.get("branch_metrics", [])
                
                lines = [
                    "# HELP gitlab_merge_requests_total Total merge requests by project",
                    "# TYPE gitlab_merge_requests_total gauge",
                    "# HELP gitlab_rework_mrs MRs with rework label",
                    "# TYPE gitlab_rework_mrs gauge",
                    "# HELP gitlab_rework_assigned_to_me MRs with rework assigned to me",
                    "# TYPE gitlab_rework_assigned_to_me gauge",
                    "# HELP gitlab_in_review_mrs MRs in review",
                    "# TYPE gitlab_in_review_mrs gauge",
                    "# HELP gitlab_rework_done_mrs MRs with rework done",
                    "# TYPE gitlab_rework_done_mrs gauge",
                    "# HELP gitlab_mr_info MR information with branch labels",
                    "# TYPE gitlab_mr_info gauge",
                    "# HELP gitlab_mr_time_in_rework_hours Time spent in rework per MR (hours)",
                    "# TYPE gitlab_mr_time_in_rework_hours gauge",
                    "# HELP gitlab_mr_time_in_review_hours Time spent in review per MR (hours)",
                    "# TYPE gitlab_mr_time_in_review_hours gauge",
                    "# HELP gitlab_mr_time_to_complete_hours Time to complete MR (hours)",
                    "# TYPE gitlab_mr_time_to_complete_hours gauge",
                ]
                
                # Project-level metrics
                for project, stats in project_metrics.items():
                    lines.append(f'gitlab_merge_requests_total{{project="{project}"}} {stats["total_mrs"]}')
                    lines.append(f'gitlab_rework_mrs{{project="{project}"}} {stats["rework_mrs"]}')
                    lines.append(f'gitlab_rework_assigned_to_me{{project="{project}"}} {stats["rework_assigned_to_me"]}')
                    lines.append(f'gitlab_in_review_mrs{{project="{project}"}} {stats["in_review_mrs"]}')
                    lines.append(f'gitlab_rework_done_mrs{{project="{project}"}} {stats["rework_done_mrs"]}')
                
                # Branch-level metrics - ALWAYS expose for ALL MRs
                for branch_data in branch_metrics:
                    project = branch_data["project"]
                    branch = branch_data["branch"].replace('"', '\\"')
                    target = branch_data["target_branch"].replace('"', '\\"')
                    title = branch_data["mr_title"].replace('"', '\\"')[:50]  # Limit length
                    
                    # Always expose MR info (value=1) so branches are always available in dropdown
                    lines.append(f'gitlab_mr_info{{project="{project}",branch="{branch}",target="{target}",title="{title}"}} 1')
                    
                    # Time metrics (only if > 0)
                    if branch_data["time_in_rework"] > 0:
                        lines.append(f'gitlab_mr_time_in_rework_hours{{project="{project}",branch="{branch}",target="{target}",title="{title}"}} {branch_data["time_in_rework"]:.2f}')
                    
                    if branch_data["time_in_review"] > 0:
                        lines.append(f'gitlab_mr_time_in_review_hours{{project="{project}",branch="{branch}",target="{target}",title="{title}"}} {branch_data["time_in_review"]:.2f}')
                    
                    if branch_data["time_to_complete"] > 0:
                        lines.append(f'gitlab_mr_time_to_complete_hours{{project="{project}",branch="{branch}",target="{target}",title="{title}"}} {branch_data["time_to_complete"]:.2f}')
                
                self.send_response(200)
                self.send_header('Content-type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write('\n'.join(lines).encode())
            except Exception as e:
                print(f"[ERROR] /metrics: {e}")
                self.send_response(500)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, *args):
        pass  # Suppress HTTP logs

if __name__ == "__main__":
    if not config.GITLAB_TOKEN:
        print("[ERROR] GITLAB_TOKEN not set in config.py!")
        exit(1)
    
    print(f"GitLab Exporter Starting...")
    print(f"GitLab URL: {config.GITLAB_URL}")
    print(f"Monitoring: {', '.join(config.REPOSITORIES)}")
    print(f"Listening on http://0.0.0.0:9200/metrics\n")
    
    server = HTTPServer(('0.0.0.0', 9200), MetricsHandler)
    server.serve_forever()

